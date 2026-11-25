"""Static offline checks for cross-account IAM policy documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROLE_ARN = re.compile(r"^arn:aws(-us-gov|-cn)?:iam::\d{12}:role/[A-Za-z0-9+=,.@_/-]+$")


def _statements(policy: dict[str, Any]) -> list[dict[str, Any]]:
    statements = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    return (
        [item for item in statements if isinstance(item, dict)]
        if isinstance(statements, list)
        else []
    )


def _values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def load_policy(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        policy = json.load(handle)
    if not isinstance(policy, dict) or policy.get("Version") != "2012-10-17":
        raise ValueError("Policy must be an IAM policy object with Version 2012-10-17")
    statements = _statements(policy)
    if not statements:
        raise ValueError("Policy must contain at least one statement")
    for statement in statements:
        if statement.get("Effect") not in {"Allow", "Deny"} or not statement.get("Action"):
            raise ValueError("Each policy statement must define a valid Effect and Action")
        if not statement.get("Resource") and not statement.get("Principal"):
            raise ValueError("Each statement must define Resource or Principal")
    return policy


def validate_trust(policy: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    statements = _statements(policy)
    trusted = False
    protected = False
    for statement in statements:
        principal = statement.get("Principal", {})
        aws = principal.get("AWS") if isinstance(principal, dict) else principal
        principal_arns = _values(aws)
        if "*" in principal_arns:
            findings.append(
                _finding(
                    "IAM001",
                    "critical",
                    "Wildcard trusted principal is forbidden",
                    "Name an explicit source role ARN.",
                )
            )
        actions = _values(statement.get("Action"))
        if "sts:AssumeRole" in actions and statement.get("Effect") == "Allow":
            explicit_principal = bool(principal_arns) and "*" not in principal_arns
            trusted = trusted or explicit_principal
            condition = statement.get("Condition", {})
            equals = condition.get("StringEquals", {}) if isinstance(condition, dict) else {}
            ids = equals.get("sts:ExternalId") if isinstance(equals, dict) else None
            if explicit_principal and any(value.strip() and value != "*" for value in _values(ids)):
                protected = True
    if not trusted:
        findings.append(
            _finding(
                "IAM002",
                "high",
                "Trust policy lacks explicit AWS principal",
                "Set Principal.AWS to the approved source role ARN.",
            )
        )
    if not protected:
        findings.append(
            _finding(
                "IAM003",
                "high",
                "AssumeRole trust lacks external ID condition",
                "Require sts:ExternalId with StringEquals.",
            )
        )
    if not any(
        "sts:AssumeRole" in _values(s.get("Action")) and s.get("Effect") == "Allow"
        for s in statements
    ):
        findings.append(
            _finding(
                "IAM004",
                "high",
                "Trust policy does not allow sts:AssumeRole",
                "Add the required action to the intended trust statement.",
            )
        )
    return findings


def validate_source(
    policy: dict[str, Any], approved_role_arns: list[str] | None = None
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    approved = set(approved_role_arns or [])
    statements = _statements(policy)
    assume_statements = [
        statement
        for statement in statements
        if statement.get("Effect") == "Allow"
        and "sts:AssumeRole" in _values(statement.get("Action"))
    ]
    if not assume_statements:
        findings.append(
            _finding(
                "IAM009",
                "high",
                "Source policy does not allow sts:AssumeRole",
                "Add an Allow statement scoped to approved target role ARNs.",
            )
        )
    for statement in assume_statements:
        resources = _values(statement.get("Resource"))
        if not resources or any(not ROLE_ARN.fullmatch(resource) for resource in resources):
            findings.append(
                _finding(
                    "IAM005",
                    "high",
                    "Source AssumeRole policy has wildcard or missing resources",
                    "Restrict Resource to approved target role ARNs.",
                )
            )
        if approved and not set(resources) <= approved:
            findings.append(
                _finding(
                    "IAM006",
                    "high",
                    "Source policy contains an unapproved target role ARN",
                    "Remove role ARNs outside the approved list.",
                )
            )
    return findings


def validate_target(policy: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for statement in _statements(policy):
        actions = _values(statement.get("Action"))
        resources = _values(statement.get("Resource"))
        if any(action == "*" or action.endswith(":*") for action in actions) or any(
            action.lower() == "administratoraccess" for action in actions
        ):
            findings.append(
                _finding(
                    "IAM007",
                    "critical",
                    "Target policy grants broad administrator actions",
                    "Use explicit service actions and resource scopes.",
                )
            )
        if "*" in resources:
            allowed_exception = set(actions) == {"ecr:GetAuthorizationToken"}
            if not allowed_exception:
                findings.append(
                    _finding(
                        "IAM008",
                        "high",
                        "Target permission uses wildcard resource scope",
                        "Scope resources to approved ARNs; document unavoidable action-specific exceptions.",
                    )
                )
    return findings


def validate_all(
    trust: dict[str, Any], source: dict[str, Any], target: dict[str, Any]
) -> list[dict[str, str]]:
    return validate_trust(trust) + validate_source(source) + validate_target(target)


def _finding(rule: str, severity: str, description: str, remediation: str) -> dict[str, str]:
    return {
        "rule_id": rule,
        "severity": severity,
        "description": description,
        "affected_configuration": "IAM policy",
        "remediation": remediation,
    }
