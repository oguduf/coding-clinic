from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from ebs_optimizer.pricing import (
    PricingUnavailable,
    add_pricing,
    estimate_monthly_cost,
    validate_pricing,
)


@pytest.mark.parametrize("volume_type", ["gp2", "gp3", "io1", "io2", "st1", "sc1", "standard"])
def test_supported_types_have_estimates(volume, pricing, volume_type):
    item = replace(volume, volume_type=volume_type, iops=1000, throughput_mibps=200)
    cost, source, effective = estimate_monthly_cost(item, pricing)
    assert cost >= Decimal("0.00")
    assert "synthetic" in source.lower()
    assert effective == "2026-01-01"


def test_gp3_included_allowances_and_additional_performance(volume, pricing):
    cost, _, _ = estimate_monthly_cost(volume, pricing)
    assert cost == Decimal("28.00")
    baseline = replace(volume, iops=3000, throughput_mibps=125)
    assert estimate_monthly_cost(baseline, pricing)[0] == Decimal("8.00")


def test_io1_and_io2_provisioned_iops_charges(volume, pricing):
    io1 = replace(volume, volume_type="io1", size_gib=4, iops=1000, throughput_mibps=None)
    io2 = replace(volume, volume_type="io2", size_gib=500, iops=40000, throughput_mibps=None)
    assert estimate_monthly_cost(io1, pricing)[0] == Decimal("65.50")
    assert estimate_monthly_cost(io2, pricing)[0] == Decimal("2510.50")


def test_missing_region_or_type_is_explicit(volume, pricing):
    with pytest.raises(PricingUnavailable):
        estimate_monthly_cost(replace(volume, region="ap-south-1"), pricing)
    with pytest.raises(PricingUnavailable):
        estimate_monthly_cost(replace(volume, volume_type="gp9"), pricing)


def test_decimal_rounding_is_deterministic(volume, pricing):
    custom = {
        "source": "test",
        "effective_date": "2026-01-01",
        "regions": {"us-east-1": {"volume_types": {"gp2": {"storage_per_gib_month": "0.005"}}}},
    }
    assert estimate_monthly_cost(
        replace(volume, volume_type="gp2", size_gib=1, iops=None, throughput_mibps=None), custom
    )[0] == Decimal("0.01")


def test_add_pricing_marks_missing_and_does_not_use_zero(volume, pricing):
    result = add_pricing([volume, replace(volume, region="ap-south-1")], pricing)
    assert result[0].pricing_status == "available"
    assert result[1].pricing_status == "unavailable"
    assert result[1].monthly_cost is None


def test_missing_billable_performance_metadata_is_unavailable(volume, pricing):
    with pytest.raises(PricingUnavailable, match="IOPS metadata"):
        estimate_monthly_cost(replace(volume, iops=None), pricing)
    with pytest.raises(PricingUnavailable, match="throughput metadata"):
        estimate_monthly_cost(replace(volume, throughput_mibps=None), pricing)


def test_pricing_fixture_validation(pricing):
    assert validate_pricing(pricing) is pricing
    with pytest.raises(ValueError, match="effective_date"):
        validate_pricing({"source": "fixture", "regions": {}})


@pytest.mark.parametrize("kwargs", [{"size_gib": 0}, {"iops": -1}, {"throughput_mibps": -1}])
def test_negative_volume_performance_rejected(volume, pricing, kwargs):
    with pytest.raises(ValueError):
        estimate_monthly_cost(replace(volume, **kwargs), pricing)
