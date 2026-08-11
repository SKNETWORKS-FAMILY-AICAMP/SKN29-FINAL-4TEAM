"""Owner-scoped ORM reads for the CUSTOMER Mobile inquiry slice."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Prefetch, QuerySet

from apps.inquiries.models import Inquiry, InquiryQA


class CustomerInquiryRepository:
    """Hide non-owned inquiries before building any public projection."""

    @staticmethod
    def visible_for_customer(actor: Any) -> QuerySet[Inquiry]:
        return (
            Inquiry.objects.filter(
                initiated_by=actor,
                subscription__customer__user=actor,
                subscription__customer__deleted_at__isnull=True,
            )
            .select_related("subscription", "subscription__product_model")
        )

    @classmethod
    def find_snapshot(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        return cls.visible_for_customer(actor).filter(
            public_id=inquiry_public_id
        ).first()

    @classmethod
    def find_with_questions(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        question_rows = InquiryQA.objects.only(
            "inquiry_id",
            "public_id",
            "sequence_no",
            "question_text",
            "answer_type_code",
            "answer_payload",
        ).filter(customer_answer__isnull=True).order_by(
            "sequence_no",
            "public_id",
        )
        return (
            cls.visible_for_customer(actor)
            .prefetch_related(
                Prefetch(
                    "qa_entries",
                    queryset=question_rows,
                    to_attr="customer_read_questions",
                )
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )
