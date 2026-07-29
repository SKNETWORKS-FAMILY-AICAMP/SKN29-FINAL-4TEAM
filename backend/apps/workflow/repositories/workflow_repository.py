"""ORM boundary for idempotency and transition-history persistence."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.utils import timezone

from apps.inquiries.models import Inquiry
from apps.workflow.models import IdempotencyRecord, TransitionHistory


class WorkflowRepository:
    """Persist workflow records without leaking internal primary keys."""

    @staticmethod
    def lock_idempotency_scope(
        *,
        actor: Any,
        operation_id: str,
        idempotency_key: str,
    ) -> IdempotencyRecord | None:
        return (
            IdempotencyRecord.objects.select_for_update()
            .filter(
                actor=actor,
                operation_id=operation_id,
                idempotency_key=idempotency_key,
            )
            .first()
        )

    @staticmethod
    def create_idempotency_record(
        *,
        actor: Any,
        operation_id: str,
        idempotency_key: str,
        request_hash: str,
    ) -> IdempotencyRecord:
        return IdempotencyRecord.objects.create(
            actor=actor,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )

    @staticmethod
    def complete_idempotency_record(
        record: IdempotencyRecord,
        *,
        response_status: int,
        response_body: dict,
        resource_public_id: UUID,
    ) -> None:
        record.response_status = response_status
        record.response_body = response_body
        record.resource_public_id = resource_public_id
        record.completed_at = timezone.now()
        record.save(
            update_fields=[
                "response_status",
                "response_body",
                "resource_public_id",
                "completed_at",
                "updated_at",
            ]
        )

    @staticmethod
    def create_transition_history(
        *,
        inquiry: Inquiry,
        actor: Any,
        event_code: str,
        from_state: str | None,
        to_state: str,
        state_version: int,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> TransitionHistory:
        return TransitionHistory.objects.create(
            inquiry=inquiry,
            actor=actor,
            event_code=event_code,
            from_state=from_state,
            to_state=to_state,
            state_version=state_version,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
