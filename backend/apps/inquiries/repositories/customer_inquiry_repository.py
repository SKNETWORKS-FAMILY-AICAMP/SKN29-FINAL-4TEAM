"""Owner-scoped ORM reads for the CUSTOMER Mobile inquiry slice."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Prefetch, QuerySet

from apps.audit.models import AIRun
from apps.inquiries.models import Guidance, Inquiry, InquiryQA


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
            .select_related(
                "subscription",
                "subscription__customer",
                "subscription__product_model",
            )
        )

    @staticmethod
    def unanswered_question_rows() -> QuerySet[InquiryQA]:
        return (
            InquiryQA.objects.only(
                "inquiry_id",
                "public_id",
                "sequence_no",
                "question_text",
                "answer_type_code",
                "answer_payload",
            )
            .filter(customer_answer__isnull=True)
            .order_by("sequence_no", "public_id")
        )

    @classmethod
    def find_snapshot(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        return (
            cls.visible_for_customer(actor)
            .prefetch_related(
                Prefetch(
                    "qa_entries",
                    queryset=cls.unanswered_question_rows(),
                    to_attr="allowed_action_open_questions",
                )
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )

    @classmethod
    def find_with_questions(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        return (
            cls.visible_for_customer(actor)
            .prefetch_related(
                Prefetch(
                    "qa_entries",
                    queryset=cls.unanswered_question_rows(),
                    to_attr="customer_read_questions",
                )
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )

    @classmethod
    def find_with_guidance(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        guidance_rows = (
            Guidance.objects.filter(
                generated_by_ai_run__status_code__in=(
                    AIRun.Status.SUCCEEDED,
                    AIRun.Status.NO_EVIDENCE,
                ),
                generated_by_ai_run__schema_validation_status_code=(
                    AIRun.SchemaValidationStatus.PASSED
                ),
                generated_by_ai_run__validated_output_payload__isnull=False,
            )
            .select_related("generated_by_ai_run")
            .prefetch_related("items")
            .order_by("-guidance_version", "-id")
        )
        return (
            cls.visible_for_customer(actor)
            .prefetch_related(
                Prefetch(
                    "qa_entries",
                    queryset=cls.unanswered_question_rows(),
                    to_attr="allowed_action_open_questions",
                ),
                Prefetch(
                    "guidance_versions",
                    queryset=guidance_rows,
                    to_attr="customer_guidance_versions",
                ),
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )
