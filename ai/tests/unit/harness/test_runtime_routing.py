from types import SimpleNamespace
from uuid import UUID

from ai.app.orchestration.harness import (
    HarnessDecision,
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.hitl import HumanReviewDecision, HumanReviewResume, HumanReviewStatus
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import UsageGuidance, UsageGuidanceStatus


def _guidance(message: str = "기본 안내") -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=message,
        next_actions=["상태 확인"],
    )


def _ctx():
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
            correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
            ai_request_id="ai-req-runtime-001",
            state_version=4,
        ),
        model_code="WPU-JAC104",
        structured_symptom=None,
        previous_answers=[],
        evidence_references=[],
        safety_assessment=None,
        usage_guidance=_guidance(),
        missing_fields=[],
    )


def _product() -> ProductContext:
    return ProductContext(
        model_code="WPU-JAC104",
        product_family=ProductFamily.DIRECT_WATER_PURIFIER,
        supported_functions={"cold_water", "hot_water"},
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="jac104-1",
        document_title="WPU-JAC104 공식 매뉴얼",
        manual_model="WPU-JAC104",
        model_code="WPU-JAC104",
        content="공식 근거",
        similarity_score=0.95,
    )


def test_human_review_decision_starts_checkpointed_hitl_without_pipeline_rerun():
    runner = HarnessRunner()
    result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )

    assert result.harness.decision == HarnessDecision.HUMAN_REVIEW
    assert result.human_review.status == HumanReviewStatus.WAITING_FOR_REVIEW
    assert result.handoff is None


def test_timeout_escalate_creates_consultation_handoff():
    runner = HarnessRunner()
    result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )

    assert result.harness.decision == HarnessDecision.ESCALATE
    assert result.handoff.model_code == "WPU-JAC104"
    assert result.handoff.escalation_reason == "AI_PROCESSING_TIMEOUT"
    assert result.human_review is None


def test_approved_review_returns_guidance_without_handoff():
    runner = HarnessRunner()
    initial = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )

    resolved = runner.resume_human_review(
        ctx=_ctx(),
        product=_product(),
        interrupted=initial.human_review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.APPROVE,
            state_version=4,
        ),
    )

    assert resolved.guidance.message == "기본 안내"
    assert resolved.handoff is None


def test_rejected_review_routes_to_consultation_handoff():
    runner = HarnessRunner()
    ctx = _ctx()
    initial = runner.run_runtime(
        ctx=ctx,
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )

    resolved = runner.resume_human_review(
        ctx=ctx,
        product=_product(),
        interrupted=initial.human_review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.REJECT,
            state_version=4,
        ),
    )

    assert resolved.guidance is None
    assert resolved.handoff.escalation_reason == "HUMAN_REVIEW_REJECTED"
    assert resolved.handoff.model_code == "WPU-JAC104"
