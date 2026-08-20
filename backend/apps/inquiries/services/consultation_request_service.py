"""Transactional CUSTOMER REQUEST_CONSULTATION workflow Slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.consultations.repositories.consultation_repository import (
    ConsultationRepository,
)
from apps.consultations.repositories.consultation_handoff_repository import (
    ConsultationHandoffRepository,
)
from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.inquiries.services.synthetic_e2e_assignment_service import (
    SyntheticE2EAssignmentService,
)
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from apps.workflow.engine.guard_evaluator import GuardContext, GuardEvaluator
from apps.workflow.engine.state_machine import (
    InvalidStateTransition,
    StateMachine,
)
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import INTERNAL_ERROR, STATE_CONFLICT


EVENT_CODE = "REQUEST_CONSULTATION"
OPERATION_ID = "requestConsultation"


@dataclass(frozen=True)
class RequestConsultationOutcome:
    status_code: int
    data: dict


class ConsultationRequestService:
    """Upsert one waiting consultation and advance the owned inquiry."""

    @classmethod
    @transaction.atomic
    def request(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> RequestConsultationOutcome:
        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": {
                    "inquiry_id": inquiry_public_id,
                },
                "normalized_request_body": validated_data,
                "target_public_id": inquiry_public_id,
            }
        )
        inquiry = InquiryRepository.lock_owned_inquiry(
            inquiry_public_id=inquiry_public_id,
            actor=actor,
        )
        if inquiry is None:
            raise NotFound()

        replay = cls._replay(
            actor=actor,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay is not None:
            return replay

        current_consultation = ConsultationRepository.lock_latest(inquiry)
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
            if exc.reason in {
                "TERMINAL_STATE",
                "UNLISTED_TRANSITION",
                "VISIT_STATE_MISMATCH",
            }:
                cls._raise_state_conflict(
                    inquiry,
                    actor=actor,
                    consultation=current_consultation,
                )
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            ) from exc

        if "UPSERT_CONSULTATION_REQUEST" not in transition.effects:
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
                domain_results={"G-INQUIRY-OWNER": True},
            ),
        )
        cls._raise_guard_failure(
            inquiry=inquiry,
            actor=actor,
            consultation=current_consultation,
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
            replay = cls._replay(
                actor=actor,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if replay is None:
                raise
            return replay

        SyntheticE2EAssignmentService.assign_if_marked(inquiry)
        consultation = ConsultationRepository.request(
            inquiry=inquiry,
            state_version=transition.state_version_after,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            current=current_consultation,
        )
        ConsultationHandoffRepository.attach_to_latest_consultation(
            inquiry=inquiry,
            consultation=consultation,
        )
        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
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
            "message": "상담 요청이 접수되었습니다.",
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
        return RequestConsultationOutcome(200, data)

    @staticmethod
    def _replay(
        *,
        actor: Any,
        idempotency_key: str,
        request_hash: str,
    ) -> RequestConsultationOutcome | None:
        record = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if record is None:
            return None
        status_code, data = IdempotencyService.replay_or_conflict(
            record,
            request_hash=request_hash,
        )
        return RequestConsultationOutcome(status_code, data)

    @classmethod
    def _raise_guard_failure(
        cls,
        *,
        inquiry: Inquiry,
        actor: Any,
        consultation: Any,
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
        consultation: Any,
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
