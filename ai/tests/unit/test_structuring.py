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
        correlation_id="corr-structuring-poor",
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
        correlation_id="corr-structuring-danger",
        ai_request_id="ai-req-structuring-danger",
        state_version=1,
        raw_symptom="정수기 아래로 물이 새고 전원선 주변이 젖었습니다",
        selected_symptoms=["누수"],
    ).to_analysis_result()

    assert result.safety_assessment.risk_level == RiskLevel.DANGER
    assert result.missing_fields == []
    assert result.followup_questions == []
