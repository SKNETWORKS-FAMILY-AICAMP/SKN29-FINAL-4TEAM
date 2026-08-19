"""Transactional CARE_PRECHECK lifecycle service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.questionnaires.models import QuestionnaireSession
from apps.questionnaires.repositories.questionnaire_repository import (
    QuestionnaireRepository,
)
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import STATE_CONFLICT


START_CARE_PRECHECK_OPERATION_ID = "startCarePrecheck"
SAVE_CARE_PRECHECK_OPERATION_ID = "saveCarePrecheck"
SUBMIT_CARE_PRECHECK_OPERATION_ID = "submitCarePrecheck"
CARE_PRECHECK_VERSION = "CARE_PRECHECK-v1"


@dataclass(frozen=True)
class CarePrecheckOutcome:
    status_code: int
    data: dict


class QuestionnaireService:
    """Create, recover, save, and submit customer precheck sessions."""

    @classmethod
    @transaction.atomic
    def start(
        cls,
        *,
        actor: Any,
        subscription_public_id: UUID,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> CarePrecheckOutcome:
        subscription = QuestionnaireRepository.find_active_owned_subscription(
            subscription_public_id=subscription_public_id,
            actor=actor,
        )
        if subscription is None:
            raise NotFound()

        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": {},
                "normalized_request_body": {
                    "subscription_id": subscription_public_id,
                },
                "target_public_id": subscription.public_id,
            }
        )
        record, replay = cls._begin_idempotent_operation(
            actor=actor,
            operation_id=START_CARE_PRECHECK_OPERATION_ID,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay is not None:
            return replay
        assert record is not None

        persisted_creation_key = IdempotencyService.canonical_request_hash(
            {
                "actor_public_id": actor.public_id,
                "operation_id": START_CARE_PRECHECK_OPERATION_ID,
                "idempotency_key": idempotency_key,
            }
        )
        session = QuestionnaireSession(
            session_no=f"QSN-{uuid4().hex.upper()}",
            subscription=subscription,
            questionnaire_version=CARE_PRECHECK_VERSION,
            creation_idempotency_key=persisted_creation_key,
        )
        session.full_clean()
        session.save()
        TransitionHistoryService.record_questionnaire_action(
            questionnaire_session=session,
            actor=actor,
            event_code="START_CARE_PRECHECK",
            from_state=None,
            to_state=session.status_code,
            state_version=session.state_version,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        data = cls._serialize(session, idempotent_replay=False)
        WorkflowRepository.complete_idempotency_record(
            record,
            response_status=201,
            response_body=data,
            resource_public_id=session.public_id,
        )
        return CarePrecheckOutcome(status_code=201, data=data)

    @classmethod
    def get(
        cls,
        *,
        actor: Any,
        session_public_id: UUID,
    ) -> dict:
        session = QuestionnaireRepository.get_owned_session(
            session_public_id=session_public_id,
            actor=actor,
        )
        if session is None:
            raise NotFound()
        return cls._serialize(session)

    @classmethod
    @transaction.atomic
    def save(
        cls,
        *,
        actor: Any,
        session_public_id: UUID,
        state_version: int,
        answers: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> CarePrecheckOutcome:
        return cls._mutate(
            actor=actor,
            session_public_id=session_public_id,
            state_version=state_version,
            answers=answers,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id=SAVE_CARE_PRECHECK_OPERATION_ID,
            event_code="SAVE_CARE_PRECHECK",
            target_status=QuestionnaireSession.Status.IN_PROGRESS,
        )

    @classmethod
    @transaction.atomic
    def submit(
        cls,
        *,
        actor: Any,
        session_public_id: UUID,
        state_version: int,
        answers: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> CarePrecheckOutcome:
        return cls._mutate(
            actor=actor,
            session_public_id=session_public_id,
            state_version=state_version,
            answers=answers,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            operation_id=SUBMIT_CARE_PRECHECK_OPERATION_ID,
            event_code="SUBMIT_CARE_PRECHECK",
            target_status=QuestionnaireSession.Status.SUBMITTED,
        )

    @classmethod
    def _mutate(
        cls,
        *,
        actor: Any,
        session_public_id: UUID,
        state_version: int,
        answers: dict,
        idempotency_key: str,
        correlation_id: UUID,
        operation_id: str,
        event_code: str,
        target_status: str,
    ) -> CarePrecheckOutcome:
        session = QuestionnaireRepository.lock_owned_session(
            session_public_id=session_public_id,
            actor=actor,
        )
        if session is None:
            raise NotFound()

        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": {
                    "questionnaire_session_id": session_public_id,
                },
                "normalized_request_body": {
                    "state_version": state_version,
                    "answers": answers,
                },
                "target_public_id": session.public_id,
            }
        )
        record, replay = cls._begin_idempotent_operation(
            actor=actor,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        if replay is not None:
            return replay
        assert record is not None

        if session.status_code == QuestionnaireSession.Status.SUBMITTED:
            cls._raise_state_conflict(session)
        if session.state_version != state_version:
            cls._raise_state_conflict(session)

        previous_status = session.status_code
        session.answers_payload = answers
        session.status_code = target_status
        session.state_version += 1
        if target_status == QuestionnaireSession.Status.SUBMITTED:
            session.submitted_at = timezone.now()
        session.full_clean()
        session.save(
            update_fields=[
                "answers_payload",
                "status_code",
                "state_version",
                "submitted_at",
                "updated_at",
            ]
        )
        TransitionHistoryService.record_questionnaire_action(
            questionnaire_session=session,
            actor=actor,
            event_code=event_code,
            from_state=previous_status,
            to_state=session.status_code,
            state_version=session.state_version,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        data = cls._serialize(session, idempotent_replay=False)
        WorkflowRepository.complete_idempotency_record(
            record,
            response_status=200,
            response_body=data,
            resource_public_id=session.public_id,
        )
        return CarePrecheckOutcome(status_code=200, data=data)

    @staticmethod
    def _begin_idempotent_operation(
        *,
        actor: Any,
        operation_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> tuple[Any | None, CarePrecheckOutcome | None]:
        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return None, CarePrecheckOutcome(
                status_code=status_code,
                data=data,
            )
        try:
            with transaction.atomic():
                record = WorkflowRepository.create_idempotency_record(
                    actor=actor,
                    operation_id=operation_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
            return record, None
        except IntegrityError:
            existing = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=operation_id,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return None, CarePrecheckOutcome(
                status_code=status_code,
                data=data,
            )

    @staticmethod
    def _serialize(
        session: QuestionnaireSession,
        *,
        idempotent_replay: bool | None = None,
    ) -> dict:
        data = {
            "questionnaire_session_id": str(session.public_id),
            "subscription_id": str(session.subscription.public_id),
            "questionnaire_type_code": session.questionnaire_type_code,
            "questionnaire_version": session.questionnaire_version,
            "status_code": session.status_code,
            "state_version": session.state_version,
            "answers": session.answers_payload,
            "started_at": session.started_at.isoformat(),
            "submitted_at": (
                session.submitted_at.isoformat()
                if session.submitted_at is not None
                else None
            ),
            "linked_inquiry_id": (
                str(session.inquiry.public_id)
                if session.inquiry_id is not None
                else None
            ),
        }
        if idempotent_replay is not None:
            data["idempotent_replay"] = idempotent_replay
        return data

    @staticmethod
    def _raise_state_conflict(session: QuestionnaireSession) -> None:
        raise BusinessError(
            STATE_CONFLICT,
            "다른 요청이 문진 세션 상태를 먼저 변경했습니다.",
            details={
                "current_status": session.status_code,
                "current_state_version": session.state_version,
            },
            status_code=409,
        )
