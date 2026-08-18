"""Transactional T-022 customer action-result append service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound

from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.action_result_repository import (
    ActionResultRepository,
)
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import STATE_CONFLICT


OPERATION_ID = "createInquiryActionResult"


@dataclass(frozen=True)
class ActionResultOutcome:
    status_code: int
    data: dict


class ActionResultService:
    """Append one result without assigning meaning to open result codes."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        validated_data: dict,
        idempotency_key: str,
    ) -> ActionResultOutcome:
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

        if (
            inquiry.status_code != Inquiry.Status.AI_GUIDANCE
            or validated_data["state_version"] != inquiry.state_version
        ):
            cls._raise_state_conflict(inquiry)

        guidance_item = ActionResultRepository.lock_guidance_item(
            inquiry=inquiry,
            guidance_item_public_id=validated_data["guidance_item_id"],
        )
        if guidance_item is None:
            raise NotFound()

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

        result = ActionResultRepository.create(
            guidance_item=guidance_item,
            actor=actor,
            attempt_no=ActionResultRepository.next_attempt_no(
                guidance_item=guidance_item
            ),
            validated_data=validated_data,
            request_token=idempotency_record.public_id,
        )
        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=inquiry.status_code,
            state_version=inquiry.state_version + 1,
        )
        data = {
            "id": str(result.public_id),
            "inquiry_id": str(inquiry.public_id),
            "guidance_item_id": str(guidance_item.public_id),
            "attempt_no": result.attempt_no,
            "result_code": result.result_code,
            "result_text": result.result_text,
            "performed_at": (
                result.performed_at.isoformat()
                if result.performed_at is not None
                else None
            ),
            "customer_comment": result.customer_comment,
            "submitted_by": str(actor.public_id),
            "state_version": inquiry.state_version,
            "idempotent_replay": False,
            "created_at": result.created_at.isoformat(),
        }
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=201,
            response_body=data,
            resource_public_id=result.public_id,
        )
        return ActionResultOutcome(201, data)

    @staticmethod
    def _replay(
        *,
        actor: Any,
        idempotency_key: str,
        request_hash: str,
    ) -> ActionResultOutcome | None:
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
        return ActionResultOutcome(status_code, data)

    @staticmethod
    def _raise_state_conflict(inquiry: Inquiry) -> None:
        raise BusinessError(
            STATE_CONFLICT,
            "The inquiry state has changed.",
            details={
                "current_status": inquiry.status_code,
                "current_state_version": inquiry.state_version,
            },
            status_code=409,
        )
