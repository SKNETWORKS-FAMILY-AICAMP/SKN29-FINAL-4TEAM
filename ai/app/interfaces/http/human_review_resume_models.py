"""Protected Backend-to-AI HumanReview resume contracts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ...orchestration.hitl.checkpoint import build_hitl_thread_id
from ...schemas.common import ContractModel, VerificationStatus
from ...schemas.pipeline import SymptomAnalysisResult


class HumanReviewResumeApiRequest(ContractModel):
    """Reconstruct one rejected review from the authoritative Backend ledger."""

    contract_version: Literal["1.0.0"] = "1.0.0"
    backend_review_id: UUID
    review_state_version: Literal[2]
    decision: Literal["REJECT"]
    decision_correlation_id: UUID
    source_inquiry_state_version: int = Field(..., ge=1)
    current_inquiry_state_version: int = Field(..., ge=2)
    checkpoint_thread_id: str = Field(
        ...,
        pattern=r"^hitl-[0-9a-f]{32}$",
        max_length=100,
    )
    analysis_result: SymptomAnalysisResult

    @model_validator(mode="after")
    def validate_backend_bindings(self) -> "HumanReviewResumeApiRequest":
        analysis = self.analysis_result
        if analysis.state_version != self.source_inquiry_state_version:
            raise ValueError(
                "analysis state_version과 source_inquiry_state_version이 일치해야 합니다."
            )
        if self.current_inquiry_state_version != (
            self.source_inquiry_state_version + 1
        ):
            raise ValueError(
                "거절 확정 상태 버전은 원본 AI 실행의 바로 다음 버전이어야 합니다."
            )
        expected_thread_id = build_hitl_thread_id(
            inquiry_id=analysis.inquiry_id,
            ai_request_id=analysis.ai_request_id,
            state_version=analysis.state_version,
        )
        if self.checkpoint_thread_id != expected_thread_id:
            raise ValueError("checkpoint_thread_id가 원본 AI 실행과 일치하지 않습니다.")

        evidence_ids = [item.chunk_id for item in analysis.evidence_references]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence chunk_id는 중복될 수 없습니다.")
        if any(
            item.verification_status
            != VerificationStatus.OFFICIAL_VERIFIED
            for item in analysis.evidence_references
        ):
            raise ValueError("맥락 재개에는 official_verified Evidence만 허용됩니다.")
        return self

    @property
    def idempotency_key(self) -> str:
        return (
            "human-review-resume:"
            f"{self.backend_review_id}:{self.review_state_version}"
        )


class HumanReviewResumeApiResponse(ContractModel):
    """Sanitized execution receipt; no prompt or Evidence body is returned."""

    contract_version: Literal["1.0.0"] = "1.0.0"
    backend_review_id: UUID
    inquiry_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    source_inquiry_state_version: int = Field(..., ge=1)
    review_state_version: Literal[2]
    status: Literal["RESUMED"] = "RESUMED"
    routing_reason: Literal["FAIL_CLOSED_CONSULTATION"]
    escalation_reason: Literal["HUMAN_REVIEW_REJECTED"]
    context_agent_calls: Literal[1] = 1
    provider_calls: Literal[0, 1]
    context_synthesis_status: Literal[
        "SUCCEEDED",
        "FALLBACK",
        "UNAVAILABLE",
    ]
    fallback_reason: Literal[
        "CONFIGURATION",
        "PROVIDER_TIMEOUT",
        "PROVIDER_UNAVAILABLE",
        "OUTPUT_INVALID",
        "REFUSED",
        "DANGER_BYPASS",
        "INPUT_TOO_LARGE",
        "INPUT_NOT_ELIGIBLE",
        "SAFETY_NOT_VERIFIED",
        "RUNTIME_PRODUCT_NOT_APPROVED",
    ] | None = None
    handoff_created: Literal[True] = True
    handoff_delivery_scheduled: bool
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def validate_synthesis_receipt(self) -> "HumanReviewResumeApiResponse":
        if self.context_synthesis_status == "SUCCEEDED" and (
            self.provider_calls != 1 or self.fallback_reason is not None
        ):
            raise ValueError("합성 성공에는 Provider 1회와 Fallback 없음이 필요합니다.")
        if (
            self.context_synthesis_status == "FALLBACK"
            and self.fallback_reason is None
        ):
            raise ValueError("합성 Fallback에는 제한된 사유 코드가 필요합니다.")
        if self.context_synthesis_status == "UNAVAILABLE" and (
            self.provider_calls != 0 or self.fallback_reason is not None
        ):
            raise ValueError(
                "합성 결과가 없으면 Provider 호출이나 Fallback을 주장할 수 없습니다."
            )
        return self
