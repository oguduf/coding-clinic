"""Configuration loading and validation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_FORMATS = {"csv", "json", "markdown"}
SUPPORTED_VOLUME_TYPES = {"gp2", "gp3", "io1", "io2", "st1", "sc1", "standard"}
REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-[a-z0-9]+)+-[0-9]+$")


class ConfigurationError(ValueError):
    """Invalid application configuration or input fixture."""


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot load YAML configuration {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration must be a YAML mapping: {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot load JSON file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Expected a JSON object: {path}")
    return data


def validate_config(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("application", "aws", "discovery", "reporting", "deletion_plan"):
        if key in data and not isinstance(data[key], dict):
            raise ConfigurationError(f"{key} must be a YAML mapping")
    discovery = data.get("discovery", {})
    age = discovery.get("minimum_age_days", 30)
    if isinstance(age, bool) or not isinstance(age, int) or age < 0:
        raise ConfigurationError("discovery.minimum_age_days must be a non-negative integer")

    regions = data.get("aws", {}).get("regions", [])
    if not isinstance(regions, list) or any(
        not isinstance(r, str) or not r.strip() for r in regions
    ):
        raise ConfigurationError("aws.regions must be a list of non-empty region names")
    if any(not REGION_PATTERN.fullmatch(region) for region in regions):
        raise ConfigurationError("aws.regions contains a malformed region identifier")
    role_name = data.get("aws", {}).get("role_name", "EBSInventoryReadOnlyRole")
    if not isinstance(role_name, str) or not role_name.strip() or "/" in role_name:
        raise ConfigurationError("aws.role_name must be a non-empty IAM role name without a path")
    for account_key in ("included_accounts", "excluded_accounts"):
        account_values = data.get("aws", {}).get(account_key, [])
        if not isinstance(account_values, list) or any(
            not isinstance(item, str) or not item.isdigit() or len(item) != 12
            for item in account_values
        ):
            raise ConfigurationError(f"aws.{account_key} must contain 12-digit account IDs")

    states = discovery.get("volume_states", ["available"])
    if states != ["available"]:
        raise ConfigurationError("Only the safe unattached state ['available'] is supported")

    formats = data.get("reporting", {}).get("formats", ["csv", "json", "markdown"])
    if (
        not isinstance(formats, list)
        or not formats
        or any(not isinstance(item, str) for item in formats)
    ):
        raise ConfigurationError("reporting.formats must be a non-empty list")
    invalid = set(formats) - SUPPORTED_FORMATS
    if invalid:
        raise ConfigurationError(f"Unsupported report format(s): {', '.join(sorted(invalid))}")
    if not isinstance(data.get("reporting", {}).get("output_directory", "reports"), str):
        raise ConfigurationError("reporting.output_directory must be a string path")

    protected = data.get("deletion_plan", {}).get("protected_tags", {})
    if not isinstance(protected, dict) or any(not isinstance(k, str) for k in protected):
        raise ConfigurationError("deletion_plan.protected_tags must be a string-keyed mapping")
    if any(not isinstance(value, str) for value in protected.values()):
        raise ConfigurationError("deletion_plan.protected_tags values must be strings")
    deletion = data.get("deletion_plan", {})
    if deletion.get("require_manual_approval", True) is not True:
        raise ConfigurationError("Deletion review plans must always require manual approval")
    for key in ("enabled", "exclude_production"):
        if key in deletion and not isinstance(deletion[key], bool):
            raise ConfigurationError(f"deletion_plan.{key} must be a boolean")
    log_level = data.get("application", {}).get("log_level", "INFO")
    if not isinstance(log_level, str) or log_level.upper() not in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }:
        raise ConfigurationError("application.log_level must be a standard logging level")
    return data


def load_config(path: Path) -> dict[str, Any]:
    return validate_config(load_yaml(path))
