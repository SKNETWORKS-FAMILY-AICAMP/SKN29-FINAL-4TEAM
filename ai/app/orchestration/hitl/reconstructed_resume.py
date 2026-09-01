"""Restart-safe rejected-review reconstruction from Backend-owned state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...retrieval import RetrievalOutcome
from ...schemas import TraceContext
from ..harness.product_registry import resolve_product_context
from ..harness.runner import HarnessRunner, ReconstructedHumanReviewResolution
from ..pipeline_context import PipelineContext


@dataclass(frozen=True, slots=True)
class ReconstructedHumanReviewResume:
    """A sanitized result plus the handoff built by the existing Harness path."""

    resolution: ReconstructedHumanReviewResolution


def resume_rejected_review_from_backend(
    request: Any,
    *,
    runner: HarnessRunner | None = None,
) -> ReconstructedHumanReviewResume:
    """Rebuild the minimum pipeline context without a process-local checkpoint."""

    analysis = request.analysis_result
    product = resolve_product_context(analysis.model_code)
    if not product.runtime_approved:
        raise ValueError("현재 Runtime에서 승인되지 않은 제품입니다.")

    context = PipelineContext(
        trace_context=TraceContext(
            inquiry_id=analysis.inquiry_id,
            correlation_id=analysis.correlation_id,
            ai_request_id=analysis.ai_request_id,
            state_version=analysis.state_version,
        ),
        # The customer original is deliberately excluded from the resume DTO.
        # Existing handoff/context builders use the validated structured result.
        raw_symptom="[backend-validated-analysis]",
        model_code=analysis.model_code,
        structured_symptom=analysis.structured_symptom,
        missing_fields=analysis.missing_fields,
        followup_questions=analysis.followup_questions,
        safety_assessment=analysis.safety_assessment,
        evidence_references=analysis.evidence_references,
        retrieval_outcome=(
            RetrievalOutcome.AVAILABLE
            if analysis.evidence_references
            else RetrievalOutcome.NO_MATCH
        ),
        retry_count=analysis.retry_count,
        usage_guidance=analysis.usage_guidance,
    )
    execution = (runner or HarnessRunner()).resume_rejected_review_from_backend(
        ctx=context,
        product=product,
        checkpoint_thread_id=request.checkpoint_thread_id,
        accepted_evidence_chunk_ids=[
            item.chunk_id for item in analysis.evidence_references
        ],
    )
    return ReconstructedHumanReviewResume(resolution=execution)
