"""ORM boundary for T-018 owner-only subscription reads."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Prefetch, QuerySet

from apps.care.models import CareRecord
from apps.subscriptions.models import CustomerSubscription


SUPPORTED_PRODUCT_MODEL_CODE = "WPUJAC104DWH"


class SubscriptionRepository:
    """Build one privacy-safe queryset shared by list and detail reads."""

    @staticmethod
    def visible_for_customer(actor: Any) -> QuerySet[CustomerSubscription]:
        completed_care = (
            CareRecord.objects.filter(status_code=CareRecord.Status.COMPLETED)
            .only("subscription_id", "performed_on", "completed_at")
            .order_by()
        )
        return (
            CustomerSubscription.objects.filter(
                customer__user=actor,
                customer__deleted_at__isnull=True,
                status_code=CustomerSubscription.Status.ACTIVE,
                product_model__model_code=SUPPORTED_PRODUCT_MODEL_CODE,
                product_model__is_active=True,
            )
            .select_related("product_model")
            .prefetch_related(
                Prefetch(
                    "care_records",
                    queryset=completed_care,
                    to_attr="t018_completed_care_records",
                )
            )
            .order_by("-started_on", "public_id")
        )

    @classmethod
    def list_page(
        cls,
        *,
        actor: Any,
        offset: int,
        limit: int,
    ) -> tuple[list[CustomerSubscription], int]:
        queryset = cls.visible_for_customer(actor)
        total = queryset.count()
        return list(queryset[offset : offset + limit]), total

    @classmethod
    def find_detail(
        cls,
        *,
        actor: Any,
        subscription_public_id: UUID,
    ) -> CustomerSubscription | None:
        return cls.visible_for_customer(actor).filter(
            public_id=subscription_public_id
        ).first()
