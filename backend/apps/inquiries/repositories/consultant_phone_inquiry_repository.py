"""ORM boundary for consultant phone inquiry intake."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import F, QuerySet, Value
from django.db.models.functions import Replace

from apps.inquiries.models import Inquiry, SymptomEntry
from apps.subscriptions.models import CustomerSubscription


class ConsultantPhoneInquiryRepository:
    """Search and lock only synthetic active customer subscriptions."""

    @staticmethod
    def _allowed_subscriptions() -> QuerySet[CustomerSubscription]:
        return CustomerSubscription.objects.filter(
            status_code=CustomerSubscription.Status.ACTIVE,
            customer__deleted_at__isnull=True,
            customer__is_synthetic=True,
            customer__user__is_active=True,
            customer__user__is_synthetic=True,
        ).select_related(
            "customer",
            "customer__user",
            "product_model",
        )

    @classmethod
    def search_active_synthetic_subscriptions(
        cls,
        *,
        query: str,
        limit: int,
    ) -> list[CustomerSubscription]:
        queryset = cls._allowed_subscriptions()
        if cls._is_phone_query(query):
            digits = cls._digits(query)
            queryset = queryset.annotate(
                normalized_customer_phone=Replace(
                    Replace(
                        Replace(
                            Replace(
                                Replace(
                                    F("customer__phone"),
                                    Value("-"),
                                    Value(""),
                                ),
                                Value(" "),
                                Value(""),
                            ),
                            Value("("),
                            Value(""),
                        ),
                        Value(")"),
                        Value(""),
                    ),
                    Value("+"),
                    Value(""),
                )
            ).filter(normalized_customer_phone__contains=digits)
        else:
            queryset = queryset.filter(
                customer__customer_name__icontains=query.strip()
            )
        return list(
            queryset.order_by(
                "customer__customer_name",
                "product_model__model_code",
                "public_id",
            )[:limit]
        )

    @classmethod
    def lock_active_synthetic_subscription(
        cls,
        *,
        subscription_public_id: UUID,
    ) -> CustomerSubscription | None:
        return (
            cls._allowed_subscriptions()
            .select_for_update(of=("self",))
            .filter(public_id=subscription_public_id)
            .first()
        )

    @staticmethod
    def create_phone_inquiry(
        *,
        subscription: CustomerSubscription,
        actor: Any,
        raw_text: str,
        priority_code: str,
        idempotency_key: str,
        correlation_id: UUID,
        status_code: str,
        state_version: int,
    ) -> Inquiry:
        return Inquiry.objects.create(
            subscription=subscription,
            initiated_by=actor,
            assigned_user=actor,
            assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
            channel_code=Inquiry.Channel.PHONE,
            raw_text=raw_text,
            priority_code=priority_code,
            source_idempotency_key=idempotency_key,
            source_correlation_id=correlation_id,
            status_code=status_code,
            state_version=state_version,
        )

    @staticmethod
    def create_representative_symptom(
        *,
        inquiry: Inquiry,
        symptom_code: str,
    ) -> SymptomEntry:
        return SymptomEntry.objects.create(
            inquiry=inquiry,
            symptom_type_code=symptom_code,
            structured_payload={
                "representative_symptom_code": symptom_code,
                "source": "CONSULTANT_PHONE_INTAKE",
            },
            schema_version="v1",
            is_customer_confirmed=False,
        )

    @staticmethod
    def _digits(value: str) -> str:
        return "".join(character for character in value if character.isdigit())

    @classmethod
    def _is_phone_query(cls, value: str) -> bool:
        stripped = value.strip()
        return bool(stripped) and all(
            character.isdigit() or character in " -()+"
            for character in stripped
        )
