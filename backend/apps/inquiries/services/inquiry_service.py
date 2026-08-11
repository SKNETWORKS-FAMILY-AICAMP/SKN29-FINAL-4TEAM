"""Transactional START_INQUIRY application service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.audit.models import AIRun
from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
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
from apps.workflow.repositories.workflow_repository import (
    WorkflowRepository,
)
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import INTERNAL_ERROR, STATE_CONFLICT


START_INQUIRY_OPERATION_ID = "startInquiry"
CANCEL_INQUIRY_OPERATION_ID = "cancelInquiry"
CANCEL_INQUIRY_EVENT_CODE = "CANCEL_INQUIRY"


@dataclass(frozen=True)
class CreateInquiryOutcome:
    """HTTP-independent create result returned to the view."""

    status_code: int
    data: dict


@dataclass(frozen=True)
class CancelInquiryOutcome:
    """HTTP-independent cancel result returned to the view."""

    status_code: int
    data: dict


class InquiryService:
    """Apply START_INQUIRY and representative CANCEL_INQUIRY flows."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        actor: Any,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> CreateInquiryOutcome:
        subscription = (
            InquiryRepository.find_active_owned_subscription(
                subscription_public_id=validated_data[
                    "subscription_id"
                ],
                actor=actor,
            )
        )
        if subscription is None:
            raise NotFound()

        normalized_request = {
            "normalized_path_parameters": {},
            "normalized_request_body": {
                "subscription_id": validated_data["subscription_id"],
                "channel_code": validated_data["channel_code"],
                "raw_text": validated_data["raw_text"],
                "representative_symptom_code": validated_data.get(
                    "representative_symptom_code"
                ),
                "questionnaire_session_id": validated_data.get(
                    "questionnaire_session_id"
                ),
            },
            "target_public_id": subscription.public_id,
        }
        request_hash = IdempotencyService.canonical_request_hash(
            normalized_request
        )

        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=START_INQUIRY_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return CreateInquiryOutcome(
                status_code=status_code,
                data=data,
            )

        try:
            with transaction.atomic():
                idempotency_record = (
                    WorkflowRepository.create_idempotency_record(
                        actor=actor,
                        operation_id=START_INQUIRY_OPERATION_ID,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                )
        except IntegrityError:
            existing = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=START_INQUIRY_OPERATION_ID,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return CreateInquiryOutcome(
                status_code=status_code,
                data=data,
            )

        inquiry = InquiryRepository.create_inquiry(
            subscription=subscription,
            actor=actor,
            channel_code=validated_data["channel_code"],
            raw_text=validated_data["raw_text"],
            questionnaire_session_public_id=validated_data.get(
                "questionnaire_session_id"
            ),
        )

        symptom_code = validated_data.get(
            "representative_symptom_code"
        )
        if symptom_code is not None:
            InquiryRepository.create_representative_symptom(
                inquiry=inquiry,
                symptom_code=symptom_code,
            )

        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
                consultation=None,
                visit=None,
            ),
        )
        data = {
            "inquiry_id": str(inquiry.public_id),
            "inquiry_code": inquiry.inquiry_code,
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "idempotent_replay": False,
            "allowed_actions": allowed_actions,
        }

        TransitionHistoryService.record_start_inquiry(
            inquiry=inquiry,
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=201,
            response_body=data,
            resource_public_id=inquiry.public_id,
        )
        return CreateInquiryOutcome(status_code=201, data=data)

    @classmethod
    @transaction.atomic
    def cancel(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> CancelInquiryOutcome:
        normalized_request = {
            "normalized_path_parameters": {
                "inquiry_id": inquiry_public_id,
            },
            "normalized_request_body": {
                "state_version": validated_data["state_version"],
                "reason_code": validated_data["reason_code"],
                "reason_detail": validated_data.get("reason_detail"),
            },
            "target_public_id": inquiry_public_id,
        }
        request_hash = IdempotencyService.canonical_request_hash(
            normalized_request
        )

        inquiry = InquiryRepository.lock_cancellable_inquiry(
            inquiry_public_id=inquiry_public_id,
            actor=actor,
        )
        if inquiry is None:
            raise NotFound()

        # A concurrent same-key request may complete while this transaction
        # waits for the inquiry row. Re-check before stale-version handling.
        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=CANCEL_INQUIRY_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
                replay_field="idempotent_replay",
            )
            return CancelInquiryOutcome(
                status_code=status_code,
                data=data,
            )

        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        try:
            transition = StateMachine().resolve(
                snapshot=snapshot,
                event_code=CANCEL_INQUIRY_EVENT_CODE,
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
                "The cancellation contract could not be evaluated.",
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
                    "G-CANCEL-ACTOR-AUTHORIZED": True,
                    "G-CANCELLATION-REASON": True,
                },
            ),
        )
        cls._raise_cancel_guard_failure(
            inquiry=inquiry,
            actor=actor,
            guard_result=guard_result,
        )

        try:
            with transaction.atomic():
                idempotency_record = (
                    WorkflowRepository.create_idempotency_record(
                        actor=actor,
                        operation_id=CANCEL_INQUIRY_OPERATION_ID,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                )
        except IntegrityError:
            existing = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=CANCEL_INQUIRY_OPERATION_ID,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
                replay_field="idempotent_replay",
            )
            return CancelInquiryOutcome(
                status_code=status_code,
                data=data,
            )

        InquiryRepository.mark_cancelled(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
            reason_code=validated_data["reason_code"],
            reason_detail=validated_data.get("reason_detail"),
        )
        cls._cancel_active_ai_runs(inquiry)
        TransitionHistoryService.record_cancel_inquiry(
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
            "allowed_actions": cls._allowed_actions(inquiry, actor=actor),
        }
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=200,
            response_body=data,
            resource_public_id=inquiry.public_id,
        )
        return CancelInquiryOutcome(status_code=200, data=data)

    @staticmethod
    def _raise_state_conflict(inquiry: Inquiry, *, actor: Any) -> None:
        allowed_actions = InquiryService._allowed_actions(inquiry, actor=actor)
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

    @staticmethod
    def _allowed_actions(inquiry: Inquiry, *, actor: Any) -> list[dict]:
        return AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
            )
        )

    @classmethod
    def _raise_cancel_guard_failure(
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
                "The cancellation contract could not be evaluated.",
                details={},
                status_code=500,
            )
        if failure.guard_id == "G-STATE-VERSION":
            cls._raise_state_conflict(inquiry, actor=actor)
        if failure.http_status == 404:
            raise NotFound()
        if failure.http_status == 403:
            raise PermissionDenied()
        if failure.http_status == 422:
            raise BusinessError(
                failure.error_code,
                failure.message,
                details={"reason_code": [failure.message]},
                status_code=422,
            )
        raise BusinessError(
            INTERNAL_ERROR,
            "The cancellation contract could not be evaluated.",
            details={},
            status_code=500,
        )

    @staticmethod
    def _cancel_active_ai_runs(inquiry: Inquiry) -> int:
        """Logically cancel active Backend AI runs inside the inquiry tx."""

        runs = AIRun.objects.select_for_update().filter(
            inquiry=inquiry,
            status_code__in={
                AIRun.Status.QUEUED,
                AIRun.Status.RUNNING,
                AIRun.Status.RETRYING,
            },
        )
        completed_at = timezone.now()
        return runs.update(
            status_code=AIRun.Status.CANCELLED,
            completed_at=completed_at,
            error_code="CANCELLED_BY_INQUIRY",
            error_message=None,
            updated_at=completed_at,
        )
