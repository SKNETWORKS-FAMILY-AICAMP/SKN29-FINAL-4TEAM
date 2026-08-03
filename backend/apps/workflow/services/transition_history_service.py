"""Workflow transition-history write service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.inquiries.models import Inquiry
from apps.workflow.domain.transition import Transition
from apps.workflow.models import TransitionHistory
from apps.workflow.repositories.workflow_repository import (
    WorkflowRepository,
)


class TransitionHistoryService:
    """Record canonical inquiry transitions."""

    @staticmethod
    def record_start_inquiry(
        *,
        inquiry: Inquiry,
        actor: Any,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> TransitionHistory:
        return WorkflowRepository.create_transition_history(
            inquiry=inquiry,
            actor=actor,
            event_code="START_INQUIRY",
            from_state=None,
            to_state=Inquiry.Status.DRAFT,
            state_version=1,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def record_cancel_inquiry(
        *,
        inquiry: Inquiry,
        actor: Any,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> TransitionHistory:
        return WorkflowRepository.create_transition_history(
            inquiry=inquiry,
            actor=actor,
            event_code="CANCEL_INQUIRY",
            from_state=Inquiry.Status.DRAFT,
            to_state=Inquiry.Status.CANCELLED,
            state_version=inquiry.state_version,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def record_submit_symptom(
        *,
        inquiry: Inquiry,
        transition: Transition,
        actor: Any,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> TransitionHistory:
        return WorkflowRepository.create_transition_history(
            inquiry=inquiry,
            actor=actor,
            event_code=transition.event_code,
            from_state=transition.inquiry_state_before,
            to_state=transition.inquiry_state_after,
            state_version=transition.state_version_after,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
