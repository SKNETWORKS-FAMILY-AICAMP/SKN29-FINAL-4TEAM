import pytest

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
from ai.app.safety.rule_loader import SafetyRuleLoader
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


def test_no_evidence_escalates_without_retrieval_retry():
    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=_safety(),
        guidance=_guidance(UsageGuidanceStatus.PENDING_CONSULTATION),
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.should_retry is False
    assert result.should_escalate is True
    assert result.retry_state.retrieval_retries == 0
    no_evidence = [
        issue
        for issue in result.verification.issues
        if issue.code.value == "NO_EVIDENCE"
    ]
    assert len(no_evidence) == 1
    assert no_evidence[0].retryable is False


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


def test_approved_danger_partial_stop_rule_passes():
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-HOT-WATER-HEATER-001"],
        detected_risks=["온수 히터·순간온수 모듈 고장 및 음용 제한"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="위험 신호가 감지되어 온수 기능 사용 제한이 필요합니다.",
        restricted_functions=["온수 출수 및 음용 중지"],
        next_actions=[
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.PASS
    assert result.verification.passed is True
    assert result.verification.safety_valid is True
    assert not any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


@pytest.mark.parametrize(
    ("restricted_functions", "next_actions"),
    [
        (
            ["제품 전체 기능 사용 중지"],
            [
                "온수 기능 사용과 온수 음용을 중단하세요.",
                "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
            ],
        ),
        (
            ["온수 출수 및 음용 중지"],
            ["전문 상담 및 기사 점검을 요청하세요."],
        ),
    ],
)
def test_danger_partial_stop_with_wrong_rule_body_escalates(
    restricted_functions,
    next_actions,
):
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-HOT-WATER-HEATER-001"],
        detected_risks=["온수 히터 이상"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="안내",
        restricted_functions=restricted_functions,
        next_actions=next_actions,
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.verification.safety_valid is False
    assert any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


@pytest.mark.parametrize(
    "rule_ids",
    [
        ["SAFETY-NOT-REGISTERED-999"],
        [],
    ],
)
def test_danger_with_unknown_or_empty_rule_escalates(rule_ids):
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=rule_ids,
        detected_risks=["위험"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.TOTAL_STOP,
        message="안내",
        restricted_functions=["제품 전체 기능 사용 중지"],
        next_actions=["전문 상담 및 기사 점검을 요청하세요."],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.verification.safety_valid is False
    assert any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


@pytest.mark.parametrize(
    "strong_rule_id",
    [
        "SAFETY-LEAK-001",
        "SAFETY-ELECTRICAL-001",
    ],
)
def test_heater_plus_total_stop_danger_rejects_partial_stop(strong_rule_id):
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=[
            "SAFETY-HOT-WATER-HEATER-001",
            strong_rule_id,
        ],
        detected_risks=["온수 히터 이상", "추가 중대 위험"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="안내",
        restricted_functions=["온수 출수 및 음용 중지"],
        next_actions=[
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.verification.safety_valid is False
    assert any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


def test_heater_plus_leak_with_exact_total_stop_passes():
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=[
            "SAFETY-HOT-WATER-HEATER-001",
            "SAFETY-LEAK-001",
        ],
        detected_risks=["온수 히터 이상", "누수"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.TOTAL_STOP,
        message="안내",
        restricted_functions=[
            "전체 출수 기능 중지",
            "제품 전원 차단 필요",
        ],
        next_actions=[
            "즉시 원수 공급 밸브(원수 밸브)를 잠그세요.",
            "젖은 손으로 전원 플러그를 만지지 마시고, 안전할 때 전원을 차단해 주세요.",
            "전문 기사 방문 점검을 요청하세요.",
        ],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.PASS
    assert result.verification.passed is True
    assert result.verification.safety_valid is True


def test_danger_alignment_is_independent_of_yaml_rule_order(monkeypatch):
    original = SafetyRuleLoader().get_safety_rules()
    reordered = dict(original)
    reordered["rules"] = dict(
        reversed(list(original["rules"].items()))
    )

    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=[
            "SAFETY-HOT-WATER-HEATER-001",
            "SAFETY-LEAK-001",
        ],
        detected_risks=["온수 히터 이상", "누수"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.TOTAL_STOP,
        message="안내",
        restricted_functions=[
            "전체 출수 기능 중지",
            "제품 전원 차단 필요",
        ],
        next_actions=[
            "즉시 원수 공급 밸브(원수 밸브)를 잠그세요.",
            "젖은 손으로 전원 플러그를 만지지 마시고, 안전할 때 전원을 차단해 주세요.",
            "전문 기사 방문 점검을 요청하세요.",
        ],
    )

    baseline = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )
    monkeypatch.setattr(
        SafetyRuleLoader,
        "get_safety_rules",
        lambda self: reordered,
    )
    reordered_result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert baseline.decision == HarnessDecision.PASS
    assert reordered_result.decision == baseline.decision
    assert reordered_result.verification.safety_valid is True


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


def test_retryable_mcp_evidence_search_failure_retries_once_then_escalates():
    from ai.app.orchestration.harness import McpToolFailure, McpToolFailureKind, McpToolName

    failure = McpToolFailure(
        tool_name=McpToolName.SEARCH_OFFICIAL_EVIDENCE,
        kind=McpToolFailureKind.TIMEOUT,
        retryable=True,
    )
    runner = HarnessRunner()
    first = runner.run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=_safety(),
        guidance=_guidance(),
        tool_failure=failure,
    )
    assert first.decision == HarnessDecision.RETRY_RETRIEVAL
    assert first.retry_state.retrieval_retries == 1
    assert any(issue.code.value == "MCP_TOOL_FAILURE" for issue in first.verification.issues)

    second = runner.run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=_safety(),
        guidance=_guidance(),
        retry_state=first.retry_state,
        tool_failure=failure,
    )
    assert second.decision == HarnessDecision.ESCALATE
    assert second.error_code == HarnessErrorCode.MCP_TOOL_FAILURE


def test_non_retrieval_mcp_tool_failure_escalates_without_retry():
    from ai.app.orchestration.harness import McpToolFailure, McpToolFailureKind, McpToolName

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=_safety(),
        guidance=_guidance(),
        tool_failure=McpToolFailure(
            tool_name=McpToolName.LOOKUP_PRODUCT_CONTEXT,
            kind=McpToolFailureKind.UNAVAILABLE,
            retryable=True,
        ),
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.should_retry is False
    assert result.retry_state.retrieval_retries == 0


def test_mcp_tool_failure_contract_rejects_raw_internal_error_fields():
    import pytest
    from pydantic import ValidationError
    from ai.app.orchestration.harness import McpToolFailure, McpToolFailureKind, McpToolName

    with pytest.raises(ValidationError):
        McpToolFailure.model_validate(
            {
                "tool_name": McpToolName.SEARCH_OFFICIAL_EVIDENCE,
                "kind": McpToolFailureKind.EXECUTION_ERROR,
                "retryable": False,
                "raw_error": "postgres password=super-secret stacktrace",
            }
        )
