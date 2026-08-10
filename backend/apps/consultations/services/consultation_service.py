"""Consultation start, explicit save, confirm and completion runtime."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.consultations.models import Consultation
from apps.consultations.repositories.consultation_repository import (
    ConsultationRepository,
)
from apps.inquiries.models import Inquiry
from apps.workflow.services.assigned_consultant_action_service import (
    AssignedConsultantActionService,
    WorkflowActionOutcome,
)


class ConsultationService:
    """Execute the four DEC-003 operations through one shared boundary."""

    @classmethod
    def start(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> WorkflowActionOutcome:
        return cls._execute(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="startConsultation",
            event_code="START_CONSULTATION",
            message="상담을 시작했습니다.",
            domain_results=lambda _inquiry, _context: {},
            mutation=lambda inquiry, transition, context: (
                ConsultationRepository.start(
                    inquiry=inquiry,
                    actor=actor,
                    state_version=transition.state_version_after,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                    current=context["consultation"],
                )
            ),
        )

    @classmethod
    def save_summary(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> WorkflowActionOutcome:
        def domain_results(_inquiry, context):
            return {
                "G-CONSULTATION-SUMMARY-PAYLOAD-VALID": (
                    context["consultation"] is not None
                    and bool(set(validated_data) - {"state_version"})
                )
            }

        def mutation(_inquiry, transition, context):
            return ConsultationRepository.save_summary(
                context["consultation"],
                values=validated_data,
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return cls._execute(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="updateConsultationSummary",
            event_code="UPDATE_CONSULTATION_SUMMARY",
            message="상담 내용을 저장했습니다.",
            domain_results=domain_results,
            mutation=mutation,
        )

    @classmethod
    def confirm_summary(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> WorkflowActionOutcome:
        def domain_results(_inquiry, context):
            consultation = context["consultation"]
            return {
                "G-CONSULTATION-SUMMARY-CONFIRMABLE": bool(
                    consultation is not None
                    and consultation.summary.strip()
                    and consultation.summary_confirmed_at is None
                )
            }

        def mutation(_inquiry, transition, context):
            return ConsultationRepository.confirm_summary(
                context["consultation"],
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return cls._execute(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="confirmConsultationSummary",
            event_code="CONFIRM_CONSULTATION_SUMMARY",
            message="상담 요약을 확정했습니다.",
            domain_results=domain_results,
            mutation=mutation,
        )

    @classmethod
    def complete(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> WorkflowActionOutcome:
        def domain_results(_inquiry, context):
            consultation = context["consultation"]
            return {
                "G-CONSULTATION-RESULT-COMPLETE": bool(
                    consultation is not None
                    and consultation.outcome
                    in {
                        Consultation.Outcome.COMPLETED_NO_VISIT,
                        Consultation.Outcome.VISIT_REQUIRED,
                        Consultation.Outcome.REOPENED_FOLLOWUP,
                    }
                    and consultation.confirmed_summary
                    and consultation.summary_confirmed_at is not None
                    and consultation.completed_at is None
                )
            }

        def mutation(_inquiry, transition, context):
            return ConsultationRepository.complete(
                context["consultation"],
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return cls._execute(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="completeConsultation",
            event_code="CONSULTATION_COMPLETED",
            message="상담 처리를 완료했습니다.",
            domain_results=domain_results,
            mutation=mutation,
        )

    @classmethod
    def _execute(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
        operation_id: str,
        event_code: str,
        message: str,
        domain_results,
        mutation,
    ) -> WorkflowActionOutcome:
        return AssignedConsultantActionService.execute(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            path_parameters={"inquiry_id": inquiry_public_id},
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id=operation_id,
            event_code=event_code,
            message=message,
            context_factory=lambda inquiry: {
                "consultation": ConsultationRepository.lock_latest(inquiry)
            },
            domain_results_factory=domain_results,
            mutation=mutation,
            resource_builder=lambda resource, _context: (
                cls.build_resource(resource)
            ),
        )

    @staticmethod
    def build_resource(consultation: Consultation | None) -> dict | None:
        if consultation is None:
            return None
        return {
            "consultation_id": str(consultation.public_id),
            "result_code": consultation.outcome,
            "summary": {
                "ai_draft_summary": consultation.ai_draft_summary,
                "edited_summary": consultation.summary or None,
                "confirmed_summary": consultation.confirmed_summary,
                "confirmed_at": (
                    consultation.summary_confirmed_at.isoformat()
                    if consultation.summary_confirmed_at is not None
                    else None
                ),
            },
            "consultation_note": consultation.consultation_note,
            "additional_check": consultation.additional_check,
            "customer_guidance": consultation.customer_guidance,
            "usage_guidance_status": (
                consultation.usage_guidance_status
            ),
        }
