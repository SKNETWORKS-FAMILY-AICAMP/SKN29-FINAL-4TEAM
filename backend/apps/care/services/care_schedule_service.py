"""T-020 출처 있는 관리 주기 기반 계산·재산정 Service."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timezone as datetime_timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.care.models import CareRecord
from apps.care.models.care_schedule import (
    CareCycleRule,
    CareScheduleStatus,
    NextCareSchedule,
)
from apps.care.repositories.care_schedule_repository import (
    CareScheduleRepository,
)
from apps.care.services.care_cycle_rule_registry import (
    ApprovedCareCycleRuleRegistry,
)
from apps.subscriptions.models import CustomerSubscription


BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class CareScheduleMutationOutcome:
    changed: bool
    schedule: NextCareSchedule
    schedule_record_id: UUID | None


class CareScheduleService:
    @staticmethod
    def calculate(
        *,
        base_on: date,
        rule: CareCycleRule | None,
    ) -> NextCareSchedule:
        if rule is None:
            return NextCareSchedule(
                status=CareScheduleStatus.CONFIRMATION_REQUIRED,
                next_care_on=None,
                basis=None,
                base_on=base_on,
                care_type_code=None,
                source_reference=None,
                source_version=None,
            )
        return NextCareSchedule(
            status=CareScheduleStatus.SCHEDULED,
            next_care_on=CareScheduleService._add_months(
                base_on,
                rule.interval_months,
            ),
            basis=rule.basis,
            base_on=base_on,
            care_type_code=rule.care_type_code,
            source_reference=rule.source_reference,
            source_version=rule.source_version,
        )

    @classmethod
    @transaction.atomic
    def recalculate(
        cls,
        *,
        subscription_public_id: UUID,
        rule: CareCycleRule | None,
        change_reason: str,
    ) -> CareScheduleMutationOutcome:
        subscription = CareScheduleRepository.lock_eligible_subscription(
            subscription_public_id
        )
        return cls._recalculate_locked(
            subscription=subscription,
            rule=rule,
            change_reason=change_reason,
        )

    @classmethod
    @transaction.atomic
    def recalculate_from_registry(
        cls,
        *,
        subscription_public_id: UUID,
        care_type_code: str,
        registry: ApprovedCareCycleRuleRegistry,
        change_reason: str,
        invalidate_official_on_miss: bool = False,
    ) -> CareScheduleMutationOutcome:
        """Resolve an exact approved rule while holding the subscription lock."""

        if care_type_code not in CareRecord.CareType.values:
            raise ValueError("care_type_code is not in the CareRecord contract")
        subscription = CareScheduleRepository.lock_eligible_subscription(
            subscription_public_id
        )
        rule = registry.resolve(
            product_model_code=subscription.product_model.model_code,
            management_type_code=subscription.management_type_code,
            care_type_code=care_type_code,
        )
        return cls._recalculate_locked(
            subscription=subscription,
            rule=rule,
            change_reason=change_reason,
            invalidate_official_on_miss=invalidate_official_on_miss,
        )

    @classmethod
    def _recalculate_locked(
        cls,
        *,
        subscription: CustomerSubscription,
        rule: CareCycleRule | None,
        change_reason: str,
        invalidate_official_on_miss: bool = False,
    ) -> CareScheduleMutationOutcome:
        """Recalculate after the caller has serialized the subscription row."""

        if rule is None:
            schedule = cls.calculate(
                base_on=subscription.started_on,
                rule=None,
            )
            if not invalidate_official_on_miss:
                return CareScheduleMutationOutcome(False, schedule, None)
            reason = change_reason.strip()
            if not reason:
                raise ValueError("change_reason is required")
            previous_next_care_on = subscription.next_care_on
            cancelled = CareScheduleRepository.cancel_official_open_schedules(
                subscription=subscription,
                care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
                reason=reason,
                cancelled_at=timezone.now(),
            )
            current_next_care_on = (
                CareScheduleRepository.sync_next_care_cache(subscription)
            )
            return CareScheduleMutationOutcome(
                cancelled > 0
                or current_next_care_on != previous_next_care_on,
                schedule,
                None,
            )
        if rule.care_type_code not in CareRecord.CareType.values:
            raise ValueError("care_type_code is not in the CareRecord contract")

        completed = CareScheduleRepository.latest_completed(
            subscription=subscription,
            care_type_code=rule.care_type_code,
        )
        base_on = (
            cls._record_date(completed)
            if completed is not None
            else subscription.started_on
        )
        schedule = cls.calculate(base_on=base_on, rule=rule)
        assert schedule.next_care_on is not None
        summary = cls._schedule_summary(schedule, rule)
        existing = CareScheduleRepository.matching_open_schedule(
            subscription=subscription,
            care_type_code=rule.care_type_code,
            scheduled_on=schedule.next_care_on,
            summary=summary,
        )
        if existing is not None:
            CareScheduleRepository.sync_next_care_cache(subscription)
            return CareScheduleMutationOutcome(
                False,
                schedule,
                existing.public_id,
            )

        reason = change_reason.strip()
        if not reason:
            raise ValueError("change_reason is required")
        now = timezone.now()
        CareScheduleRepository.cancel_open_schedules(
            subscription=subscription,
            care_type_code=rule.care_type_code,
            reason=reason,
            cancelled_at=now,
        )
        record = CareScheduleRepository.create_schedule(
            subscription=subscription,
            care_type_code=rule.care_type_code,
            scheduled_on=schedule.next_care_on,
            summary=summary,
        )
        CareScheduleRepository.sync_next_care_cache(subscription)
        return CareScheduleMutationOutcome(True, schedule, record.public_id)

    @staticmethod
    def _add_months(base_on: date, months: int) -> date:
        month_index = base_on.year * 12 + (base_on.month - 1) + months
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(base_on.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def _record_date(record: CareRecord) -> date:
        if record.performed_on is not None:
            return record.performed_on
        completed_at = record.completed_at
        if completed_at is None:
            raise ValueError("COMPLETED CareRecord has no business date")
        if timezone.is_naive(completed_at):
            completed_at = completed_at.replace(tzinfo=datetime_timezone.utc)
        return timezone.localtime(completed_at, BUSINESS_TIMEZONE).date()

    @staticmethod
    def _schedule_summary(
        schedule: NextCareSchedule,
        rule: CareCycleRule,
    ) -> str:
        return (
            f"basis={schedule.basis};"
            f"source_reference={rule.source_reference};"
            f"source_version={rule.source_version};"
            f"interval_months={rule.interval_months};"
            f"base_on={schedule.base_on.isoformat()}"
        )
