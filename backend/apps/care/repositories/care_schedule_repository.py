"""T-020 케어 일정과 next_care_on 캐시 ORM 경계."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID, uuid4

from django.db.models import Min

from apps.care.models import CareRecord
from apps.subscriptions.models import CustomerSubscription
from apps.subscriptions.repositories.subscription_repository import (
    SUPPORTED_PRODUCT_MODEL_CODES,
)


OPEN_SCHEDULE_STATUSES = (
    CareRecord.Status.DUE,
    CareRecord.Status.SCHEDULED,
    CareRecord.Status.OVERDUE,
)


class CareScheduleRepository:
    @staticmethod
    def lock_eligible_subscription(
        subscription_public_id: UUID,
    ) -> CustomerSubscription:
        return (
            CustomerSubscription.objects.select_for_update()
            .select_related("product_model")
            .get(
                public_id=subscription_public_id,
                status_code=CustomerSubscription.Status.ACTIVE,
                product_model__model_code__in=SUPPORTED_PRODUCT_MODEL_CODES,
                product_model__is_supported_mvp=True,
                product_model__is_active=True,
            )
        )

    @staticmethod
    def latest_completed(
        *,
        subscription: CustomerSubscription,
        care_type_code: str,
    ) -> CareRecord | None:
        return (
            CareRecord.objects.filter(
                subscription=subscription,
                care_type_code=care_type_code,
                status_code=CareRecord.Status.COMPLETED,
            )
            .order_by("-performed_on", "-completed_at", "-public_id")
            .first()
        )

    @staticmethod
    def matching_open_schedule(
        *,
        subscription: CustomerSubscription,
        care_type_code: str,
        scheduled_on: date,
        summary: str,
    ) -> CareRecord | None:
        return (
            CareRecord.objects.filter(
                subscription=subscription,
                care_type_code=care_type_code,
                status_code__in=OPEN_SCHEDULE_STATUSES,
                scheduled_on=scheduled_on,
                summary=summary,
            )
            .order_by("public_id")
            .first()
        )

    @staticmethod
    def cancel_open_schedules(
        *,
        subscription: CustomerSubscription,
        care_type_code: str,
        reason: str,
        cancelled_at,
    ) -> int:
        return CareRecord.objects.filter(
            subscription=subscription,
            care_type_code=care_type_code,
            status_code__in=OPEN_SCHEDULE_STATUSES,
        ).update(
            status_code=CareRecord.Status.CANCELLED,
            cancelled_at=cancelled_at,
            cancellation_reason=reason,
            updated_at=cancelled_at,
        )

    @staticmethod
    def cancel_official_open_schedules(
        *,
        subscription: CustomerSubscription,
        care_type_code: str,
        reason: str,
        cancelled_at,
    ) -> int:
        """Cancel only schedules produced from an approved official rule."""

        return CareRecord.objects.filter(
            subscription=subscription,
            care_type_code=care_type_code,
            status_code__in=OPEN_SCHEDULE_STATUSES,
            source_code=CareRecord.Source.SYSTEM,
            summary__startswith="basis=OFFICIAL;",
        ).update(
            status_code=CareRecord.Status.CANCELLED,
            cancelled_at=cancelled_at,
            cancellation_reason=reason,
            updated_at=cancelled_at,
        )

    @staticmethod
    def create_schedule(
        *,
        subscription: CustomerSubscription,
        care_type_code: str,
        scheduled_on: date,
        summary: str,
    ) -> CareRecord:
        public_id = uuid4()
        return CareRecord.objects.create(
            public_id=public_id,
            care_code=f"SCHEDULE-{public_id.hex.upper()}",
            subscription=subscription,
            care_type_code=care_type_code,
            status_code=CareRecord.Status.SCHEDULED,
            scheduled_on=scheduled_on,
            summary=summary,
            source_code=CareRecord.Source.SYSTEM,
        )

    @staticmethod
    def sync_next_care_cache(
        subscription: CustomerSubscription,
    ) -> date | None:
        next_care_on = (
            CareRecord.objects.filter(
                subscription=subscription,
                status_code__in=OPEN_SCHEDULE_STATUSES,
                scheduled_on__isnull=False,
            ).aggregate(value=Min("scheduled_on"))["value"]
        )
        if subscription.next_care_on != next_care_on:
            subscription.next_care_on = next_care_on
            subscription.save(update_fields=["next_care_on", "updated_at"])
        return next_care_on
