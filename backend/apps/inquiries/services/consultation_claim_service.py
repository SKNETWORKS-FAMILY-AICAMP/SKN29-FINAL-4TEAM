"""Atomic consultant Claim for the approved unassigned waiting queue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.consultations.models import Consultation
from apps.consultations.repositories.consultation_repository import (
    ConsultationRepository,
)
from apps.inquiries.models import Inquiry
from apps.inquiries.p1_team_routing import P1TeamConsultantRouting
from apps.inquiries.repositories.consultant_inquiry_repository import (
    ConsultantInquiryRepository,
)
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from apps.workflow.engine.guard_evaluator import GuardContext, GuardEvaluator
from apps.workflow.engine.state_machine import InvalidStateTransition, StateMachine
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import INTERNAL_ERROR, STATE_CONFLICT


EVENT_CODE = "CLAIM_CONSULTATION"
OPERATION_ID = "claimConsultation"
EXPECTED_EFFECTS = {
    "ASSIGN_CURRENT_CONSULTANT",
    "ASSIGN_WAITING_CONSULTATION",
}


@dataclass(frozen=True)
class ConsultationClaimOutcome:
    status_code: int
    data: dict


class ConsultationClaimService:
    """Claim one queue item without starting the actual consultation."""

    @classmethod
    @transaction.atomic
    def claim(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> ConsultationClaimOutcome:
        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": {
                    "inquiry_id": inquiry_public_id,
                },
                "normalized_request_body": validated_data,
                "target_public_id": inquiry_public_id,
            }
        )
        inquiry = ConsultantInquiryRepository.lock_claimable(
            inquiry_public_id
        )
        if inquiry is None:
            raise NotFound()
        if not P1TeamConsultantRouting.can_access_contract(
            actor=actor,
            contract_no=inquiry.subscription.contract_no,
        ):
            raise NotFound()

        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None and (
            existing.request_hash == request_hash
            or existing.resource_public_id == inquiry.public_id
        ):
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return ConsultationClaimOutcome(status_code, data)

        consultation = ConsultationRepository.lock_latest(inquiry)
        if not cls._is_claimable(inquiry, consultation):
            # The dedicated queue is visible, but full unassigned/other-user
            # detail remains concealed after another consultant wins.
            raise NotFound()
        if existing is not None:
            # A key used for another target may return 409 only when this
            # target is independently visible in the unassigned queue.
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return ConsultationClaimOutcome(status_code, data)

        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        try:
            transition = StateMachine().resolve(
                snapshot=snapshot,
                event_code=EVENT_CODE,
            )
        except InvalidStateTransition as exc:
            raise NotFound() from exc
        if not EXPECTED_EFFECTS.issubset(set(transition.effects)):
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            )

        guard_result = GuardEvaluator().evaluate(
            transition=transition,
            snapshot=snapshot,
            context=GuardContext(
                actor_role=actor.role_code,
                is_authenticated=bool(actor.is_authenticated),
                correlation_id=str(correlation_id),
                idempotency_key=idempotency_key,
                requested_state_version=validated_data["state_version"],
                domain_results={
                    "G-UNASSIGNED-CONSULTATION-CLAIMABLE": True,
                },
            ),
        )
        cls._raise_guard_failure(
            inquiry=inquiry,
            actor=actor,
            consultation=consultation,
            guard_result=guard_result,
        )

        try:
            with transaction.atomic():
                idempotency_record = (
                    WorkflowRepository.create_idempotency_record(
                        actor=actor,
                        operation_id=OPERATION_ID,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                )
        except IntegrityError:
            existing = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=OPERATION_ID,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return ConsultationClaimOutcome(status_code, data)

        InquiryRepository.assign_consultant(
            inquiry,
            actor=actor,
            state_version=transition.state_version_after,
        )
        consultation = ConsultationRepository.claim(
            consultation,
            actor=actor,
            state_version=transition.state_version_after,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        if transition.record_business_event:
            TransitionHistoryService.record_inquiry_action(
                inquiry=inquiry,
                transition=transition,
                actor=actor,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )
        data = {
            "message": "상담 대기 문의를 배정받았습니다.",
            "inquiry_id": str(inquiry.public_id),
            "status": inquiry.status_code,
            "state_version": inquiry.state_version,
            "allowed_actions": AllowedActionResolver.resolve(
                context=AllowedActionContext.from_models(
                    inquiry=inquiry,
                    actor=actor,
                    consultation=consultation,
                )
            ),
            "idempotent_replay": False,
            "resource": None,
        }
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=200,
            response_body=data,
            resource_public_id=inquiry.public_id,
        )
        return ConsultationClaimOutcome(200, data)

    @staticmethod
    def _is_claimable(
        inquiry: Inquiry,
        consultation: Consultation | None,
    ) -> bool:
        return bool(
            inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
            and inquiry.assigned_user_id is None
            and inquiry.assigned_role_code == Inquiry.AssignedRole.NONE
            and consultation is not None
            and consultation.status == Consultation.Status.WAITING
            and consultation.consultant_id is None
            and consultation.started_at is None
        )

    @classmethod
    def _raise_guard_failure(
        cls,
        *,
        inquiry: Inquiry,
        actor: Any,
        consultation: Consultation,
        guard_result: Any,
    ) -> None:
        if guard_result.allowed:
            return
        failure = guard_result.failure
        if failure is None:
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            )
        if failure.guard_id == "G-STATE-VERSION":
            cls._raise_state_conflict(
                inquiry,
                actor=actor,
                consultation=consultation,
            )
        if failure.http_status == 404:
            raise NotFound()
        if failure.http_status == 403:
            raise PermissionDenied()
        raise BusinessError(
            failure.error_code,
            failure.message,
            details={},
            status_code=failure.http_status,
        )

    @staticmethod
    def _raise_state_conflict(
        inquiry: Inquiry,
        *,
        actor: Any,
        consultation: Consultation,
    ) -> None:
        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
                consultation=consultation,
            )
        )
        raise BusinessError(
            STATE_CONFLICT,
            "다른 사용자가 문의 상태를 먼저 변경했습니다.",
            details={
                "current_status": inquiry.status_code,
                "current_state_version": inquiry.state_version,
                "allowed_actions": [
                    action["code"] for action in allowed_actions
                ],
            },
            status_code=409,
        )
