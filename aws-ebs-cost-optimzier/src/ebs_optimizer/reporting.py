"""Deterministic CSV, JSON, and Markdown report generation."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import ScanResult, Volume


def build_report(result: ScanResult, minimum_age_days: int) -> dict[str, Any]:
    volumes = sorted(result.volumes, key=lambda v: (v.account_id, v.region, v.volume_id))
    aged = [v for v in volumes if v.meets_age_threshold and v.state == "available"]
    eligible = [v for v in aged if v.eligible_for_review]

    def aggregate(items: list[Volume], key_fn: object) -> dict[str, dict[str, Any]]:
        totals: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"volume_count": 0, "storage_gib": 0, "monthly_cost_usd": Decimal("0")}
        )
        for volume in items:
            key = key_fn(volume)
            row = totals[key]
            row["volume_count"] += 1
            row["storage_gib"] += volume.size_gib
            if volume.monthly_cost is not None and volume.eligible_for_review:
                row["monthly_cost_usd"] += volume.monthly_cost
        return {
            key: {
                **value,
                "monthly_cost_usd": str(value["monthly_cost_usd"].quantize(Decimal("0.01"))),
            }
            for key, value in sorted(totals.items())
        }

    total_monthly = sum((v.monthly_cost or Decimal("0") for v in eligible), Decimal("0"))
    total_monthly = total_monthly.quantize(Decimal("0.01"))
    return {
        "execution_mode": result.execution_mode,
        "coverage": {
            "complete": not result.is_partial,
            "accounts_discovered": result.accounts_discovered,
            "accounts_scanned": len(result.accounts_scanned),
            "accounts_failed": len(result.accounts_failed),
            "regions_scanned": sorted(result.regions_scanned),
            "volumes_inspected": result.volumes_inspected,
            "unattached_volumes_found": len(volumes),
            "unattached_volumes_meeting_age_threshold": len(aged),
            "review_candidates": len(eligible),
            "candidate_storage_gib": sum(v.size_gib for v in eligible),
            "estimated_monthly_candidate_cost_usd": str(total_monthly),
            "estimated_annualized_candidate_cost_usd": str(
                (total_monthly * 12).quantize(Decimal("0.01"))
            ),
            "cost_is_run_rate_estimate": True,
        },
        "by_account": aggregate(aged, lambda v: f"{v.account_id} ({v.account_name})"),
        "by_region": aggregate(aged, lambda v: v.region),
        "by_volume_type": aggregate(aged, lambda v: v.volume_type),
        "volumes": [v.to_dict() for v in volumes],
        "errors": [
            {"scope": e.scope, "target": e.target, "code": e.code, "message": e.message}
            for e in sorted(result.errors, key=lambda e: (e.scope, e.target, e.code))
        ],
    }


CSV_FIELDS = [
    "account_id",
    "account_name",
    "environment",
    "region",
    "volume_id",
    "availability_zone",
    "volume_type",
    "size_gib",
    "create_time",
    "age_days",
    "meets_age_threshold",
    "state",
    "tags",
    "encrypted",
    "kms_key_id",
    "iops",
    "throughput_mibps",
    "eligible_for_review",
    "exclusion_reason",
    "pricing_status",
    "monthly_cost",
    "pricing_source",
    "pricing_effective_date",
]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass  # Windows ACLs control access on Windows.
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_reports(report: dict[str, Any], output_dir: Path, formats: list[str]) -> list[Path]:
    supported = {"csv", "json", "markdown"}
    if not formats or set(formats) - supported:
        raise ValueError("formats must be a non-empty subset of csv, json, markdown")
    written: list[Path] = []
    if "json" in formats:
        path = output_dir / "ebs-cost-report.json"
        _atomic_write(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        written.append(path)
    if "csv" in formats:
        path = output_dir / "ebs-cost-report.csv"
        from io import StringIO

        stream = StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for volume in report["volumes"]:
            row = dict(volume)
            row["tags"] = json.dumps(row["tags"], sort_keys=True)
            writer.writerow(row)
        _atomic_write(path, stream.getvalue())
        written.append(path)
    if "markdown" in formats:
        path = output_dir / "ebs-cost-report.md"
        _atomic_write(path, render_markdown(report))
        written.append(path)
    return written


def render_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    state = "COMPLETE" if coverage["complete"] else "PARTIAL — review errors"
    lines = [
        "# EBS Cost Optimization Report",
        "",
        f"**Execution mode:** {report['execution_mode']}  ",
        f"**Coverage:** {state}",
        "",
        "All cost values are illustrative monthly run-rate estimates, not AWS charges "
        "or realized savings.",
        "Age is calculated from volume creation time, not historical unattached duration.",
        "",
        "## Summary",
        "",
        f"- Accounts discovered: {coverage['accounts_discovered']}",
        f"- Accounts scanned: {coverage['accounts_scanned']}",
        f"- Accounts failed: {coverage['accounts_failed']}",
        f"- Regions scanned: {len(coverage['regions_scanned'])}",
        f"- Volumes inspected: {coverage['volumes_inspected']}",
        f"- Unattached volumes found: {coverage['unattached_volumes_found']}",
        "- Unattached volumes meeting age threshold: "
        f"{coverage['unattached_volumes_meeting_age_threshold']}",
        f"- Review candidates: {coverage['review_candidates']}",
        f"- Candidate storage: {coverage['candidate_storage_gib']} GiB",
        f"- Estimated monthly run rate: ${coverage['estimated_monthly_candidate_cost_usd']} USD",
        f"- Annualized projection: ${coverage['estimated_annualized_candidate_cost_usd']} USD",
        "",
        "## Volumes",
        "",
        "| Account | Region | Volume | Type | GiB | Age | Monthly USD | Review status |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]

    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    for volume in report["volumes"]:
        monthly = volume["monthly_cost"] if volume["monthly_cost"] is not None else "unavailable"
        status = (
            "review only"
            if volume["eligible_for_review"]
            else volume["exclusion_reason"] or "excluded"
        )
        lines.append(
            f"| {cell(volume['account_name'])} | {cell(volume['region'])} | "
            f"{cell(volume['volume_id'])} | {cell(volume['volume_type'])} | "
            f"{cell(volume['size_gib'])} | {cell(volume['age_days'])} days | "
            f"{cell(monthly)} | {cell(status)} |"
        )
    if report["errors"]:
        lines.extend(["", "## Scan errors", ""])
        for error in report["errors"]:
            lines.append(f"- {error['scope']} `{error['target']}`: {error['code']}")
    lines.append("")
    return "\n".join(lines)
