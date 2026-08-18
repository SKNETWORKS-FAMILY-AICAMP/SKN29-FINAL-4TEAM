"""T-020 fail-closed approved care-cycle registry tests."""

from __future__ import annotations

from datetime import date

import pytest

from apps.care.models import CareRecord
from apps.care.models.care_schedule import (
    CareCycleRule,
    CareScheduleBasis,
    CareScheduleStatus,
)
from apps.care.services.care_cycle_rule_registry import (
    ApprovedCareCycleRule,
    ApprovedCareCycleRuleRegistry,
)
from apps.care.services.care_schedule_service import CareScheduleService
from apps.subscriptions.models import CustomerSubscription
from tests.unit.care.test_care_schedule_service import create_subscription


pytestmark = pytest.mark.django_db


def synthetic_rule(
    *,
    months: int = 2,
    care_type_code: str = CareRecord.CareType.FILTER_REPLACEMENT,
) -> CareCycleRule:
    """Return an explicitly synthetic rule, never an operating policy."""

    return CareCycleRule(
        care_type_code=care_type_code,
        interval_months=months,
        basis=CareScheduleBasis.TEAM_RULE,
        source_reference="test-fixture://t020/cycle",
        source_version="test-only-v1",
    )


def entry(
    *,
    model_code: str = "WPUJAC104DWH",
    management_type_code: str = (
        CustomerSubscription.ManagementType.SELF_MANAGED
    ),
    rule: CareCycleRule | None = None,
) -> ApprovedCareCycleRule:
    return ApprovedCareCycleRule(
        product_model_code=model_code,
        management_type_code=management_type_code,
        rule=rule or synthetic_rule(),
    )


def test_registry_resolves_only_the_exact_approved_scope():
    registry = ApprovedCareCycleRuleRegistry([entry()])

    resolved = registry.resolve(
        product_model_code="WPUJAC104DWH",
        management_type_code=CustomerSubscription.ManagementType.SELF_MANAGED,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
    )

    assert registry.size == 1
    assert resolved == synthetic_rule()
    assert (
        registry.resolve(
            product_model_code="WPUJAC104DWH",
            management_type_code=(
                CustomerSubscription.ManagementType.VISIT_CARE
            ),
            care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        )
        is None
    )
    assert (
        registry.resolve(
            product_model_code="UNAPPROVED-MODEL",
            management_type_code=(
                CustomerSubscription.ManagementType.SELF_MANAGED
            ),
            care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        )
        is None
    )
    assert (
        registry.resolve(
            product_model_code="WPUJAC104DWH",
            management_type_code=(
                CustomerSubscription.ManagementType.SELF_MANAGED
            ),
            care_type_code=CareRecord.CareType.CLEANING,
        )
        is None
    )


def test_registry_rejects_duplicate_or_invalid_scope():
    with pytest.raises(
        ValueError,
        match="duplicate approved care-cycle rule scope",
    ):
        ApprovedCareCycleRuleRegistry([entry(), entry()])

    with pytest.raises(ValueError, match="management_type_code"):
        entry(management_type_code="UNAPPROVED")

    with pytest.raises(ValueError, match="care_type_code"):
        entry(rule=synthetic_rule(care_type_code="UNAPPROVED"))


def test_registry_miss_returns_confirmation_required_without_date_or_write():
    subscription = create_subscription(sequence=201)
    registry = ApprovedCareCycleRuleRegistry([])

    outcome = CareScheduleService.recalculate_from_registry(
        subscription_public_id=subscription.public_id,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        registry=registry,
        change_reason="NO_APPROVED_RULE",
    )

    assert outcome.changed is False
    assert outcome.schedule.status == CareScheduleStatus.CONFIRMATION_REQUIRED
    assert outcome.schedule.next_care_on is None
    assert outcome.schedule.source_reference is None
    assert outcome.schedule_record_id is None
    assert not CareRecord.objects.filter(subscription=subscription).exists()
    subscription.refresh_from_db()
    assert subscription.next_care_on is None


def test_registry_exact_match_reuses_calendar_and_persistence_service():
    subscription = create_subscription(sequence=202)
    registry = ApprovedCareCycleRuleRegistry([entry()])

    outcome = CareScheduleService.recalculate_from_registry(
        subscription_public_id=subscription.public_id,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        registry=registry,
        change_reason="TEST_APPROVED_RULE_APPLIED",
    )

    assert outcome.changed is True
    assert outcome.schedule.status == CareScheduleStatus.SCHEDULED
    assert outcome.schedule.next_care_on == date(2026, 3, 31)
    record = CareRecord.objects.get(subscription=subscription)
    assert record.scheduled_on == date(2026, 3, 31)
    assert "source_reference=test-fixture://t020/cycle" in record.summary
    subscription.refresh_from_db()
    assert subscription.next_care_on == date(2026, 3, 31)


def test_registry_replay_keeps_one_open_schedule():
    subscription = create_subscription(sequence=203)
    registry = ApprovedCareCycleRuleRegistry([entry()])

    first = CareScheduleService.recalculate_from_registry(
        subscription_public_id=subscription.public_id,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        registry=registry,
        change_reason="TEST_INITIAL",
    )
    second = CareScheduleService.recalculate_from_registry(
        subscription_public_id=subscription.public_id,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        registry=registry,
        change_reason="TEST_REPLAY",
    )

    assert first.changed is True
    assert second.changed is False
    assert first.schedule_record_id == second.schedule_record_id
    assert (
        CareRecord.objects.filter(
            subscription=subscription,
            status_code=CareRecord.Status.SCHEDULED,
        ).count()
        == 1
    )


def test_invalid_requested_care_type_fails_before_lookup_or_write():
    subscription = create_subscription(sequence=204)
    registry = ApprovedCareCycleRuleRegistry([entry()])

    with pytest.raises(ValueError, match="care_type_code"):
        CareScheduleService.recalculate_from_registry(
            subscription_public_id=subscription.public_id,
            care_type_code="UNAPPROVED",
            registry=registry,
            change_reason="MUST_NOT_WRITE",
        )

    assert not CareRecord.objects.filter(subscription=subscription).exists()
