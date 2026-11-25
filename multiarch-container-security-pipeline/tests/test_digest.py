import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
VALID = "sha256:" + "a" * 64


def call(script, *args):
    return subprocess.run(["bash", str(ROOT / "scripts" / script), *args], capture_output=True, text=True)


def test_digest_validation():
    assert call("validate-digest.sh", VALID).returncode == 0
    assert call("validate-digest.sh").returncode == 2
    assert call("validate-digest.sh", "sha256:bad").returncode == 2


def test_immutable_reference_is_digest_addressed():
    result = call("immutable-ref.sh", "registry.example.invalid/team/app", VALID)
    assert result.returncode == 0
    assert result.stdout.strip() == f"registry.example.invalid/team/app@{VALID}"


def test_immutable_reference_rejects_mutable_tags_and_bad_repository():
    assert call("immutable-ref.sh", "bad image", VALID).returncode == 2
    assert call("immutable-ref.sh", "registry.example.invalid/team/app", "latest").returncode == 2
