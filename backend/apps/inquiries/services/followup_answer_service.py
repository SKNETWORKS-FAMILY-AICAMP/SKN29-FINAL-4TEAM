"""Transactional CUSTOMER SUBMIT_ANSWERS workflow Slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.inquiries.models import Inquiry, InquiryQA
from apps.inquiries.models.inquiry_qa import public_question_options
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
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import INTERNAL_ERROR, STATE_CONFLICT


EVENT_CODE = "SUBMIT_ANSWERS"
OPERATION_ID = "submitFollowUpAnswers"


@dataclass(frozen=True)
class SubmitFollowUpAnswersOutcome:
    status_code: int
    data: dict


class FollowUpAnswerService:
    """Append validated answers and advance only the inquiry version."""

    @classmethod
    @transaction.atomic
    def submit(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> SubmitFollowUpAnswersOutcome:
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
                cls._raise_state_conflict(inquiry, actor=actor)
            raise BusinessError(
                INTERNAL_ERROR,
                "The workflow contract could not be resolved.",
                details={},
                status_code=500,
            ) from exc

        submitted = validated_data["answers"]
        questions = InquiryRepository.lock_unanswered_questions(
            inquiry=inquiry,
            question_public_ids=[item["question_id"] for item in submitted],
        )
        answers_by_question = {
            item["question_id"]: item for item in submitted
        }
        answers_are_valid = (
            len(questions) == len(submitted)
            and all(
                cls._answer_matches_question(
                    question,
                    answers_by_question[question.public_id],
                )
                for question in questions
            )
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
                    "G-INQUIRY-OWNER": True,
                    "G-FOLLOWUP-ANSWERS-VALID": answers_are_valid,
                },
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

        for question in questions:
            item = answers_by_question[question.public_id]
            InquiryRepository.create_followup_answer(
                question=question,
                actor=actor,
                answer_text=item.get("answer_text"),
                answer_payload=item.get("answer_payload"),
                accepted_state_version=snapshot.state_version,
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
            "message": "Follow-up answers were saved.",
            "inquiry_id": str(inquiry.public_id),
            "status": inquiry.status_code,
            "state_version": inquiry.state_version,
            "allowed_actions": AllowedActionResolver.resolve(
                context=AllowedActionContext.from_models(
                    inquiry=inquiry,
                    actor=actor,
                ),
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
        cls._request_ai_reevaluation_after_commit(
            inquiry_public_id=inquiry.public_id,
            correlation_id=correlation_id,
            ai_request_id=idempotency_record.public_id,
        )
        return SubmitFollowUpAnswersOutcome(200, data)

    @staticmethod
    def _answer_matches_question(
        question: InquiryQA,
        answer: dict,
    ) -> bool:
        if question.answer_type_code == "FREE_TEXT":
            return "answer_text" in answer and "answer_payload" not in answer
        if question.answer_type_code == "SINGLE_CHOICE":
            payload = answer.get("answer_payload")
            return (
                "answer_text" not in answer
                and isinstance(payload, dict)
                and set(payload) == {"selected_option"}
                and payload["selected_option"]
                in public_question_options(question.question_options)
            )
        return False

    @staticmethod
    def _request_ai_reevaluation_after_commit(
        *,
        inquiry_public_id: UUID,
        correlation_id: UUID,
        ai_request_id: UUID,
    ) -> None:
        """Apply TR-INQ-003's AI effect only after durable answer commit."""

        def request_ai_reevaluation() -> None:
            # Local import avoids coupling the transactional write module to
            # AI client construction during module import.
            from apps.inquiries.services.inquiry_ai_service import (
                InquiryAIService,
            )

            InquiryAIService.analyze_inquiry(
                inquiry_public_id=inquiry_public_id,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
            )

        transaction.on_commit(request_ai_reevaluation, robust=True)

    @staticmethod
    def _replay(
        *,
        actor: Any,
        idempotency_key: str,
        request_hash: str,
    ) -> SubmitFollowUpAnswersOutcome | None:
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
        return SubmitFollowUpAnswersOutcome(status_code, data)

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
                "The request could not be processed.",
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
                details={"answers": [failure.message]},
                status_code=422,
            )
        raise BusinessError(
            INTERNAL_ERROR,
            "The request could not be processed.",
            details={},
            status_code=500,
        )

    @staticmethod
    def _raise_state_conflict(inquiry: Inquiry, *, actor: Any) -> None:
        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
            ),
        )
        raise BusinessError(
            STATE_CONFLICT,
            "The inquiry state has changed.",
            details={
                "current_status": inquiry.status_code,
                "current_state_version": inquiry.state_version,
                "allowed_actions": [
                    action["code"] for action in allowed_actions
                ],
            },
            status_code=409,
        )
