from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from cross_account_iam.assume_role import (
    AssumeRoleError,
    assume_role,
    create_session,
    create_sts_client,
    get_caller_identity,
)
from cross_account_iam.config import ConfigError, load_config, validate_config
from cross_account_iam.policy_validator import (
    load_policy,
    validate_all,
    validate_source,
    validate_target,
    validate_trust,
)

ROOT = Path(__file__).parents[1]


def test_example_config_loads():
    assert load_config(ROOT / "config/config.example.yaml")["application"]["environment"] == "dev"


def test_rejects_unsafe_config():
    data = load_config(ROOT / "config/config.example.yaml")
    data["security"]["allow_wildcard_principal"] = True
    with pytest.raises(ConfigError):
        validate_config(data)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["application"].update(environment="qa"),
        lambda d: d["cross_account"].update(source_account_id="123"),
        lambda d: d["cross_account"].update(target_role_name="bad role"),
        lambda d: d["aws"].update(region="not-a-region"),
        lambda d: d["cross_account"].update(session_duration=100),
        lambda d: d["cross_account"].update(external_id_env_var="bad-name"),
        lambda d: d["security"].update(require_external_id=False),
        lambda d: d["security"].update(allow_administrator_access=True),
    ],
)
def test_config_rejects_invalid_values(mutate):
    data = load_config(ROOT / "config/config.example.yaml")
    mutate(data)
    with pytest.raises(ConfigError):
        validate_config(data)


def test_config_rejects_missing_field():
    with pytest.raises(ConfigError, match="Missing"):
        validate_config({})


def test_policy_fixtures_pass_static_validation():
    load = lambda name: load_policy(ROOT / f"examples/{name}.json")
    findings = validate_all(
        load("trust-policy.example"), load("source-policy.example"), load("target-policy.example")
    )
    assert findings == []


def test_policy_loader_rejects_invalid_statement_shape(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"Version":"2012-10-17","Statement":[{"Action":"s3:GetObject"}]}')
    with pytest.raises(ValueError, match="Effect and Action"):
        load_policy(path)


def test_trust_rejects_wildcard_and_missing_external_id():
    findings = validate_trust(
        {
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "sts:AssumeRole"}],
        }
    )
    assert {item["rule_id"] for item in findings} >= {"IAM001", "IAM002", "IAM003"}


def test_trust_requires_external_id_on_the_explicit_assume_statement():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::111122223333:role/pipeline"},
                "Action": "sts:AssumeRole",
            },
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"sts:ExternalId": "id"}},
            },
        ],
    }
    findings = validate_trust(policy)
    assert "IAM003" in {finding["rule_id"] for finding in findings}


def test_source_and_target_policy_findings():
    source = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*"}],
    }
    target = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}],
    }
    assert validate_source(source)[0]["rule_id"] == "IAM005"
    assert validate_target(target)[0]["rule_id"] == "IAM007"


def test_source_policy_must_include_assume_role():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::bucket/*"}
        ],
    }
    assert validate_source(policy)[0]["rule_id"] == "IAM009"


def test_service_wildcard_is_flagged():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iam:*",
                "Resource": "arn:aws:iam::444455556666:role/example",
            }
        ],
    }
    assert validate_target(policy)[0]["rule_id"] == "IAM007"


def test_source_rejects_unapproved_role():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": "arn:aws:iam::111122223333:role/other",
            }
        ],
    }
    assert (
        validate_source(policy, ["arn:aws:iam::444455556666:role/approved"])[0]["rule_id"]
        == "IAM006"
    )


def test_target_allows_documented_ecr_token_scope():
    policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*"}],
    }
    assert validate_target(policy) == []


def test_assume_role_builds_request_and_returns_memory_credentials():
    sts = Mock()
    sts.assume_role.return_value = {
        "Credentials": {"AccessKeyId": "A", "SecretAccessKey": "S", "SessionToken": "T"}
    }
    creds = assume_role(
        sts,
        role_arn="arn:aws:iam::444455556666:role/deploy",
        external_id="secret",
        session_name="unit-test",
    )
    assert creds == {"AccessKeyId": "A", "SecretAccessKey": "S", "SessionToken": "T"}
    assert sts.assume_role.call_args.kwargs["ExternalId"] == "secret"


def test_assume_role_with_botocore_stubber_is_offline():
    session = boto3.Session(
        aws_access_key_id="synthetic-access-key",
        aws_secret_access_key="synthetic-secret-key-value-only-for-unit-tests",
        region_name="us-east-1",
    )
    client = session.client("sts", region_name="us-east-1")
    expected = {
        "RoleArn": "arn:aws:iam::444455556666:role/deploy",
        "RoleSessionName": "offline-test",
        "ExternalId": "synthetic-test-id",
        "DurationSeconds": 3600,
    }
    response = {
        "Credentials": {
            "AccessKeyId": "ASIA1234567890123456",
            "SecretAccessKey": "x" * 40,
            "SessionToken": "synthetic-session-token",
            "Expiration": datetime(2030, 1, 1, tzinfo=UTC),
        },
        "AssumedRoleUser": {
            "AssumedRoleId": "ARO123EXAMPLE:offline-test",
            "Arn": "arn:aws:sts::444455556666:assumed-role/deploy/offline-test",
        },
    }
    with Stubber(client) as stubber:
        stubber.add_response("assume_role", response, expected)
        credentials = assume_role(
            client,
            role_arn=expected["RoleArn"],
            external_id=expected["ExternalId"],
            session_name=expected["RoleSessionName"],
        )
    assert credentials["SessionToken"] == "synthetic-session-token"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role_arn": "bad", "external_id": "x", "duration": 3600},
        {"role_arn": "arn:aws:iam::444455556666:role/x", "external_id": "", "duration": 3600},
        {"role_arn": "arn:aws:iam::444455556666:role/x", "external_id": "x", "duration": 800},
    ],
)
def test_assume_role_rejects_invalid_request(kwargs):
    with pytest.raises(AssumeRoleError):
        from cross_account_iam.assume_role import validate_request

        validate_request(**kwargs)


def test_assume_role_redacts_api_error():
    sts = Mock()
    sts.assume_role.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "secret value"}}, "AssumeRole"
    )
    with pytest.raises(AssumeRoleError, match="AccessDenied") as error:
        assume_role(
            sts,
            role_arn="arn:aws:iam::444455556666:role/deploy",
            external_id="private",
            session_name="unit-test",
        )
    assert "secret value" not in str(error.value)
    assert "private" not in str(error.value)


def test_assume_role_rejects_bad_session_and_response():
    sts = Mock()
    with pytest.raises(AssumeRoleError, match="session name"):
        assume_role(
            sts,
            role_arn="arn:aws:iam::444455556666:role/deploy",
            external_id="id",
            session_name="x",
        )
    sts.assume_role.return_value = {"Credentials": {"AccessKeyId": ""}}
    with pytest.raises(AssumeRoleError, match="response"):
        assume_role(
            sts,
            role_arn="arn:aws:iam::444455556666:role/deploy",
            external_id="id",
            session_name="unit-test",
        )


def test_identity_validation_is_injected_and_checks_response():
    sts = Mock()
    sts.get_caller_identity.return_value = {
        "Account": "444455556666",
        "Arn": "arn:aws:iam::444455556666:role/x",
        "UserId": "A",
    }
    assert get_caller_identity(sts)["Account"] == "444455556666"
    sts.get_caller_identity.return_value = {}
    with pytest.raises(AssumeRoleError, match="incomplete"):
        get_caller_identity(sts)


def test_identity_validation_redacts_errors():
    sts = Mock()
    sts.get_caller_identity.side_effect = ClientError(
        {"Error": {"Code": "ExpiredToken", "Message": "secret"}}, "GetCallerIdentity"
    )
    with pytest.raises(AssumeRoleError, match="ExpiredToken") as error:
        get_caller_identity(sts)
    assert "secret" not in str(error.value)


def test_create_session_injects_credentials():
    module = Mock()
    credentials = {"AccessKeyId": "A", "SecretAccessKey": "S", "SessionToken": "T"}
    create_session(module, credentials, "us-east-1")
    module.Session.assert_called_once_with(
        aws_access_key_id="A",
        aws_secret_access_key="S",
        aws_session_token="T",
        region_name="us-east-1",
    )


def test_sts_client_uses_standard_retries_without_calling_api():
    session = Mock()
    create_sts_client(session, "us-east-1")
    kwargs = session.client.call_args.kwargs
    assert session.client.call_args.args == ("sts",)
    assert kwargs["region_name"] == "us-east-1"
    assert kwargs["config"].retries["mode"] == "standard"
