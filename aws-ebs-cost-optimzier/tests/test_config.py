from __future__ import annotations

import pytest

from ebs_optimizer.config import ConfigurationError, load_config, validate_config


def test_example_configuration_loads(project_root):
    config = load_config(project_root / "config/config.example.yaml")
    assert config["discovery"]["minimum_age_days"] == 30
    assert config["reporting"]["formats"] == ["csv", "json", "markdown"]


@pytest.mark.parametrize("age", [-1, True, "30", 1.5])
def test_invalid_age_configuration_rejected(age):
    with pytest.raises(ConfigurationError, match="minimum_age_days"):
        validate_config({"discovery": {"minimum_age_days": age}})


def test_invalid_report_format_rejected():
    with pytest.raises(ConfigurationError, match="Unsupported"):
        validate_config({"reporting": {"formats": ["html"]}})


def test_invalid_account_filter_rejected():
    with pytest.raises(ConfigurationError, match="12-digit"):
        validate_config({"aws": {"included_accounts": ["123"]}})


def test_malformed_mapping_and_non_safe_state_rejected():
    with pytest.raises(ConfigurationError, match="must be a YAML mapping"):
        validate_config({"aws": ["us-east-1"]})
    with pytest.raises(ConfigurationError, match="Only the safe"):
        validate_config({"discovery": {"volume_states": ["in-use"]}})


def test_empty_region_list_enables_future_discovery():
    assert validate_config({"aws": {"regions": []}})["aws"]["regions"] == []


def test_malformed_region_and_manual_approval_disabled_rejected():
    with pytest.raises(ConfigurationError, match="malformed region"):
        validate_config({"aws": {"regions": ["not-a-region"]}})
    with pytest.raises(ConfigurationError, match="manual approval"):
        validate_config({"deletion_plan": {"require_manual_approval": False}})
