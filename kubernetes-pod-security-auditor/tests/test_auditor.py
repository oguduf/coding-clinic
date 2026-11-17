import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import auditor


CONFIG = {
    "check_privileged": True,
    "check_hostpath": True,
    "check_resource_limits": True,
    "fail_on_violations": True,
}


def container(name="app", *, privileged=None, limits=None, env=None):
    result = {"name": name, "image": "example.invalid/app:1.0"}
    if privileged is not None:
        result["securityContext"] = {"privileged": privileged}
    if limits is not None:
        result["resources"] = {"limits": limits}
    if env is not None:
        result["env"] = env
    return result


def pod(
    name="demo-pod",
    namespace="demo",
    *,
    phase="Running",
    containers=None,
    init_containers=None,
    ephemeral_containers=None,
    volumes=None,
):
    spec = {"containers": containers if containers is not None else [container(limits={"cpu": "100m", "memory": "128Mi"})]}
    if init_containers is not None:
        spec["initContainers"] = init_containers
    if ephemeral_containers is not None:
        spec["ephemeralContainers"] = ephemeral_containers
    if volumes is not None:
        spec["volumes"] = volumes
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name, "namespace": namespace},
        "spec": spec,
        "status": {"phase": phase},
    }


def pod_list(*pods):
    return {"apiVersion": "v1", "kind": "PodList", "items": list(pods)}


class AuditorTests(unittest.TestCase):
    def test_compliant_running_pod(self):
        report = auditor.audit_pods([pod()], CONFIG)
        self.assertEqual(report["counts"]["running_pods_audited"], 1)
        self.assertEqual(report["counts"]["compliant_pods"], 1)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["overall_result"], "PASS")

    def test_privileged_container_is_reported(self):
        report = auditor.audit_pods(
            [pod(containers=[container(privileged=True, limits={"cpu": "1", "memory": "1Gi"})])],
            CONFIG,
        )
        self.assertEqual(report["violations"][0]["rule"], "privileged-container")

    def test_explicit_non_privileged_container_is_compliant(self):
        report = auditor.audit_pods(
            [pod(containers=[container(privileged=False, limits={"cpu": "1", "memory": "1Gi"})])],
            CONFIG,
        )
        self.assertEqual(report["violations"], [])

    def test_missing_privileged_field_is_not_assumed_privileged(self):
        report = auditor.audit_pods(
            [pod(containers=[container(limits={"cpu": "1", "memory": "1Gi"})])],
            CONFIG,
        )
        self.assertFalse(
            any(v["rule"] == "privileged-container" for v in report["violations"])
        )

    def test_hostpath_volume_is_reported_with_safe_path(self):
        report = auditor.audit_pods(
            [
                pod(
                    volumes=[
                        {"name": "host-data", "hostPath": {"path": "/var/lib/example"}}
                    ]
                )
            ],
            CONFIG,
        )
        violation = next(v for v in report["violations"] if v["rule"] == "hostpath-volume")
        self.assertEqual(violation["volume"], "host-data")
        self.assertEqual(violation["host_path"], "/var/lib/example")

    def test_normal_kubernetes_volumes_are_not_reported(self):
        normal_volumes = [
            {"name": "cfg", "configMap": {"name": "demo-config"}},
            {"name": "credentials", "secret": {"secretName": "synthetic-secret"}},
            {"name": "scratch", "emptyDir": {}},
        ]
        report = auditor.audit_pods([pod(volumes=normal_volumes)], CONFIG)
        self.assertEqual(report["violations"], [])

    def test_missing_cpu_limit_is_reported(self):
        report = auditor.audit_pods(
            [pod(containers=[container(limits={"memory": "128Mi"})])], CONFIG
        )
        self.assertEqual(
            [v["rule"] for v in report["violations"]], ["missing-cpu-limit"]
        )

    def test_missing_memory_limit_is_reported(self):
        report = auditor.audit_pods(
            [pod(containers=[container(limits={"cpu": "100m"})])], CONFIG
        )
        self.assertEqual(
            [v["rule"] for v in report["violations"]], ["missing-memory-limit"]
        )

    def test_both_resource_limits_are_present(self):
        report = auditor.audit_pods(
            [pod(containers=[container(limits={"cpu": "100m", "memory": "128Mi"})])],
            CONFIG,
        )
        self.assertEqual(report["violations"], [])

    def test_init_container_security_and_limits_are_checked(self):
        report = auditor.audit_pods(
            [
                pod(
                    containers=[container(limits={"cpu": "1", "memory": "1Gi"})],
                    init_containers=[container("setup", privileged=True, limits={})],
                )
            ],
            CONFIG,
        )
        self.assertEqual(
            {v["rule"] for v in report["violations"]},
            {
                "privileged-container",
                "missing-cpu-limit",
                "missing-memory-limit",
            },
        )
        self.assertTrue(all(v["container"] == "setup" for v in report["violations"]))

    def test_ephemeral_container_privileged_check_skips_resource_limits(self):
        report = auditor.audit_pods(
            [
                pod(
                    ephemeral_containers=[
                        container("debug", privileged=True, limits={})
                    ]
                )
            ],
            CONFIG,
        )
        self.assertEqual(
            [v["rule"] for v in report["violations"]], ["privileged-container"]
        )
        self.assertIn("ephemeral", report["violations"][0]["description"])

    def test_pending_pod_is_skipped(self):
        report = auditor.audit_pods([pod(phase="Pending")], CONFIG)
        self.assertEqual(report["counts"]["skipped_pods"], 1)
        self.assertEqual(report["counts"]["running_pods_audited"], 0)

    def test_succeeded_pod_is_skipped(self):
        report = auditor.audit_pods([pod(phase="Succeeded")], CONFIG)
        self.assertEqual(report["counts"]["skipped_pods"], 1)
        self.assertEqual(report["counts"]["compliant_pods"], 0)

    def test_multiple_namespaces_are_kept_in_findings(self):
        report = auditor.audit_pods(
            [
                pod("api", "production", containers=[container(privileged=True, limits={"cpu": "1", "memory": "1Gi"})]),
                pod("web", "staging", containers=[container(limits={"memory": "1Gi"})]),
            ],
            CONFIG,
        )
        self.assertEqual(
            {(v["namespace"], v["pod"]) for v in report["violations"]},
            {("production", "api"), ("staging", "web")},
        )

    def test_multiple_violations_in_one_pod_are_counted(self):
        report = auditor.audit_pods(
            [
                pod(
                    containers=[container(privileged=True, limits={"memory": "128Mi"})],
                    volumes=[{"name": "host", "hostPath": {"path": "/etc"}}],
                )
            ],
            CONFIG,
        )
        self.assertEqual(report["counts"]["noncompliant_pods"], 1)
        self.assertEqual(report["counts"]["violations"], 3)
        self.assertEqual(len(report["violations"]), 3)

    def test_invalid_json_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "pods.json"
            source.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(auditor.AuditError, "not valid JSON"):
                auditor.load_pods_file(source)

    def test_missing_required_pod_fields_are_rejected(self):
        malformed = {"metadata": {"name": "pod", "namespace": "demo"}, "spec": {}}
        with self.assertRaisesRegex(auditor.AuditError, "status.phase"):
            auditor.validate_pod_list(pod_list(malformed))

    def test_configuration_must_have_boolean_values_and_known_keys(self):
        invalid = {**CONFIG, "check_hostpath": "true"}
        with self.assertRaisesRegex(auditor.AuditError, "true or false"):
            auditor.validate_config(invalid)
        with self.assertRaisesRegex(auditor.AuditError, "unknown keys"):
            auditor.validate_config({**CONFIG, "unexpected": True})

    def test_exit_codes_reflect_fail_on_violations_setting(self):
        report = auditor.audit_pods(
            [pod(containers=[container(privileged=True, limits={"cpu": "1", "memory": "1Gi"})])],
            CONFIG,
        )
        self.assertEqual(auditor.audit_exit_code(report, CONFIG), 1)
        nonblocking = {**CONFIG, "fail_on_violations": False}
        self.assertEqual(auditor.audit_exit_code(report, nonblocking), 0)
        self.assertEqual(report["overall_result"], "FAIL")

    def test_json_report_is_written_and_environment_values_are_omitted(self):
        sensitive_value = "SYNTHETIC-NEVER-REPORT-THIS"
        sample = pod(
            containers=[
                container(
                    privileged=True,
                    limits={"cpu": "1", "memory": "1Gi"},
                    env=[{"name": "API_TOKEN", "value": sensitive_value}],
                )
            ]
        )
        report = auditor.audit_pods([sample], CONFIG)
        rendered = json.dumps(report)
        self.assertNotIn(sensitive_value, rendered)
        self.assertNotIn("API_TOKEN", rendered)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            output.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(json.loads(output.read_text())["counts"]["violations"], 1)

    def test_configuration_flags_disable_selected_checks(self):
        disabled = {
            **CONFIG,
            "check_privileged": False,
            "check_hostpath": False,
            "check_resource_limits": False,
        }
        sample = pod(
            containers=[container(privileged=True, limits={})],
            volumes=[{"name": "host", "hostPath": {"path": "/etc"}}],
        )
        report = auditor.audit_pods([sample], disabled)
        self.assertEqual(report["violations"], [])
        self.assertEqual(auditor.audit_exit_code(report, disabled), 0)

    def test_mocked_kubectl_uses_read_only_argument_list(self):
        payload = json.dumps(pod_list(pod()))
        completed = subprocess.CompletedProcess(
            args=["kubectl"], returncode=0, stdout=payload, stderr=""
        )
        with patch("auditor.subprocess.run", return_value=completed) as run:
            pods = auditor.load_live_pods()

        self.assertEqual(len(pods), 1)
        args, kwargs = run.call_args
        self.assertEqual(
            args[0], ["kubectl", "get", "pods", "--all-namespaces", "-o", "json"]
        )
        self.assertFalse(kwargs["shell"])

    def test_missing_offline_file_does_not_fall_back_to_live(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.json"
            with patch("auditor.subprocess.run") as run:
                with self.assertRaises(auditor.AuditError):
                    auditor.load_pods_file(missing)
            run.assert_not_called()

    def test_main_returns_one_for_blocking_fixture(self):
        config_path = Path(__file__).parents[1] / "config.json"
        fixture = Path(__file__).parents[1] / "examples" / "noncompliant-pods.json"
        with contextlib.redirect_stdout(io.StringIO()):
            result = auditor.main(
                ["--input", str(fixture), "--config", str(config_path)]
            )
        self.assertEqual(result, 1)

    def test_main_returns_zero_for_compliant_fixture(self):
        config_path = Path(__file__).parents[1] / "config.json"
        fixture = Path(__file__).parents[1] / "examples" / "compliant-pods.json"
        with contextlib.redirect_stdout(io.StringIO()):
            result = auditor.main(
                ["--input", str(fixture), "--config", str(config_path)]
            )
        self.assertEqual(result, 0)

    def test_main_writes_json_report_when_requested(self):
        config_path = Path(__file__).parents[1] / "config.json"
        fixture = Path(__file__).parents[1] / "examples" / "compliant-pods.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                result = auditor.main(
                    [
                        "--input",
                        str(fixture),
                        "--config",
                        str(config_path),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.read_text())["overall_result"], "PASS")


if __name__ == "__main__":
    unittest.main()

