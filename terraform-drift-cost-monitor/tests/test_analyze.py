import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze  # noqa: E402


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.examples = ROOT / "examples"

    def test_no_drift(self):
        report = analyze.analyze(self.examples / "no-drift-plan.json", self.examples / "infracost-example.json", "dev")
        self.assertEqual(report["status"], "NO DRIFT")
        self.assertEqual(report["resources_changed"], 0)
        self.assertFalse(report["action_required"])

    def test_drift_detected(self):
        report = analyze.analyze(self.examples / "drift-plan.json", self.examples / "infracost-example.json", "dev")
        self.assertEqual(report["status"], "DRIFT DETECTED")
        self.assertEqual(report["resources_changed"], 2)
        self.assertTrue(report["action_required"])

    def test_multiple_changed_resources_are_deduplicated_and_identified(self):
        plan = {
            "resource_changes": [],
            "resource_drift": [
                {"address": "aws_instance.web", "mode": "managed", "change": {"actions": ["update"]}},
                {"address": "aws_instance.web", "mode": "managed", "change": {"actions": ["update"]}},
                {"address": "data.aws_region.current", "mode": "data", "change": {"actions": ["read"]}},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            changed = analyze.changed_resources(analyze.load_plan(path))
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0]["address"], "aws_instance.web")

    def test_terraform_error_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text('{"resource_changes": [], "errored": true}', encoding="utf-8")
            report = analyze.analyze(path, None, "dev")
        self.assertEqual(report["status"], "ERROR")
        self.assertIn("errored", report["error"])

    def test_valid_infracost_estimate_uses_decimal(self):
        cost, warning = analyze.load_cost(self.examples / "infracost-example.json")
        self.assertIsNone(warning)
        self.assertEqual(cost, {"amount": "125.50", "currency": "USD"})

    def test_missing_cost_data_is_na(self):
        cost, warning = analyze.load_cost(None)
        self.assertIsNone(cost)
        self.assertIn("not supplied", warning)

    def test_invalid_cost_data_is_na(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cost.json"
            path.write_text('{"totalMonthlyCost": "NaN", "currency": "USD"}', encoding="utf-8")
            cost, warning = analyze.load_cost(path)
        self.assertIsNone(cost)
        self.assertIn("finite", warning)

    def test_report_does_not_include_plan_values_and_delta_is_na(self):
        report = analyze.analyze(self.examples / "drift-plan.json", self.examples / "infracost-example.json", "dev")
        serialized = json.dumps(report)
        self.assertNotIn("synthetic out-of-band change", serialized)
        self.assertEqual(report["estimated_drift_cost_impact"], "N/A")

    def test_invalid_plan_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(analyze.AnalysisError):
                analyze.load_plan(path)

    def test_cli_writes_json_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "analyze.py"), "--plan", str(self.examples / "no-drift-plan.json"), "--cost", str(self.examples / "infracost-example.json"), "--environment", "dev", "--output", str(report)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "NO DRIFT")


if __name__ == "__main__":
    unittest.main()
