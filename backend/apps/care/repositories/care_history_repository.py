"""ORM boundary for T-019 care history Runtime."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import QuerySet

from apps.accounts.models import CustomerProfile
from apps.care.models import CareRecord
from apps.inquiries.models import Inquiry
from apps.subscriptions.models import CustomerSubscription
from apps.subscriptions.repositories.subscription_repository import (
    SUPPORTED_PRODUCT_MODEL_CODE,
)


class CareHistoryRepository:
    @staticmethod
    def lock_customer(actor: Any) -> CustomerProfile | None:
        return (
            CustomerProfile.objects.select_for_update()
            .filter(user=actor, deleted_at__isnull=True)
            .first()
        )

    @staticmethod
    def visible_subscription(
        *,
        actor: Any,
        subscription_public_id: UUID,
        for_update: bool = False,
    ) -> CustomerSubscription | None:
        queryset = CustomerSubscription.objects.select_related(
            "product_model",
            "customer",
        )
        if for_update:
            queryset = queryset.select_for_update()
        return queryset.filter(
            public_id=subscription_public_id,
            customer__user=actor,
            customer__deleted_at__isnull=True,
            status_code=CustomerSubscription.Status.ACTIVE,
            product_model__model_code=SUPPORTED_PRODUCT_MODEL_CODE,
            product_model__is_supported_mvp=True,
            product_model__is_active=True,
        ).first()

    @staticmethod
    def assigned_subscription(
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> CustomerSubscription | None:
        inquiry = (
            Inquiry.objects.select_related(
                "subscription",
                "subscription__product_model",
            )
            .filter(
                public_id=inquiry_public_id,
                assigned_user=actor,
                assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
                subscription__status_code=CustomerSubscription.Status.ACTIVE,
                subscription__product_model__model_code=(
                    SUPPORTED_PRODUCT_MODEL_CODE
                ),
                subscription__product_model__is_supported_mvp=True,
                subscription__product_model__is_active=True,
            )
            .first()
        )
        return inquiry.subscription if inquiry is not None else None

    @staticmethod
    def completed_for_subscription(
        subscription: CustomerSubscription,
    ) -> QuerySet[CareRecord]:
        return (
            CareRecord.objects.select_related("subscription")
            .filter(
                subscription=subscription,
                status_code=CareRecord.Status.COMPLETED,
            )
            .order_by(
                "-performed_on",
                "-completed_at",
                "public_id",
            )
        )

    @classmethod
    def list_page(
        cls,
        *,
        subscription: CustomerSubscription,
        offset: int,
        limit: int,
    ) -> tuple[list[CareRecord], int]:
        queryset = cls.completed_for_subscription(subscription)
        return list(queryset[offset : offset + limit]), queryset.count()

    @classmethod
    def find_detail(
        cls,
        *,
        subscription: CustomerSubscription,
        care_record_public_id: UUID,
    ) -> CareRecord | None:
        return cls.completed_for_subscription(subscription).filter(
            public_id=care_record_public_id
        ).first()

    @staticmethod
    def create_customer_completed(
        *,
        public_id: UUID,
        subscription: CustomerSubscription,
        actor: Any,
        care_type_code: str,
        performed_on,
        result_code: str,
        completed_at,
    ) -> CareRecord:
        return CareRecord.objects.create(
            public_id=public_id,
            care_code=f"CARE-{public_id.hex.upper()}",
            subscription=subscription,
            care_type_code=care_type_code,
            status_code=CareRecord.Status.COMPLETED,
            performed_on=performed_on,
            result_code=result_code,
            completed_at=completed_at,
            performed_by=actor,
            source_code=CareRecord.Source.CUSTOMER,
        )

    @classmethod
    def recent_completed(
        cls,
        *,
        subscription: CustomerSubscription,
        limit: int,
    ) -> list[CareRecord]:
        return list(cls.completed_for_subscription(subscription)[:limit])
