"""6주차 3-Agent Supervisor·Routing·Feedback 후보 Runtime 검증."""

from __future__ import annotations

import json

import pytest

from ai.app.generation.customer_guidance.models import GuidanceGenerationResult
from ai.evaluation.runners.pipeline_comparison_runner import PipelineComparisonRunner
from ai.app.integrations.llm import GuidanceLLMResponse, LLMUsage
from ai.app.orchestration.agents import (
    AgentHopLimitExceeded,
    AgentRole,
    CareDecisionAgent,
    EvidenceAnalysisAgent,
    HandoffReason,
    SymptomAnalysisAgent,
)
from ai.app.common.timeout import CancellationToken
from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.orchestration.pipelines.multi_agent_pipeline import MultiAgentPipeline
from ai.app.retrieval import RetrievedChunk, RetrievalOutcome
from ai.app.schemas import RiskLevel, TraceContext, UsageGuidanceStatus
from ai.app.validation.routing import ResponseRoutingDisposition


INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88b601"
CORRELATION_ID = "018f2f9b-7c30-7981-b541-1a987c88b602"
COMPLETE_SYMPTOM = "어제부터 냉수 버튼을 누르면 물이 졸졸 나옵니다. 전원을 껐다 켰어요."
CONTEXT_CANARY_LOW_FLOW_SYMPTOM = (
    "오늘부터 정수 출수 버튼을 누르면 출수량이 평소보다 줄었고, "
    "원수 밸브를 확인했지만 동일합니다."
)
EVIDENCE_SUMMARY = "출수량이 적은 경우 원수 공급 밸브가 열려 있는지 확인합니다."
TASTE_EVIDENCE_SUMMARY = "단기(10일 이내) : 냉수, 정수, 온수를 1L씩 각각 1회 이상 출수하여 버린 후 사용해 주세요."


class EmptySearchService:
    def search(self, *args, **kwargs):
        return []


class UnexpectedSearchService:
    def search(self, *args, **kwargs):
        raise AssertionError("문진 완료 전에는 근거 검색을 호출하면 안 됩니다.")


class EvidenceSearchService:
    def __init__(self):
        self.queries = []

    def search(self, *args, **kwargs):
        self.queries.append(args[0])
        return [
            RetrievedChunk(
                chunk_id="RAG-WPUJAC104DWH-LOW-FLOW-MA-TEST",
                document_title="WPU-JAC104D 사용설명서",
                document_version="REV.00",
                page=37,
                page_refs=[37],
                manual_model="WPUJAC104DWH",
                model_code="WPUJAC104DWH",
                product_generation="D",
                content=EVIDENCE_SUMMARY,
                similarity_score=0.91,
                official_url="https://example.invalid/official-manual",
                verification_status="official_verified",
                allowed_use=True,
                topic_code="symptom_low_flow",
            )
        ]


class TasteEvidenceSearchService:
    def __init__(self):
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        return [
            RetrievedChunk(
                chunk_id="RAG-WPUJAC104DWH-TASTE-ODOR-001",
                document_title="WPU-JAC104D 사용설명서",
                manual_model="WPUJAC104DWH",
                model_code="WPUJAC104DWH",
                product_generation="D",
                content=TASTE_EVIDENCE_SUMMARY,
                similarity_score=0.91,
                verification_status="official_verified",
                allowed_use=True,
                topic_code="symptom_taste_odor",
            )
        ]


class FakeGuidanceLLMClient:
    def __init__(self):
        self.calls = 0

    def generate_guidance(self, request, *, timeout_seconds):
        self.calls += 1
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                message=EVIDENCE_SUMMARY,
                next_actions=["안내된 자가조치 단계별 점검 수행"],
            ),
            model_name="gpt-4.1-mini",
            usage=LLMUsage(input_tokens=10, output_tokens=8, total_tokens=18),
            latency_ms=12.5,
        )


class UnexpectedGuidanceLLMClient:
    def generate_guidance(self, request, *, timeout_seconds):
        raise AssertionError("문진 완료 전에는 LLM을 호출하면 안 됩니다.")


class TasteGuidanceLLMClient:
    def __init__(self):
        self.calls = 0
        self.requests = []

    def generate_guidance(self, request, *, timeout_seconds):
        self.calls += 1
        self.requests.append(request)
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                message=TASTE_EVIDENCE_SUMMARY,
                next_actions=["기본 필터 및 사용 환경 유지"],
            ),
            model_name="gpt-4.1-mini",
            usage=LLMUsage(input_tokens=10, output_tokens=8, total_tokens=18),
            latency_ms=12.5,
        )


def _run_multi_agent(
    *,
    search_service,
    raw_symptom=COMPLETE_SYMPTOM,
    selected_symptoms=None,
    previous_answers=None,
    llm_client=None,
):
    return PipelineRouter(
        search_service=search_service,
        llm_client=llm_client or FakeGuidanceLLMClient(),
    ).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-multi-agent",
        state_version=1,
        raw_symptom=raw_symptom,
        model_code="WPUJAC104DWH",
        selected_symptoms=selected_symptoms or [],
        previous_answers=previous_answers or [],
        runtime_name="multi_agent",
    )


def test_default_runtime_remains_single_rag():
    result = PipelineRouter(search_service=None).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-default-runtime",
        state_version=1,
        raw_symptom="정수기 밑 바닥에 물이 새서 누수가 심합니다.",
        selected_symptoms=["누수"],
    )

    assert result.runtime_name == "single_rag"
    assert result.multi_agent_metadata is None


def test_multi_agent_danger_routes_without_retrieval_or_llm():
    llm = FakeGuidanceLLMClient()
    result = PipelineRouter(
        search_service=UnexpectedSearchService(),
        llm_client=llm,
    ).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-multi-danger",
        state_version=1,
        raw_symptom="정수기 밑 바닥에 물이 새서 누수가 심합니다.",
        selected_symptoms=["누수"],
        runtime_name="multi_agent",
    )
    response = result.to_analysis_result()

    assert result.runtime_name == "multi_agent"
    assert response.safety_assessment.risk_level.value == "danger"
    assert response.usage_guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    assert response.missing_fields == []
    assert response.followup_questions == []
    assert response.evidence_references == []
    assert llm.calls == 0
    assert [item.reason_code for item in result.multi_agent_metadata.handoffs] == [
        HandoffReason.START_ANALYSIS,
        HandoffReason.DANGER_PRIORITY,
        HandoffReason.CARE_DECISION_READY,
    ]


@pytest.mark.parametrize(
    (
        "case_id",
        "raw_symptom",
        "expected_status",
        "expected_rule_ids",
    ),
    [
        (
            "HOT-WATER-HEATER-ONLY",
            "온수 히터 고장으로 온수는 음용하지 말아야 합니다.",
            UsageGuidanceStatus.PARTIAL_STOP,
            {"SAFETY-HOT-WATER-HEATER-001"},
        ),
        (
            "HOT-WATER-HEATER-WITH-LEAK",
            "온수 히터 고장과 누수가 함께 발생했습니다.",
            UsageGuidanceStatus.TOTAL_STOP,
            {"SAFETY-HOT-WATER-HEATER-001", "SAFETY-LEAK-001"},
        ),
        (
            "HOT-WATER-HEATER-WITH-ELECTRICAL-RISK",
            "온수 히터 고장 중에 스파크가 발생했습니다.",
            UsageGuidanceStatus.TOTAL_STOP,
            {
                "SAFETY-HOT-WATER-HEATER-001",
                "SAFETY-ELECTRICAL-001",
            },
        ),
        (
            "HOT-WATER-HEATER-WITH-FIRE-RISK",
            "온수 히터 고장과 화재 위험이 함께 있습니다.",
            UsageGuidanceStatus.TOTAL_STOP,
            {
                "SAFETY-HOT-WATER-HEATER-001",
                "SAFETY-ELECTRICAL-001",
            },
        ),
    ],
)
def test_multi_agent_applies_total_stop_precedence_for_composite_danger(
    case_id,
    raw_symptom,
    expected_status,
    expected_rule_ids,
):
    llm = FakeGuidanceLLMClient()
    result = _run_multi_agent(
        search_service=UnexpectedSearchService(),
        raw_symptom=raw_symptom,
        llm_client=llm,
    )
    response = result.to_analysis_result()

    assert case_id.startswith("HOT-WATER-HEATER-")
    assert response.safety_assessment.risk_level == RiskLevel.DANGER
    assert response.safety_assessment.requires_consultation is True
    assert set(response.safety_assessment.matched_safety_rule_ids) == (
        expected_rule_ids
    )
    assert response.usage_guidance.guidance_status == expected_status
    assert llm.calls == 0

    if expected_status == UsageGuidanceStatus.PARTIAL_STOP:
        assert response.usage_guidance.restricted_functions == [
            "온수 출수 및 음용 중지"
        ]
        assert response.usage_guidance.next_actions == [
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ]


def test_multi_agent_evidence_path_matches_single_rag_public_contract():
    single = PipelineRouter(
        search_service=EvidenceSearchService(),
        llm_client=FakeGuidanceLLMClient(),
    ).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-parity",
        state_version=1,
        raw_symptom=COMPLETE_SYMPTOM,
        runtime_name="single_rag",
    )
    multi = PipelineRouter(
        search_service=EvidenceSearchService(),
        llm_client=FakeGuidanceLLMClient(),
    ).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-parity",
        state_version=1,
        raw_symptom=COMPLETE_SYMPTOM,
        runtime_name="multi_agent",
    )

    assert multi.to_analysis_result().model_dump(mode="json") == (
        single.to_analysis_result().model_dump(mode="json")
    )
    assert [item.to_agent for item in multi.multi_agent_metadata.handoffs] == [
        AgentRole.SYMPTOM_ANALYSIS,
        AgentRole.EVIDENCE_ANALYSIS,
        AgentRole.CARE_DECISION,
        AgentRole.SUPERVISOR,
    ]


def test_context_canary_fixture_reaches_evidence_without_followup_wait():
    search_service = EvidenceSearchService()
    result = _run_multi_agent(
        search_service=search_service,
        raw_symptom=CONTEXT_CANARY_LOW_FLOW_SYMPTOM,
        selected_symptoms=["LOW_FLOW"],
    )
    response = result.to_analysis_result()

    assert result.context.awaiting_customer_input is False
    assert response.missing_fields == []
    assert response.followup_questions == []
    assert len(search_service.queries) == 1
    assert search_service.queries[0].model_code == "WPUJAC104DWH"
    assert "출수량 저하" in search_service.queries[0].query_text
    assert [item.chunk_id for item in response.evidence_references] == [
        "RAG-WPUJAC104DWH-LOW-FLOW-MA-TEST"
    ]
    assert HandoffReason.EVIDENCE_READY in {
        item.reason_code for item in result.multi_agent_metadata.handoffs
    }


def test_incomplete_low_flow_fixture_still_stops_before_evidence_search():
    result = _run_multi_agent(
        search_service=UnexpectedSearchService(),
        raw_symptom="정수기 출수량이 평소보다 줄었습니다.",
        selected_symptoms=["LOW_FLOW"],
    )
    response = result.to_analysis_result()

    assert result.context.awaiting_customer_input is True
    assert "target_water_type" in {
        item.field_name for item in response.missing_fields
    }
    assert response.evidence_references == []


def test_evidence_gap_with_missing_information_returns_questions_not_no_evidence():
    raw_symptom = "출수 온도가 이상합니다."
    result = _run_multi_agent(
        search_service=EmptySearchService(),
        raw_symptom=raw_symptom,
    )
    response = result.to_analysis_result()

    assert result.context.awaiting_customer_input is True
    assert result.multi_agent_metadata.awaiting_customer_input is True
    assert response.status.value == "SUCCEEDED"
    assert response.failure_stage is None
    assert str(response.correlation_id) == CORRELATION_ID
    assert response.followup_questions
    assert response.evidence_references == []
    assert response.usage_guidance.guidance_status == UsageGuidanceStatus.PENDING_CONSULTATION
    assert response.safety_assessment.risk_level == RiskLevel.CAUTION
    assert response.safety_assessment.requires_consultation is True
    assert HandoffReason.CUSTOMER_INPUT_PENDING in {
        item.reason_code for item in result.multi_agent_metadata.handoffs
    }
    assert result.routing_disposition == (
        ResponseRoutingDisposition.CUSTOMER_INPUT_PENDING
    )
    assert raw_symptom not in json.dumps(
        result.multi_agent_metadata.model_dump(mode="json"),
        ensure_ascii=False,
    )


def test_multi_agent_earthy_taste_waits_for_context_before_evidence_handoff():
    result = _run_multi_agent(
        search_service=UnexpectedSearchService(),
        raw_symptom="물에서 흙맛이 나는 것 같아요",
        llm_client=UnexpectedGuidanceLLMClient(),
    )
    response = result.to_analysis_result()
    reasons = [item.reason_code for item in result.multi_agent_metadata.handoffs]

    assert result.context.awaiting_customer_input is True
    assert result.context.retrieval_outcome == RetrievalOutcome.NOT_RUN
    assert result.multi_agent_metadata.awaiting_customer_input is True
    assert response.status.value == "SUCCEEDED"
    assert response.failure_stage is None
    assert str(response.correlation_id) == CORRELATION_ID
    assert response.followup_questions
    assert response.evidence_references == []
    assert response.usage_guidance.guidance_status == UsageGuidanceStatus.PENDING_CONSULTATION
    assert HandoffReason.CUSTOMER_INPUT_PENDING in reasons
    assert HandoffReason.RETRIEVAL_REQUIRED not in reasons
    assert AgentRole.EVIDENCE_ANALYSIS not in {
        item.to_agent for item in result.multi_agent_metadata.handoffs
    }


def test_multi_agent_earthy_taste_non_applicable_context_stops_before_search():
    llm = FakeGuidanceLLMClient()
    result = _run_multi_agent(
        search_service=UnexpectedSearchService(),
        raw_symptom="물에서 흙맛이 나는 것 같아요",
        previous_answers=[
            {"question_id": "followup-occurrence-time", "answer_text": "오늘부터"},
            {"question_id": "followup-target-water-type", "answer_text": "정수"},
            {"question_id": "followup-actions-taken", "answer_text": "없음"},
            {
                "question_id": "followup-taste-odor-applicability",
                "answer_text": "해당 없음",
            },
        ],
        llm_client=llm,
    )
    response = result.to_analysis_result()

    assert llm.calls == 0
    assert result.context.retrieval_outcome == RetrievalOutcome.NOT_RUN
    assert response.status.value == "FALLBACK"
    assert response.failure_stage.value == "CHECKING_MISSING_FIELDS"
    assert response.fallback_reason_code.value == "UNSPECIFIED_FALLBACK"
    assert response.followup_questions == []
    assert response.safety_assessment.requires_consultation is True
    assert response.evidence_references == []
    assert HandoffReason.NO_EVIDENCE not in {
        item.reason_code for item in result.multi_agent_metadata.handoffs
    }


def test_multi_agent_earthy_taste_within_ten_days_uses_applicable_evidence():
    llm = TasteGuidanceLLMClient()
    search_service = TasteEvidenceSearchService()
    result = _run_multi_agent(
        search_service=search_service,
        raw_symptom="물에서 흙맛이 나는 것 같아요",
        previous_answers=[
            {"question_id": "followup-occurrence-time", "answer_text": "오늘부터"},
            {"question_id": "followup-target-water-type", "answer_text": "정수"},
            {"question_id": "followup-actions-taken", "answer_text": "없음"},
            {
                "question_id": "followup-taste-odor-applicability",
                "answer_text": "10일 이내 부재 후",
            },
        ],
        llm_client=llm,
    )
    response = result.to_analysis_result()

    assert llm.calls == 1
    assert search_service.calls == 1
    assert result.context.retrieval_outcome == RetrievalOutcome.AVAILABLE
    assert response.status.value == "SUCCEEDED"
    assert response.failure_stage is None
    assert str(response.correlation_id) == CORRELATION_ID
    assert len(response.evidence_references) == 1
    assert "10일 이내 부재 후" in llm.requests[0].symptom_summary
    assert HandoffReason.EVIDENCE_READY in {
        item.reason_code for item in result.multi_agent_metadata.handoffs
    }
    assert result.routing_disposition == ResponseRoutingDisposition.AUTO_GUIDANCE


def test_answered_questions_then_empty_retrieval_becomes_no_evidence():
    result = _run_multi_agent(
        search_service=EmptySearchService(),
        raw_symptom="정수기 상태가 이상합니다.",
        previous_answers=[
            {"question_id": "followup-occurrence-time", "answer_text": "어제부터"},
            {"question_id": "followup-target-water-type", "answer_text": "냉수"},
            {"question_id": "followup-occurrence-condition", "answer_text": "버튼을 누를 때"},
            {"question_id": "followup-actions-taken", "answer_text": "전원 재부팅"},
        ],
    )
    response = result.to_analysis_result()

    assert result.context.awaiting_customer_input is False
    assert response.followup_questions == []
    assert response.status.value == "FALLBACK"
    assert response.failure_stage.value == "RETRIEVING"
    assert HandoffReason.NO_EVIDENCE in {
        item.reason_code for item in result.multi_agent_metadata.handoffs
    }


def test_multi_agent_hop_limit_fails_closed():
    ctx = PipelineContext(
        trace_context=TraceContext(
            inquiry_id=INQUIRY_ID,
            correlation_id=CORRELATION_ID,
            ai_request_id="ai-req-hop-limit",
            state_version=1,
        ),
        raw_symptom="정수기 밑 바닥에 물이 새서 누수가 심합니다.",
        selected_symptoms=["누수"],
    )

    with pytest.raises(AgentHopLimitExceeded, match="최대 Handoff 1회"):
        MultiAgentPipeline(search_service=None, max_hops=1).run(ctx)


def test_invalid_runtime_name_does_not_silently_fallback():
    with pytest.raises(RuntimeError, match="single_rag 또는 multi_agent"):
        PipelineRouter(search_service=None).run_pipeline(
            inquiry_id=INQUIRY_ID,
            correlation_id=CORRELATION_ID,
            ai_request_id="ai-req-invalid-runtime",
            state_version=1,
            raw_symptom="정수기 밑 바닥에 물이 새서 누수가 심합니다.",
            selected_symptoms=["누수"],
            runtime_name="unknown",
        )


def test_each_agent_returns_its_explicit_output_contract():
    ctx = PipelineContext(
        trace_context=TraceContext(
            inquiry_id=INQUIRY_ID,
            correlation_id=CORRELATION_ID,
            ai_request_id="ai-req-agent-contracts",
            state_version=1,
        ),
        raw_symptom=COMPLETE_SYMPTOM,
    )
    token = CancellationToken()

    symptom_output = SymptomAnalysisAgent(token).run(ctx)
    evidence_output = EvidenceAnalysisAgent(
        EvidenceSearchService(),
        token,
    ).run(ctx)
    care_output = CareDecisionAgent(token, FakeGuidanceLLMClient()).run(ctx)

    assert symptom_output.structured_symptom == ctx.structured_symptom
    assert symptom_output.safety_assessment == ctx.safety_assessment
    assert evidence_output.evidence_sufficient is True
    assert evidence_output.evidence_references == ctx.evidence_references
    assert care_output.usage_guidance == ctx.usage_guidance
    assert care_output.awaiting_customer_input is False


def test_comparison_runner_records_parity_without_exposing_bodies():
    request = {
        "inquiry_id": INQUIRY_ID,
        "correlation_id": CORRELATION_ID,
        "ai_request_id": "ai-req-comparison",
        "state_version": 1,
        "raw_symptom": COMPLETE_SYMPTOM,
        "model_code": "WPUJAC104DWH",
    }
    report = PipelineComparisonRunner().compare(
        single_router=PipelineRouter(
            search_service=EvidenceSearchService(),
            llm_client=FakeGuidanceLLMClient(),
        ),
        multi_agent_router=PipelineRouter(
            search_service=EvidenceSearchService(),
            llm_client=FakeGuidanceLLMClient(),
        ),
        request_kwargs=request,
    )

    assert report.public_contract_equal is True
    assert report.safety_result_equal is True
    assert report.evidence_identity_equal is True
    assert report.single_rag.tokens_used == 18
    assert report.multi_agent.tokens_used == 18
    serialized = report.model_dump_json()
    assert COMPLETE_SYMPTOM not in serialized
    assert EVIDENCE_SUMMARY not in serialized
