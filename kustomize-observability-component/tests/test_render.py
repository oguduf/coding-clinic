import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render(path):
    if shutil.which("kustomize"):
        command = ["kustomize", "build", str(path)]
    elif shutil.which("kubectl"):
        command = ["kubectl", "kustomize", str(path)]
    else:
        raise unittest.SkipTest("kustomize or kubectl is required for rendering")
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


class RenderTests(unittest.TestCase):
    def test_both_examples_render_and_include_component_contract(self):
        for app in ("app-one", "app-two"):
            with self.subTest(app=app):
                output = render(ROOT / "examples" / app)
                self.assertIn("kind: Deployment", output)
                self.assertIn("name: metrics-exporter", output)
                self.assertIn("prom/statsd-exporter:v0.31.0", output)
                self.assertIn("name: fluent-bit", output)
                self.assertIn("fluent-bit:5.1.5", output)
                self.assertIn("prometheus.io/scrape: \"true\"", output)
                self.assertIn("prometheus.io/port: \"9102\"", output)
                self.assertIn("prometheus.io/path: /metrics", output)
                self.assertIn("name: fluent-bit-config", output)
                self.assertIn("name: app-logs", output)
                self.assertIn("/var/log/app", output)
                self.assertIn("runAsNonRoot: true", output)
                self.assertIn("allowPrivilegeEscalation: false", output)
                self.assertIn("type: RuntimeDefault", output)
                self.assertRegex(output, r"drop:\s*\n\s+- ALL")
                self.assertIn("requests:", output)
                self.assertIn("limits:", output)
                self.assertNotIn("hostPath:", output)
                self.assertNotRegex(output, r"(?i)(password|secretAccessKey|api[_-]?key):")
                names = re.findall(r"^\s{8}- name: ([\w.-]+)$", output, re.MULTILINE)
                self.assertEqual(len(names), len(set(names)), f"duplicate container name: {names}")

    def test_component_does_not_target_app_specific_deployment_name(self):
        component = (ROOT / "components/observability/kustomization.yaml").read_text()
        self.assertIn("labelSelector: observability.example.com/enabled=true", component)
        self.assertNotIn("name:", component)


if __name__ == "__main__":
    unittest.main()


