from __future__ import annotations

import json

import pytest

from ebs_optimizer.cli import _fixture_scan, main, parser


def test_offline_cli_writes_reports_and_optional_plan(tmp_path, project_root, capsys):
    fixture = project_root / "examples/sample_organization.json"
    config = project_root / "config/config.example.yaml"
    pricing = project_root / "config/pricing.example.json"
    output = tmp_path / "reports"
    code = main(
        [
            "--fixture",
            str(fixture),
            "--config",
            str(config),
            "--pricing",
            str(pricing),
            "--output-dir",
            str(output),
            "--generate-deletion-plan",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "offline fixture" in captured.out
    assert (output / "ebs-cost-report.csv").exists()
    assert (output / "ebs-cost-report.json").exists()
    assert (output / "ebs-cost-report.md").exists()
    plan = json.loads((output / "ebs-deletion-review-plan.json").read_text(encoding="utf-8"))
    assert all(item["manual_approval_required"] for item in plan["entries"])


def test_minimum_age_override_changes_candidate_count(tmp_path, project_root):
    args = [
        "--fixture",
        str(project_root / "examples/sample_organization.json"),
        "--config",
        str(project_root / "config/config.example.yaml"),
        "--pricing",
        str(project_root / "config/pricing.example.json"),
        "--output-dir",
        str(tmp_path),
        "--min-age-days",
        "90",
        "--format",
        "json",
    ]
    assert main(args) == 0
    report = json.loads((tmp_path / "ebs-cost-report.json").read_text(encoding="utf-8"))
    assert report["coverage"]["unattached_volumes_meeting_age_threshold"] == 4


def test_invalid_age_is_rejected(tmp_path, project_root, capsys):
    code = main(
        [
            "--fixture",
            str(project_root / "examples/sample_organization.json"),
            "--config",
            str(project_root / "config/config.example.yaml"),
            "--pricing",
            str(project_root / "config/pricing.example.json"),
            "--output-dir",
            str(tmp_path),
            "--min-age-days",
            "-1",
        ]
    )
    assert code == 1
    assert "zero or greater" in capsys.readouterr().err


def test_missing_fixture_returns_readable_error(tmp_path, project_root, capsys):
    code = main(
        [
            "--fixture",
            str(tmp_path / "missing.json"),
            "--config",
            str(project_root / "config/config.example.yaml"),
            "--pricing",
            str(project_root / "config/pricing.example.json"),
        ]
    )
    assert code == 1
    assert "Cannot load JSON" in capsys.readouterr().err


def test_malformed_volume_creates_partial_report_and_nonzero_status(tmp_path, project_root):
    fixture = tmp_path / "bad-volume.json"
    fixture.write_text(
        json.dumps(
            {"accounts": [{"account_id": "000000000101", "volumes": [{"Region": "us-east-1"}]}]}
        ),
        encoding="utf-8",
    )
    result, volumes = _fixture_scan(fixture)
    assert volumes == []
    assert result.is_partial
    assert result.accounts_failed == {"000000000101"}


def test_bad_argument_types_fail_in_parser():
    with pytest.raises(SystemExit):
        parser().parse_args(["--format", "html"])


def test_configuration_include_exclude_account_filter(project_root):
    fixture = project_root / "examples/sample_organization.json"
    result, volumes = _fixture_scan(fixture, include_accounts=["000000000202"])
    assert result.accounts_scanned == {"000000000202"}
    assert all(volume.account_id == "000000000202" for volume in volumes)
