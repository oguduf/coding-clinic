#!/usr/bin/env python3
"""Preview or explicitly send a Terraform drift report to a Slack webhook."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class NotificationError(Exception):
    """Slack notification could not be validated or delivered."""


def read_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise NotificationError(f"Report file not found: {path}") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise NotificationError(f"Unable to read valid report JSON from {path}: {error}") from error
    if not isinstance(report, dict):
        raise NotificationError("Report JSON must be an object.")
    if report.get("environment") not in {"dev", "stage", "prod"} or report.get("status") not in {"DRIFT DETECTED", "NO DRIFT", "ERROR"}:
        raise NotificationError("Report must include a valid environment and status.")
    if not isinstance(report.get("resources_changed"), int) or report["resources_changed"] < 0:
        raise NotificationError("Report resources_changed must be a non-negative integer.")
    return report


def _safe(value: object, maximum: int = 120) -> str:
    text = re.sub(r"[\r\n\x00-\x1f]+", " ", str(value)).strip()
    return text[:maximum]


def format_message(report: dict[str, Any]) -> str:
    estimate = report.get("estimated_monthly_cost")
    if isinstance(estimate, dict) and isinstance(estimate.get("amount"), str) and isinstance(estimate.get("currency"), str):
        cost = f"{_safe(estimate['currency'], 3)} {_safe(estimate['amount'], 32)}"
    else:
        cost = "N/A"
    review = "Yes" if report.get("action_required") is True else "No"
    return "\n".join(
        (
            f"Terraform drift report - {_safe(report['environment'], 32)}",
            f"Run ID: {_safe(report.get('run_id', 'local'), 64)}",
            f"Status: {_safe(report['status'], 32)}",
            f"Changed resources: {report['resources_changed']}",
            f"Estimated monthly cost: {cost}",
            f"Estimated drift cost impact: {_safe(report.get('estimated_drift_cost_impact', 'N/A'), 32)}",
            f"Review required: {review}",
        )
    )


def send_message(webhook_url: str, message: str) -> None:
    parsed_url = urlsplit(webhook_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc or parsed_url.username or parsed_url.password:
        raise NotificationError("SLACK_WEBHOOK_URL must be an HTTPS webhook URL.")
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status < 200 or response.status >= 300:
                raise NotificationError(f"Slack webhook returned HTTP status {response.status}.")
    except urllib.error.HTTPError as error:
        raise NotificationError(f"Slack webhook returned HTTP status {error.code}.") from error
    except urllib.error.URLError as error:
        # Do not print the exception: some urllib errors include the webhook URL.
        raise NotificationError("Slack webhook request failed; URL details were suppressed.") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path, help="JSON report from analyze.py")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print preview without network access (default)")
    mode.add_argument("--send", action="store_true", help="Send the message using SLACK_WEBHOOK_URL")
    args = parser.parse_args(argv)
    try:
        report = read_report(args.report)
        message = format_message(report)
        if not args.send:
            print("Slack message preview (dry-run; no network request):\n")
            print(message)
            return 0
        webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not webhook:
            raise NotificationError("SLACK_WEBHOOK_URL is required when --send is specified.")
        send_message(webhook, message)
        print("Slack notification sent.")
        return 0
    except NotificationError as error:
        print(f"Notification error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
