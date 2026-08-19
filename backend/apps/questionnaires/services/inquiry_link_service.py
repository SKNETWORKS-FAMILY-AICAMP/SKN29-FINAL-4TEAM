"""Atomic link between one submitted precheck and one new inquiry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.inquiries.models import Inquiry
from apps.questionnaires.models import QuestionnaireSession
from apps.questionnaires.repositories.questionnaire_repository import (
    QuestionnaireRepository,
)
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import STATE_CONFLICT


class InquiryLinkService:
    """Validate a precheck under a row lock and link it exactly once."""

    @staticmethod
    def lock_candidate(
        *,
        actor: Any,
        subscription: CustomerSubscription,
        session_public_id: UUID | None,
    ) -> QuestionnaireSession | None:
        if session_public_id is None:
            return None
        session = QuestionnaireRepository.lock_link_candidate(
            session_public_id=session_public_id,
            actor=actor,
            subscription=subscription,
        )
        if session is None:
            raise NotFound()
        if (
            session.status_code
            != QuestionnaireSession.Status.SUBMITTED
            or session.inquiry_id is not None
        ):
            raise BusinessError(
                STATE_CONFLICT,
                "제출 완료되고 아직 연결되지 않은 문진만 사용할 수 있습니다.",
                details={
                    "current_status": session.status_code,
                    "current_state_version": session.state_version,
                    "linked": session.inquiry_id is not None,
                },
                status_code=409,
            )
        return session

    @staticmethod
    def link(
        *,
        session: QuestionnaireSession | None,
        inquiry: Inquiry,
        actor: Any,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        if session is None:
            return
        previous_status = session.status_code
        session.inquiry = inquiry
        session.linked_at = timezone.now()
        session.state_version += 1
        session.full_clean()
        session.save(
            update_fields=[
                "inquiry",
                "linked_at",
                "state_version",
                "updated_at",
            ]
        )
        TransitionHistoryService.record_questionnaire_action(
            questionnaire_session=session,
            actor=actor,
            event_code="START_INQUIRY",
            from_state=previous_status,
            to_state=session.status_code,
            state_version=session.state_version,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
