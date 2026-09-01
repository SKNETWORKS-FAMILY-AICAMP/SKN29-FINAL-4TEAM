"""Crash-durable, at-most-once dispatch for rejected HumanReview resume."""

from __future__ import annotations

import hashlib
import json
import logging
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.inquiries.models import HumanReview, HumanReviewResumeDispatch
from integrations.ai.human_review_resume import (
    HumanReviewResumeFailure,
    HumanReviewResumeReceipt,
    build_human_review_resume_payload,
    send_human_review_resume_payload,
)


ai_trace_logger = logging.getLogger("watercare.ai")


def _payload_sha256(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class HumanReviewResumeDispatchService:
    """Own the persistent one-attempt boundary around the AI HTTP call."""

    @classmethod
    def enqueue(
        cls,
        review: HumanReview,
    ) -> HumanReviewResumeDispatch:
        """Create the outbox row inside the official REJECT transaction."""

        if (
            review.status_code != HumanReview.Status.REJECTED
            or review.decision_code != HumanReview.Decision.REJECT
            or review.review_state_version != 2
        ):
            raise ValueError("only an official rejected review can be enqueued")
        idempotency_key = (
            "human-review-resume:"
            f"{review.public_id}:{review.review_state_version}"
        )
        dispatch, created = HumanReviewResumeDispatch.objects.get_or_create(
            human_review=review,
            defaults={
                "idempotency_key": idempotency_key,
                "source_review_state_version": review.review_state_version,
            },
        )
        if not created and (
            dispatch.idempotency_key != idempotency_key
            or dispatch.source_review_state_version
            != review.review_state_version
        ):
            raise ValueError("resume dispatch binding conflict")
        return dispatch

    @classmethod
    def process_pending(cls, *, max_rows: int = 100) -> dict[str, int]:
        """Process only never-started rows; no failure is auto-retried."""

        counts = {
            "processed": 0,
            "succeeded": 0,
            "failed_pre_send": 0,
            "outcome_unknown": 0,
            "skipped": 0,
        }
        if not settings.AI_HUMAN_REVIEW_RESUME_ENABLED:
            return counts
        for _ in range(max(1, int(max_rows))):
            public_id = (
                HumanReviewResumeDispatch.objects.filter(
                    status=HumanReviewResumeDispatch.Status.PENDING
                )
                .order_by("created_at", "pk")
                .values_list("public_id", flat=True)
                .first()
            )
            if public_id is None:
                break
            outcome = cls.process_dispatch(public_id)
            counts["processed"] += 1
            counts[outcome] += 1
        return counts

    @classmethod
    def process_dispatch(cls, dispatch_public_id: UUID) -> str:
        """Claim, send once, and persist a sanitized terminal result."""

        if not settings.AI_HUMAN_REVIEW_RESUME_ENABLED:
            return "skipped"
        claimed = cls._claim(dispatch_public_id)
        if claimed is None:
            status = (
                HumanReviewResumeDispatch.objects.filter(
                    public_id=dispatch_public_id
                )
                .values_list("status", flat=True)
                .first()
            )
            if status == HumanReviewResumeDispatch.Status.FAILED_PRE_SEND:
                return "failed_pre_send"
            return "skipped"
        payload, idempotency_key, payload_sha256 = claimed
        try:
            receipt = send_human_review_resume_payload(
                payload,
                idempotency_key=idempotency_key,
            )
        except HumanReviewResumeFailure as exc:
            cls._mark_outcome_unknown(
                dispatch_public_id,
                payload_sha256=payload_sha256,
                failure_code=exc.failure_code,
            )
            return "outcome_unknown"
        except Exception:
            cls._mark_outcome_unknown(
                dispatch_public_id,
                payload_sha256=payload_sha256,
                failure_code="AI_RESUME_UNEXPECTED",
            )
            return "outcome_unknown"

        cls._mark_succeeded(
            dispatch_public_id,
            payload_sha256=payload_sha256,
            receipt=receipt,
        )
        return "succeeded"

    @classmethod
    @transaction.atomic
    def _claim(
        cls,
        dispatch_public_id: UUID,
    ) -> tuple[dict, str, str] | None:
        dispatch = (
            HumanReviewResumeDispatch.objects.select_for_update()
            .select_related("human_review")
            .filter(public_id=dispatch_public_id)
            .first()
        )
        if (
            dispatch is None
            or dispatch.status != HumanReviewResumeDispatch.Status.PENDING
        ):
            return None
        try:
            payload, idempotency_key = build_human_review_resume_payload(
                dispatch.human_review.public_id
            )
        except HumanReviewResumeFailure as exc:
            cls._set_failed_pre_send(dispatch, exc.failure_code)
            return None
        except Exception:
            cls._set_failed_pre_send(dispatch, "AI_RESUME_PRE_SEND_UNEXPECTED")
            return None
        if idempotency_key != dispatch.idempotency_key:
            cls._set_failed_pre_send(
                dispatch,
                "AI_RESUME_IDEMPOTENCY_BINDING_MISMATCH",
            )
            return None

        payload_sha256 = _payload_sha256(payload)
        dispatch.status = HumanReviewResumeDispatch.Status.DISPATCHING
        dispatch.attempt_count = 1
        dispatch.payload_sha256 = payload_sha256
        dispatch.started_at = timezone.now()
        dispatch.full_clean()
        dispatch.save()
        return payload, idempotency_key, payload_sha256

    @staticmethod
    def _set_failed_pre_send(
        dispatch: HumanReviewResumeDispatch,
        failure_code: str,
    ) -> None:
        dispatch.status = HumanReviewResumeDispatch.Status.FAILED_PRE_SEND
        dispatch.completed_at = timezone.now()
        dispatch.failure_code = str(failure_code)[:80]
        dispatch.full_clean()
        dispatch.save()
        ai_trace_logger.error(
            "human_review_resume_failed_pre_send",
            extra={
                "review_id": str(dispatch.human_review.public_id),
                "dispatch_id": str(dispatch.public_id),
                "failure_code": dispatch.failure_code,
            },
        )

    @classmethod
    @transaction.atomic
    def _mark_outcome_unknown(
        cls,
        dispatch_public_id: UUID,
        *,
        payload_sha256: str,
        failure_code: str,
    ) -> None:
        dispatch = HumanReviewResumeDispatch.objects.select_for_update().get(
            public_id=dispatch_public_id
        )
        if (
            dispatch.status
            != HumanReviewResumeDispatch.Status.DISPATCHING
            or dispatch.payload_sha256 != payload_sha256
        ):
            return
        dispatch.status = HumanReviewResumeDispatch.Status.OUTCOME_UNKNOWN
        dispatch.completed_at = timezone.now()
        dispatch.failure_code = str(failure_code)[:80]
        dispatch.full_clean()
        dispatch.save()
        ai_trace_logger.error(
            "human_review_resume_outcome_unknown",
            extra={
                "review_id": str(dispatch.human_review.public_id),
                "dispatch_id": str(dispatch.public_id),
                "failure_code": dispatch.failure_code,
            },
        )

    @classmethod
    @transaction.atomic
    def _mark_succeeded(
        cls,
        dispatch_public_id: UUID,
        *,
        payload_sha256: str,
        receipt: HumanReviewResumeReceipt,
    ) -> None:
        dispatch = HumanReviewResumeDispatch.objects.select_for_update().get(
            public_id=dispatch_public_id
        )
        if (
            dispatch.status
            != HumanReviewResumeDispatch.Status.DISPATCHING
            or dispatch.payload_sha256 != payload_sha256
        ):
            return
        dispatch.status = HumanReviewResumeDispatch.Status.SUCCEEDED
        dispatch.completed_at = timezone.now()
        dispatch.provider_calls = receipt.provider_calls
        dispatch.context_synthesis_status = receipt.context_synthesis_status
        dispatch.fallback_reason = receipt.fallback_reason
        dispatch.handoff_delivery_scheduled = (
            receipt.handoff_delivery_scheduled
        )
        dispatch.idempotent_replay = receipt.idempotent_replay
        dispatch.full_clean()
        dispatch.save()
        ai_trace_logger.info(
            "human_review_resume_completed",
            extra={
                "review_id": str(dispatch.human_review.public_id),
                "dispatch_id": str(dispatch.public_id),
                "inquiry_id": str(receipt.inquiry_id),
                "ai_request_id": receipt.ai_request_id,
                "review_state_version": receipt.review_state_version,
                "context_agent_calls": receipt.context_agent_calls,
                "provider_calls": receipt.provider_calls,
                "context_synthesis_status": receipt.context_synthesis_status,
                "fallback_reason": receipt.fallback_reason,
                "handoff_created": receipt.handoff_created,
                "handoff_delivery_scheduled": (
                    receipt.handoff_delivery_scheduled
                ),
                "idempotent_replay": receipt.idempotent_replay,
            },
        )
