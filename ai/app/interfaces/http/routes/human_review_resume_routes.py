"""Protected Backend-to-AI rejected HumanReview resume endpoint."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from hashlib import sha256
import hmac
import os
from threading import Lock
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from ....integrations.backend.handoff_client import (
    handoff_delivery_enabled,
    publish_consultation_handoff,
)
from ....orchestration.hitl.reconstructed_resume import (
    ReconstructedHumanReviewResume,
    resume_rejected_review_from_backend,
)
from ..human_review_resume_models import (
    HumanReviewResumeApiRequest,
    HumanReviewResumeApiResponse,
)


router = APIRouter(prefix="/api/v1/internal/ai", tags=["Internal AI"])
_MAX_PROCESS_RECEIPTS = 2048


class _ProcessResumeRegistry:
    """Prevent duplicate Provider/Handoff work inside one AI process.

    The Backend decision idempotency ledger suppresses an official API replay.
    Failed executions remain cached so an automatic retry cannot call the
    Provider again in this process. Crash-durable dispatch still requires the
    later Backend outbox/attempt ledger and is not claimed here.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: OrderedDict[str, _ResumeEntry] = OrderedDict()

    def run_once(
        self,
        key: str,
        binding_sha256: str,
        operation: Callable[[], ReconstructedHumanReviewResume],
    ) -> tuple[ReconstructedHumanReviewResume, bool]:
        with self._lock:
            entry = self._entries.get(key)
            created = entry is None
            if entry is None:
                entry = _ResumeEntry(
                    binding_sha256=binding_sha256,
                    future=Future(),
                )
                self._entries[key] = entry
                self._evict_completed()
            else:
                self._entries.move_to_end(key)
                if not hmac.compare_digest(
                    entry.binding_sha256,
                    binding_sha256,
                ):
                    raise ValueError("idempotency key payload conflict")

        future = entry.future

        if not created:
            return future.result(), False

        try:
            result = operation()
        except BaseException as exc:
            future.set_exception(exc)
            raise
        future.set_result(result)
        return result, True

    def _evict_completed(self) -> None:
        while len(self._entries) > _MAX_PROCESS_RECEIPTS:
            oldest_key, oldest = next(iter(self._entries.items()))
            if not oldest.future.done():
                break
            self._entries.pop(oldest_key)


@dataclass(frozen=True, slots=True)
class _ResumeEntry:
    binding_sha256: str
    future: Future


_PROCESS_RESUME_REGISTRY = _ProcessResumeRegistry()


def _strict_enabled() -> bool:
    return (
        os.getenv("AI_HUMAN_REVIEW_RESUME_ENABLED", "false")
        .strip()
        .lower()
        == "true"
    )


def _protected_token() -> str:
    return os.getenv("AI_HUMAN_REVIEW_RESUME_TOKEN", "").strip()


def _deliver_handoff(handoff) -> None:
    # The existing client performs protected AI-to-Backend delivery. The
    # receipt never contains prompt, Evidence body, or a secret.
    publish_consultation_handoff(handoff)


@router.post(
    "/human-reviews/resume",
    response_model=HumanReviewResumeApiResponse,
    summary="Resume one officially rejected HumanReview",
    include_in_schema=False,
)
async def resume_rejected_human_review(
    body: HumanReviewResumeApiRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    x_backend_resume_token: str | None = Header(
        None,
        alias="X-Backend-Resume-Token",
    ),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    x_correlation_id: UUID | None = Header(None, alias="X-Correlation-ID"),
) -> HumanReviewResumeApiResponse:
    """Run only after Backend has committed the official REJECT decision."""

    analysis = body.analysis_result
    request.state.inquiry_id = analysis.inquiry_id
    request.state.correlation_id = body.decision_correlation_id
    request.state.ai_request_id = analysis.ai_request_id
    request.state.state_version = analysis.state_version

    if not _strict_enabled():
        raise HTTPException(
            status_code=503,
            detail="HumanReview 재개 기능이 비활성 상태입니다.",
        )
    expected_token = _protected_token()
    if (
        len(expected_token.encode("utf-8")) < 32
        or not x_backend_resume_token
        or not hmac.compare_digest(expected_token, x_backend_resume_token)
    ):
        raise HTTPException(
            status_code=403,
            detail="보호된 HumanReview 재개 요청이 아닙니다.",
        )
    if idempotency_key != body.idempotency_key:
        raise HTTPException(
            status_code=409,
            detail="HumanReview 재개 멱등 키가 일치하지 않습니다.",
        )
    if x_correlation_id != body.decision_correlation_id:
        raise HTTPException(
            status_code=409,
            detail="검토 결정 추적 식별자가 일치하지 않습니다.",
        )

    try:
        binding_sha256 = sha256(
            body.model_dump_json().encode("utf-8")
        ).hexdigest()
        reconstructed, created = await asyncio.to_thread(
            _PROCESS_RESUME_REGISTRY.run_once,
            body.idempotency_key,
            binding_sha256,
            lambda: resume_rejected_review_from_backend(body),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="HumanReview 재개 결속 검증에 실패했습니다.",
        ) from exc

    handoff = reconstructed.resolution.handoff
    context_synthesis = handoff.context_synthesis
    scheduled = bool(created and handoff_delivery_enabled())
    if scheduled:
        background_tasks.add_task(_deliver_handoff, handoff)

    return HumanReviewResumeApiResponse(
        backend_review_id=body.backend_review_id,
        inquiry_id=analysis.inquiry_id,
        ai_request_id=analysis.ai_request_id,
        source_inquiry_state_version=analysis.state_version,
        review_state_version=body.review_state_version,
        routing_reason="FAIL_CLOSED_CONSULTATION",
        escalation_reason="HUMAN_REVIEW_REJECTED",
        provider_calls=(
            1
            if context_synthesis is not None
            and context_synthesis.provider_called
            else 0
        ),
        context_synthesis_status=(
            context_synthesis.status
            if context_synthesis is not None
            else "UNAVAILABLE"
        ),
        fallback_reason=(
            context_synthesis.fallback_reason
            if context_synthesis is not None
            else None
        ),
        handoff_delivery_scheduled=scheduled,
        idempotent_replay=not created,
    )
