"""Volume-age and cleanup review policy."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from .models import Volume, parse_utc


def apply_age_filter(
    volumes: list[Volume], minimum_age_days: int, reference_time: datetime
) -> list[Volume]:
    if (
        isinstance(minimum_age_days, bool)
        or not isinstance(minimum_age_days, int)
        or minimum_age_days < 0
    ):
        raise ValueError("minimum_age_days must be a non-negative integer")
    now = parse_utc(reference_time)
    cutoff = now - timedelta(days=minimum_age_days)
    result: list[Volume] = []
    for volume in volumes:
        created = parse_utc(volume.create_time)
        age_days = max(0, (now - created).days)
        eligible = created <= cutoff and volume.state == "available"
        result.append(
            replace(
                volume,
                create_time=created,
                age_days=age_days,
                meets_age_threshold=eligible,
                eligible_for_review=eligible,
            )
        )
    return result


def apply_cleanup_policy(
    volumes: list[Volume],
    *,
    exclude_production: bool,
    protected_tags: dict[str, str],
) -> list[Volume]:
    result: list[Volume] = []
    for volume in volumes:
        reasons: list[str] = []
        if not volume.eligible_for_review:
            reasons.append("below age threshold or not currently unattached")
        environment = volume.environment.lower()
        tag_environment = volume.tags.get("Environment", "").lower()
        if exclude_production and {environment, tag_environment} & {"prod", "production"}:
            reasons.append("production environment is excluded by policy")
        for key, expected in protected_tags.items():
            if volume.tags.get(key, "").lower() == str(expected).lower():
                reasons.append(f"protected tag {key}={expected}")
        if volume.pricing_status != "available":
            reasons.append("pricing is unavailable")
        if (
            not volume.volume_id
            or volume.size_gib <= 0
            or not volume.region
            or volume.availability_zone == "unknown"
        ):
            reasons.append("required volume metadata is missing")
        result.append(
            replace(
                volume,
                eligible_for_review=not reasons,
                exclusion_reason="; ".join(reasons) if reasons else None,
            )
        )
    return result
