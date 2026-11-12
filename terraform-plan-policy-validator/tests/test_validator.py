import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import validator  # noqa: E402


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.examples = ROOT / "examples"
        self.policy = ROOT / "policies.json"

    def test_compliant_plan_passes(self):
        report = validator.validate(self.examples / "compliant-plan.json", self.policy, self.examples / "compliant-cost.json")
        self.assertEqual(report["overall_result"], "PASS")
        self.assertEqual(report["resources_checked"], 3)

    def test_noncompliant_plan_fails(self):
        report = validator.validate(self.examples / "noncompliant-plan.json", self.policy, self.examples / "over-budget-cost.json")
        self.assertEqual(report["overall_result"], "FAIL")
        self.assertTrue(report["checks"]["required_tags"]["violations"])

    def test_public_s3_acl_fails_with_address(self):
        report = validator.check_s3(self.plan(self.resource("aws_s3_bucket.public", "aws_s3_bucket", {"acl": "public-read"})), True)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("aws_s3_bucket.public", report.violations[0])

    def test_public_s3_policy_fails(self):
        policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "*"}]}
        report = validator.check_s3(self.plan(self.resource("aws_s3_bucket_policy.public", "aws_s3_bucket_policy", {"policy": policy})), True)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("unconditional public-principal", report.violations[0])

    def test_unsafe_public_access_block_fails(self):
        values = {key: True for key in validator.PUBLIC_ACCESS_KEYS}
        values["block_public_policy"] = False
        report = validator.check_s3(self.plan(self.resource("aws_s3_bucket_public_access_block.assets", "aws_s3_bucket_public_access_block", values)), True)
        self.assertEqual(report.status, "FAIL")
        self.assertIn("block_public_policy=false", report.violations[0])

    def test_missing_required_tag_fails(self):
        resource = self.resource("aws_instance.web", "aws_instance", {"tags": {"Environment": "dev", "Project": "x"}})
        report = validator.check_tags(self.plan(resource), ["Environment", "Owner", "Project"])
        self.assertEqual(report.status, "FAIL")
        self.assertTrue(any("Owner" in item for item in report.violations))

    def test_correct_tags_pass(self):
        tags = {"Environment": "dev", "Owner": "team", "Project": "app"}
        report = validator.check_tags(self.plan(self.resource("aws_instance.web", "aws_instance", {"tags_all": tags})), list(tags))
        self.assertEqual(report.status, "PASS")

    def test_delete_only_resource_is_skipped(self):
        deleted = self.resource("aws_instance.old", "aws_instance", None, actions=["delete"])
        self.assertEqual(validator.check_tags(self.plan(deleted), ["Owner"]).status, "PASS")

    def test_unknown_values_require_review_and_fail_closed(self):
        resource = self.resource("aws_instance.web", "aws_instance", {"tags": {}}, unknown={"tags": {"Owner": True}})
        report = validator.check_tags(self.plan(resource), ["Owner"])
        self.assertEqual(report.status, "REVIEW_REQUIRED")
        s3 = self.resource("aws_s3_bucket.assets", "aws_s3_bucket", {}, unknown={"acl": True})
        self.assertEqual(validator.check_s3(self.plan(s3), True).status, "REVIEW_REQUIRED")

    def test_cost_below_threshold_passes(self):
        self.assertEqual(validator.check_cost(self.examples / "compliant-cost.json", Decimal("500")).status, "PASS")

    def test_cost_above_threshold_fails(self):
        result = validator.check_cost(self.examples / "over-budget-cost.json", Decimal("500"))
        self.assertEqual(result.status, "FAIL")
        self.assertIn("650.00", result.violations[0])

    def test_cost_equal_to_threshold_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cost.json"
            path.write_text('{"estimated_monthly_cost_usd": 500.00}', encoding="utf-8")
            self.assertEqual(validator.check_cost(path, Decimal("500")).status, "PASS")

    def test_missing_cost_estimate_is_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cost.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(validator.InputError, "estimated_monthly_cost_usd"):
                validator.check_cost(path, Decimal("500"))

    def test_invalid_json_is_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaisesRegex(validator.InputError, "Invalid JSON"):
                validator.load_plan(path)

    def test_unsupported_plan_format_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text('{"format_version":"2.0","resource_changes":[]}', encoding="utf-8")
            with self.assertRaisesRegex(validator.InputError, "Unsupported Terraform plan JSON format_version"):
                validator.load_plan(path)

    def test_negative_cost_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cost.json"
            path.write_text('{"estimated_monthly_cost_usd": -1}', encoding="utf-8")
            with self.assertRaisesRegex(validator.InputError, "non-negative"):
                validator.check_cost(path, Decimal("500"))

    def test_empty_resource_changes_pass(self):
        plan = {"format_version": "1.2", "resource_changes": []}
        self.assertEqual(validator.check_tags(plan, ["Owner"]).status, "PASS")

    def test_nested_module_address_is_checked(self):
        nested = self.resource("module.network.module.app.aws_instance.web", "aws_instance", {"tags": {}})
        report = validator.check_tags(self.plan(nested), ["Owner"])
        self.assertTrue(any("module.network.module.app.aws_instance.web" in item for item in report.violations))

    def test_cli_exit_codes_for_pass_fail_and_invalid_input(self):
        base = [sys.executable, str(ROOT / "validator.py")]

        def invoke(plan, policy, cost):
            return subprocess.run(base + ["--plan", str(plan), "--policy", str(policy), "--cost", str(cost)], capture_output=True, text=True)

        passed = invoke(self.examples / "compliant-plan.json", self.policy, self.examples / "compliant-cost.json")
        failed = invoke(self.examples / "noncompliant-plan.json", self.policy, self.examples / "over-budget-cost.json")
        invalid = invoke(self.examples / "missing.json", self.policy, self.examples / "compliant-cost.json")
        self.assertEqual(passed.returncode, 0)
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(invalid.returncode, 2)

    @staticmethod
    def resource(address, kind, after, actions=None, unknown=None):
        return {
            "address": address,
            "type": kind,
            "change": {
                "actions": actions or ["create"],
                "after": after,
                "after_unknown": unknown or {},
            },
        }

    @staticmethod
    def plan(*resources):
        return {"format_version": "1.2", "resource_changes": list(resources)}


if __name__ == "__main__":
    unittest.main()
