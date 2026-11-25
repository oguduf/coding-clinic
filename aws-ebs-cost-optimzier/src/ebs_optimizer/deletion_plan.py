"""Create an informational review artifact; there is intentionally no delete API."""

from __future__ import annotations

from typing import Any

from .models import Volume


def build_deletion_plan(volumes: list[Volume]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for volume in sorted(volumes, key=lambda v: (v.account_id, v.region, v.volume_id)):
        excluded = not volume.eligible_for_review
        if excluded:
            risk = "excluded"
        elif not volume.encrypted:
            risk = "high review priority"
        elif volume.tags:
            risk = "low review priority"
        else:
            risk = "medium review priority"
        entries.append(
            {
                "account_id": volume.account_id,
                "account_name": volume.account_name,
                "region": volume.region,
                "volume_id": volume.volume_id,
                "volume_type": volume.volume_type,
                "size_gib": volume.size_gib,
                "age_days": volume.age_days,
                "monthly_cost_usd": str(volume.monthly_cost)
                if volume.monthly_cost is not None
                else None,
                "tags": dict(sorted(volume.tags.items())),
                "excluded": excluded,
                "exclusion_reason": volume.exclusion_reason,
                "proposed_action": "manual_review_only" if not excluded else "no_action_excluded",
                "risk_classification": risk,
                "manual_approval_required": True,
            }
        )
    return {"artifact_type": "non_executable_review_plan", "entries": entries}
