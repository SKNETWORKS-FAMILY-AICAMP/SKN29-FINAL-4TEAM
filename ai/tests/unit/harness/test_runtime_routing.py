from types import SimpleNamespace
from uuid import UUID

from ai.app.orchestration.agents import ConsultationContextSynthesisAgent
from ai.app.orchestration.harness import (
    HarnessDecision,
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.hitl import HumanReviewDecision, HumanReviewResume, HumanReviewStatus
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import (
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    UsageGuidance,
    UsageGuidanceStatus,
)


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


class _RecordingContextSynthesisAgent:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = []
        self.fail = fail
        self.delegate = ConsultationContextSynthesisAgent()

    def run(self, synthesis_input, *, timeout_seconds: float = 5.0):
        self.calls.append(synthesis_input)
        if self.fail:
            raise RuntimeError("context synthesis failed")
        return self.delegate.run(
            synthesis_input,
            timeout_seconds=timeout_seconds,
        )


def _ctx_with_evidence():
    ctx = _ctx()
    ctx.evidence_references = [
        SimpleNamespace(
            chunk_id="jac104-1",
            document_title="WPU-JAC104 공식 매뉴얼",
            page=10,
            summary="상담용 공식 근거",
        )
    ]
    return ctx


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
    assert result.handoff.state_version == 4
    assert result.handoff.routing_reason == "HARNESS_ESCALATE"
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
    assert resolved.handoff.state_version == 4
    assert resolved.handoff.routing_reason == "FAIL_CLOSED_CONSULTATION"


def test_mcp_context_tool_failure_creates_sanitized_consultation_handoff():
    from ai.app.orchestration.harness import McpToolFailure, McpToolFailureKind, McpToolName

    result = HarnessRunner().run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        tool_failure=McpToolFailure(
            tool_name=McpToolName.GET_INQUIRY_CONTEXT,
            kind=McpToolFailureKind.EXECUTION_ERROR,
            retryable=False,
        ),
    )

    assert result.harness.decision == HarnessDecision.ESCALATE
    assert result.handoff is not None
    assert result.handoff.escalation_reason == "MCP_TOOL_FAILURE"
    assert result.handoff.model_code == "WPU-JAC104"


def test_context_synthesis_runs_only_after_actual_handoff():
    context_agent = _RecordingContextSynthesisAgent()
    runner = HarnessRunner(context_synthesis_agent=context_agent)

    auto_result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
    )
    assert auto_result.harness.decision == HarnessDecision.PASS
    assert auto_result.handoff is None
    assert context_agent.calls == []

    review_result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )
    assert review_result.harness.decision == HarnessDecision.HUMAN_REVIEW
    assert review_result.handoff is None
    assert context_agent.calls == []


def test_rejected_review_calls_context_synthesis_with_only_harness_accepted_evidence():
    context_agent = _RecordingContextSynthesisAgent()
    runner = HarnessRunner(context_synthesis_agent=context_agent)
    ctx = _ctx_with_evidence()

    initial = runner.run_runtime(
        ctx=ctx,
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )
    assert context_agent.calls == []

    resolved = runner.resume_human_review(
        ctx=ctx,
        product=_product(),
        interrupted=initial.human_review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.REJECT,
            state_version=4,
        ),
    )

    assert len(context_agent.calls) == 1
    synthesis_input = context_agent.calls[0]
    assert [item.chunk_id for item in synthesis_input.evidence] == ["jac104-1"]
    assert synthesis_input.safety_requires_consultation is False
    assert resolved.handoff is not None
    assert resolved.handoff.context_synthesis is not None
    assert resolved.handoff.source_chunk_ids == ["jac104-1"]


def test_context_synthesis_failure_does_not_block_existing_handoff():
    context_agent = _RecordingContextSynthesisAgent(fail=True)
    runner = HarnessRunner(context_synthesis_agent=context_agent)

    result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )

    assert len(context_agent.calls) == 1
    assert result.harness.decision == HarnessDecision.ESCALATE
    assert result.handoff is not None
    assert result.handoff.escalation_reason == "AI_PROCESSING_TIMEOUT"
    assert result.handoff.context_synthesis is None
    assert result.handoff.state_version == 4
    assert result.handoff.routing_reason == "HARNESS_ESCALATE"


def test_danger_handoff_calls_context_synthesis_after_handoff_is_forced():
    context_agent = _RecordingContextSynthesisAgent()
    runner = HarnessRunner(context_synthesis_agent=context_agent)
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-HOT-WATER-HEATER-001"],
        detected_risks=["온수 히터 이상"],
        safety_reason="온수 음용 제한이 필요합니다.",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="온수 기능 사용을 중단하세요.",
        restricted_functions=["온수 출수 및 음용 중지"],
        next_actions=[
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    )
    ctx = _ctx()
    ctx.safety_assessment = safety
    ctx.usage_guidance = guidance

    harness = runner.run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
        evidence_required=False,
    )
    routed = runner.route_runtime(
        ctx=ctx,
        product=_product(),
        harness=harness,
        guidance=guidance,
        force_handoff_reason="DANGER_PRIORITY",
    )

    assert harness.decision == HarnessDecision.PASS
    assert len(context_agent.calls) == 1
    assert context_agent.calls[0].routing_reason.value == "DANGER_HANDOFF"
    assert routed.handoff is not None
    assert routed.handoff.context_synthesis is not None
    assert routed.handoff.state_version == 4
    assert routed.handoff.routing_reason == "DANGER_HANDOFF"


def test_timeout_handoff_preserves_unknown_safety_without_forcing_consultation():
    context_agent = _RecordingContextSynthesisAgent()
    runner = HarnessRunner(context_synthesis_agent=context_agent)

    result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )

    assert result.harness.decision == HarnessDecision.ESCALATE
    assert len(context_agent.calls) == 1
    synthesis_input = context_agent.calls[0]
    assert synthesis_input.routing_reason.value == "HARNESS_ESCALATE"
    assert synthesis_input.safety_level == "unknown"
    assert synthesis_input.safety_requires_consultation is False
    assert synthesis_input.matched_safety_rule_ids == []
    assert result.handoff is not None
    assert result.handoff.safety_requires_consultation is False
    assert result.handoff.context_synthesis is not None


def test_mcp_failure_handoff_does_not_turn_system_failure_into_safety_risk():
    from ai.app.orchestration.harness import (
        McpToolFailure,
        McpToolFailureKind,
        McpToolName,
    )

    context_agent = _RecordingContextSynthesisAgent()
    runner = HarnessRunner(context_synthesis_agent=context_agent)

    result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        tool_failure=McpToolFailure(
            tool_name=McpToolName.GET_INQUIRY_CONTEXT,
            kind=McpToolFailureKind.EXECUTION_ERROR,
            retryable=False,
        ),
    )

    assert result.harness.decision == HarnessDecision.ESCALATE
    assert len(context_agent.calls) == 1
    synthesis_input = context_agent.calls[0]
    assert synthesis_input.routing_reason.value == "HARNESS_ESCALATE"
    assert synthesis_input.safety_level == "unknown"
    assert synthesis_input.safety_requires_consultation is False
    assert result.handoff is not None
    assert result.handoff.safety_requires_consultation is False
    assert result.handoff.context_synthesis is not None
