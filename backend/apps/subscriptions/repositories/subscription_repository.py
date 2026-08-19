"""ORM boundary for T-018 owner-only subscription reads."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Prefetch, QuerySet

from apps.accounts.models import CustomerProfile
from apps.care.models import CareRecord
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


SUPPORTED_PRODUCT_MODEL_CODE = "WPUJAC104DWH"
SUPPORTED_PRODUCT_MODEL_CODES = (
    "WPUJAC104DWH",
    "WPUIAC425SNW",
    "WPUIAC606SNW",
)


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
                product_model__model_code__in=SUPPORTED_PRODUCT_MODEL_CODES,
                product_model__is_supported_mvp=True,
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

    @staticmethod
    def lock_synthetic_customer(actor: Any) -> CustomerProfile | None:
        return (
            CustomerProfile.objects.select_for_update()
            .select_related("user")
            .filter(
                user=actor,
                deleted_at__isnull=True,
                is_synthetic=True,
            )
            .first()
        )

    @staticmethod
    def find_supported_product(model_code: str) -> ProductModel | None:
        return ProductModel.objects.filter(
            model_code=model_code,
            model_code__in=SUPPORTED_PRODUCT_MODEL_CODES,
            is_supported_mvp=True,
            is_active=True,
        ).first()

    @staticmethod
    def find_active_product_subscription(
        *,
        customer: CustomerProfile,
        product: ProductModel,
    ) -> CustomerSubscription | None:
        return CustomerSubscription.objects.filter(
            customer=customer,
            product_model=product,
            status_code__in=[
                CustomerSubscription.Status.ACTIVE,
                CustomerSubscription.Status.SUSPENDED,
            ],
        ).first()

    @staticmethod
    def create_synthetic_subscription(
        *,
        public_id: UUID,
        customer: CustomerProfile,
        product: ProductModel,
        started_on,
        management_type_code: str,
    ) -> CustomerSubscription:
        suffix = public_id.hex.upper()
        return CustomerSubscription.objects.create(
            public_id=public_id,
            contract_no=f"SYN-SUB-{suffix}",
            customer=customer,
            product_model=product,
            serial_no=f"SYN-SERIAL-{suffix}",
            management_type_code=management_type_code,
            status_code=CustomerSubscription.Status.ACTIVE,
            started_on=started_on,
        )

    @staticmethod
    def lock_owned_active_subscription(
        *,
        actor: Any,
        subscription_public_id: UUID,
    ) -> CustomerSubscription | None:
        return (
            CustomerSubscription.objects.select_for_update()
            .select_related("customer", "customer__user", "product_model")
            .filter(
                public_id=subscription_public_id,
                customer__user=actor,
                customer__deleted_at__isnull=True,
                status_code=CustomerSubscription.Status.ACTIVE,
                product_model__model_code__in=SUPPORTED_PRODUCT_MODEL_CODES,
                product_model__is_supported_mvp=True,
                product_model__is_active=True,
            )
            .first()
        )

    @staticmethod
    def save_allowed_updates(
        subscription: CustomerSubscription,
        *,
        started_on=None,
        management_type_code: str | None = None,
    ) -> None:
        fields: list[str] = []
        if started_on is not None:
            subscription.started_on = started_on
            fields.append("started_on")
        if management_type_code is not None:
            subscription.management_type_code = management_type_code
            fields.append("management_type_code")
        if fields:
            subscription.save(update_fields=[*fields, "updated_at"])

    @staticmethod
    def completed_care_rows(
        subscription: CustomerSubscription,
    ) -> list[CareRecord]:
        return list(
            CareRecord.objects.filter(
                subscription=subscription,
                status_code=CareRecord.Status.COMPLETED,
            ).only("performed_on", "completed_at")
        )

    @staticmethod
    def set_registration_care_baseline(
        subscription: CustomerSubscription,
        *,
        performed_on,
    ) -> CareRecord:
        care, _created = CareRecord.objects.update_or_create(
            care_code=f"T018-BASE-{subscription.public_id.hex}",
            defaults={
                "subscription": subscription,
                "care_type_code": CareRecord.CareType.FILTER_REPLACEMENT,
                "status_code": CareRecord.Status.COMPLETED,
                "scheduled_on": None,
                "performed_on": performed_on,
                "result_code": CareRecord.Result.FILTER_REPLACED,
                "completed_at": None,
                "cancelled_at": None,
                "cancellation_reason": None,
                "summary": "T-018 synthetic registration baseline",
                "performed_by": None,
                "source_code": CareRecord.Source.IMPORT,
            },
        )
        return care
