"""Explicitly injected STS role assumption; never invoked implicitly."""

from __future__ import annotations

import logging
import re
from typing import Any

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

LOG = logging.getLogger(__name__)
ROLE_ARN = re.compile(r"^arn:(aws|aws-us-gov|aws-cn):iam::\d{12}:role/[A-Za-z0-9+=,.@_/-]+$")


class AssumeRoleError(RuntimeError):
    """Safe, non-secret error from role assumption or response validation."""


def create_sts_client(session: Any, region: str) -> Any:
    """Create an STS client with standard SDK retries; does not make a request."""
    if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region):
        raise AssumeRoleError("Invalid AWS region")
    return session.client(
        "sts",
        region_name=region,
        config=Config(retries={"mode": "standard", "max_attempts": 4}),
    )


def validate_request(role_arn: str, external_id: str, duration: int) -> None:
    if not ROLE_ARN.fullmatch(role_arn):
        raise AssumeRoleError("Invalid IAM role ARN")
    if not isinstance(external_id, str) or not external_id.strip():
        raise AssumeRoleError("External ID is required")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 900 <= duration <= 43200:
        raise AssumeRoleError("Session duration must be between 900 and 43200 seconds")


def assume_role(
    sts_client: Any,
    *,
    role_arn: str,
    external_id: str,
    session_name: str,
    duration: int = 3600,
) -> dict[str, str]:
    """Call an injected STS client and return credentials only in memory.

    The caller owns the client and its retry configuration. No credential data or
    external ID is logged, and underlying SDK messages are not re-exposed.
    """
    validate_request(role_arn, external_id, duration)
    if not re.fullmatch(r"[A-Za-z0-9+=,.@_-]{2,64}", session_name):
        raise AssumeRoleError("Invalid role session name")
    try:
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            ExternalId=external_id,
            DurationSeconds=duration,
        )
    except (BotoCoreError, ClientError) as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        safe_code = code if re.fullmatch(r"[A-Za-z0-9]+", str(code)) else "RequestFailed"
        LOG.warning("STS AssumeRole failed (%s)", safe_code)
        raise AssumeRoleError(f"STS AssumeRole failed ({safe_code})") from None
    credentials = response.get("Credentials") if isinstance(response, dict) else None
    expected = ("AccessKeyId", "SecretAccessKey", "SessionToken")
    if not isinstance(credentials, dict) or any(not credentials.get(key) for key in expected):
        raise AssumeRoleError("STS response did not contain valid temporary credentials")
    return {key: credentials[key] for key in expected}


def create_session(boto3_module: Any, credentials: dict[str, str], region: str) -> Any:
    """Create a Boto3 session from in-memory STS credentials."""
    required = {"AccessKeyId", "SecretAccessKey", "SessionToken"}
    if set(credentials) != required or not all(credentials.values()):
        raise AssumeRoleError("Temporary credential set is incomplete")
    return boto3_module.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=region,
    )


def get_caller_identity(sts_client: Any) -> dict[str, str]:
    """Optional identity verification, only through an explicitly supplied client."""
    try:
        result = sts_client.get_caller_identity()
    except (BotoCoreError, ClientError) as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "RequestFailed")
        safe_code = code if re.fullmatch(r"[A-Za-z0-9]+", str(code)) else "RequestFailed"
        raise AssumeRoleError(f"Caller identity verification failed ({safe_code})") from None
    if not all(result.get(key) for key in ("Account", "Arn", "UserId")):
        raise AssumeRoleError("STS identity response is incomplete")
    return {key: result[key] for key in ("Account", "Arn", "UserId")}
