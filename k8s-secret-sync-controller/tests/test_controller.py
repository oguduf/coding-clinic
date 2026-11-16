import base64
import logging
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from kubernetes.client.exceptions import ApiException

import controller


SECRET_VALUE = "synthetic-password-not-for-logs"
SOURCE_ANNOTATIONS = {
    controller.ENABLED_ANNOTATION: "true",
    controller.AWS_SECRET_ANNOTATION: "demo/database",
    controller.TARGET_SECRET_ANNOTATION: "database-credentials",
}


def configmap(annotations=None, *, name="database-secret-config", namespace="demo"):
    return {
        "metadata": {
            "name": name,
            "namespace": namespace,
            "annotations": SOURCE_ANNOTATIONS.copy() if annotations is None else annotations,
        }
    }


def client_error(code):
    return ClientError(
        {"Error": {"Code": code, "Message": "synthetic test error"}},
        "GetSecretValue",
    )


class FakeSecretsManager:
    def __init__(self, response=None, error=None):
        self.response = response or {"SecretString": '{"DB_PASSWORD":"example-value"}'}
        self.error = error
        self.calls = []

    def get_secret_value(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeCoreV1Api:
    def __init__(self, existing=None, read_error=None):
        self.existing = existing
        self.read_error = read_error
        self.created = []
        self.patched = []
        self.reads = []

    def read_namespaced_secret(self, *, name, namespace):
        self.reads.append((name, namespace))
        if self.read_error:
            raise self.read_error
        if self.existing is None:
            raise ApiException(status=404, reason="Not Found")
        return self.existing

    def create_namespaced_secret(self, *, namespace, body):
        self.created.append((namespace, body))
        return body

    def patch_namespaced_secret(self, *, name, namespace, body):
        self.patched.append((name, namespace, body))
        return body


def owned_secret(values, *, source="demo/database-secret-config"):
    encoded = {
        key: base64.b64encode(value.encode("utf-8")).decode("ascii")
        for key, value in values.items()
    }
    return SimpleNamespace(
        metadata=SimpleNamespace(
            annotations={
                controller.MANAGED_BY_ANNOTATION: controller.CONTROLLER_ID,
                controller.SOURCE_CONFIGMAP_ANNOTATION: source,
            }
        ),
        data=encoded,
    )


def test_configmap_without_enabled_annotation_is_ignored():
    annotations = {
        controller.AWS_SECRET_ANNOTATION: "demo/database",
        controller.TARGET_SECRET_ANNOTATION: "database-credentials",
    }
    assert controller.parse_annotations(configmap(annotations)) is None


def test_valid_annotated_configmap_is_parsed():
    parsed = controller.parse_annotations(configmap())
    assert parsed == controller.SyncConfig(
        namespace="demo",
        configmap_name="database-secret-config",
        aws_secret_name="demo/database",
        target_secret_name="database-credentials",
    )


def test_update_filter_ignores_kopf_progress_metadata():
    old = configmap()
    new = configmap()
    new["metadata"]["annotations"]["kopf.zalando.org/last-handled-configuration"] = "{}"
    assert not controller.should_reconcile_update(old, new)


def test_update_filter_detects_secret_reference_change():
    old = configmap()
    new = configmap()
    new["metadata"]["annotations"][controller.AWS_SECRET_ANNOTATION] = "demo/rotated"
    assert controller.should_reconcile_update(old, new)


def test_missing_aws_secret_identifier_is_rejected():
    annotations = {
        controller.ENABLED_ANNOTATION: "true",
        controller.TARGET_SECRET_ANNOTATION: "database-credentials",
    }
    with pytest.raises(controller.ConfigurationError, match="aws-secret-name"):
        controller.parse_annotations(configmap(annotations))


def test_missing_target_secret_name_is_rejected():
    annotations = {
        controller.ENABLED_ANNOTATION: "true",
        controller.AWS_SECRET_ANNOTATION: "demo/database",
    }
    with pytest.raises(controller.ConfigurationError, match="target-secret-name"):
        controller.parse_annotations(configmap(annotations))


def test_successful_aws_secret_retrieval():
    aws = FakeSecretsManager(
        {"SecretString": '{"DB_USERNAME":"example-user","DB_PASSWORD":"example-password"}'}
    )
    values = controller.get_aws_secret("demo/database", aws)
    assert values == {
        "DB_USERNAME": "example-user",
        "DB_PASSWORD": "example-password",
    }
    assert aws.calls == [{"SecretId": "demo/database"}]


def test_sync_creates_secret_when_missing():
    aws = FakeSecretsManager()
    api = FakeCoreV1Api()
    result = controller.sync_secret(configmap(), aws, api)

    assert result == "created"
    assert len(api.created) == 1
    namespace, secret = api.created[0]
    assert namespace == "demo"
    assert secret.api_version == "v1"
    assert secret.kind == "Secret"
    assert secret.type == "Opaque"
    assert secret.metadata.name == "database-credentials"
    assert secret.string_data == {"DB_PASSWORD": "example-value"}
    assert secret.metadata.annotations[controller.MANAGED_BY_ANNOTATION] == controller.CONTROLLER_ID


def test_sync_updates_owned_secret_when_values_change():
    aws = FakeSecretsManager({"SecretString": '{"DB_PASSWORD":"new-value"}'})
    api = FakeCoreV1Api(existing=owned_secret({"DB_PASSWORD": "old-value"}))

    result = controller.sync_secret(configmap(), aws, api)
    assert result == "updated"
    assert len(api.patched) == 1
    assert api.patched[0][2].string_data == {"DB_PASSWORD": "new-value"}


def test_unchanged_secret_is_not_updated():
    aws = FakeSecretsManager()
    api = FakeCoreV1Api(existing=owned_secret({"DB_PASSWORD": "example-value"}))

    result = controller.sync_secret(configmap(), aws, api)
    assert result == "unchanged"
    assert api.patched == []
    assert api.created == []


def test_invalid_aws_json_is_rejected():
    aws = FakeSecretsManager({"SecretString": "{not-json"})
    with pytest.raises(controller.InvalidSecretPayloadError):
        controller.get_aws_secret("demo/database", aws)


def test_aws_secret_not_found_is_reported_safely():
    aws = FakeSecretsManager(error=client_error("ResourceNotFoundException"))
    with pytest.raises(controller.SecretNotFoundError, match="not found"):
        controller.get_aws_secret("demo/database", aws)


def test_aws_access_denied_is_reported_safely():
    aws = FakeSecretsManager(error=client_error("AccessDeniedException"))
    with pytest.raises(controller.SecretAccessDeniedError, match="not permitted"):
        controller.get_aws_secret("demo/database", aws)


def test_aws_connectivity_error_is_retryable():
    aws = FakeSecretsManager(
        error=EndpointConnectionError(endpoint_url="https://secretsmanager.example.invalid")
    )
    with pytest.raises(controller.AWSRequestError, match="request failed"):
        controller.get_aws_secret("demo/database", aws)


def test_kubernetes_api_failure_is_retryable_error():
    aws = FakeSecretsManager()
    api = FakeCoreV1Api(read_error=ApiException(status=500, reason="Internal Server Error"))
    with pytest.raises(controller.KubernetesRequestError, match="status 500"):
        controller.sync_secret(configmap(), aws, api)
    assert aws.calls == []


def test_existing_unmanaged_secret_is_not_overwritten():
    aws = FakeSecretsManager()
    unmanaged = SimpleNamespace(metadata=SimpleNamespace(annotations={}), data={})
    api = FakeCoreV1Api(existing=unmanaged)

    with pytest.raises(controller.SecretOwnershipError, match="not owned"):
        controller.sync_secret(configmap(), aws, api)

    assert aws.calls == []
    assert api.created == []
    assert api.patched == []


def test_invalid_kubernetes_secret_name_is_rejected():
    with pytest.raises(controller.ConfigurationError, match="valid DNS subdomain"):
        controller.parse_annotations(
            configmap(
                {
                    **SOURCE_ANNOTATIONS,
                    controller.TARGET_SECRET_ANNOTATION: "not a valid name",
                }
            )
        )


def test_secret_value_is_not_written_to_logs(caplog):
    aws = FakeSecretsManager({"SecretString": f'{{"DB_PASSWORD":"{SECRET_VALUE}"}}'})
    api = FakeCoreV1Api()

    with caplog.at_level(logging.INFO):
        controller.sync_secret(configmap(), aws, api)

    assert SECRET_VALUE not in caplog.text
    assert "Created managed Secret demo/database-credentials" in caplog.text


def test_binary_aws_secret_is_not_supported():
    aws = FakeSecretsManager({"SecretBinary": b"synthetic"})
    with pytest.raises(controller.InvalidSecretPayloadError, match="Binary"):
        controller.get_aws_secret("demo/database", aws)


def test_non_string_aws_secret_values_are_rejected():
    aws = FakeSecretsManager({"SecretString": '{"PORT":5432}'})
    with pytest.raises(controller.InvalidSecretPayloadError, match="string values"):
        controller.get_aws_secret("demo/database", aws)

