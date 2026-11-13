import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import notify_slack  # noqa: E402


class NotifyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.report_path = Path(self.temporary.name) / "report.json"
        self.report_path.write_text(json.dumps({
            "environment": "dev",
            "run_id": "run-1234",
            "status": "DRIFT DETECTED",
            "resources_changed": 2,
            "affected_resources": [{"address": "aws_instance.web", "actions": ["update"]}],
            "estimated_monthly_cost": {"amount": "125.50", "currency": "USD"},
            "estimated_drift_cost_impact": "N/A",
            "action_required": True,
        }), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_slack_message_format(self):
        report = notify_slack.read_report(self.report_path)
        message = notify_slack.format_message(report)
        self.assertIn("dev", message)
        self.assertIn("run-1234", message)
        self.assertIn("DRIFT DETECTED", message)
        self.assertIn("Changed resources: 2", message)
        self.assertIn("USD 125.50", message)
        self.assertIn("Review required: Yes", message)

    def test_dry_run_prints_preview_without_network(self):
        with patch.object(sys, "stdout", new=MagicMock()), patch("notify_slack.urllib.request.urlopen") as urlopen:
            result = notify_slack.main(["--report", str(self.report_path), "--dry-run"])
        self.assertEqual(result, 0)
        urlopen.assert_not_called()

    def test_mocked_webhook_delivery(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.example.invalid/services/mock"}), patch("notify_slack.urllib.request.urlopen", return_value=response) as urlopen:
            result = notify_slack.main(["--report", str(self.report_path), "--send"])
        self.assertEqual(result, 0)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertIn("DRIFT DETECTED", payload["text"])

    def test_missing_webhook_fails_without_network(self):
        with patch.dict(os.environ, {}, clear=True), patch("notify_slack.urllib.request.urlopen") as urlopen:
            result = notify_slack.main(["--report", str(self.report_path), "--send"])
        self.assertEqual(result, 2)
        urlopen.assert_not_called()

    def test_invalid_report_is_rejected(self):
        bad = Path(self.temporary.name) / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        with self.assertRaises(notify_slack.NotificationError):
            notify_slack.read_report(bad)


if __name__ == "__main__":
    unittest.main()
