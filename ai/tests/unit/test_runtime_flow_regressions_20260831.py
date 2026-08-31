from types import SimpleNamespace
from uuid import UUID

import pytest

from ai.app.retrieval.filters import evidence_topic_filter as topic_filter_module
from ai.app.retrieval.filters.evidence_topic_filter import EvidenceTopicFilter
from ai.app.retrieval.filters.evidence_applicability_gate import (
    EvidenceApplicability,
    EvidenceApplicabilityGate,
)
from ai.app.retrieval.filters.scenario_evidence_selector import ScenarioEvidenceSelector
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.retrieval.query.context_builder import RetrievalContextBuilder
from ai.app.orchestration.clarification_policy import should_wait_for_customer_input
from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.orchestration.pipelines.single_rag_pipeline import SingleRAGPipeline
from ai.app.safety import RiskClassifier, UsageGuidanceClassifier
from ai.app.schemas import (
    FollowUpQuestion,
    MissingField,
    RiskLevel,
    SafetyAssessment,
    StructuredSymptom,
    TraceContext,
)
from ai.app.structuring.followup_question_generator import FollowUpQuestionGenerator
from ai.app.structuring.llm_contracts import (
    FollowUpWording,
    SafetySignals,
    SymptomEvidenceClaim,
    SymptomStructuringLLMResponse,
)
from ai.app.structuring.missing_field_checker import MissingFieldChecker
from ai.app.structuring.symptom_normalizer import SymptomNormalizer
from ai.app.structuring.symptom_structurer import SymptomStructurer


class _SemanticSymptomClient:
    prompt_version = "symptom_structuring/v1"

    def __init__(self, output, claims, *, signals=None):
        self.output = output
        self.claims = tuple(claims)
        self.signals = signals or SafetySignals()

    def structure_symptom(self, request, *, timeout_seconds):
        return SymptomStructuringLLMResponse(
            output=self.output,
            model_name="fake-semantic-model",
            prompt_version=self.prompt_version,
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2),
            latency_ms=1.0,
            evidence_claims=self.claims,
            safety_signals=self.signals,
        )


def _claim(field_name, value, quote, source="RAW_SYMPTOM"):
    return SymptomEvidenceClaim(
        field_name=field_name,
        value=value,
        source=source,
        evidence_quote=quote,
    )


def _chunk(content: str, *, chunk_id="HOT") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_title="공식 사용설명서",
        manual_model="WPUJAC104DWH",
        model_code="WPUJAC104DWH",
        content=content,
        similarity_score=0.9,
        topic_code="symptom_hot_water_safety",
    )


def test_occurrence_condition_wording_cannot_turn_into_start_time_question():
    generator = FollowUpQuestionGenerator()
    fallback = generator._fixed_questions(
        [
            MissingField(
                field_name="occurrence_condition",
                reason="발생 조건 확인",
                importance="medium",
            )
        ]
    )

    with pytest.raises(ValueError):
        generator._apply_wording(
            fallback,
            [
                FollowUpWording(
                    target_field="occurrence_condition",
                    question_text="증상이 어제부터 발생했나요?",
                )
            ],
        )


def test_occurrence_condition_wording_accepts_condition_question():
    generator = FollowUpQuestionGenerator()
    fallback = generator._fixed_questions(
        [
            MissingField(
                field_name="occurrence_condition",
                reason="발생 조건 확인",
                importance="medium",
            )
        ]
    )

    result = generator._apply_wording(
        fallback,
        [
            FollowUpWording(
                target_field="occurrence_condition",
                question_text="증상이 항상 발생하나요, 아니면 특정 조건에서 발생하나요?",
            )
        ],
    )

    assert result[0].target_field == "occurrence_condition"
    assert result[0].question_text.startswith("증상이 항상")


def test_low_flow_normalizer_understands_jal_an_nawaeyo():
    normalizer = SymptomNormalizer()

    assert (
        normalizer.normalize_symptom_type(
            "어제부터 냉수가 잘 안 나와요",
            [],
        )
        == "출수량 저하"
    )


def test_low_flow_topic_filter_rejects_cold_temperature_chunk(monkeypatch):
    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )
    low_flow = SimpleNamespace(
        chunk_id="LOW",
        topic_code="symptom_low_flow",
    )
    cold_temperature = SimpleNamespace(
        chunk_id="COLD",
        topic_code="symptom_cold_temperature",
    )

    filtered = EvidenceTopicFilter().filter_chunks(
        [cold_temperature, low_flow],
        symptom_type="출수량 저하",
        target_water_type="냉수",
    )

    assert filtered == [low_flow]


def test_temperature_topic_uses_target_water_type(monkeypatch):
    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )
    cold_temperature = SimpleNamespace(
        chunk_id="COLD",
        topic_code="symptom_cold_temperature",
    )
    hot_temperature = SimpleNamespace(
        chunk_id="HOT",
        topic_code="symptom_hot_water_safety",
    )

    cold = EvidenceTopicFilter().filter_chunks(
        [hot_temperature, cold_temperature],
        symptom_type="온도 이상",
        target_water_type="냉수",
    )
    hot = EvidenceTopicFilter().filter_chunks(
        [cold_temperature, hot_temperature],
        symptom_type="온도 이상",
        target_water_type="온수",
    )

    assert cold == [cold_temperature]
    assert hot == [hot_temperature]


@pytest.mark.parametrize(
    "raw_symptom",
    [
        "냉수가 자꾸 새네요",
        "물이 밑으로 흐르고 있어요",
        "정수기 아래에 물이 계속 고여요",
        "호스 쪽에서 물이 새는 것 같아요",
    ],
)
def test_llm_semantic_leak_meaning_is_primary_without_expanding_rules(raw_symptom):
    result = SymptomStructurer(
        llm_client=_SemanticSymptomClient(
            StructuredSymptom(symptom_type="제품 누수"),
            [_claim("symptom_type", "제품 누수", raw_symptom)],
        )
    ).structure(raw_symptom, ["TEMPERATURE_ABNORMAL"])

    assert result.symptom_type == "제품 누수"


def test_raw_semantic_meaning_can_override_selected_category_hint():
    raw = "냉수가 자꾸 새네요"
    result = SymptomStructurer(
        llm_client=_SemanticSymptomClient(
            StructuredSymptom(symptom_type="제품 누수", target_water_type="냉수"),
            [
                _claim("symptom_type", "제품 누수", raw),
                _claim("target_water_type", "냉수", "냉수"),
            ],
        )
    ).structure(raw, ["TEMPERATURE_ABNORMAL"])

    assert result.symptom_type == "제품 누수"
    assert result.target_water_type == "냉수"


def test_symptom_type_provenance_rejects_context_only_quote():
    result = SymptomStructurer(
        llm_client=_SemanticSymptomClient(
            StructuredSymptom(symptom_type="온도 이상", target_water_type="냉수"),
            [
                _claim("symptom_type", "온도 이상", "냉수"),
                _claim("target_water_type", "냉수", "냉수"),
            ],
        )
    ).structure("냉수가 자꾸 새네요")

    assert result.symptom_type != "온도 이상"


@pytest.mark.parametrize(
    ("raw_symptom", "signals"),
    [
        (
            "정수기 전선 피복이 벗겨졌어요",
            SafetySignals(electrical_component_damage=True, exposed_wire=True),
        ),
        (
            "전원선 주변으로 물이 새요",
            SafetySignals(water_near_electrical_part=True),
        ),
    ],
)
def test_semantic_safety_signal_drives_deterministic_danger_policy(raw_symptom, signals):
    assessment = RiskClassifier().classify(
        raw_symptom,
        safety_signals=signals,
    )
    guidance = UsageGuidanceClassifier().determine_guidance(
        assessment,
        raw_symptom,
        has_evidence=False,
    )

    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation is True
    assert guidance.guidance_status.value == "TOTAL_STOP"


def test_semantic_safety_signal_is_wired_through_runtime_without_public_schema_change():
    raw = "정수기 전선 피복이 벗겨졌어요"
    result = PipelineRouter(
        search_service=None,
        symptom_llm_client=_SemanticSymptomClient(
            StructuredSymptom(symptom_type="전기 이상"),
            [_claim("symptom_type", "전기 이상", raw)],
            signals=SafetySignals(
                electrical_component_damage=True,
                exposed_wire=True,
            ),
        ),
    ).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b801",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b802",
        ai_request_id="ai-req-semantic-safety",
        state_version=1,
        raw_symptom=raw,
    ).to_analysis_result()

    assert result.safety_assessment.risk_level == RiskLevel.DANGER
    assert result.safety_assessment.requires_consultation is True
    assert result.usage_guidance.guidance_status.value == "TOTAL_STOP"


def test_noise_missing_field_policy_does_not_require_water_type():
    missing = MissingFieldChecker().check(
        StructuredSymptom(symptom_type="소음 이상")
    )

    assert "target_water_type" not in {item.field_name for item in missing}


def test_retrieval_context_contains_validated_followup_fields_and_redacts_pii():
    query = RetrievalContextBuilder().build(
        raw_symptom="온수가 이상해요 010-1234-5678",
        structured_symptom=StructuredSymptom(
            symptom_type="온도 이상",
            occurrence_time="어제부터",
            target_water_type="온수",
            occurrence_condition="항상 미지근함",
            actions_taken=["전원 재부팅"],
        ),
    )

    assert "어제부터" in query
    assert "항상 미지근함" in query
    assert "전원 재부팅" in query
    assert "010-1234-5678" not in query


def test_hot_water_scenario_selector_removes_unmentioned_subscenarios():
    content = (
        "온수가 미지근하면 두 번째 잔의 온도를 확인합니다. "
        "전원 플러그를 뽑고 10초 뒤 재연결합니다. "
        "스팀이 계속 나오면 사용을 중지합니다. "
        "LCD 모듈 오류를 확인합니다. "
        "온수가 나오지 않으면 잠금을 확인합니다. "
        "온수는 음용하지 않습니다."
    )
    selection = ScenarioEvidenceSelector().select_chunks(
        [_chunk(content)],
        structured_symptom=StructuredSymptom(
            symptom_type="온도 이상",
            target_water_type="온수",
            occurrence_condition="항상 미지근함",
        ),
        raw_symptom="어제부터 온수가 미지근해요",
        applicability=None,
    )
    selected = selection.chunks[0].content

    assert "두 번째 잔" in selected
    assert "10초" in selected
    assert "음용하지" in selected
    assert "스팀" not in selected
    assert "LCD" not in selected
    assert "나오지 않" not in selected


@pytest.mark.parametrize(
    "applicability",
    [
        EvidenceApplicability.ABSENCE_OVER_10_DAYS,
        EvidenceApplicability.LONG_UNUSED,
        EvidenceApplicability.UNSUITABLE_INSTALLATION,
    ],
)
def test_known_taste_odor_applicability_does_not_remove_official_chunk(applicability):
    chunks = [_chunk("공식 물맛·냄새 점검 근거", chunk_id="TASTE")]

    assert EvidenceApplicabilityGate().filter_chunks(
        chunks,
        symptom_type="물맛/냄새 이상",
        applicability=applicability,
    ) == chunks


def test_single_rag_waits_for_required_question_but_not_optional_question():
    trace = TraceContext(
        inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b701"),
        correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b702"),
        ai_request_id="ai-req-clarification",
        state_version=1,
    )
    ctx = PipelineContext(
        trace_context=trace,
        raw_symptom="온도가 이상해요",
        structured_symptom=StructuredSymptom(symptom_type="온도 이상"),
        safety_assessment=SafetyAssessment(
            risk_level="general",
            priority="general_guidance",
            requires_consultation=False,
            matched_safety_rule_ids=[],
            safety_reason="일반",
        ),
        missing_fields=[
            MissingField(
                field_name="target_water_type",
                reason="필수",
                importance="high",
            )
        ],
        followup_questions=[
            FollowUpQuestion(
                question_id="followup-target-water-type",
                question_text="어떤 출수에서 발생하나요?",
                target_field="target_water_type",
            )
        ],
    )

    assert should_wait_for_customer_input(ctx) is True
    assert SingleRAGPipeline._route_after_missing_fields({"ctx": ctx}) == "questionnaire_pending"
    ctx.missing_fields[0] = ctx.missing_fields[0].model_copy(
        update={"importance": "low"}
    )
    assert should_wait_for_customer_input(ctx) is False
