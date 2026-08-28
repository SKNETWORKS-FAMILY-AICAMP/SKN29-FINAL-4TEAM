"""Transactional T-023 resolution, finalization, and reopen service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.consultations.repositories.consultation_repository import (
    ConsultationRepository,
)
from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.inquiries.repositories.resolution_repository import (
    CompletedHandling,
    ResolutionRepository,
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


@dataclass(frozen=True)
class ResolutionOutcome:
    status_code: int
    data: dict


@dataclass(frozen=True)
class ActionConfig:
    operation_id: str
    event_code: str
    message: str
    scope: str
    required_effect: str


ACTION_CONFIGS = {
    "feedback": ActionConfig(
        operation_id="submitResolutionFeedback",
        event_code="SUBMIT_RESOLUTION_FEEDBACK",
        message="해결 피드백이 저장되었습니다.",
        scope="OWNER",
        required_effect="STORE_RESOLVED_CUSTOMER_FEEDBACK",
    ),
    "unresolved": ActionConfig(
        operation_id="reportUnresolved",
        event_code="CUSTOMER_REPORTED_UNRESOLVED",
        message="미해결 보고로 문의가 다시 열렸습니다.",
        scope="OWNER",
        required_effect="STORE_UNRESOLVED_CUSTOMER_FEEDBACK",
    ),
    "resume": ActionConfig(
        operation_id="resumeConsultation",
        event_code="RESUME_CONSULTATION",
        message="재개 문의가 상담 대기열로 복귀했습니다.",
        scope="ASSIGNED_CONSULTANT",
        required_effect="RESTORE_TO_CONSULTATION_QUEUE",
    ),
    "finalize": ActionConfig(
        operation_id="finalizeInquiry",
        event_code="FINALIZE_INQUIRY",
        message="문의가 최종 완료되었습니다.",
        scope="STAFF",
        required_effect="SET_RESOLVED_AT",
    ),
}


class ResolutionService:
    """Apply the approved completion policy without client-owned shortcuts."""

    @classmethod
    def submit_feedback(cls, **kwargs) -> ResolutionOutcome:
        return cls._execute(action="feedback", **kwargs)

    @classmethod
    def report_unresolved(cls, **kwargs) -> ResolutionOutcome:
        return cls._execute(action="unresolved", **kwargs)

    @classmethod
    def resume_consultation(cls, **kwargs) -> ResolutionOutcome:
        return cls._execute(action="resume", **kwargs)

    @classmethod
    def finalize(cls, **kwargs) -> ResolutionOutcome:
        return cls._execute(action="finalize", **kwargs)

    @classmethod
    @transaction.atomic
    def _execute(
        cls,
        *,
        action: str,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> ResolutionOutcome:
        config = ACTION_CONFIGS[action]
        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": {
                    "inquiry_id": inquiry_public_id,
                },
                "normalized_request_body": validated_data,
                "target_public_id": inquiry_public_id,
            }
        )
        inquiry = cls._lock_inquiry(
            config=config,
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if inquiry is None:
            raise NotFound()

        replay = cls._replay(
            actor=actor,
            operation_id=config.operation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay is not None:
            return replay

        handling = (
            None
            if action == "resume"
            else ResolutionRepository.lock_completed_handling(inquiry)
        )
        if action != "resume" and handling is None:
            raise BusinessError(
                "COMPLETION_SOURCE_REQUIRED",
                "완료 처리 원본을 확인할 수 없습니다.",
                details={},
                status_code=422,
            )

        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        try:
            transition = StateMachine().resolve(
                snapshot=snapshot,
                event_code=config.event_code,
            )
        except InvalidStateTransition as exc:
            if exc.reason in {
                "TERMINAL_STATE",
                "UNLISTED_TRANSITION",
                "VISIT_STATE_MISMATCH",
            }:
                cls._raise_state_conflict(inquiry, actor=actor)
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            ) from exc
        if config.required_effect not in transition.effects:
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
                domain_results=cls._domain_results(
                    action=action,
                    actor=actor,
                    inquiry=inquiry,
                    handling=handling,
                ),
            ),
        )
        cls._raise_guard_failure(
            inquiry=inquiry,
            actor=actor,
            guard_result=guard_result,
        )

        try:
            with transaction.atomic():
                idempotency_record = (
                    WorkflowRepository.create_idempotency_record(
                        actor=actor,
                        operation_id=config.operation_id,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                )
        except IntegrityError:
            replay = cls._replay(
                actor=actor,
                operation_id=config.operation_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            if replay is None:
                raise
            return replay

        resource = cls._mutate(
            action=action,
            inquiry=inquiry,
            actor=actor,
            handling=handling,
            transition_state_version=transition.state_version_after,
            validated_data=validated_data,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
        )
        if transition.record_inquiry_state_history:
            TransitionHistoryService.record_inquiry_action(
                inquiry=inquiry,
                transition=transition,
                actor=actor,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                change_reason=cls._change_reason(
                    action=action,
                    validated_data=validated_data,
                    handling=handling,
                ),
            )

        data = {
            "message": config.message,
            "inquiry_id": str(inquiry.public_id),
            "status": inquiry.status_code,
            "state_version": inquiry.state_version,
            "allowed_actions": AllowedActionResolver.resolve(
                context=AllowedActionContext.from_models(
                    inquiry=inquiry,
                    actor=actor,
                )
            ),
            "idempotent_replay": False,
            "resource": None,
        }
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=200,
            response_body=data,
            resource_public_id=getattr(
                resource,
                "public_id",
                inquiry.public_id,
            ),
        )
        return ResolutionOutcome(200, data)

    @staticmethod
    def _lock_inquiry(
        *,
        config: ActionConfig,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> Inquiry | None:
        if config.scope == "OWNER":
            return InquiryRepository.lock_owned_inquiry(
                inquiry_public_id=inquiry_public_id,
                actor=actor,
            )
        if config.scope == "ASSIGNED_CONSULTANT":
            return ResolutionRepository.lock_assigned_consultant_inquiry(
                inquiry_public_id=inquiry_public_id,
                actor=actor,
            )
        return ResolutionRepository.lock_staff_inquiry(
            inquiry_public_id=inquiry_public_id,
        )

    @staticmethod
    def _domain_results(
        *,
        action: str,
        actor: Any,
        inquiry: Inquiry,
        handling: CompletedHandling | None,
    ) -> dict[str, bool]:
        if action == "feedback":
            assert handling is not None
            return {
                "G-INQUIRY-OWNER": True,
                "G-NO-FRESH-RESOLVED-CUSTOMER-FEEDBACK": (
                    not ResolutionRepository.fresh_resolved_feedback_exists(
                        inquiry=inquiry,
                        handling=handling,
                    )
                ),
                "G-RESOLUTION-FEEDBACK-RESOLVED": True,
            }
        if action == "unresolved":
            return {
                "G-INQUIRY-OWNER": True,
                # The confirmed OpenAPI contract intentionally restricts only
                # the format until the official reason registry is approved.
                "G-UNRESOLVED-FEEDBACK-VALID": True,
            }
        if action == "finalize":
            assert handling is not None
            return {
                "G-ACTOR-LAST-HANDLER": (
                    handling.handler is not None
                    and handling.handler.pk == actor.pk
                    and handling.handler.role_code == actor.role_code
                ),
                "G-RESOLVED-CUSTOMER-FEEDBACK-EXISTS": (
                    ResolutionRepository.fresh_resolved_feedback_exists(
                        inquiry=inquiry,
                        handling=handling,
                    )
                ),
                "G-FINALIZATION-PAYLOAD-VALID": True,
            }
        return {}

    @staticmethod
    def _mutate(
        *,
        action: str,
        inquiry: Inquiry,
        actor: Any,
        handling: CompletedHandling | None,
        transition_state_version: int,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> Any:
        if action == "feedback":
            assert handling is not None
            return ResolutionRepository.create_resolved_feedback(
                inquiry=inquiry,
                handling=handling,
                state_version=transition_state_version,
                comment=validated_data.get("comment"),
            )
        if action == "unresolved":
            assert handling is not None
            followup = ResolutionRepository.create_unresolved_feedback(
                inquiry=inquiry,
                handling=handling,
                state_version=transition_state_version,
                reason_code=validated_data.get("reason_code"),
                comment=validated_data.get("comment"),
            )
            return followup
        if action == "resume":
            current = ConsultationRepository.lock_latest(inquiry)
            return ConsultationRepository.request(
                inquiry=inquiry,
                state_version=transition_state_version,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                current=current,
            )
        assert handling is not None
        return inquiry

    @staticmethod
    def _change_reason(
        *,
        action: str,
        validated_data: dict,
        handling: CompletedHandling | None,
    ) -> str | None:
        if action == "finalize":
            assert handling is not None
            final_note = validated_data.get("final_note")
            if final_note:
                return f"{handling.source_code} | {final_note}"
            return handling.source_code
        if action == "unresolved":
            return validated_data.get("reason_code") or validated_data.get(
                "comment"
            )
        return None

    @staticmethod
    def _replay(
        *,
        actor: Any,
        operation_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> ResolutionOutcome | None:
        record = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
        )
        if record is None:
            return None
        status_code, data = IdempotencyService.replay_or_conflict(
            record,
            request_hash=request_hash,
        )
        return ResolutionOutcome(status_code, data)

    @classmethod
    def _raise_guard_failure(
        cls,
        *,
        inquiry: Inquiry,
        actor: Any,
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
        if failure.guard_id in {
            "G-STATE-VERSION",
            "G-NO-FRESH-RESOLVED-CUSTOMER-FEEDBACK",
        }:
            cls._raise_state_conflict(inquiry, actor=actor)
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
    def _raise_state_conflict(inquiry: Inquiry, *, actor: Any) -> None:
        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
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
