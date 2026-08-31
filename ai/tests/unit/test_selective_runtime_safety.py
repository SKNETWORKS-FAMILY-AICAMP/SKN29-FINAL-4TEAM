"""Independent counterexamples; never imports the 45-case reference Oracle."""

from types import SimpleNamespace

import pytest

from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.safety.risk_classifier import RiskClassifier
from ai.app.schemas import MissingField, RiskLevel, StructuredSymptom
from ai.app.structuring.followup_question_generator import FollowUpQuestionGenerator
from ai.app.structuring.llm_contracts import (
    FollowUpWording, FollowUpWordingLLMResponse, FollowUpWordingResult,
    SymptomEvidenceClaim, SymptomStructuringLLMResponse,
)
from ai.app.structuring.symptom_structurer import SymptomStructurer
from ai.app.validation.safety.guidance_message_guard import GuidanceMessageGuard


class ForbiddenSearch:
    def search(self, *args, **kwargs):
        raise AssertionError("search must not run")


class FailingStructurer:
    def __init__(self):
        self.calls = 0

    def structure_symptom(self, *args, **kwargs):
        self.calls += 1
        raise TimeoutError("provider unavailable")


def run(raw, *, runtime="single_rag", previous=(), client=None):
    return PipelineRouter(
        search_service=ForbiddenSearch(), symptom_llm_client=client,
        followup_llm_client=None, llm_client=None, mcp_context_service=None,
    ).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b801",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b802",
        ai_request_id="selective-safety-regression", state_version=3,
        raw_symptom=raw, runtime_name=runtime, previous_answers=list(previous),
    )


@pytest.mark.parametrize(("raw", "selected", "expected"), [
    ("물이 졸졸 나와요", "NOISE", "출수량 저하"),
    ("냉수가 미지근해요", "LEAK", "온도 이상"),
    ("누수가 아니라 냉수가 덜 시원해요", "LEAK", "온도 이상"),
    ("출수할 때 웅웅 소리가 나요", "TEMPERATURE_ABNORMAL", "소음 이상"),
    ("물이 전혀 안 나와요", "TEMPERATURE_ABNORMAL", "출수량 저하"),
])
def test_current_raw_symptom_wins_over_selected_hint(raw, selected, expected):
    assert SymptomStructurer().structure(raw, [selected]).symptom_type == expected


def test_explicit_raw_water_type_wins_over_old_answer():
    result = SymptomStructurer().structure("온수는 정상인데 냉수가 미지근해요", previous_answers=[
        {"question_id": "followup-target-water-type", "answer_text": "온수"},
    ])
    assert result.target_water_type == "냉수"


def test_selected_source_llm_claim_cannot_override_raw():
    class Client:
        def structure_symptom(self, *args, **kwargs):
            return SymptomStructuringLLMResponse(
                output=StructuredSymptom(symptom_type="소음 이상"),
                model_name="test-model", prompt_version="test", latency_ms=1,
                usage=SimpleNamespace(input_tokens=0, output_tokens=0, total_tokens=0),
                evidence_claims=(SymptomEvidenceClaim(field_name="symptom_type", value="소음 이상",
                    source="SELECTED_SYMPTOM", evidence_quote="NOISE"),),
            )
    result = SymptomStructurer(llm_client=Client()).structure("냉수가 미지근해요", ["NOISE"])
    assert result.symptom_type == "온도 이상"


def test_semantic_merge_cannot_restore_stale_water_type_after_validation():
    class Client:
        def structure_symptom(self, *args, **kwargs):
            return SymptomStructuringLLMResponse(
                output=StructuredSymptom(symptom_type="온도 이상", target_water_type="냉수"),
                model_name="test-model", prompt_version="test", latency_ms=1,
                usage=SimpleNamespace(input_tokens=0, output_tokens=0, total_tokens=0),
                evidence_claims=(SymptomEvidenceClaim(field_name="target_water_type", value="냉수",
                    source="RAW_SYMPTOM", evidence_quote="냉수가 미지근해요"),),
            )
    result = SymptomStructurer(llm_client=Client()).structure("온수는 정상인데 냉수가 미지근해요", previous_answers=[
        {"question_id": "followup-target-water-type", "answer_text": "온수"},
    ])
    assert result.target_water_type == "냉수"


@pytest.mark.parametrize("raw", [
    "전선 피복이 벗겨졌어요", "구리선이 드러났어요", "콘센트에 물이 들어갔어요",
    "콘센트가 물에 잠겼어요", "연기가 나는데 냄새는 없어요",
    "전선 피복이 벗겨졌는데 냄새는 없어요", "물이 새지만 작동은 정상이에요",
    "스파크가 튀는데 소음은 없어요", "연기가 나고 냄새는 없어요",
    "정수기 아래로 물이 흘러나와요", "온수가 샙니다",
    "연기가 나는 게 정상인가요?", "전\u200b선 피복이 벗겨졌어요",
    "순간온수 모듈은 정상이지만 연기가 나요",
])
def test_explicit_physical_danger_survives_provider_failure(raw):
    structurer = SymptomStructurer(llm_client=FailingStructurer())
    structurer.structure(raw)
    assessment = RiskClassifier().classify(raw, safety_signals=structurer.last_safety_signals)
    assert structurer.last_safety_signals.requires_danger_policy
    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation and assessment.matched_safety_rule_ids


@pytest.mark.parametrize("raw", [
    "연기는 없습니다", "전선 피복이 벗겨진 것은 아닙니다", "스파크가 튀지 않아요",
    "연기가 나지 않는데 냄새도 없어요", "물이 새지 않지만 작동은 정상이에요",
    "콘센트에 물이 들어가지 않았어요", "콘센트가 물에 잠기지 않았어요",
    "콘센트에 물이 들어가면 어떻게 하나요?", "콘센트가 물에 잠기면 위험한가요?",
    "전선 피복이 벗겨지면 어떻게 하나요?", "물 샘플을 보냈어요", "정수기 아래에 물건을 놓았어요",
])
def test_denial_hypothetical_and_unrelated_nouns_are_not_observed_danger(raw):
    assert RiskClassifier().classify(raw).risk_level != RiskLevel.DANGER


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
@pytest.mark.parametrize("raw", ["전선 피복이 벗겨졌어요", "온수 히터 고장이에요"])
def test_danger_bypasses_external_provider_and_search(runtime, raw):
    client = FailingStructurer()
    response = run(raw, runtime=runtime, client=client).to_analysis_result()
    assert client.calls == 0
    assert response.safety_assessment.risk_level == RiskLevel.DANGER
    assert response.usage_guidance.guidance_status.value in {"TOTAL_STOP", "PARTIAL_STOP"}


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
def test_danger_in_answer_to_unrelated_question_is_not_discarded(runtime):
    response = run("냉수가 미지근해요", runtime=runtime, previous=[{
        "question_id": "followup-occurrence-time", "answer_text": "전선 피복이 벗겨졌어요",
    }]).to_analysis_result()
    assert response.safety_assessment.risk_level == RiskLevel.DANGER
    assert response.usage_guidance.guidance_status.value == "TOTAL_STOP"


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
@pytest.mark.parametrize("answer", ["확인 불가", "모름", "답변 거절", "잘 모르겠어요"])
def test_required_answer_unknown_does_not_trigger_search_or_repeat(runtime, answer):
    result = run("온도가 이상해요", runtime=runtime, previous=[{
        "question_id": "followup-target-water-type", "answer_text": answer,
    }])
    response = result.to_analysis_result()
    assert result.context.retrieval_outcome.value == "NOT_RUN"
    assert response.status.value == "FALLBACK"
    assert response.fallback_reason_code.value == "UNSPECIFIED_FALLBACK"
    assert response.failure_stage.value == "CHECKING_MISSING_FIELDS"
    assert response.safety_assessment.requires_consultation
    assert not response.followup_questions and not response.evidence_references


@pytest.mark.parametrize("unsafe", [
    "확인을 위해 커버를 벗긴 뒤 전선을 살펴본 결과를 알려주시겠어요?",
    "정수기를 분해해서 내부를 확인해 보시겠어요?",
    "고장이 확실하므로 전선을 확인해 보실까요?",
    "안전한 물이니 마셔도 괜찮습니다. 이미 어떤 조치를 했나요?",
    "이미 확인한 내용에 따라 덮개를 제거하고 전선을 살펴봐요?",
])
def test_generated_unsafe_question_is_replaced_by_fixed_question(unsafe):
    class Client:
        def generate_followup_wording(self, *args, **kwargs):
            return FollowUpWordingLLMResponse(
                output=FollowUpWordingResult(questions=[FollowUpWording(
                    target_field="actions_taken", question_text=unsafe,
                )]), model_name="test-model", prompt_version="test", latency_ms=1,
                usage=SimpleNamespace(input_tokens=0, output_tokens=0, total_tokens=0),
            )
    questions = FollowUpQuestionGenerator(Client()).generate(
        [MissingField(field_name="actions_taken", reason="확인", importance="low")],
        symptom=StructuredSymptom(symptom_type="온도 이상", target_water_type="냉수"),
    )
    assert len(questions) == 1
    assert questions[0].question_text == "이미 확인하거나 조치해 본 내용이 있나요?"


SOURCE = "전원이 꺼져 있으면 표시등을 확인하세요. 문제가 계속되면 고객상담센터로 문의하세요."


@pytest.mark.parametrize("message", [
    SOURCE + " 이 물은 안전하니 마셔도 됩니다.",
    SOURCE + " 30분 동안 기다리세요.",
    "표시등을 확인하세요. 문제가 계속되면 고객상담센터로 문의하세요.",
    "전원이 꺼져 있으면 표시등을 확인하세요.",
    "문제가 계속되면 고객상담센터로 문의하세요. 전원이 꺼져 있으면 표시등을 확인하세요.",
    "전원이 꺼져 있으면 표시등을 확인하지 마세요. 문제가 계속되면 고객상담센터로 문의하세요.",
])
def test_guidance_rejects_unsupported_claim_condition_omission_and_reordering(message):
    with pytest.raises(ValueError):
        GuidanceMessageGuard().validate_grounding(message, grounding_texts=[SOURCE])


def test_guidance_accepts_complete_evidence_with_limited_politeness_change():
    GuidanceMessageGuard().validate_grounding(
        SOURCE.replace("확인하세요", "확인해 주세요").replace("문의하세요", "문의하십시오"),
        grounding_texts=[SOURCE],
    )
