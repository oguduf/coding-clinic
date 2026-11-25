"""Deterministic cost estimation using version-controlled illustrative fixtures."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .config import SUPPORTED_VOLUME_TYPES
from .models import Volume


class PricingUnavailable(LookupError):
    """No fixture price exists for a region or volume type."""


def validate_pricing(pricing: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(pricing.get("source"), str) or not pricing["source"]:
        raise ValueError("Pricing fixture must declare a source")
    if not isinstance(pricing.get("effective_date"), str) or not pricing["effective_date"]:
        raise ValueError("Pricing fixture must declare an effective_date")
    try:
        date.fromisoformat(pricing["effective_date"])
    except ValueError as exc:
        raise ValueError("Pricing effective_date must use YYYY-MM-DD") from exc
    if pricing.get("currency") != "USD":
        raise ValueError("This sample cost estimator supports USD only")
    regions = pricing.get("regions")
    if not isinstance(regions, dict) or not regions:
        raise ValueError("Pricing fixture must contain regional prices")
    try:
        for region, region_data in regions.items():
            if not isinstance(region_data, dict) or not isinstance(
                region_data.get("volume_types"), dict
            ):
                raise ValueError(f"Invalid volume_types map for region {region}")
            for volume_type, spec in region_data["volume_types"].items():
                if volume_type not in SUPPORTED_VOLUME_TYPES or not isinstance(spec, dict):
                    raise ValueError(f"Unsupported or malformed volume type: {volume_type}")
                if (
                    volume_type == "gp3"
                    and not {
                        "included_iops",
                        "iops_per_month",
                        "included_throughput_mibps",
                        "throughput_per_mibps_month",
                    }
                    <= spec.keys()
                ):
                    raise ValueError(f"gp3 performance pricing is incomplete: {region}")
                if volume_type == "io1" and "iops_per_month" not in spec:
                    raise ValueError(f"io1 IOPS pricing is incomplete: {region}")
                if volume_type == "io2" and not spec.get("iops_tiers"):
                    raise ValueError(f"io2 IOPS pricing tiers are missing: {region}")
                values = [_d(spec["storage_per_gib_month"])]
                if spec.get("iops_per_month") is not None:
                    values.append(_d(spec["iops_per_month"]))
                if spec.get("throughput_per_mibps_month") is not None:
                    values.append(_d(spec["throughput_per_mibps_month"]))
                for tier in spec.get("iops_tiers", []):
                    values.append(_d(tier["price_per_iops_month"]))
                    upper = tier.get("up_to")
                    if upper is not None and (not isinstance(upper, int) or upper < 1):
                        raise ValueError(f"Invalid IOPS pricing tier: {region}/{volume_type}")
                for allowance in ("included_iops", "included_throughput_mibps"):
                    if allowance in spec and (
                        not isinstance(spec[allowance], int) or spec[allowance] < 0
                    ):
                        raise ValueError(f"Invalid performance allowance: {region}/{volume_type}")
                if any(not value.is_finite() or value < 0 for value in values):
                    raise ValueError(
                        f"Prices must be finite and non-negative: {region}/{volume_type}"
                    )
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError(f"Malformed regional pricing fixture: {exc}") from exc
    return pricing


def _d(value: Any) -> Decimal:
    return Decimal(str(value))


def estimate_monthly_cost(volume: Volume, pricing: dict[str, Any]) -> tuple[Decimal, str, str]:
    """Return storage plus explicitly billable performance monthly run-rate."""
    if volume.size_gib < 1 or (volume.iops is not None and volume.iops < 0):
        raise ValueError("Volume size must be positive and provisioned IOPS cannot be negative")
    if volume.throughput_mibps is not None and volume.throughput_mibps < 0:
        raise ValueError("Provisioned throughput cannot be negative")
    if volume.volume_type in {"gp3", "io1", "io2"} and volume.iops is None:
        raise PricingUnavailable(f"Provisioned IOPS metadata is missing for {volume.volume_id}")
    if volume.volume_type == "gp3" and volume.throughput_mibps is None:
        raise PricingUnavailable(
            f"Provisioned throughput metadata is missing for {volume.volume_id}"
        )
    region_data = pricing.get("regions", {}).get(volume.region)
    if not region_data or volume.volume_type not in region_data.get("volume_types", {}):
        raise PricingUnavailable(f"No sample price for {volume.region}/{volume.volume_type}")
    try:
        spec = region_data["volume_types"][volume.volume_type]
        cost = _d(spec["storage_per_gib_month"]) * volume.size_gib
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise PricingUnavailable(
            f"Incomplete price for {volume.region}/{volume.volume_type}"
        ) from exc
    iops = volume.iops or 0
    if spec.get("iops_per_month") is not None:
        included = int(spec.get("included_iops", 0))
        cost += _d(spec["iops_per_month"]) * max(0, iops - included)
    elif spec.get("iops_tiers"):
        remaining = max(0, iops - int(spec.get("included_iops", 0)))
        for tier in spec["iops_tiers"]:
            upper = tier.get("up_to")
            capacity = remaining if upper is None else min(remaining, int(upper))
            cost += _d(tier["price_per_iops_month"]) * capacity
            remaining -= capacity
            if remaining <= 0:
                break
        if remaining > 0:
            raise PricingUnavailable("IOPS exceed configured fixture pricing tiers")
    if spec.get("throughput_per_mibps_month") is not None:
        included = int(spec.get("included_throughput_mibps", 0))
        throughput = volume.throughput_mibps or 0
        cost += _d(spec["throughput_per_mibps_month"]) * max(0, throughput - included)
    rounded = cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return rounded, str(pricing["source"]), str(pricing["effective_date"])


def add_pricing(volumes: list[Volume], pricing: dict[str, Any]) -> list[Volume]:
    enriched: list[Volume] = []
    for volume in volumes:
        try:
            cost, source, effective = estimate_monthly_cost(volume, pricing)
            enriched.append(
                replace(
                    volume,
                    pricing_status="available",
                    monthly_cost=cost,
                    pricing_source=source,
                    pricing_effective_date=effective,
                )
            )
        except PricingUnavailable:
            enriched.append(replace(volume, pricing_status="unavailable"))
    return enriched
