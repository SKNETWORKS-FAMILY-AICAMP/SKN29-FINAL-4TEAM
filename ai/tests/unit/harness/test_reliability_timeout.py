from types import SimpleNamespace
from uuid import UUID

from ai.app.common.timeout import CancellationToken, PipelineStageTimeoutError
from ai.app.orchestration.harness import HarnessDecision, HarnessErrorCode, ProductContext, ProductFamily
from ai.app.orchestration.harness.runtime import ReliabilityRuntime
from ai.app.retrieval import RetrievalOutcome, RetrievedChunk
from ai.app.schemas import RiskLevel, SafetyAssessment, UsageGuidance, UsageGuidanceStatus


def _ctx():
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b601"),
            correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e601"),
            ai_request_id="ai-req-timeout-001",
            state_version=1,
        ),
        model_code="WPUJAC104DWH",
        structured_symptom=SimpleNamespace(
            symptom_type="출수량 저하",
            occurrence_time="오늘",
            target_water_type="냉수",
            occurrence_condition="출수 시",
            error_code=None,
            accompanying_symptoms=[],
        ),
        previous_answers=[],
        evidence_references=[],
        safety_assessment=SafetyAssessment(
            risk_level=RiskLevel.CAUTION,
            priority="consultation_recommended",
            requires_consultation=False,
            matched_safety_rule_ids=[],
            detected_risks=[],
            safety_reason="일반 증상",
        ),
        usage_guidance=UsageGuidance(
            guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
            message="점검 안내",
            restricted_functions=[],
            next_actions=["상태 확인"],
        ),
        missing_fields=[],
        awaiting_customer_input=False,
        retrieval_outcome=RetrievalOutcome.NO_MATCH,
        retry_count=0,
    )


class _RetryableEvidenceCapture:
    rejected_chunk_ids = []

    def evidence_for_harness(self, _ctx):
        return [
            RetrievedChunk(
                chunk_id="RAG-WRONG-MODEL-TIMEOUT-001",
                document_title="official manual",
                manual_model="WPUIAC606SNW",
                model_code="WPUIAC606SNW",
                content="다른 제품의 공식 근거",
                similarity_score=0.9,
                verification_status="official_verified",
                allowed_use=True,
            )
        ]


def test_retrieval_retry_stage_timeout_is_converted_to_harness_handoff(monkeypatch):
    runtime = ReliabilityRuntime()

    def raise_timeout(**kwargs):
        raise PipelineStageTimeoutError("RETRIEVING")

    monkeypatch.setattr(runtime, "_retry_retrieval", raise_timeout)
    ctx = _ctx()
    result = runtime.run(
        ctx=ctx,
        product=ProductContext(
            model_code="WPUJAC104DWH",
            product_family=ProductFamily.DIRECT_WATER_PURIFIER,
            runtime_approved=True,
        ),
        evidence_capture=_RetryableEvidenceCapture(),
        search_service=object(),
        llm_client=None,
        cancellation_token=CancellationToken(),
    )

    assert result.retrieval_retry_performed is True
    assert result.timeout_stage == "RETRIEVING"
    assert result.harness_runtime.harness.decision == HarnessDecision.ESCALATE
    assert result.harness_runtime.harness.error_code == HarnessErrorCode.AI_PROCESSING_TIMEOUT
    assert result.harness_runtime.handoff is not None
    assert result.harness_runtime.handoff.escalation_reason == "AI_PROCESSING_TIMEOUT"
    assert ctx.usage_guidance.guidance_status == UsageGuidanceStatus.PENDING_CONSULTATION
