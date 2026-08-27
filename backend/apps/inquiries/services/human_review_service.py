"""Atomic HumanReview ledger creation, read projection, and decision runtime."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.inquiries.models import Guidance, GuidanceItem, HumanReview
from apps.inquiries.repositories.human_review_repository import (
    HumanReviewRepository,
)
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import STATE_CONFLICT


OPERATION_ID = "decideHumanReview"
PENDING_REASON_CODE = "CAUTION_PRE_SEND_REVIEW"


@dataclass(frozen=True)
class HumanReviewOutcome:
    status_code: int
    data: dict[str, Any]


class HumanReviewService:
    """Own the Backend business ledger; AI owns checkpoint mechanics."""

    @classmethod
    def create_pending(
        cls,
        *,
        guidance: Guidance,
        ai_request_id: str,
        source_inquiry_state_version: int,
    ) -> HumanReview:
        """Create exactly one review for a new fail-closed pending Guidance."""

        thread_id = cls._checkpoint_thread_id(
            inquiry_public_id=guidance.inquiry.public_id,
            ai_request_id=ai_request_id,
            state_version=source_inquiry_state_version,
        )
        review = HumanReview(
            inquiry=guidance.inquiry,
            guidance=guidance,
            checkpoint_thread_id=thread_id,
            source_ai_request_id=ai_request_id,
            source_inquiry_state_version=source_inquiry_state_version,
            initial_reason_code=PENDING_REASON_CODE,
        )
        review.full_clean()
        review.save()
        return review

    @staticmethod
    def _checkpoint_thread_id(
        *,
        inquiry_public_id: UUID,
        ai_request_id: str,
        state_version: int,
    ) -> str:
        raw = (
            f"{inquiry_public_id}:{ai_request_id}:{state_version}"
        ).encode("utf-8")
        return f"hitl-{hashlib.sha256(raw).hexdigest()[:32]}"

    @classmethod
    def list_pending(cls, *, actor: Any) -> dict[str, list[dict[str, Any]]]:
        return {
            "items": [
                cls._projection(review)
                for review in HumanReviewRepository.list_pending(actor)
            ]
        }

    @classmethod
    def retrieve(
        cls,
        *,
        actor: Any,
        review_public_id: UUID,
    ) -> dict[str, Any]:
        review = HumanReviewRepository.retrieve_visible(
            actor=actor,
            review_public_id=review_public_id,
        )
        if review is None:
            raise NotFound()
        return cls._projection(review)

    @classmethod
    @transaction.atomic
    def decide(
        cls,
        *,
        actor: Any,
        review_public_id: UUID,
        validated_data: dict[str, Any],
        idempotency_key: str,
        correlation_id: UUID,
    ) -> HumanReviewOutcome:
        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": {
                    "review_id": review_public_id,
                },
                "normalized_request_body": validated_data,
                "target_public_id": review_public_id,
            }
        )
        review = HumanReviewRepository.lock_visible(
            actor=actor,
            review_public_id=review_public_id,
        )
        if review is None:
            raise NotFound()

        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return HumanReviewOutcome(status_code, data)

        if (
            review.status_code != HumanReview.Status.PENDING
            or review.review_state_version
            != validated_data["review_state_version"]
        ):
            cls._raise_state_conflict(review)

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
            winner = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=OPERATION_ID,
                idempotency_key=idempotency_key,
            )
            if winner is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                winner,
                request_hash=request_hash,
            )
            return HumanReviewOutcome(status_code, data)

        published_guidance = cls._apply_guidance_decision(
            review=review,
            actor=actor,
            decision=validated_data["decision"],
            modified=validated_data.get("modified_guidance"),
        )
        decision = validated_data["decision"]
        review.status_code = {
            HumanReview.Decision.APPROVE: HumanReview.Status.APPROVED,
            HumanReview.Decision.MODIFY: HumanReview.Status.MODIFIED,
            HumanReview.Decision.REJECT: HumanReview.Status.REJECTED,
        }[decision]
        review.decision_code = decision
        review.review_state_version += 1
        review.decision_reason_code = validated_data.get(
            "reason_code",
            "APPROVED_AS_IS",
        )
        review.reviewer = actor
        review.decided_at = timezone.now()
        review.decision_idempotency_key = idempotency_key
        review.decision_correlation_id = correlation_id
        review.modified_guidance_payload = (
            validated_data.get("modified_guidance") or {}
        )
        review.published_guidance = published_guidance
        review.full_clean()
        review.save()

        data = cls._projection(review)
        data["idempotent_replay"] = False
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=200,
            response_body=data,
            resource_public_id=review.public_id,
        )
        return HumanReviewOutcome(200, data)

    @staticmethod
    def _apply_guidance_decision(
        *,
        review: HumanReview,
        actor: Any,
        decision: str,
        modified: dict[str, Any] | None,
    ) -> Guidance | None:
        now = timezone.now()
        original = review.guidance
        if decision == HumanReview.Decision.APPROVE:
            original.review_status_code = "APPROVED"
            original.reviewed_by = actor
            original.reviewed_at = now
            original.full_clean()
            original.save()
            return original

        original.review_status_code = "REJECTED"
        original.reviewed_by = actor
        original.reviewed_at = now
        original.full_clean()
        original.save()
        if decision == HumanReview.Decision.REJECT:
            return None

        latest_version = (
            Guidance.objects.select_for_update()
            .filter(inquiry=review.inquiry)
            .aggregate(value=Max("guidance_version"))["value"]
            or 0
        )
        published = Guidance(
            inquiry=review.inquiry,
            guidance_version=latest_version + 1,
            review_status_code="APPROVED",
            title=modified["title"],
            summary_text=modified["summary_text"],
            safety_notice=modified.get("safety_notice"),
            evidence_sufficiency_code=original.evidence_sufficiency_code,
            requires_consultation=original.requires_consultation,
            generated_by_ai_run=original.generated_by_ai_run,
            reviewed_by=actor,
            reviewed_at=now,
        )
        published.full_clean()
        published.save()
        for step_no, item_payload in enumerate(modified["items"], start=1):
            item = GuidanceItem(
                guidance=published,
                step_no=step_no,
                action_type_code="NEXT_ACTION",
                instruction_text=item_payload["instruction_text"],
                caution_text=item_payload.get("caution_text"),
                requires_confirmation=item_payload.get(
                    "requires_confirmation",
                    True,
                ),
            )
            item.full_clean()
            item.save()
        return published

    @classmethod
    @transaction.atomic
    def mark_resume_failed(
        cls,
        *,
        review_public_id: UUID,
        failure_code: str,
    ) -> HumanReview:
        """Record a bounded AI resume failure without persisting raw errors."""

        review = (
            HumanReview.objects.select_for_update()
            .filter(public_id=review_public_id)
            .first()
        )
        if review is None:
            raise NotFound()
        if review.status_code not in {
            HumanReview.Status.APPROVED,
            HumanReview.Status.MODIFIED,
            HumanReview.Status.REJECTED,
        }:
            cls._raise_state_conflict(review)
        review.status_code = HumanReview.Status.RESUME_FAILED
        review.resume_failure_code = failure_code
        review.review_state_version += 1
        review.full_clean()
        review.save()
        return review

    @staticmethod
    def _raise_state_conflict(review: HumanReview) -> None:
        raise BusinessError(
            STATE_CONFLICT,
            "다른 검토 결정이 먼저 반영되었습니다.",
            details={
                "current_status": review.status_code,
                "current_review_state_version": review.review_state_version,
                "allowed_actions": (
                    ["DECIDE_HUMAN_REVIEW"]
                    if review.status_code == HumanReview.Status.PENDING
                    else []
                ),
            },
            status_code=409,
        )

    @classmethod
    def _projection(cls, review: HumanReview) -> dict[str, Any]:
        return {
            "review_id": str(review.public_id),
            "inquiry_id": str(review.inquiry.public_id),
            "model_code": review.inquiry.subscription.product_model.model_code,
            "status": review.status_code,
            "decision": review.decision_code,
            "review_state_version": review.review_state_version,
            "source_inquiry_state_version": (
                review.source_inquiry_state_version
            ),
            "reason_code": review.initial_reason_code,
            "proposed_guidance": cls._guidance_projection(review.guidance),
            "published_guidance": (
                cls._guidance_projection(review.published_guidance)
                if review.published_guidance_id
                else None
            ),
            "allowed_actions": (
                ["DECIDE_HUMAN_REVIEW"]
                if review.status_code == HumanReview.Status.PENDING
                else []
            ),
            "created_at": review.created_at.isoformat(),
            "updated_at": review.updated_at.isoformat(),
        }

    @staticmethod
    def _guidance_projection(guidance: Guidance) -> dict[str, Any]:
        return {
            "guidance_id": str(guidance.public_id),
            "guidance_version": guidance.guidance_version,
            "title": guidance.title,
            "summary_text": guidance.summary_text,
            "safety_notice": guidance.safety_notice,
            "requires_consultation": guidance.requires_consultation,
            "items": [
                {
                    "step_no": item.step_no,
                    "instruction_text": item.instruction_text,
                    "caution_text": item.caution_text,
                    "requires_confirmation": item.requires_confirmation,
                }
                for item in sorted(
                    guidance.items.all(),
                    key=lambda value: (value.step_no, value.public_id),
                )
            ],
        }
