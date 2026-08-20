"""Read-only ORM boundary for trusted AI Inquiry Context."""

from __future__ import annotations

from uuid import UUID

from django.db.models import Prefetch

from apps.inquiries.models import Inquiry, InquiryQA


class InternalAIContextRepository:
    """Load one Inquiry without exposing customer identity fields."""

    @staticmethod
    def find(inquiry_public_id: UUID) -> Inquiry | None:
        answered_questions = (
            InquiryQA.objects.filter(customer_answer__isnull=False)
            .select_related("customer_answer")
            .order_by("sequence_no", "public_id")
        )
        return (
            Inquiry.objects.select_related(
                "subscription",
                "subscription__product_model",
                "representative_symptom",
            )
            .prefetch_related(
                Prefetch(
                    "qa_entries",
                    queryset=answered_questions,
                    to_attr="ai_qa_entries",
                )
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )
