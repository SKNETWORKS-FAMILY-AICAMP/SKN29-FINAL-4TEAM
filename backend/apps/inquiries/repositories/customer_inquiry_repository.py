"""Owner-scoped ORM reads for the CUSTOMER Mobile inquiry slice."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import F, OuterRef, Prefetch, QuerySet, Subquery

from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.inquiries.models import (
    FollowupConfirmation,
    Guidance,
    GuidanceItem,
    Inquiry,
    InquiryQA,
)
from apps.visits.models import Visit
from apps.workflow.models import TransitionHistory


class CustomerInquiryRepository:
    """Hide non-owned inquiries before building any public projection."""

    @staticmethod
    def visible_for_customer(actor: Any) -> QuerySet[Inquiry]:
        latest_completed_consultation = Consultation.objects.filter(
            inquiry_id=OuterRef("pk"),
            status=Consultation.Status.COMPLETED,
            completed_at__isnull=False,
        ).order_by("-completed_at", "-id")
        latest_completed_visit = Visit.objects.filter(
            inquiry_id=OuterRef("pk"),
            status=Visit.Status.COMPLETED,
            completed_at__isnull=False,
        ).order_by("-completed_at", "-id")
        latest_resolved_feedback = FollowupConfirmation.objects.filter(
            inquiry_id=OuterRef("pk"),
            resolution_status_code=FollowupConfirmation.ResolutionStatus.RESOLVED,
        ).order_by("-created_at", "-id")
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
            .annotate(
                allowed_action_latest_completed_consultation_at=Subquery(
                    latest_completed_consultation.values("completed_at")[:1]
                ),
                allowed_action_latest_completed_consultation_handler_id=Subquery(
                    latest_completed_consultation.values("consultant_id")[:1]
                ),
                allowed_action_latest_completed_visit_at=Subquery(
                    latest_completed_visit.values("completed_at")[:1]
                ),
                allowed_action_latest_completed_visit_handler_id=Subquery(
                    latest_completed_visit.values("technician_id")[:1]
                ),
                allowed_action_latest_resolved_feedback_at=Subquery(
                    latest_resolved_feedback.values("created_at")[:1]
                ),
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

    @staticmethod
    def latest_state_change_event() -> QuerySet[TransitionHistory]:
        """Select the event that most recently changed the Inquiry state."""

        return (
            TransitionHistory.objects.filter(inquiry_id=OuterRef("pk"))
            .exclude(from_state=F("to_state"))
            .order_by("-state_version", "-pk")
        )

    @classmethod
    def find_latest_active(cls, *, actor: Any) -> Inquiry | None:
        """Return the customer's most recently updated non-terminal inquiry."""

        return (
            cls.visible_for_customer(actor)
            .prefetch_related(
                Prefetch(
                    "qa_entries",
                    queryset=cls.unanswered_question_rows(),
                    to_attr="allowed_action_open_questions",
                )
            )
            .exclude(
                status_code__in=(
                    Inquiry.Status.RESOLVED,
                    Inquiry.Status.CANCELLED,
                )
            )
            .order_by("-updated_at", "-created_at", "-pk")
            .first()
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
            .annotate(
                latest_state_change_event=Subquery(
                    cls.latest_state_change_event().values("event_code")[:1]
                )
            )
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
        """Load only guidance backed by a successful validated AI run."""

        trusted_guidance = (
            Guidance.objects.filter(
                # Load the newest validated draft before applying visibility.
                # Filtering PENDING/REJECTED here could make an older Guidance
                # look current and leak stale advice after a newer review.
                generated_by_ai_run__task_type_code__in=(
                    AIRun.TaskType.ANALYZE_SYMPTOM,
                    AIRun.TaskType.GENERATE_GUIDANCE,
                ),
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
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=(
                        GuidanceItem.objects.only(
                            "guidance_id",
                            "step_no",
                            "instruction_text",
                        ).order_by("step_no", "public_id")
                    ),
                    to_attr="customer_public_items",
                ),
            )
            .order_by("-guidance_version", "-created_at", "-public_id")
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
                    queryset=trusted_guidance,
                    to_attr="customer_guidance_versions",
                ),
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )

    @classmethod
    def find_with_consultation_result(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        """Load only the latest completed consultation's public result fields."""

        completed_consultations = (
            Consultation.objects.filter(
                status=Consultation.Status.COMPLETED,
                completed_at__isnull=False,
            )
            .only(
                "id",
                "inquiry_id",
                "consultant_id",
                "outcome",
                "customer_guidance",
                "usage_guidance_status",
                "completed_at",
            )
            .order_by("-completed_at", "-id")
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
                    "consultations",
                    queryset=completed_consultations,
                    to_attr="customer_completed_consultations",
                ),
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )
