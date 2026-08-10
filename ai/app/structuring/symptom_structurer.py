"""고객 자연어 증상을 표준 증상 필드로 구조화."""

from __future__ import annotations

from ..schemas import StructuredSymptom
from .symptom_normalizer import SymptomNormalizer


class SymptomStructurer:
    """원문과 기존 문진 답변을 계약의 StructuredSymptom으로 변환한다."""

    _QUESTION_FIELD_MAP = {
        "followup-occurrence-time": "occurrence_time",
        "followup-target-water-type": "target_water_type",
        "followup-occurrence-condition": "occurrence_condition",
        "followup-actions-taken": "actions_taken",
    }
    _INTENTIONAL_NON_ANSWERS = {
        "답변하지 않음",
        "답변 거절",
        "모름",
        "모르겠음",
        "확인 불가",
    }

    def __init__(self, normalizer: SymptomNormalizer | None = None) -> None:
        self.normalizer = normalizer or SymptomNormalizer()

    def structure(
        self,
        raw_text: str,
        selected_symptoms: list[str] | None = None,
        previous_answers: list[dict[str, str]] | None = None,
    ) -> StructuredSymptom:
        selected = selected_symptoms or []
        answer_by_field: dict[str, str] = {}
        actions = self.normalizer.extract_actions(raw_text)

        for answer in previous_answers or []:
            if not isinstance(answer, dict):
                continue
            question_id = answer.get("question_id", "")
            answer_text = answer.get("answer_text", "").strip()
            target_field = self._QUESTION_FIELD_MAP.get(question_id)
            if not target_field or not answer_text:
                continue
            if answer_text in self._INTENTIONAL_NON_ANSWERS:
                # 거절·확인 불가를 실제 증상 값으로 저장하지 않되 같은 질문은 반복하지 않는다.
                continue
            if target_field == "actions_taken":
                if answer_text not in actions:
                    actions.append(answer_text)
            else:
                answer_by_field[target_field] = answer_text

        return StructuredSymptom(
            symptom_type=self.normalizer.normalize_symptom_type(raw_text, selected),
            occurrence_time=(
                answer_by_field.get("occurrence_time")
                or self.normalizer.extract_occurrence_time(raw_text)
            ),
            target_water_type=(
                answer_by_field.get("target_water_type")
                or self.normalizer.normalize_water_type(raw_text)
            ),
            occurrence_condition=(
                answer_by_field.get("occurrence_condition")
                or self.normalizer.extract_occurrence_condition(raw_text)
            ),
            error_code=self.normalizer.extract_error_code(raw_text),
            accompanying_symptoms=list(dict.fromkeys(selected)),
            actions_taken=actions,
        )
