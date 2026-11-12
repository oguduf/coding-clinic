#!/usr/bin/env python3
"""Validate Terraform plan JSON against a small, configurable policy set."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class InputError(Exception):
    """Input files are malformed or do not match the supported schema."""


@dataclass
class Check:
    status: str = "PASS"
    violations: list[str] | None = None

    def __post_init__(self) -> None:
        if self.violations is None:
            self.violations = []

    def fail(self, message: str) -> None:
        self.status = "FAIL"
        self.violations.append(message)

    def review(self, message: str) -> None:
        if self.status != "FAIL":
            self.status = "REVIEW_REQUIRED"
        self.violations.append(message)


TAGGABLE_AWS_TYPES = {
    "aws_instance", "aws_launch_template", "aws_security_group", "aws_vpc",
    "aws_subnet", "aws_ebs_volume", "aws_kms_key", "aws_iam_role",
    "aws_lambda_function", "aws_dynamodb_table", "aws_rds_cluster",
    "aws_db_instance", "aws_s3_bucket", "aws_sqs_queue", "aws_sns_topic",
    "aws_ecs_cluster", "aws_ecs_service", "aws_eks_cluster",
}
PUBLIC_ACLS = {"public-read", "public-read-write", "authenticated-read"}
PUBLIC_GROUPS = {
    "http://acs.amazonaws.com/groups/global/allusers",
    "http://acs.amazonaws.com/groups/global/authenticatedusers",
}
PUBLIC_ACCESS_KEYS = (
    "block_public_acls", "ignore_public_acls",
    "block_public_policy", "restrict_public_buckets",
)


def read_json(path: Path, label: str, *, decimal_numbers: bool = False) -> Any:
    try:
        with path.open(encoding="utf-8") as stream:
            if decimal_numbers:
                return json.load(stream, parse_float=Decimal, parse_int=Decimal)
            return json.load(stream)
    except FileNotFoundError as error:
        raise InputError(f"{label} file not found: {path}") from error
    except OSError as error:
        raise InputError(f"Unable to read {label} file {path}: {error}") from error
    except (json.JSONDecodeError, UnicodeDecodeError, InvalidOperation) as error:
        raise InputError(f"Invalid JSON in {label} file {path}: {error}") from error


def load_policy(path: Path) -> dict[str, Any]:
    policy = read_json(path, "policy", decimal_numbers=True)
    if not isinstance(policy, dict):
        raise InputError("Policy must be a JSON object.")
    required_fields = {"required_tags", "enforce_s3_private", "max_monthly_cost_usd"}
    missing = required_fields - policy.keys()
    if missing:
        raise InputError(f"Policy is missing required field(s): {', '.join(sorted(missing))}.")
    tags = policy["required_tags"]
    if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise InputError("Policy field 'required_tags' must be a non-empty list of non-empty strings.")
    if len({tag.casefold() for tag in tags}) != len(tags):
        raise InputError("Policy field 'required_tags' must not contain duplicates (case-insensitive).")
    if not isinstance(policy["enforce_s3_private"], bool):
        raise InputError("Policy field 'enforce_s3_private' must be a boolean.")
    policy["max_monthly_cost_usd"] = parse_money(
        policy["max_monthly_cost_usd"], "policy max_monthly_cost_usd"
    )
    return policy


def parse_money(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise InputError(f"{label} must be a non-negative finite number.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise InputError(f"{label} must be a non-negative finite number.") from error
    if not amount.is_finite() or amount < 0:
        raise InputError(f"{label} must be a non-negative finite number.")
    return amount


def load_plan(path: Path) -> dict[str, Any]:
    plan = read_json(path, "Terraform plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("format_version"), str):
        raise InputError("Input is not Terraform plan JSON: expected a top-level format_version string.")
    if not re.fullmatch(r"1\.\d+", plan["format_version"]):
        raise InputError(f"Unsupported Terraform plan JSON format_version {plan['format_version']!r}; supported major format is 1.")
    if "resource_changes" not in plan or not isinstance(plan["resource_changes"], list):
        raise InputError("Terraform plan JSON must contain a resource_changes array.")
    for index, resource in enumerate(plan["resource_changes"]):
        if not isinstance(resource, dict) or not all(isinstance(resource.get(key), str) for key in ("address", "type")):
            raise InputError(f"resource_changes[{index}] must include string address and type fields.")
        change = resource.get("change")
        if not isinstance(change, dict) or not isinstance(change.get("actions"), list):
            raise InputError(f"Resource {resource['address']} must include change.actions as an array.")
    return plan


def _has_unknown(unknown: Any, key: str) -> bool:
    return isinstance(unknown, dict) and (unknown.get(key) is True or isinstance(unknown.get(key), (dict, list)))


def _active_changes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    active = []
    for resource in plan["resource_changes"]:
        actions = resource["change"]["actions"]
        if not all(isinstance(action, str) for action in actions):
            raise InputError(f"Resource {resource['address']} has invalid change.actions values.")
        if actions != ["delete"] and ("create" in actions or "update" in actions):
            active.append(resource)
    return active


def _public_principal(principal: Any) -> bool:
    if principal == "*":
        return True
    if isinstance(principal, dict):
        return any(value == "*" or (isinstance(value, list) and "*" in value) for value in principal.values())
    return False


def _policy_statements(policy_value: Any) -> list[dict[str, Any]] | None:
    if isinstance(policy_value, str):
        try:
            policy_value = json.loads(policy_value)
        except json.JSONDecodeError:
            return None
    if not isinstance(policy_value, dict) or not isinstance(policy_value.get("Statement"), (dict, list)):
        return None
    statements = policy_value["Statement"]
    statements = [statements] if isinstance(statements, dict) else statements
    return [statement for statement in statements if isinstance(statement, dict)]


def check_s3(plan: dict[str, Any], enforce: bool) -> Check:
    result = Check()
    if not enforce:
        return result
    for resource in _active_changes(plan):
        kind = resource["type"]
        address = resource["address"]
        change = resource["change"]
        after = change.get("after")
        unknown = change.get("after_unknown", {})
        if kind not in {"aws_s3_bucket", "aws_s3_bucket_public_access_block", "aws_s3_bucket_acl", "aws_s3_bucket_policy"}:
            continue
        if not isinstance(after, dict):
            result.review(f"{address}: planned S3 values are missing or unknown; verify exposure manually.")
            continue
        if kind == "aws_s3_bucket":
            if _has_unknown(unknown, "acl") or "acl" not in after or after.get("acl") is None:
                result.review(f"{address}: ACL is unknown; verify that it is not public.")
            elif str(after.get("acl", "private")).lower() in PUBLIC_ACLS:
                result.fail(f"{address}: public ACL '{after['acl']}' is not allowed; use private access.")
        elif kind == "aws_s3_bucket_public_access_block":
            for key in PUBLIC_ACCESS_KEYS:
                if _has_unknown(unknown, key) or key not in after or not isinstance(after.get(key), bool):
                    result.review(f"{address}: {key} is missing or unknown; confirm all S3 public access protections are enabled.")
                elif after[key] is False:
                    result.fail(f"{address}: {key}=false disables an S3 public access protection; set it to true.")
        elif kind == "aws_s3_bucket_acl":
            if _has_unknown(unknown, "acl"):
                result.review(f"{address}: ACL is unknown; verify that it is not public.")
            elif str(after.get("acl", "")).lower() in PUBLIC_ACLS:
                result.fail(f"{address}: public ACL '{after['acl']}' is not allowed; use private access.")
            grants = (after.get("access_control_policy") or {}).get("grant", []) if isinstance(after.get("access_control_policy"), dict) else []
            for grant in grants if isinstance(grants, list) else []:
                grantee = grant.get("grantee", {}) if isinstance(grant, dict) else {}
                uri = grantee.get("uri") if isinstance(grantee, dict) else None
                if uri and uri.lower() in PUBLIC_GROUPS:
                    result.fail(f"{address}: ACL grants access to public group {uri}; remove the public grant.")
            if _has_unknown(unknown, "access_control_policy"):
                result.review(f"{address}: ACL grants are unknown; verify that no public group is granted access.")
        elif kind == "aws_s3_bucket_policy":
            if _has_unknown(unknown, "policy") or "policy" not in after:
                result.review(f"{address}: bucket policy is missing or unknown; review its principals and conditions.")
                continue
            statements = _policy_statements(after["policy"])
            if statements is None:
                result.review(f"{address}: bucket policy could not be interpreted; review it manually.")
                continue
            for statement in statements:
                if str(statement.get("Effect", "")).lower() != "allow" or not _public_principal(statement.get("Principal")):
                    continue
                if statement.get("Condition"):
                    result.review(f"{address}: public-principal Allow statement has conditions; verify reachability and intended access.")
                else:
                    result.fail(f"{address}: bucket policy has an unconditional public-principal Allow statement; restrict the principal.")
    return result


def check_tags(plan: dict[str, Any], required_tags: list[str]) -> Check:
    result = Check()
    for resource in _active_changes(plan):
        if resource["type"] not in TAGGABLE_AWS_TYPES:
            continue
        address = resource["address"]
        change = resource["change"]
        after = change.get("after")
        unknown = change.get("after_unknown", {})
        if not isinstance(after, dict):
            result.review(f"{address}: planned tags are unavailable; required tags cannot be verified.")
            continue
        after_tags: dict[str, Any] = {}
        if isinstance(after.get("tags_all"), dict):
            after_tags.update(after["tags_all"])
        if isinstance(after.get("tags"), dict):
            after_tags.update(after["tags"])
        unknown_keys: set[str] = set()
        for attr in ("tags_all", "tags"):
            attr_unknown = unknown.get(attr) if isinstance(unknown, dict) else None
            if attr_unknown is True:
                unknown_keys.update(required_tags)
            elif isinstance(attr_unknown, dict):
                unknown_keys.update(key for key, value in attr_unknown.items() if value is True and key in required_tags)
        for tag in required_tags:
            if tag in unknown_keys:
                result.review(f"{address}: required tag '{tag}' has an unknown planned value.")
            elif tag not in after_tags or after_tags[tag] is None or after_tags[tag] == "":
                result.fail(f"{address}: missing required tag '{tag}'; add it to tags or tags_all.")
    return result


def check_cost(path: Path, threshold: Decimal) -> Check:
    cost_data = read_json(path, "cost estimate", decimal_numbers=True)
    if not isinstance(cost_data, dict) or "estimated_monthly_cost_usd" not in cost_data:
        raise InputError("Cost estimate must be a JSON object with estimated_monthly_cost_usd.")
    estimate = parse_money(cost_data["estimated_monthly_cost_usd"], "estimated_monthly_cost_usd")
    result = Check()
    if estimate > threshold:
        result.fail(f"Estimated monthly cost ${estimate:.2f} exceeds configured budget ${threshold:.2f}.")
    return result


def validate(plan_path: Path, policy_path: Path, cost_path: Path) -> dict[str, Any]:
    policy = load_policy(policy_path)
    plan = load_plan(plan_path)
    active = _active_changes(plan)
    checks = {
        "s3_security": check_s3(plan, policy["enforce_s3_private"]),
        "required_tags": check_tags(plan, policy["required_tags"]),
        "cost_threshold": check_cost(cost_path, policy["max_monthly_cost_usd"]),
    }
    statuses = [check.status for check in checks.values()]
    overall = "FAIL" if "FAIL" in statuses else "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "PASS"
    return {
        "overall_result": overall,
        "resources_checked": len(active),
        "checks": {key: asdict(value) for key, value in checks.items()},
    }


def print_report(report: dict[str, Any]) -> None:
    checks = report["checks"]
    print("Terraform Policy Validation\n")
    print(f"S3 Security: {checks['s3_security']['status']}")
    print(f"Required Tags: {checks['required_tags']['status']}")
    print(f"Cost Threshold: {checks['cost_threshold']['status']}")
    print(f"\nResources checked: {report['resources_checked']}")
    for key, check in checks.items():
        for message in check["violations"]:
            print(f"- {key.replace('_', ' ').title()}: {message}")
    print(f"\nOverall Result: {report['overall_result']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="Terraform plan JSON from terraform show -json")
    parser.add_argument("--policy", required=True, type=Path, help="JSON policy configuration")
    parser.add_argument("--cost", required=True, type=Path, help="External monthly cost estimate JSON")
    parser.add_argument("--output", type=Path, help="Optional path for a JSON validation report")
    args = parser.parse_args(argv)
    try:
        report = validate(args.plan, args.policy, args.cost)
        print_report(report)
        if args.output:
            try:
                args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            except OSError as error:
                raise InputError(f"Unable to write report {args.output}: {error}") from error
        return 0 if report["overall_result"] == "PASS" else 1
    except InputError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
