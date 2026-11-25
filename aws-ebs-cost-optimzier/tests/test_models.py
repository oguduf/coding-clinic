from __future__ import annotations

from datetime import UTC

import pytest

from ebs_optimizer.models import Volume, parse_utc


def test_aws_volume_mapping_captures_required_metadata(account):
    volume = Volume.from_aws(
        {
            "VolumeId": "vol-synthetic001",
            "VolumeType": "io2",
            "Size": 64,
            "CreateTime": "2025-06-01T00:00:00-04:00",
            "State": "available",
            "AvailabilityZone": "us-east-1a",
            "Encrypted": True,
            "KmsKeyId": "alias/lab",
            "Iops": 5000,
            "Tags": [{"Key": "Owner", "Value": "platform"}],
        },
        account,
        "us-east-1",
    )
    assert volume.create_time.tzinfo == UTC
    assert volume.kms_key_id == "alias/lab"
    assert volume.iops == 5000
    assert volume.tags == {"Owner": "platform"}
    assert volume.to_dict()["monthly_cost"] is None


@pytest.mark.parametrize("raw", [{}, {"VolumeId": "vol-x", "VolumeType": "gp3"}])
def test_malformed_aws_volume_response_rejected(account, raw):
    with pytest.raises(ValueError, match="Malformed EBS volume"):
        Volume.from_aws(raw, account, "us-east-1")


def test_timestamp_with_timezone_converted_to_utc():
    assert parse_utc("2026-01-01T07:00:00+07:00").isoformat() == "2026-01-01T00:00:00+00:00"
