"""T-026 증상 구조화·누락 필드·추가 질문 검증."""

from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.schemas import RiskLevel
from ai.app.structuring import (
    DuplicateQuestionGuard,
    FollowUpQuestionGenerator,
    MissingFieldChecker,
    SymptomStructurer,
)


class EmptySearchService:
    def search(self, *args, **kwargs):
        return []


def test_structures_low_flow_and_only_reports_unconfirmed_fields():
    symptom = SymptomStructurer().structure(
        "어제부터 냉수 버튼을 누르면 물이 졸졸 나옵니다",
        ["출수량 저하"],
    )

    assert symptom.symptom_type == "출수량 저하"
    assert symptom.occurrence_time == "어제부터"
    assert symptom.target_water_type == "냉수"
    assert symptom.occurrence_condition is not None
    assert [item.field_name for item in MissingFieldChecker().check(symptom)] == ["actions_taken"]


def test_previous_answer_populates_field_and_blocks_duplicate_question():
    previous_answers = [
        {"question_id": "followup-occurrence-time", "answer_text": "3일 전부터"},
        {"question_id": "followup-actions-taken", "answer_text": "전원 재부팅"},
    ]
    symptom = SymptomStructurer().structure("냉수 출수량이 줄었습니다", [], previous_answers)
    missing = MissingFieldChecker().check(symptom)
    questions = FollowUpQuestionGenerator().generate(missing)
    filtered = DuplicateQuestionGuard().filter(questions, previous_answers)

    assert symptom.occurrence_time == "3일 전부터"
    assert symptom.actions_taken == ["전원 재부팅"]
    assert "occurrence_time" not in {item.field_name for item in missing}
    assert "actions_taken" not in {question.target_field for question in filtered}


def test_information_poor_input_generates_deterministic_questions():
    result = PipelineRouter(search_service=EmptySearchService()).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b401",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b499",
        ai_request_id="ai-req-structuring-poor",
        state_version=1,
        raw_symptom="이상해요",
    ).to_analysis_result()

    assert {item.field_name for item in result.missing_fields} == {
        "occurrence_time",
        "target_water_type",
        "occurrence_condition",
        "actions_taken",
    }
    assert [question.target_field for question in result.followup_questions] == [
        "occurrence_time",
        "target_water_type",
        "occurrence_condition",
        "actions_taken",
    ]


def test_danger_input_prioritizes_safety_and_skips_question_generation():
    result = PipelineRouter(search_service=None).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b402",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b499",
        ai_request_id="ai-req-structuring-danger",
        state_version=1,
        raw_symptom="정수기 아래로 물이 새고 전원선 주변이 젖었습니다",
        selected_symptoms=["누수"],
    ).to_analysis_result()

    assert result.safety_assessment.risk_level == RiskLevel.DANGER
    assert result.missing_fields == []
    assert result.followup_questions == []


def test_typo_and_negated_symptom_are_structured_without_false_leak_label():
    typo = SymptomStructurer().structure("어제부터 냉수 출수양이 줄고 물이 쫄쫄 나와요")
    negated = SymptomStructurer().structure("누수는 아니고 어제부터 냉수가 미지근합니다")
    error_code = SymptomStructurer().structure("정수 버튼을 누르면 E-12가 표시됩니다")

    assert typo.symptom_type == "출수량 저하"
    assert negated.symptom_type == "온도 이상"
    assert error_code.error_code == "E-12"


def test_declined_answer_is_not_stored_as_symptom_value_and_is_not_reasked():
    previous_answers = [
        {"question_id": "followup-occurrence-time", "answer_text": "답변하지 않음"},
    ]
    symptom = SymptomStructurer().structure("냉수가 미지근합니다", previous_answers=previous_answers)
    missing = MissingFieldChecker().check(symptom)
    questions = DuplicateQuestionGuard().filter(
        FollowUpQuestionGenerator().generate(missing),
        previous_answers,
    )

    assert symptom.occurrence_time is None
    assert "occurrence_time" in {item.field_name for item in missing}
    assert "occurrence_time" not in {question.target_field for question in questions}
