"""추가문진·비제품 입력·미세입자 오검색 회귀 테스트."""

from __future__ import annotations

from uuid import uuid4

import pytest

from ai.app.generation.customer_guidance.models import GuidanceGenerationResult
from ai.app.integrations.llm import GuidanceLLMResponse, LLMUsage
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.schemas import AiExecutionStatus, FallbackReasonCode
from ai.app.structuring import ProductSymptomDomainGuard, SymptomStructurer


class RecordingSearchService:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.queries = []

    def search(self, query, **kwargs):
        self.queries.append(query)
        return self.chunks[: query.top_k]


class FailingSearchService:
    def search(self, *args, **kwargs):
        raise AssertionError("OFF_DOMAIN 입력은 Vector Search를 실행하면 안 됩니다.")


class GroundedGuidanceLLMClient:
    def generate_guidance(self, request, *, timeout_seconds):
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                message=request.evidence_summaries[0],
                next_actions=[request.allowed_next_actions[0]],
            ),
            model_name="test-grounded-guidance",
            usage=LLMUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            latency_ms=1.0,
        )


def _run(*, raw_symptom, search_service, previous_answers=None):
    return PipelineRouter(
        search_service=search_service,
        llm_client=GroundedGuidanceLLMClient(),
    ).run_pipeline(
        inquiry_id=uuid4(),
        correlation_id=uuid4(),
        ai_request_id=f"ai-req-{uuid4()}",
        state_version=1,
        raw_symptom=raw_symptom,
        selected_symptoms=["OTHER"],
        previous_answers=previous_answers or [],
    )


@pytest.mark.parametrize("target_water_type", ("냉수", "온수", "정수", "전체"))
def test_low_flow_followup_answer_reaches_structuring_query_and_evidence(
    target_water_type,
):
    low_flow = next(
        chunk
        for chunk in ChunkLoader().load_verified_chunks()
        if chunk.topic_code == "symptom_low_flow"
    ).model_copy(update={"similarity_score": 0.91})
    service = RecordingSearchService([low_flow])

    result = _run(
        raw_symptom="물이 약해요",
        search_service=service,
        previous_answers=[
            {
                "question_id": "followup-target-water-type",
                "answer_text": target_water_type,
            }
        ],
    )
    ctx = result.context

    assert ctx.structured_symptom.symptom_type == "출수량 저하"
    assert ctx.structured_symptom.target_water_type == target_water_type
    assert target_water_type in ctx.retrieval_query_text.split(" | ")
    assert service.queries[0].query_text == ctx.retrieval_query_text
    assert ctx.retrieval_selected_chunk_ids == [low_flow.chunk_id]
    assert [item.chunk_id for item in ctx.evidence_references] == [low_flow.chunk_id]


@pytest.mark.parametrize(
    "raw_symptom",
    (
        "정수된 물에 미세한 입자가 발생해요",
        "물에 이물질이 둥둥 떠다녀요",
    ),
)
def test_particles_are_structured_but_low_flow_evidence_is_rejected(raw_symptom):
    low_flow = next(
        chunk
        for chunk in ChunkLoader().load_verified_chunks()
        if chunk.topic_code == "symptom_low_flow"
    ).model_copy(update={"similarity_score": 0.93})
    service = RecordingSearchService([low_flow])

    pipeline_result = _run(raw_symptom=raw_symptom, search_service=service)
    ctx = pipeline_result.context
    response = pipeline_result.to_analysis_result()

    assert ctx.structured_symptom.symptom_type == "수질 이물질"
    assert ctx.domain_relevance == "IN_DOMAIN"
    assert ctx.retrieval_top_k_chunk_ids == [low_flow.chunk_id]
    assert ctx.retrieval_post_topic_chunk_ids == []
    assert ctx.retrieval_selected_chunk_ids == []
    assert ctx.evidence_references == []
    assert ctx.followup_questions == []
    assert response.status == AiExecutionStatus.FALLBACK
    assert response.fallback_reason_code == FallbackReasonCode.NO_EVIDENCE
    assert "출수량" not in response.usage_guidance.message


def test_delivery_request_is_off_domain_and_never_searches_or_generates_self_care():
    raw_symptom = "어제 시킨 치킨이 아직 안 왔어요"
    pipeline_result = _run(
        raw_symptom=raw_symptom,
        search_service=FailingSearchService(),
    )
    ctx = pipeline_result.context
    response = pipeline_result.to_analysis_result()

    assert ProductSymptomDomainGuard().evaluate(
        raw_symptom=raw_symptom,
        selected_symptoms=["OTHER"],
        structured_symptom=ctx.structured_symptom,
    ).relevance == "OFF_DOMAIN"
    assert ctx.domain_relevance == "OFF_DOMAIN"
    assert ctx.retrieval_top_k_chunk_ids == []
    assert ctx.evidence_references == []
    assert ctx.followup_questions == []
    assert response.status == AiExecutionStatus.FALLBACK
    assert response.fallback_reason_code == FallbackReasonCode.NO_EVIDENCE
    assert "정수기 사용 중 발생한 불편한 점" in response.usage_guidance.message
    assert all(
        term not in response.usage_guidance.message
        for term in ("필터", "출수량", "온수", "정상 사용")
    )


def test_ambiguous_product_screen_input_is_not_forced_into_off_domain():
    symptom = SymptomStructurer().structure("이상해요", ["OTHER"])

    decision = ProductSymptomDomainGuard().evaluate(
        raw_symptom="이상해요",
        selected_symptoms=["OTHER"],
        structured_symptom=symptom,
    )

    assert decision.relevance == "UNDETERMINED"


def test_unrelated_long_form_input_is_off_domain_without_keyword_blacklist():
    symptom = SymptomStructurer().structure("주말 여행 일정을 추천해 주세요", ["OTHER"])

    decision = ProductSymptomDomainGuard().evaluate(
        raw_symptom="주말 여행 일정을 추천해 주세요",
        selected_symptoms=["OTHER"],
        structured_symptom=symptom,
    )

    assert decision.relevance == "OFF_DOMAIN"
    assert decision.reason == "NO_PRODUCT_SYMPTOM_SIGNAL"
