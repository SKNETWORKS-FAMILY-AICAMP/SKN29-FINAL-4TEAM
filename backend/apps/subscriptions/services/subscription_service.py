"""T-018 list/detail projection service."""

from __future__ import annotations

from datetime import date, timezone as datetime_timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.subscriptions.models import CustomerSubscription
from apps.subscriptions.repositories.subscription_repository import (
    SubscriptionRepository,
)
from common.api.pagination import build_page_data


BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")


class SubscriptionService:
    """Return allowlisted values without leaking internal subscription data."""

    @classmethod
    def list_for_customer(
        cls,
        *,
        actor: Any,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        subscriptions, total = SubscriptionRepository.list_page(
            actor=actor,
            offset=(page - 1) * size,
            limit=size,
        )
        return build_page_data(
            [cls._summary(subscription) for subscription in subscriptions],
            page=page,
            size=size,
            total=total,
        )

    @classmethod
    def detail_for_customer(
        cls,
        *,
        actor: Any,
        subscription_public_id: UUID,
    ) -> dict[str, Any]:
        subscription = SubscriptionRepository.find_detail(
            actor=actor,
            subscription_public_id=subscription_public_id,
        )
        if subscription is None:
            raise NotFound()
        return {
            **cls._summary(subscription),
            "ended_on": subscription.ended_on,
        }

    @classmethod
    def _summary(
        cls,
        subscription: CustomerSubscription,
    ) -> dict[str, Any]:
        product = subscription.product_model
        return {
            "subscription_id": subscription.public_id,
            "status_code": subscription.status_code,
            "management_type_code": subscription.management_type_code,
            "started_on": subscription.started_on,
            "last_care_on": cls._last_care_on(subscription),
            "next_care_on": subscription.next_care_on,
            "product": {
                "product_model_id": product.public_id,
                "model_code": product.model_code,
                "model_name": product.model_name,
                "generation_code": product.generation_code,
                "manufacturer": product.manufacturer,
            },
        }

    @staticmethod
    def _last_care_on(subscription: CustomerSubscription) -> date | None:
        care_dates: list[date] = []
        for care_record in subscription.t018_completed_care_records:
            if care_record.performed_on is not None:
                care_dates.append(care_record.performed_on)
                continue
            if care_record.completed_at is None:
                continue
            completed_at = care_record.completed_at
            if timezone.is_naive(completed_at):
                completed_at = completed_at.replace(
                    tzinfo=datetime_timezone.utc
                )
            care_dates.append(
                timezone.localtime(completed_at, BUSINESS_TIMEZONE).date()
            )
        return max(care_dates, default=None)
