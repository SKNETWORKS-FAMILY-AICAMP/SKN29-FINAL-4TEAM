"""Presentation-path regressions for clarification-only synthetic scenarios."""

from __future__ import annotations

import pytest

from ai.app.orchestration.harness import HarnessVerifier
from ai.app.orchestration.harness.product_match import ProductContext, ProductFamily
from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.orchestration.pipelines.multi_agent_pipeline import MultiAgentPipeline
from ai.app.retrieval import RetrievedChunk, RetrievalOutcome
from ai.app.retrieval.synthetic_scenarios import SyntheticScenarioRetriever
from ai.app.schemas import RiskLevel, TraceContext, UsageGuidanceStatus
from ai.app.structuring.symptom_structurer import SymptomStructurer


INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88b701"
CORRELATION_ID = "018f2f9b-7c30-7981-b541-1a987c88b702"


class UnexpectedOfficialSearch:
    def search(self, *args, **kwargs):
        raise AssertionError("Synthetic clarification must happen before official RAG.")


class EmptyOfficialSearch:
    def __init__(self) -> None:
        self.calls = 0
        self.last_query = None

    def search(self, query, *args, **kwargs):
        self.calls += 1
        self.last_query = query
        return []


def _context(
    raw_symptom: str,
    *,
    previous_answers: list[dict[str, str]] | None = None,
) -> PipelineContext:
    return PipelineContext(
        trace_context=TraceContext(
            inquiry_id=INQUIRY_ID,
            correlation_id=CORRELATION_ID,
            ai_request_id="ai-req-synthetic-demo",
            state_version=1,
        ),
        raw_symptom=raw_symptom,
        previous_answers=previous_answers or [],
    )


def test_dataset_loads_36_isolated_clarification_candidates():
    retriever = SyntheticScenarioRetriever()

    assert len(retriever.groups) == 6
    assert len(retriever.candidates) == 36
    assert all(item.chunk_id.startswith("syn-scn-") for item in retriever.candidates)


def test_low_flow_requests_canonical_water_type_question_before_official_rag():
    ctx = _context("물이 약하게 나와요")
    result = MultiAgentPipeline(search_service=UnexpectedOfficialSearch()).run(ctx)

    assert result.context.retrieval_outcome == RetrievalOutcome.NOT_RUN
    assert result.context.synthetic_scenario_candidate_count == 6
    assert result.context.synthetic_clarification_requested is True
    assert result.context.awaiting_customer_input is True
    assert result.context.evidence_references == []
    assert len(result.context.followup_questions) == 1
    question = result.context.followup_questions[0]
    assert question.question_id == "followup-target-water-type"
    assert question.target_field == "target_water_type"
    assert question.options == ["냉수", "온수", "정수", "전체"]


def test_known_water_type_uses_occurrence_condition_as_the_single_question():
    ctx = _context("전체적으로 물이 약해요")
    result = MultiAgentPipeline(search_service=UnexpectedOfficialSearch()).run(ctx)

    question = result.context.followup_questions[0]
    assert result.context.structured_symptom.target_water_type == "전체"
    assert question.question_id == "followup-occurrence-condition"
    assert question.target_field == "occurrence_condition"


def test_hot_water_ambiguity_uses_occurrence_condition_question():
    ctx = _context("온수가 이상해요")
    result = MultiAgentPipeline(search_service=UnexpectedOfficialSearch()).run(ctx)

    assert result.context.structured_symptom.symptom_type == "온도 이상"
    assert result.context.structured_symptom.target_water_type == "온수"
    question = result.context.followup_questions[0]
    assert question.question_id == "followup-occurrence-condition"
    assert "여러 잔 연속 사용할 때" in question.options


@pytest.mark.parametrize(
    ("raw_symptom", "expected_question_id", "expected_target"),
    [
        (
            "물에서 냄새가 나요",
            "followup-taste-odor-applicability",
            "taste_odor_applicability",
        ),
        (
            "정수기 소리가 이상해요",
            "followup-occurrence-condition",
            "occurrence_condition",
        ),
        (
            "정수기에서 물이 새요",
            "followup-occurrence-condition",
            "occurrence_condition",
        ),
        (
            "필터 바꾸고 나서 이상해요",
            "followup-occurrence-condition",
            "occurrence_condition",
        ),
    ],
)
def test_demo_categories_choose_one_canonical_question(
    raw_symptom: str,
    expected_question_id: str,
    expected_target: str,
):
    ctx = _context(raw_symptom)
    result = MultiAgentPipeline(search_service=UnexpectedOfficialSearch()).run(ctx)

    assert len(result.context.followup_questions) == 1
    question = result.context.followup_questions[0]
    assert question.question_id == expected_question_id
    assert question.target_field == expected_target
    assert result.context.retrieval_outcome == RetrievalOutcome.NOT_RUN


def test_customer_answer_is_not_reasked_and_no_official_evidence_fails_closed():
    search = EmptyOfficialSearch()
    ctx = _context(
        "물이 약하게 나와요",
        previous_answers=[
            {
                "question_id": "followup-target-water-type",
                "answer_text": "냉수",
            }
        ],
    )
    result = MultiAgentPipeline(search_service=search).run(ctx)

    assert search.calls == 1
    assert "냉수" in search.last_query.query_text
    assert result.context.retrieval_outcome == RetrievalOutcome.NO_MATCH
    assert result.context.followup_questions == []
    assert result.context.awaiting_customer_input is False
    assert (
        result.context.usage_guidance.guidance_status
        == UsageGuidanceStatus.PENDING_CONSULTATION
    )


def test_electrical_leak_bypasses_synthetic_and_official_retrieval():
    ctx = _context("콘센트 근처로 물이 새요")
    result = MultiAgentPipeline(search_service=UnexpectedOfficialSearch()).run(ctx)

    assert result.context.safety_assessment.risk_level == RiskLevel.DANGER
    assert result.context.synthetic_scenario_candidate_count == 0
    assert result.context.synthetic_clarification_requested is False
    assert result.context.followup_questions == []
    assert result.context.retrieval_outcome == RetrievalOutcome.NOT_RUN


def test_harness_rejects_synthetic_scenario_as_verified_evidence():
    synthetic = RetrievedChunk(
        chunk_id="syn-scn-low-flow-001",
        document_title="Synthetic clarification scenario",
        manual_model="WPUJAC104DWH",
        model_code="WPUJAC104DWH",
        product_generation="D",
        content="clarification only",
        similarity_score=0.99,
        verification_status="official_verified",
        knowledge_type="SYNTHETIC_SCENARIO",
        evidence_eligible=False,
        official_evidence=False,
        customer_citation_allowed=False,
    )

    verification = HarnessVerifier().verify(
        product=ProductContext(
            model_code="WPUJAC104DWH",
            product_family=ProductFamily.DIRECT_WATER_PURIFIER,
            supported_functions=frozenset(),
            runtime_approved=True,
        ),
        evidence_chunks=[synthetic],
        safety_assessment=None,
        guidance=None,
        evidence_required=True,
    )

    assert verification.accepted_evidence_chunk_ids == []
    assert verification.rejected_evidence_chunk_ids == [synthetic.chunk_id]
