import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
EVALUATOR = ROOT / "scripts" / "evaluate_trivy.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run_gate(tmp_path, amd64="trivy-clean-amd64.json", arm64="trivy-clean-arm64.json"):
    return subprocess.run(
        [sys.executable, str(EVALUATOR), "--amd64", str(FIXTURES / amd64), "--arm64",
         str(FIXTURES / arm64), "--summary", str(tmp_path / "summary.json")],
        capture_output=True, text=True, check=False,
    )


def test_clean_reports_for_both_platforms_pass(tmp_path):
    result = run_gate(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((tmp_path / "summary.json").read_text())["passed"] is True


def test_high_and_critical_findings_fail(tmp_path):
    assert run_gate(tmp_path, amd64="trivy-high.json").returncode == 1
    assert run_gate(tmp_path, arm64="trivy-critical.json").returncode == 1


def test_missing_or_malformed_report_fails_closed(tmp_path):
    missing = subprocess.run([sys.executable, str(EVALUATOR), "--amd64", str(FIXTURES / "missing.json"),
        "--arm64", str(FIXTURES / "trivy-clean-arm64.json")], capture_output=True, text=True)
    assert missing.returncode == 1
    assert run_gate(tmp_path, amd64="trivy-malformed.json").returncode == 1


def test_empty_result_list_fails_closed(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text('{"Results": []}')
    result = subprocess.run([sys.executable, str(EVALUATOR), "--amd64", str(empty), "--arm64",
        str(FIXTURES / "trivy-clean-arm64.json")], capture_output=True, text=True)
    assert result.returncode == 1
