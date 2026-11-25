from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ebs_optimizer.models import Account, Volume

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = datetime(2026, 1, 31, 12, tzinfo=UTC)


@pytest.fixture
def account() -> Account:
    return Account("000000000101", "dev-account", "ACTIVE", "dev")


@pytest.fixture
def volume(account: Account) -> Volume:
    return Volume.from_aws(
        {
            "VolumeId": "vol-synthetic001",
            "VolumeType": "gp3",
            "Size": 100,
            "CreateTime": "2025-12-17T12:00:00Z",
            "State": "available",
            "AvailabilityZone": "us-east-1a",
            "Encrypted": True,
            "Iops": 6000,
            "Throughput": 250,
            "Tags": [{"Key": "Environment", "Value": "dev"}],
        },
        account,
        "us-east-1",
    )


@pytest.fixture
def pricing() -> dict:
    return json.loads((ROOT / "config/pricing.example.json").read_text(encoding="utf-8"))


@pytest.fixture
def reference_time() -> datetime:
    return REFERENCE


@pytest.fixture
def project_root() -> Path:
    return ROOT
