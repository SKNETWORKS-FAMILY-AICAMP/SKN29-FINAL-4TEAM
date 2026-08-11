"""Transactional inquiry transitions backed by the PM state contract."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.allowed_action_resolver import AllowedActionResolver
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
from common.exceptions.error_codes import (
    INTERNAL_ERROR,
    STATE_CONFLICT,
    VALIDATION_ERROR,
)


SUBMIT_SYMPTOM_EVENT_CODE = "SUBMIT_SYMPTOM"
SUBMIT_SYMPTOM_OPERATION_ID = "submitSymptom"
ai_trace_logger = logging.getLogger("watercare.ai")


@dataclass(frozen=True)
class SubmitSymptomOutcome:
    """HTTP-independent SUBMIT_SYMPTOM result returned to the view."""

    status_code: int
    data: dict


class InquiryTransitionService:
    """Apply one approved inquiry transition per atomic transaction."""

    @classmethod
    @transaction.atomic
    def submit_symptom(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> SubmitSymptomOutcome:
        normalized_request = {
            "normalized_path_parameters": {
                "inquiry_id": inquiry_public_id,
            },
            "normalized_request_body": {
                "state_version": validated_data["state_version"],
            },
            "target_public_id": inquiry_public_id,
        }
        request_hash = IdempotencyService.canonical_request_hash(
            normalized_request
        )

        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=SUBMIT_SYMPTOM_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return SubmitSymptomOutcome(status_code=status_code, data=data)

        inquiry = InquiryRepository.lock_owned_inquiry(
            inquiry_public_id=inquiry_public_id,
            actor=actor,
        )
        if inquiry is None:
            raise NotFound()

        # The inquiry lock can wait for another request to commit. Re-check
        # the key so the waiter returns Replay instead of a stale-state 409.
        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=SUBMIT_SYMPTOM_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return SubmitSymptomOutcome(status_code=status_code, data=data)

        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        try:
            transition = StateMachine().resolve(
                snapshot=snapshot,
                event_code=SUBMIT_SYMPTOM_EVENT_CODE,
            )
        except InvalidStateTransition as exc:
            # Terminal/unlisted actions are expected client state conflicts.
            # Contract ambiguity, invalid version rules, or inquiry/visit
            # inconsistency are server integrity failures and must not invite
            # a client to retry the same action indefinitely.
            if exc.reason in {"TERMINAL_STATE", "UNLISTED_TRANSITION"}:
                cls._raise_state_conflict(inquiry, actor=actor)
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            ) from exc

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
                    "G-INQUIRY-OWNER": True,
                    "G-SYMPTOM-PAYLOAD-VALID": (
                        cls._symptom_payload_is_valid(inquiry)
                    ),
                },
            ),
        )
        if not guard_result.allowed:
            failure = guard_result.failure
            if failure is None:
                raise BusinessError(
                    INTERNAL_ERROR,
                    "요청 처리 중 오류가 발생했습니다.",
                    details={},
                    status_code=500,
                )
            if failure.guard_id == "G-STATE-VERSION":
                cls._raise_state_conflict(inquiry, actor=actor)
            if failure.http_status == 422:
                raise BusinessError(
                    VALIDATION_ERROR,
                    "입력값을 확인해 주세요.",
                    details={"symptom": [failure.message]},
                    status_code=422,
                )
            if failure.http_status == 404:
                raise NotFound()
            if failure.http_status == 403:
                raise PermissionDenied()
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            )

        try:
            with transaction.atomic():
                idempotency_record = (
                    WorkflowRepository.create_idempotency_record(
                        actor=actor,
                        operation_id=SUBMIT_SYMPTOM_OPERATION_ID,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                )
        except IntegrityError:
            existing = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=SUBMIT_SYMPTOM_OPERATION_ID,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return SubmitSymptomOutcome(status_code=status_code, data=data)

        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
        )
        TransitionHistoryService.record_submit_symptom(
            inquiry=inquiry,
            transition=transition,
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        data = {
            "inquiry_id": str(inquiry.public_id),
            "state": inquiry.status_code,
            "state_version": inquiry.state_version,
            "idempotent_replay": False,
            "allowed_actions": AllowedActionResolver.resolve(
                state_code=inquiry.status_code,
                role_code=actor.role_code,
            ),
        }
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=200,
            response_body=data,
            resource_public_id=inquiry.public_id,
        )
        cls._request_ai_structuring_after_commit(
            inquiry_public_id=inquiry.public_id,
            correlation_id=correlation_id,
            ai_request_id=idempotency_record.public_id,
        )
        return SubmitSymptomOutcome(status_code=200, data=data)

    @staticmethod
    def _request_ai_structuring_after_commit(
        *,
        inquiry_public_id: UUID,
        correlation_id: UUID,
        ai_request_id: UUID,
    ) -> None:
        """Apply TR-INQ-002's AI effect only after durable symptom commit."""

        def request_ai_structuring() -> None:
            # Keep the transactional transition module independent from AI
            # client construction until the durable callback actually runs.
            from apps.inquiries.services.inquiry_ai_service import (
                InquiryAIOutcome,
                InquiryAIService,
            )

            trace = {
                "correlation_id": str(correlation_id),
                "inquiry_id": str(inquiry_public_id),
                "ai_request_id": str(ai_request_id),
            }
            ai_trace_logger.info(
                "ai_callback_started",
                extra={**trace, "trace_stage": "CALLBACK_STARTED"},
            )
            try:
                outcome = InquiryAIService.analyze_inquiry(
                    inquiry_public_id=inquiry_public_id,
                    correlation_id=correlation_id,
                    ai_request_id=ai_request_id,
                )
            except Exception:
                # The durable business commit has already completed.  Do not
                # re-raise into Django's on_commit logger because an exception
                # message may contain customer input or an upstream payload.
                ai_trace_logger.error(
                    "ai_callback_failed_unexpected",
                    extra={
                        **trace,
                        "trace_stage": "CALLBACK_FAILED_UNEXPECTED",
                        "failure_code": "UNEXPECTED_CALLBACK_ERROR",
                    },
                )
                return

            completion = {**trace, "trace_stage": "CALLBACK_COMPLETED"}
            if isinstance(outcome, InquiryAIOutcome):
                completion.update(
                    {
                        "ai_run_id": outcome.ai_run_id,
                        "ai_status": outcome.status,
                        "event_candidate": outcome.event_candidate,
                        "event_applied": outcome.event_applied,
                        "pending_reason": outcome.pending_reason,
                        "idempotent_replay": outcome.idempotent_replay,
                        "stale": outcome.stale,
                    }
                )
            ai_trace_logger.info(
                "ai_callback_completed",
                extra=completion,
            )

        transaction.on_commit(request_ai_structuring, robust=True)

    @staticmethod
    def _symptom_payload_is_valid(inquiry: Inquiry) -> bool:
        raw_text = inquiry.raw_text
        normalized_text = (
            raw_text.strip() if isinstance(raw_text, str) else ""
        )
        subscription = inquiry.subscription
        return (
            2 <= len(normalized_text) <= 2000
            and subscription.product_model_id is not None
            and subscription.status_code
            == CustomerSubscription.Status.ACTIVE
        )

    @staticmethod
    def _raise_state_conflict(inquiry: Inquiry, *, actor: Any) -> None:
        allowed_actions = AllowedActionResolver.resolve(
            state_code=inquiry.status_code,
            role_code=actor.role_code,
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
