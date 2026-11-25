"""Load and validate non-secret YAML configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ACCOUNT = re.compile(r"^\d{12}$")
ROLE = re.compile(r"^[A-Za-z0-9+=,.@_-]{1,64}$")


class ConfigError(ValueError):
    """Configuration is invalid or incomplete."""


def load_config(path: str | Path) -> dict[str, Any]:
    """Read YAML without resolving or logging any secret values."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Unable to load configuration: {exc.__class__.__name__}") from exc
    if not isinstance(data, dict):
        raise ConfigError("Configuration root must be a mapping")
    validate_config(data)
    return data


def validate_config(data: dict[str, Any]) -> None:
    """Raise ConfigError if required structural values are invalid."""
    try:
        app = data["application"]
        aws = data["aws"]
        cross = data["cross_account"]
        security = data["security"]
        env = app["environment"]
        source = cross["source_account_id"]
        target = cross["target_account_id"]
        role = cross["target_role_name"]
        region = aws["region"]
        duration = cross["session_duration"]
        env_var = cross["external_id_env_var"]
    except (KeyError, TypeError) as exc:
        raise ConfigError("Missing required configuration field") from exc
    if env not in {"dev", "stage", "prod"}:
        raise ConfigError("environment must be dev, stage, or prod")
    if not ACCOUNT.fullmatch(str(source)) or not ACCOUNT.fullmatch(str(target)):
        raise ConfigError("source and target account IDs must contain 12 digits")
    if not ROLE.fullmatch(str(role)):
        raise ConfigError("target_role_name contains unsupported characters")
    if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", str(region)):
        raise ConfigError("aws.region must be a valid region-shaped value")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 900 <= duration <= 43200:
        raise ConfigError("session_duration must be an integer from 900 through 43200")
    if not isinstance(env_var, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]+", env_var):
        raise ConfigError("external_id_env_var must be an environment variable name")
    if security.get("require_external_id") is not True:
        raise ConfigError("require_external_id must be true")
    if security.get("allow_wildcard_principal") is not False:
        raise ConfigError("wildcard principals must be disabled")
    if security.get("allow_administrator_access") is not False:
        raise ConfigError("administrator access must be disabled")
