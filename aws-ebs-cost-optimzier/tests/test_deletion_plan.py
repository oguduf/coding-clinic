from __future__ import annotations

from dataclasses import replace

from ebs_optimizer.deletion_plan import build_deletion_plan
from ebs_optimizer.filters import apply_age_filter, apply_cleanup_policy


def test_plan_marks_eligible_items_manual_review_only(volume, reference_time):
    aged = apply_age_filter([volume], 30, reference_time)
    priced = replace(
        aged[0], pricing_status="available", monthly_cost=__import__("decimal").Decimal("8.00")
    )
    reviewed = apply_cleanup_policy([priced], exclude_production=True, protected_tags={})
    plan = build_deletion_plan(reviewed)
    item = plan["entries"][0]
    assert plan["artifact_type"] == "non_executable_review_plan"
    assert item["proposed_action"] == "manual_review_only"
    assert item["manual_approval_required"] is True
    assert item["excluded"] is False


def test_plan_excludes_production_and_protected_tags(volume, reference_time):
    aged = apply_age_filter(
        [replace(volume, environment="prod", tags={"DoNotDelete": "true"})], 30, reference_time
    )
    priced = replace(
        aged[0], pricing_status="available", monthly_cost=__import__("decimal").Decimal("8.00")
    )
    reviewed = apply_cleanup_policy(
        [priced], exclude_production=True, protected_tags={"DoNotDelete": "true"}
    )
    item = build_deletion_plan(reviewed)["entries"][0]
    assert item["excluded"] is True
    assert item["proposed_action"] == "no_action_excluded"
    assert item["risk_classification"] == "excluded"
    assert "production" in item["exclusion_reason"]
    assert "protected tag" in item["exclusion_reason"]


def test_unencrypted_volume_gets_high_review_priority(volume, reference_time):
    aged = apply_age_filter([replace(volume, encrypted=False)], 30, reference_time)
    reviewed = apply_cleanup_policy(
        [replace(aged[0], pricing_status="available")],
        exclude_production=True,
        protected_tags={},
    )
    item = build_deletion_plan(reviewed)["entries"][0]
    assert item["risk_classification"] == "high review priority"
    assert item["manual_approval_required"] is True


def test_missing_metadata_and_price_are_excluded(volume, reference_time):
    aged = apply_age_filter([replace(volume, availability_zone="unknown")], 30, reference_time)
    item = build_deletion_plan(
        apply_cleanup_policy([aged[0]], exclude_production=True, protected_tags={})
    )["entries"][0]
    assert item["excluded"] is True
    assert "metadata" in item["exclusion_reason"]
    assert "pricing" in item["exclusion_reason"]


def test_application_contains_no_destructive_ec2_api(project_root):
    source = (project_root / "src/ebs_optimizer").rglob("*.py")
    assert all("delete_volume" not in path.read_text(encoding="utf-8") for path in source)
