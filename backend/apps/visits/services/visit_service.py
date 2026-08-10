"""Visit review, creation, scheduling and confirmation runtime."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.exceptions import NotFound

from apps.consultations.models import Consultation
from apps.consultations.repositories.consultation_repository import (
    ConsultationRepository,
)
from apps.visits.models import Visit
from apps.visits.repositories.visit_repository import VisitRepository
from apps.workflow.services.assigned_consultant_action_service import (
    AssignedConsultantActionService,
    WorkflowActionOutcome,
)


class VisitService:
    """Execute the five DEC-004 operations through one shared boundary."""

    @classmethod
    def request_review(
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
                "G-VISIT-REVIEW-PAYLOAD-VALID": bool(
                    consultation is not None
                    and consultation.outcome
                    == Consultation.Outcome.VISIT_REQUIRED
                    and consultation.confirmed_summary
                    and context["visit"] is None
                )
            }

        def mutation(_inquiry, transition, context):
            return ConsultationRepository.record_visit_review(
                context["consultation"],
                reason_code=validated_data["reason_code"],
                reason_detail=validated_data.get("reason_detail"),
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return cls._execute_inquiry_action(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="requestVisitReview",
            event_code="VISIT_REVIEW_REQUIRED",
            message="방문 필요 여부 검토를 시작했습니다.",
            domain_results=domain_results,
            mutation=mutation,
        )

    @classmethod
    def create_request(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> WorkflowActionOutcome:
        def domain_results(inquiry, context):
            consultation = context["consultation"]
            return {
                "G-VISIT-HANDOFF-COMPLETE": bool(
                    consultation is not None
                    and consultation.outcome
                    == Consultation.Outcome.VISIT_REQUIRED
                    and consultation.confirmed_summary
                    and inquiry.subscription.product_model_id is not None
                    and context["visit"] is None
                    and validated_data.get("handoff")
                )
            }

        def mutation(inquiry, transition, context):
            return VisitRepository.create(
                inquiry=inquiry,
                consultation=context["consultation"],
                actor=actor,
                values=validated_data,
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return cls._execute_inquiry_action(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="createVisitRequest",
            event_code="VISIT_NEEDED",
            message="방문 요청을 생성했습니다.",
            domain_results=domain_results,
            mutation=mutation,
        )

    @classmethod
    def mark_not_needed(
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
                "G-VISIT-NOT-NEEDED-RESULT-COMPLETE": bool(
                    consultation is not None
                    and consultation.outcome
                    == Consultation.Outcome.VISIT_REQUIRED
                    and consultation.confirmed_summary
                    and consultation.summary_confirmed_at is not None
                    and context["visit"] is None
                )
            }

        def mutation(_inquiry, transition, context):
            return ConsultationRepository.mark_visit_not_needed(
                context["consultation"],
                reason_code=validated_data["reason_code"],
                reason_detail=validated_data.get("reason_detail"),
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return cls._execute_inquiry_action(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="markVisitNotNeeded",
            event_code="VISIT_NOT_NEEDED",
            message="방문 불필요 처리를 완료했습니다.",
            domain_results=domain_results,
            mutation=mutation,
        )

    @classmethod
    def update_schedule(
        cls,
        *,
        actor: Any,
        visit_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> WorkflowActionOutcome:
        inquiry_public_id = VisitRepository.find_inquiry_public_id(
            visit_public_id
        )
        if inquiry_public_id is None:
            raise NotFound()

        def context_factory(inquiry):
            visit = VisitRepository.lock_by_public_id(
                inquiry=inquiry,
                visit_public_id=visit_public_id,
            )
            latest = VisitRepository.lock_latest(inquiry)
            technician = VisitRepository.synthetic_technician(
                validated_data["synthetic_technician_id"]
            )
            return {
                "consultation": ConsultationRepository.lock_latest(inquiry),
                "visit": visit,
                "latest_visit": latest,
                "technician": technician,
            }

        def domain_results(_inquiry, context):
            visit = context["visit"]
            latest = context["latest_visit"]
            return {
                "G-VISIT-SCHEDULE-PAYLOAD-VALID": bool(
                    visit is not None
                    and latest is not None
                    and visit.pk == latest.pk
                    and context["technician"] is not None
                )
            }

        def mutation(_inquiry, transition, context):
            return VisitRepository.update_schedule(
                context["visit"],
                technician=context["technician"],
                preferred_date=validated_data["preferred_date"],
                confirmed_date=validated_data["confirmed_date"],
                status=transition.visit_status_after,
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return AssignedConsultantActionService.execute(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            path_parameters={"visit_id": visit_public_id},
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="updateVisitSchedule",
            event_code="UPDATE_VISIT_SCHEDULE",
            message="방문 일정을 저장했습니다.",
            context_factory=context_factory,
            domain_results_factory=domain_results,
            mutation=mutation,
            resource_builder=lambda resource, _context: (
                cls.build_resource(resource)
            ),
        )

    @classmethod
    def confirm(
        cls,
        *,
        actor: Any,
        visit_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> WorkflowActionOutcome:
        inquiry_public_id = VisitRepository.find_inquiry_public_id(
            visit_public_id
        )
        if inquiry_public_id is None:
            raise NotFound()

        def context_factory(inquiry):
            visit = VisitRepository.lock_by_public_id(
                inquiry=inquiry,
                visit_public_id=visit_public_id,
            )
            latest = VisitRepository.lock_latest(inquiry)
            return {
                "consultation": ConsultationRepository.lock_latest(inquiry),
                "visit": visit,
                "latest_visit": latest,
            }

        def domain_results(_inquiry, context):
            visit = context["visit"]
            latest = context["latest_visit"]
            technician_ok = bool(
                visit is not None
                and visit.technician is not None
                and visit.technician.role_code == "TECHNICIAN"
                and visit.technician.is_active
                and visit.technician.is_synthetic
            )
            current_visit = bool(
                visit is not None
                and latest is not None
                and visit.pk == latest.pk
            )
            return {
                "G-CONFIRMED-VISIT-DATE": bool(
                    current_visit and visit.confirmed_date is not None
                ),
                "G-ASSIGNED-TECHNICIAN-PRESENT": bool(
                    current_visit and technician_ok
                ),
            }

        def mutation(_inquiry, transition, context):
            return VisitRepository.confirm(
                context["visit"],
                status=transition.visit_status_after,
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )

        return AssignedConsultantActionService.execute(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            path_parameters={"visit_id": visit_public_id},
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id="confirmVisit",
            event_code="CONFIRM_VISIT",
            message="방문일을 확정했습니다.",
            context_factory=context_factory,
            domain_results_factory=domain_results,
            mutation=mutation,
            resource_builder=lambda resource, _context: (
                cls.build_resource(resource)
            ),
        )

    @classmethod
    def _execute_inquiry_action(
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
                "consultation": ConsultationRepository.lock_latest(inquiry),
                "visit": VisitRepository.lock_latest(inquiry),
            },
            domain_results_factory=domain_results,
            mutation=mutation,
            resource_builder=lambda resource, _context: (
                cls.build_resource(resource)
            ),
        )

    @staticmethod
    def build_resource(resource) -> dict | None:
        if isinstance(resource, Consultation):
            from apps.consultations.services.consultation_service import (
                ConsultationService,
            )

            return ConsultationService.build_resource(resource)
        if not isinstance(resource, Visit):
            return None
        technician = resource.technician
        return {
            "visit_id": str(resource.public_id),
            "inquiry_id": str(resource.inquiry.public_id),
            "schedule": {
                "preferred_date": (
                    resource.preferred_date.isoformat()
                    if resource.preferred_date is not None
                    else None
                ),
                "confirmed_date": (
                    resource.confirmed_date.isoformat()
                    if resource.confirmed_date is not None
                    else None
                ),
                "schedule_status": resource.status,
                "synthetic_technician_id": (
                    str(technician.public_id)
                    if technician is not None
                    else None
                ),
            },
            "technician": (
                {
                    "is_synthetic": True,
                    "technician_id": str(technician.public_id),
                    "display_name": technician.full_name[:80],
                    "phone": technician.phone[:32],
                }
                if technician is not None
                else None
            ),
        }
