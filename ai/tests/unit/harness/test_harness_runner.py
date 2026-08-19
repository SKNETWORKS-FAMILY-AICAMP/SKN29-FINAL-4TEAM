from pydantic import BaseModel

from ai.app.orchestration.harness import (
    HarnessDecision,
    HarnessErrorCode,
    HarnessRetryState,
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import RiskLevel, SafetyAssessment, SafetyPriority, UsageGuidance, UsageGuidanceStatus


class OutputSchema(BaseModel):
    message: str


def _chunk(model_code: str = "WPU-IAC425") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="e1",
        document_title="official manual",
        manual_model=model_code,
        model_code=model_code,
        content="official evidence",
        similarity_score=0.9,
    )


def _product() -> ProductContext:
    return ProductContext(
        model_code="WPU-IAC425",
        product_family=ProductFamily.ICE_WATER_PURIFIER,
        supported_functions={"cold_water", "hot_water", "ice", "ice_water"},
    )


def _safety(danger: bool = False) -> SafetyAssessment:
    return SafetyAssessment(
        risk_level=RiskLevel.DANGER if danger else RiskLevel.GENERAL,
        priority=SafetyPriority.PRIORITY_CONSULTATION if danger else SafetyPriority.GENERAL_GUIDANCE,
        requires_consultation=danger,
        matched_safety_rule_ids=["SAFETY-WATER-001"] if danger else [],
        detected_risks=["누수"] if danger else [],
        safety_reason="test",
    )


def _guidance(status: UsageGuidanceStatus = UsageGuidanceStatus.NORMAL) -> UsageGuidance:
    return UsageGuidance(guidance_status=status, message="안내", next_actions=["확인"])


def test_pass_when_all_gates_match():
    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=_safety(),
        guidance=_guidance(),
        output_payload={"message": "ok"},
        output_schema=OutputSchema,
    )
    assert result.decision == HarnessDecision.PASS
    assert result.verification.passed is True


def test_wrong_model_requests_one_retrieval_retry_then_no_evidence_escalation():
    first = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[_chunk("WPU-IAC606")],
        safety_assessment=_safety(),
        guidance=_guidance(),
    )
    assert first.decision == HarnessDecision.RETRY_RETRIEVAL
    assert first.retry_state.retrieval_retries == 1

    second = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[_chunk("WPU-IAC606")],
        safety_assessment=_safety(),
        guidance=_guidance(),
        retry_state=first.retry_state,
    )
    assert second.decision == HarnessDecision.ESCALATE
    assert second.error_code == HarnessErrorCode.NO_EVIDENCE


def test_invalid_schema_requests_generation_retry():
    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=_safety(),
        guidance=_guidance(),
        output_payload={"wrong": "shape"},
        output_schema=OutputSchema,
    )
    assert result.decision == HarnessDecision.RETRY_GENERATION
    assert result.retry_state.generation_retries == 1


def test_danger_with_normal_guidance_escalates():
    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=_safety(danger=True),
        guidance=_guidance(UsageGuidanceStatus.NORMAL),
    )
    assert result.decision == HarnessDecision.ESCALATE
    assert any(issue.code.value == "SAFETY_CONFLICT" for issue in result.verification.issues)


def test_timeout_maps_to_ai_processing_timeout():
    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )
    assert result.decision == HarnessDecision.ESCALATE
    assert result.error_code == HarnessErrorCode.AI_PROCESSING_TIMEOUT
