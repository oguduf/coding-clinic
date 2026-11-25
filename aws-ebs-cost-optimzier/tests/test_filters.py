from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from ebs_optimizer.filters import apply_age_filter, apply_cleanup_policy
from ebs_optimizer.models import parse_utc


def test_volume_exactly_threshold_days_is_included(volume, reference_time):
    exact = replace(volume, create_time=reference_time - timedelta(days=30))
    result = apply_age_filter([exact], 30, reference_time)[0]
    assert result.age_days == 30
    assert result.eligible_for_review is True


def test_younger_volume_is_not_candidate(volume, reference_time):
    young = replace(volume, create_time=reference_time - timedelta(days=29, hours=23))
    result = apply_age_filter([young], 30, reference_time)[0]
    assert result.age_days == 29
    assert result.eligible_for_review is False


def test_older_volume_and_timezone_are_handled(volume, reference_time):
    older = replace(volume, create_time=parse_utc("2025-11-02T07:00:00-05:00"))
    result = apply_age_filter([older], 30, reference_time)[0]
    assert result.age_days == 90
    assert result.create_time.tzinfo is not None


@pytest.mark.parametrize("stamp", ["not-time", "2025-01-01T00:00:00"])
def test_invalid_or_naive_timestamps_are_rejected(stamp):
    with pytest.raises(ValueError):
        parse_utc(stamp)


def test_production_and_protected_tags_are_excluded(volume, reference_time):
    old = apply_age_filter([volume], 30, reference_time)
    prod = replace(old[0], environment="prod")
    protected = replace(old[0], tags={"DoNotDelete": "true"}, pricing_status="available")
    results = apply_cleanup_policy(
        [prod, protected], exclude_production=True, protected_tags={"DoNotDelete": "true"}
    )
    assert all(not item.eligible_for_review for item in results)
    assert "production" in results[0].exclusion_reason
    assert "protected tag" in results[1].exclusion_reason


def test_production_tag_excludes_volume_even_when_account_environment_is_unknown(
    volume, reference_time
):
    tagged = replace(volume, environment="unknown", tags={"Environment": "Production"})
    old = apply_age_filter([tagged], 30, reference_time)
    result = apply_cleanup_policy(old, exclude_production=True, protected_tags={})[0]
    assert not result.eligible_for_review
    assert "production environment" in result.exclusion_reason


def test_missing_pricing_is_excluded(volume, reference_time):
    old = apply_age_filter([volume], 30, reference_time)[0]
    excluded = apply_cleanup_policy([old], exclude_production=True, protected_tags={})[0]
    assert not excluded.eligible_for_review
    assert "pricing is unavailable" in excluded.exclusion_reason


def test_in_use_volume_never_becomes_candidate(volume, reference_time):
    attached = replace(volume, state="in-use")
    assert not apply_age_filter([attached], 1, reference_time)[0].eligible_for_review


def test_future_created_volume_does_not_meet_zero_day_age(volume, reference_time):
    future = replace(volume, create_time=reference_time + timedelta(seconds=1))
    result = apply_age_filter([future], 0, reference_time)[0]
    assert result.age_days == 0
    assert not result.meets_age_threshold
