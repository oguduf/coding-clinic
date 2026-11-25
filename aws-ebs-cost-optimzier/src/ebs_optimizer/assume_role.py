"""STS role assumption. Credentials are passed only to an in-memory session."""

from __future__ import annotations

import boto3


class RoleAssumptionError(RuntimeError):
    """A read-only member account role could not be assumed."""


def assume_account_role(
    sts_client: object,
    account_id: str,
    role_name: str,
    *,
    session_name: str = "ebs-cost-inventory",
    session_factory: object = boto3.Session,
) -> object:
    if not account_id.isdigit() or len(account_id) != 12:
        raise ValueError("account_id must be a 12-digit AWS account identifier")
    normalized_role_name = role_name.strip("/")
    if not normalized_role_name or "/" in normalized_role_name:
        raise ValueError("role_name must be a non-empty IAM role name without a path")
    role_arn = f"arn:aws:iam::{account_id}:role/{normalized_role_name}"
    try:
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=900,
        )
        credentials = response["Credentials"]
        return session_factory(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
    except Exception as exc:  # botocore errors vary by service/code
        response = getattr(exc, "response", {})
        code = response.get("Error", {}).get("Code", type(exc).__name__)
        raise RoleAssumptionError(f"AssumeRole failed for {account_id}: {code}") from exc
