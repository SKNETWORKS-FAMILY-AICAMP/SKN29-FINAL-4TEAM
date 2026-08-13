"""T-020 official-rule care schedule calculation and persistence tests."""

from __future__ import annotations

from datetime import date

import pytest
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.care.models import CareRecord
from apps.care.models.care_schedule import (
    CareCycleRule,
    CareScheduleBasis,
    CareScheduleStatus,
)
from apps.care.services.care_schedule_service import CareScheduleService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_subscription(sequence: int = 1) -> CustomerSubscription:
    user = User.objects.create_user(
        username=f"T020-CUSTOMER-{sequence:03d}",
        full_name=f"T020 customer {sequence}",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    customer = CustomerProfile.objects.create(
        user=user,
        customer_no=f"T020-C-{sequence:03d}",
        customer_name=f"T020 customer {sequence}",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code="WPUJAC104DWH",
        model_name="T020 supported purifier",
        is_supported_mvp=True,
        is_active=True,
    )
    return CustomerSubscription.objects.create(
        contract_no=f"T020-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"T020-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.SELF_MANAGED,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 1, 31),
    )


def official_rule(months: int) -> CareCycleRule:
    return CareCycleRule(
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        interval_months=months,
        basis=CareScheduleBasis.OFFICIAL,
        source_reference="official://WPUJAC104DWH/filter-cycle",
        source_version="2026-08-12",
    )


def test_missing_rule_returns_confirmation_required_without_guessing():
    result = CareScheduleService.calculate(
        base_on=date(2026, 1, 31),
        rule=None,
    )

    assert result.status == CareScheduleStatus.CONFIRMATION_REQUIRED
    assert result.next_care_on is None
    assert result.basis is None
    assert result.source_reference is None


@pytest.mark.parametrize(
    ("base_on", "expected"),
    [
        (date(2026, 1, 31), date(2026, 2, 28)),
        (date(2028, 1, 31), date(2028, 2, 29)),
        (date(2026, 8, 31), date(2026, 9, 30)),
    ],
)
def test_calendar_month_end_and_leap_year_are_deterministic(
    base_on,
    expected,
):
    result = CareScheduleService.calculate(
        base_on=base_on,
        rule=official_rule(1),
    )

    assert result.status == CareScheduleStatus.SCHEDULED
    assert result.next_care_on == expected
    assert result.basis == CareScheduleBasis.OFFICIAL


def test_recalculate_uses_latest_matching_completed_history_and_syncs_cache():
    subscription = create_subscription()
    performer = subscription.customer.user
    CareRecord.objects.create(
        care_code="T020-COMPLETED-001",
        subscription=subscription,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
        status_code=CareRecord.Status.COMPLETED,
        performed_on=date(2026, 7, 31),
        result_code=CareRecord.Result.FILTER_REPLACED,
        completed_at=timezone.now(),
        performed_by=performer,
        source_code=CareRecord.Source.CUSTOMER,
    )

    outcome = CareScheduleService.recalculate(
        subscription_public_id=subscription.public_id,
        rule=official_rule(1),
        change_reason="OFFICIAL_CYCLE_APPLIED",
    )

    assert outcome.changed is True
    assert outcome.schedule.next_care_on == date(2026, 8, 31)
    scheduled = CareRecord.objects.get(status_code=CareRecord.Status.SCHEDULED)
    assert scheduled.scheduled_on == date(2026, 8, 31)
    assert "basis=OFFICIAL" in (scheduled.summary or "")
    subscription.refresh_from_db()
    assert subscription.next_care_on == date(2026, 8, 31)


def test_same_rule_and_date_is_idempotent_without_duplicate_schedule():
    subscription = create_subscription()

    first = CareScheduleService.recalculate(
        subscription_public_id=subscription.public_id,
        rule=official_rule(1),
        change_reason="INITIAL",
    )
    second = CareScheduleService.recalculate(
        subscription_public_id=subscription.public_id,
        rule=official_rule(1),
        change_reason="REPLAY",
    )

    assert first.changed is True
    assert second.changed is False
    assert CareRecord.objects.filter(
        status_code=CareRecord.Status.SCHEDULED
    ).count() == 1


def test_changed_rule_cancels_old_schedule_and_preserves_change_history():
    subscription = create_subscription()
    CareScheduleService.recalculate(
        subscription_public_id=subscription.public_id,
        rule=official_rule(1),
        change_reason="INITIAL",
    )

    outcome = CareScheduleService.recalculate(
        subscription_public_id=subscription.public_id,
        rule=official_rule(3),
        change_reason="OFFICIAL_RULE_VERSION_CHANGED",
    )

    assert outcome.changed is True
    old = CareRecord.objects.get(status_code=CareRecord.Status.CANCELLED)
    new = CareRecord.objects.get(status_code=CareRecord.Status.SCHEDULED)
    assert old.scheduled_on == date(2026, 2, 28)
    assert old.cancellation_reason == "OFFICIAL_RULE_VERSION_CHANGED"
    assert new.scheduled_on == date(2026, 4, 30)
    subscription.refresh_from_db()
    assert subscription.next_care_on == date(2026, 4, 30)


def test_missing_rule_does_not_destroy_existing_schedule_or_cache():
    subscription = create_subscription()
    subscription.next_care_on = date(2026, 9, 30)
    subscription.save(update_fields=["next_care_on", "updated_at"])

    outcome = CareScheduleService.recalculate(
        subscription_public_id=subscription.public_id,
        rule=None,
        change_reason="NO_OFFICIAL_RULE",
    )

    assert outcome.changed is False
    assert outcome.schedule.status == CareScheduleStatus.CONFIRMATION_REQUIRED
    subscription.refresh_from_db()
    assert subscription.next_care_on == date(2026, 9, 30)
    assert CareRecord.objects.count() == 0


def test_inactive_or_unsupported_subscription_is_not_recalculated():
    subscription = create_subscription()
    subscription.status_code = CustomerSubscription.Status.EXPIRED
    subscription.ended_on = date(2026, 8, 1)
    subscription.save(
        update_fields=["status_code", "ended_on", "updated_at"]
    )

    with pytest.raises(CustomerSubscription.DoesNotExist):
        CareScheduleService.recalculate(
            subscription_public_id=subscription.public_id,
            rule=official_rule(1),
            change_reason="SHOULD_NOT_RUN",
        )
