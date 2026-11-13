#!/usr/bin/env python3
"""Summarize Terraform drift and an independent Infracost monthly estimate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


class AnalysisError(Exception):
    """Plan input cannot be analyzed safely."""


def load_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AnalysisError(f"Terraform plan JSON not found: {path}") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisError(f"Unable to read valid Terraform plan JSON from {path}: {error}") from error
    if not isinstance(plan, dict) or not isinstance(plan.get("resource_changes"), list):
        raise AnalysisError("Plan JSON must be an object containing a resource_changes array.")
    if "resource_drift" in plan and not isinstance(plan["resource_drift"], list):
        raise AnalysisError("Plan field resource_drift must be an array when present.")
    return plan


def changed_resources(plan: dict[str, Any]) -> list[dict[str, Any]]:
    if plan.get("errored") is True:
        raise AnalysisError("Terraform plan JSON is marked errored.")
    # resource_drift is the direct refresh-vs-state signal in modern plan JSON.
    # Older/synthetic formats without it use resource_changes as a fallback.
    source = plan.get("resource_drift", plan["resource_changes"])
    by_address: dict[str, dict[str, Any]] = {}
    for item in source:
        if not isinstance(item, dict):
            raise AnalysisError("Each drift/resource change entry must be a JSON object.")
        if item.get("mode", "managed") != "managed":
            continue
        address = item.get("address")
        change = item.get("change")
        actions = change.get("actions") if isinstance(change, dict) else None
        if not isinstance(address, str) or not address or not isinstance(actions, list) or any(not isinstance(action, str) for action in actions):
            raise AnalysisError("Each managed resource change must include an address and a string change.actions array.")
        if actions != ["no-op"]:
            by_address[address] = {"address": address, "actions": actions}
    return [by_address[address] for address in sorted(by_address)]


def load_cost(path: Path | None) -> tuple[dict[str, str] | None, str | None]:
    if path is None:
        return None, "Cost estimate not supplied."
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    except FileNotFoundError:
        return None, "Cost estimate file is missing."
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, InvalidOperation):
        return None, "Cost estimate JSON is invalid."
    if not isinstance(payload, dict):
        return None, "Cost estimate must be a JSON object."
    amount = payload.get("totalMonthlyCost")
    currency = payload.get("currency")
    if isinstance(amount, bool) or not isinstance(amount, (Decimal, int, float, str)):
        return None, "Monthly cost is missing or invalid."
    try:
        monthly = Decimal(str(amount))
    except InvalidOperation:
        return None, "Monthly cost is invalid."
    if not monthly.is_finite() or monthly < 0:
        return None, "Monthly cost must be finite and non-negative."
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        return None, "Cost currency is missing or invalid."
    return {"amount": f"{monthly:.2f}", "currency": currency}, None


def analyze(plan_path: Path, cost_path: Path | None, environment: str, run_id: str = "local") -> dict[str, Any]:
    plan = load_plan(plan_path)
    try:
        resources = changed_resources(plan)
    except AnalysisError as error:
        return {
            "environment": environment,
            "run_id": run_id,
            "status": "ERROR",
            "resources_changed": 0,
            "affected_resources": [],
            "estimated_monthly_cost": None,
            "estimated_drift_cost_impact": "N/A",
            "action_required": True,
            "warnings": [],
            "error": str(error),
        }
    monthly_cost, cost_warning = load_cost(cost_path)
    drifted = bool(resources)
    warnings = [cost_warning] if cost_warning else []
    return {
        "environment": environment,
        "run_id": run_id,
        "status": "DRIFT DETECTED" if drifted else "NO DRIFT",
        "resources_changed": len(resources),
        "affected_resources": resources,
        "estimated_monthly_cost": monthly_cost,
        "estimated_drift_cost_impact": "N/A",
        "action_required": drifted,
        "warnings": warnings,
    }


def print_report(report: dict[str, Any]) -> None:
    print("Terraform Drift Detection Report\n")
    print(f"Environment: {report['environment']}")
    print(f"Run ID: {report['run_id']}")
    print(f"Status: {report['status']}")
    print(f"\nResources Changed: {report['resources_changed']}")
    if report["affected_resources"]:
        print("\nAffected Resources:")
        for resource in report["affected_resources"]:
            print(f"- {resource['address']} ({', '.join(resource['actions'])})")
    estimate = report["estimated_monthly_cost"]
    if estimate:
        value = f"${estimate['amount']}" if estimate["currency"] == "USD" else f"{estimate['currency']} {estimate['amount']}"
        print(f"\nEstimated Monthly Cost: {value}")
    else:
        print("\nEstimated Monthly Cost: N/A")
    print(f"Estimated Drift Cost Impact: {report['estimated_drift_cost_impact']}")
    for warning in report["warnings"]:
        print(f"Cost Note: {warning}")
    if report.get("error"):
        print(f"\nError: {report['error']}")
    print(f"\nAction Required: {'Review detected drift.' if report['action_required'] else 'None.'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path, help="Terraform show -json output")
    parser.add_argument("--cost", type=Path, help="Optional Infracost JSON estimate")
    parser.add_argument("--environment", required=True, choices=("dev", "stage", "prod"))
    parser.add_argument("--run-id", default="local", help="Run identifier included in reports and notifications")
    parser.add_argument("--output", type=Path, default=Path("report.json"), help="JSON report destination (default: report.json)")
    args = parser.parse_args(argv)
    try:
        report = analyze(args.plan, args.cost, args.environment, args.run_id)
        print_report(report)
        try:
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            raise AnalysisError(f"Unable to write report {args.output}: {error}") from error
        return 2 if report["status"] == "ERROR" else 0
    except AnalysisError as error:
        print(f"Analysis error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
