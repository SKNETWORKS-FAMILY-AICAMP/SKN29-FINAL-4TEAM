"""ORM boundary for inquiry creation and subscription ownership checks."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.utils import timezone

from apps.inquiries.models import (
    FollowUpAnswer,
    Inquiry,
    InquiryQA,
    SymptomEntry,
)
from apps.subscriptions.models import CustomerSubscription


class InquiryRepository:
    """Keep create-flow persistence details out of the API and service layer."""

    @staticmethod
    def find_active_owned_subscription(
        *,
        subscription_public_id: UUID,
        actor: Any,
    ) -> CustomerSubscription | None:
        return (
            CustomerSubscription.objects.select_related(
                "customer",
                "customer__user",
                "product_model",
            )
            .filter(
                public_id=subscription_public_id,
                customer__user=actor,
                customer__deleted_at__isnull=True,
                status_code=CustomerSubscription.Status.ACTIVE,
            )
            .first()
        )

    @staticmethod
    def create_inquiry(
        *,
        subscription: CustomerSubscription,
        actor: Any,
        channel_code: str,
        raw_text: str,
        questionnaire_session_public_id: UUID | None,
    ) -> Inquiry:
        return Inquiry.objects.create(
            subscription=subscription,
            initiated_by=actor,
            channel_code=channel_code,
            raw_text=raw_text,
            questionnaire_session_public_id=(
                questionnaire_session_public_id
            ),
            status_code=Inquiry.Status.DRAFT,
            state_version=1,
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
            },
            schema_version="v1",
            is_customer_confirmed=True,
        )

    @staticmethod
    def lock_owned_inquiry(
        *,
        inquiry_public_id: UUID,
        actor: Any,
    ) -> Inquiry | None:
        return (
            Inquiry.objects.select_for_update()
            .select_related(
                "subscription",
                "subscription__customer",
                "subscription__customer__user",
                "subscription__product_model",
            )
            .filter(
                public_id=inquiry_public_id,
                subscription__customer__user=actor,
                subscription__customer__deleted_at__isnull=True,
            )
            .first()
        )

    @staticmethod
    def lock_for_human_review(*, inquiry_id: int) -> Inquiry | None:
        """Lock the aggregate root before applying a review-derived event."""

        return (
            Inquiry.objects.select_for_update(of=("self",))
            .select_related(
                "subscription",
                "subscription__customer",
                "subscription__customer__user",
                "subscription__product_model",
            )
            .filter(pk=inquiry_id)
            .first()
        )

    @staticmethod
    def lock_cancellable_inquiry(
        *,
        inquiry_public_id: UUID,
        actor: Any,
    ) -> Inquiry | None:
        """Lock only the CANCEL_INQUIRY object scope visible to the actor."""

        queryset = Inquiry.objects.select_for_update(of=("self",)).select_related(
            "subscription",
            "subscription__customer",
            "subscription__customer__user",
            "subscription__product_model",
            "assigned_user",
        )
        role = getattr(actor, "role_code", None)
        if role == "CUSTOMER":
            queryset = queryset.filter(
                subscription__customer__user=actor,
                subscription__customer__deleted_at__isnull=True,
            )
        elif role == "CONSULTANT":
            queryset = queryset.filter(
                assigned_user=actor,
                assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
            )
        elif role == "OPERATOR" and actor.has_perm(
            "inquiries.cancel_inquiry"
        ):
            pass
        else:
            return None
        return queryset.filter(public_id=inquiry_public_id).first()

    @staticmethod
    def latest_visit_status(inquiry: Inquiry) -> str | None:
        """Return the newest visit status for workflow snapshot validation."""

        return (
            inquiry.visits.order_by("-created_at")
            .values_list("status", flat=True)
            .first()
        )

    @staticmethod
    def lock_unanswered_questions(
        *,
        inquiry: Inquiry,
        question_public_ids: list[UUID],
    ) -> list[InquiryQA]:
        """Lock only unanswered questions owned by the aggregate."""

        return list(
            InquiryQA.objects.select_for_update(of=("self",))
            .select_related(
                "inquiry__subscription__customer__user",
            )
            .filter(
                inquiry=inquiry,
                public_id__in=question_public_ids,
                customer_answer__isnull=True,
            )
            .order_by("sequence_no")
        )

    @staticmethod
    def create_followup_answer(
        *,
        question: InquiryQA,
        actor: Any,
        answer_text: str | None,
        answer_payload: dict | None,
        accepted_state_version: int,
    ) -> FollowUpAnswer:
        answer = FollowUpAnswer(
            question=question,
            answered_by=actor,
            answer_text=answer_text,
            answer_payload=answer_payload,
            accepted_state_version=accepted_state_version,
        )
        answer.full_clean()
        answer.save()
        return answer

    @staticmethod
    def apply_state_transition(
        inquiry: Inquiry,
        *,
        status_code: str,
        state_version: int,
    ) -> None:
        """Persist only workflow state fields and preserve customer input."""

        inquiry.status_code = status_code
        inquiry.state_version = state_version
        inquiry.save(
            update_fields=[
                "status_code",
                "state_version",
                "updated_at",
            ]
        )

    @staticmethod
    def assign_consultant(
        inquiry: Inquiry,
        *,
        actor: Any,
        state_version: int,
    ) -> None:
        """Assign one unclaimed inquiry without starting consultation work."""

        inquiry.assigned_user = actor
        inquiry.assigned_role_code = Inquiry.AssignedRole.CONSULTANT
        inquiry.state_version = state_version
        inquiry.save(
            update_fields=[
                "assigned_user",
                "assigned_role_code",
                "state_version",
                "updated_at",
            ]
        )

    @staticmethod
    def mark_cancelled(
        inquiry: Inquiry,
        *,
        status_code: str,
        state_version: int,
        reason_code: str,
        reason_detail: str | None,
    ) -> None:
        inquiry.status_code = status_code
        inquiry.state_version = state_version
        inquiry.cancelled_at = timezone.now()
        inquiry.cancellation_reason_code = reason_code
        inquiry.cancellation_reason_detail = reason_detail
        inquiry.save(
            update_fields=[
                "status_code",
                "state_version",
                "cancelled_at",
                "cancellation_reason_code",
                "cancellation_reason_detail",
                "updated_at",
            ]
        )
