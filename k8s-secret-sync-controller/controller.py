"""Kopf controller that mirrors opted-in AWS JSON secrets to namespace-local Secrets.

The module is safe to import in tests: AWS and Kubernetes clients are created only
inside the Kopf handler after a matching ConfigMap event arrives.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import boto3
import kopf
from botocore.exceptions import BotoCoreError, ClientError
from kubernetes import client as kube_client
from kubernetes import config as kube_config
from kubernetes.client.exceptions import ApiException

ENABLED_ANNOTATION = "secret-sync.example.com/enabled"
AWS_SECRET_ANNOTATION = "secret-sync.example.com/aws-secret-name"
TARGET_SECRET_ANNOTATION = "secret-sync.example.com/target-secret-name"
MANAGED_BY_ANNOTATION = "secret-sync.example.com/managed-by"
SOURCE_CONFIGMAP_ANNOTATION = "secret-sync.example.com/source-configmap"
CONTROLLER_ID = "k8s-secret-sync-controller"

_DNS_SUBDOMAIN = re.compile(
    r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[-a-z0-9]*[a-z0-9])?)*$"
)
_SECRET_KEY = re.compile(r"^[A-Za-z0-9._-]+$")


class ControllerError(Exception):
    """Base class for safe, user-facing controller errors."""


class ConfigurationError(ControllerError):
    """A ConfigMap annotation is missing or invalid."""


class SecretNotFoundError(ControllerError):
    """The referenced AWS secret does not exist."""


class SecretAccessDeniedError(ControllerError):
    """The AWS identity is not allowed to read the referenced secret."""


class InvalidSecretPayloadError(ControllerError):
    """The AWS secret is not a supported JSON string object."""


class AWSRequestError(ControllerError):
    """A retryable AWS Secrets Manager request failed."""


class SecretOwnershipError(ControllerError):
    """An existing Kubernetes Secret is not owned by this controller."""


class KubernetesPermissionError(ControllerError):
    """The controller lacks permission for the Kubernetes API operation."""


class KubernetesRequestError(ControllerError):
    """A retryable Kubernetes API operation failed."""


@dataclass(frozen=True)
class SyncConfig:
    namespace: str
    configmap_name: str
    aws_secret_name: str
    target_secret_name: str


def _metadata(configmap: Any) -> dict[str, Any]:
    if isinstance(configmap, dict):
        metadata = configmap.get("metadata", {})
    else:
        metadata_obj = getattr(configmap, "metadata", None)
        metadata = {
            "name": getattr(metadata_obj, "name", None),
            "namespace": getattr(metadata_obj, "namespace", None),
            "annotations": getattr(metadata_obj, "annotations", None),
        }
    return metadata if isinstance(metadata, dict) else {}


def parse_annotations(configmap: Any) -> SyncConfig | None:
    """Return sync settings for an opted-in ConfigMap, or None when disabled."""
    metadata = _metadata(configmap)
    annotations = metadata.get("annotations") or {}
    if not isinstance(annotations, dict):
        raise ConfigurationError("ConfigMap annotations must be a mapping.")
    if str(annotations.get(ENABLED_ANNOTATION, "")).lower() != "true":
        return None

    namespace = metadata.get("namespace")
    configmap_name = metadata.get("name")
    aws_secret_name = annotations.get(AWS_SECRET_ANNOTATION)
    target_secret_name = annotations.get(TARGET_SECRET_ANNOTATION)

    if not isinstance(namespace, str) or not namespace.strip():
        raise ConfigurationError("Opted-in ConfigMap must have a namespace.")
    if not isinstance(configmap_name, str) or not configmap_name.strip():
        raise ConfigurationError("Opted-in ConfigMap must have a name.")
    if not isinstance(aws_secret_name, str) or not aws_secret_name.strip():
        raise ConfigurationError(f"Missing required annotation: {AWS_SECRET_ANNOTATION}.")
    if not isinstance(target_secret_name, str) or not target_secret_name.strip():
        raise ConfigurationError(f"Missing required annotation: {TARGET_SECRET_ANNOTATION}.")
    if len(target_secret_name) > 253 or not _DNS_SUBDOMAIN.fullmatch(target_secret_name):
        raise ConfigurationError("Target Secret name is not a valid DNS subdomain.")

    return SyncConfig(
        namespace=namespace,
        configmap_name=configmap_name,
        aws_secret_name=aws_secret_name.strip(),
        target_secret_name=target_secret_name,
    )


def should_reconcile_update(old: dict[str, Any], new: dict[str, Any]) -> bool:
    """Ignore ConfigMap data and Kopf's own progress-annotation updates."""
    old_annotations = (old.get("metadata", {}).get("annotations") or {})
    new_annotations = (new.get("metadata", {}).get("annotations") or {})
    return any(
        old_annotations.get(key) != new_annotations.get(key)
        for key in (
            ENABLED_ANNOTATION,
            AWS_SECRET_ANNOTATION,
            TARGET_SECRET_ANNOTATION,
        )
    )


def get_aws_secret(secret_name: str, secretsmanager_client: Any) -> dict[str, str]:
    """Retrieve and validate a JSON SecretString without logging its contents."""
    try:
        response = secretsmanager_client.get_secret_value(SecretId=secret_name)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        if code == "ResourceNotFoundException":
            raise SecretNotFoundError("Referenced AWS secret was not found.") from None
        if code in {"AccessDenied", "AccessDeniedException"}:
            raise SecretAccessDeniedError(
                "AWS identity is not permitted to read the referenced secret."
            ) from None
        raise AWSRequestError(f"AWS Secrets Manager request failed ({code}).") from None
    except BotoCoreError:
        raise AWSRequestError("AWS Secrets Manager request failed.") from None

    secret_string = response.get("SecretString")
    if not isinstance(secret_string, str):
        raise InvalidSecretPayloadError("Binary AWS secrets are not supported.")

    try:
        payload = json.loads(secret_string)
    except (json.JSONDecodeError, TypeError):
        raise InvalidSecretPayloadError("AWS SecretString must contain a JSON object.") from None

    if not isinstance(payload, dict) or not payload:
        raise InvalidSecretPayloadError("AWS SecretString must contain a non-empty JSON object.")

    validated: dict[str, str] = {}
    for key, value in payload.items():
        if (
            not isinstance(key, str)
            or not _SECRET_KEY.fullmatch(key)
            or not isinstance(value, str)
        ):
            raise InvalidSecretPayloadError(
                "AWS secret JSON must map valid Kubernetes Secret keys to string values."
            )
        validated[key] = value
    return validated


def build_kubernetes_secret(config: SyncConfig, values: dict[str, str]) -> kube_client.V1Secret:
    """Build an Opaque Secret tagged with controller and source ownership metadata."""
    source = f"{config.namespace}/{config.configmap_name}"
    return kube_client.V1Secret(
        api_version="v1",
        kind="Secret",
        metadata=kube_client.V1ObjectMeta(
            name=config.target_secret_name,
            namespace=config.namespace,
            labels={"app.kubernetes.io/managed-by": CONTROLLER_ID},
            annotations={
                MANAGED_BY_ANNOTATION: CONTROLLER_ID,
                SOURCE_CONFIGMAP_ANNOTATION: source,
            },
        ),
        type="Opaque",
        string_data=values,
    )


def _metadata_annotations(secret: Any) -> dict[str, str]:
    metadata = getattr(secret, "metadata", None)
    annotations = getattr(metadata, "annotations", None)
    return annotations if isinstance(annotations, dict) else {}


def _is_owned_by_configmap(secret: Any, config: SyncConfig) -> bool:
    annotations = _metadata_annotations(secret)
    return (
        annotations.get(MANAGED_BY_ANNOTATION) == CONTROLLER_ID
        and annotations.get(SOURCE_CONFIGMAP_ANNOTATION)
        == f"{config.namespace}/{config.configmap_name}"
    )


def _existing_values_match(secret: Any, expected: dict[str, str]) -> bool:
    """Compare Kubernetes base64 data to desired strings without logging either."""
    encoded_data = getattr(secret, "data", None) or {}
    decoded: dict[str, str] = {}
    try:
        for key, encoded_value in encoded_data.items():
            if not isinstance(encoded_value, str):
                return False
            decoded[key] = base64.b64decode(encoded_value, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    return decoded == expected


def _raise_kubernetes_error(exc: ApiException) -> None:
    if exc.status == 403:
        raise KubernetesPermissionError(
            "Kubernetes API denied a Secret operation; review namespace RBAC."
        ) from None
    raise KubernetesRequestError(
        f"Kubernetes API Secret operation failed with status {exc.status or 'unknown'}."
    ) from None


def sync_secret(
    configmap: Any,
    secretsmanager_client: Any,
    core_v1_api: Any,
    logger: logging.Logger | Any | None = None,
) -> str:
    """Create or reconcile the owned Secret. Return created, updated, unchanged, or skipped."""
    logger = logger or logging.getLogger(__name__)
    config = parse_annotations(configmap)
    if config is None:
        logger.debug("ConfigMap is not opted in for secret synchronization.")
        return "skipped"

    try:
        existing = core_v1_api.read_namespaced_secret(
            name=config.target_secret_name, namespace=config.namespace
        )
    except ApiException as exc:
        if exc.status == 404:
            existing = None
        else:
            _raise_kubernetes_error(exc)

    if existing is not None and not _is_owned_by_configmap(existing, config):
        raise SecretOwnershipError(
            "Refusing to modify an existing Secret not owned by this ConfigMap."
        )

    values = get_aws_secret(config.aws_secret_name, secretsmanager_client)
    desired = build_kubernetes_secret(config, values)

    try:
        if existing is None:
            core_v1_api.create_namespaced_secret(namespace=config.namespace, body=desired)
            logger.info(
                "Created managed Secret %s/%s.", config.namespace, config.target_secret_name
            )
            return "created"

        if _existing_values_match(existing, values):
            logger.debug(
                "Managed Secret %s/%s is already current.",
                config.namespace,
                config.target_secret_name,
            )
            return "unchanged"

        core_v1_api.patch_namespaced_secret(
            name=config.target_secret_name, namespace=config.namespace, body=desired
        )
        logger.info(
            "Updated managed Secret %s/%s.", config.namespace, config.target_secret_name
        )
        return "updated"
    except ApiException as exc:
        _raise_kubernetes_error(exc)


def _make_clients() -> tuple[Any, Any]:
    """Use in-cluster Kubernetes identity and Boto3's standard AWS credential chain."""
    try:
        kube_config.load_incluster_config()
    except Exception:
        raise ConfigurationError(
            "Kubernetes in-cluster client configuration is unavailable."
        ) from None
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    aws_client = boto3.client("secretsmanager", region_name=region)
    return aws_client, kube_client.CoreV1Api()


def _handle_configmap(body: dict[str, Any], logger: Any) -> None:
    try:
        config = parse_annotations(body)
        if config is None:
            logger.debug("ConfigMap is not opted in for secret synchronization.")
            return
        secretsmanager_client, core_v1_api = _make_clients()
        sync_secret(body, secretsmanager_client, core_v1_api, logger)
    except (
        ConfigurationError,
        SecretNotFoundError,
        SecretAccessDeniedError,
        InvalidSecretPayloadError,
        SecretOwnershipError,
        KubernetesPermissionError,
    ) as exc:
        raise kopf.PermanentError(str(exc)) from None
    except (AWSRequestError, KubernetesRequestError, BotoCoreError, ApiException):
        raise kopf.TemporaryError(
            "Secret synchronization request failed; Kopf will retry.", delay=30
        ) from None


@kopf.on.create("", "v1", "configmaps")
def on_configmap_create(body: dict[str, Any], logger: Any, **_: Any) -> None:
    _handle_configmap(body, logger)


@kopf.on.update("", "v1", "configmaps")
def on_configmap_update(
    body: dict[str, Any],
    old: dict[str, Any],
    new: dict[str, Any],
    logger: Any,
    **_: Any,
) -> None:
    if not should_reconcile_update(old, new):
        return
    _handle_configmap(body, logger)

