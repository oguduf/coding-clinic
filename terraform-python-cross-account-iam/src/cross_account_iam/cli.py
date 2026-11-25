"""Offline CLI for configuration and policy checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cross_account_iam.config import ConfigError, load_config
from cross_account_iam.policy_validator import load_policy, validate_all


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cross-account-iam", description="Offline cross-account IAM validation"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    config = sub.add_parser("validate-config", help="Validate an example YAML configuration")
    config.add_argument("--config", required=True)
    policies = sub.add_parser(
        "validate-policy", help="Validate trust, source, and target IAM policy JSON"
    )
    policies.add_argument("--trust-policy", required=True)
    policies.add_argument("--source-policy", required=True)
    policies.add_argument("--target-policy", required=True)
    report = sub.add_parser("report", help="Generate an offline validation report")
    report.add_argument("--config", required=True)
    report.add_argument("--output", required=True)
    return parser


def _report(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "offline-static-validation",
        "environment": config["application"]["environment"],
        "account_ids": {
            "source": config["cross_account"]["source_account_id"],
            "target": config["cross_account"]["target_account_id"],
        },
        "external_id": "configured-via-environment-variable; value-redacted",
        "aws_api_calls": 0,
        "findings": [],
        "limitations": ["Static checks are not full AWS IAM authorization evaluation."],
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-config":
            config = load_config(args.config)
            print(
                json.dumps(
                    {
                        "valid": True,
                        "environment": config["application"]["environment"],
                        "external_id": "redacted",
                    }
                )
            )
            return 0
        if args.command == "validate-policy":
            trust = load_policy(args.trust_policy)
            source = load_policy(args.source_policy)
            target = load_policy(args.target_policy)
            findings = validate_all(trust, source, target)
            print(json.dumps({"valid": not findings, "findings": findings}, indent=2))
            return 1 if findings else 0
        config = load_config(args.config)
        content = json.dumps(_report(config), indent=2) + "\n"
        Path(args.output).write_text(content, encoding="utf-8")
        print(
            json.dumps(
                {"report_written": args.output, "external_id": "redacted", "aws_api_calls": 0}
            )
        )
        return 0
    except (ConfigError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
