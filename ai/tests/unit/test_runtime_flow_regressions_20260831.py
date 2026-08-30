from types import SimpleNamespace

import pytest

from ai.app.retrieval.filters import evidence_topic_filter as topic_filter_module
from ai.app.retrieval.filters.evidence_topic_filter import EvidenceTopicFilter
from ai.app.schemas import MissingField
from ai.app.structuring.followup_question_generator import FollowUpQuestionGenerator
from ai.app.structuring.llm_contracts import FollowUpWording
from ai.app.structuring.symptom_normalizer import SymptomNormalizer


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
