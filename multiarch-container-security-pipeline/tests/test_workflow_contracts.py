from pathlib import Path
import re
import yaml

ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_ci_is_read_only_and_has_no_oidc():
    workflow = load("ci-validation.yml")
    assert workflow["permissions"] == {"contents": "read"}
    assert "id-token" not in str(workflow)


def test_publication_requires_protected_push_and_environment():
    workflow = load("publish-image.yml")
    job = workflow["jobs"]["authorize"]
    assert "vars.PUBLISHING_ENABLED == 'true'" in job["if"]
    assert "github.ref_protected" in job["if"]
    assert "github.event_name == 'push'" in job["if"]
    assert workflow["jobs"]["publish"]["permissions"]["id-token"] == "write"
    reusable = load("reusable-container-build.yml")
    assert "evaluate-trivy.sh" in str(reusable)
    assert "needs.scan.result == 'success'" in reusable["jobs"]["publish"]["if"]
    assert reusable["jobs"]["publish"]["environment"] == "production-publish"


def test_candidate_scan_never_has_cloud_permissions_or_publication():
    candidate = load("container-security.yml")
    assert candidate["permissions"] == {"contents": "read"}
    assert "id-token" not in str(candidate)
    assert "push: false" in str(candidate)
    assert "trivy-amd64.json" in str(candidate)
    assert "trivy-arm64.json" in str(candidate)


def test_actions_are_full_sha_pinned():
    for path in WORKFLOWS.glob("*.yml"):
        for ref in re.findall(r"uses:\s*([^\s]+)", path.read_text()):
            if not ref.startswith("./"):
                assert re.search(r"@[0-9a-f]{40}$", ref), f"{path.name}: unpinned action {ref}"


def test_validation_workflow_does_not_run_external_scans_or_publish():
    text = (WORKFLOWS / "ci-validation.yml").read_text()
    assert "docker/build-push-action" not in text
    assert "id-token: write" not in text
    assert "aws-actions/" not in text
    assert "azure/login" not in text
    assert "google-github-actions/auth" not in text
