from pathlib import Path
import yaml

ROOT = Path(__file__).parents[1]


def test_configuration_has_safe_defaults():
    data = yaml.safe_load((ROOT / "config/pipeline.example.yaml").read_text())
    assert data["image"]["platforms"] == ["linux/amd64", "linux/arm64"]
    assert data["publishing"]["enabled"] is False
    assert data["security"]["severity"] == ["HIGH", "CRITICAL"]
