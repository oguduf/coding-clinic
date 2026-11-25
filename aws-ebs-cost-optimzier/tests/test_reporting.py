from __future__ import annotations

import csv
import json
from dataclasses import replace
from decimal import Decimal

import pytest

from ebs_optimizer.models import ScanError, ScanResult
from ebs_optimizer.reporting import build_report, render_markdown, write_reports


def result_with_volumes(volume, reference_time):
    candidate = replace(
        volume,
        age_days=45,
        meets_age_threshold=True,
        eligible_for_review=True,
        pricing_status="available",
        monthly_cost=Decimal("12.50"),
    )
    second = replace(candidate, volume_id="vol-synthetic000", region="us-west-2", size_gib=25)
    return ScanResult(
        accounts_discovered=2,
        accounts_scanned={volume.account_id},
        regions_scanned={"us-east-1", "us-west-2"},
        volumes_inspected=3,
        volumes=[candidate, second],
        reference_time=reference_time,
    )


def test_summary_annualization_aggregation_and_deterministic_order(volume, reference_time):
    report = build_report(result_with_volumes(volume, reference_time), 30)
    assert report["coverage"]["estimated_monthly_candidate_cost_usd"] == "25.00"
    assert report["coverage"]["estimated_annualized_candidate_cost_usd"] == "300.00"
    assert report["coverage"]["volumes_inspected"] == 3
    assert report["coverage"]["review_candidates"] == 2
    assert report["volumes"][0]["volume_id"] == "vol-synthetic001"
    assert len(report["by_region"]) == 2


def test_partial_failures_are_visible(volume, reference_time):
    result = result_with_volumes(volume, reference_time)
    result.errors.append(ScanError("region", "acct/us-east-1", "AccessDenied", "denied"))
    report = build_report(result, 30)
    assert report["coverage"]["complete"] is False
    assert report["errors"][0]["code"] == "AccessDenied"
    assert "PARTIAL" in render_markdown(report)


def test_csv_json_and_markdown_reports_are_written_and_overwritten(
    tmp_path, volume, reference_time
):
    report = build_report(result_with_volumes(volume, reference_time), 30)
    files = write_reports(report, tmp_path, ["csv", "json", "markdown"])
    assert {path.suffix for path in files} == {".csv", ".json", ".md"}
    parsed = json.loads((tmp_path / "ebs-cost-report.json").read_text(encoding="utf-8"))
    assert parsed == report
    with (tmp_path / "ebs-cost-report.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert "not AWS charges" in (tmp_path / "ebs-cost-report.md").read_text(encoding="utf-8")
    write_reports(report, tmp_path, ["json"])
    assert len(list(tmp_path.iterdir())) == 3


def test_invalid_format_rejected(tmp_path):
    with pytest.raises(ValueError):
        write_reports({}, tmp_path, ["html"])
