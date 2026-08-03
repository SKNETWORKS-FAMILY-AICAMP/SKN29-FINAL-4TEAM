"""이미 확인한 내용을 반복 질문하지 않도록 차단."""

from ..schemas import FollowUpQuestion


class DuplicateQuestionGuard:
    """기존 질문 ID와 목표 필드를 기준으로 반복 질문을 제거한다."""

    _QUESTION_FIELD_MAP = {
        "followup-occurrence-time": "occurrence_time",
        "followup-target-water-type": "target_water_type",
        "followup-occurrence-condition": "occurrence_condition",
        "followup-actions-taken": "actions_taken",
    }

    def filter(
        self,
        questions: list[FollowUpQuestion],
        previous_answers: list[dict[str, str]] | None = None,
    ) -> list[FollowUpQuestion]:
        answered_ids: set[str] = set()
        answered_fields: set[str] = set()
        for answer in previous_answers or []:
            if not isinstance(answer, dict) or not answer.get("answer_text", "").strip():
                continue
            question_id = answer.get("question_id", "")
            answered_ids.add(question_id)
            target_field = self._QUESTION_FIELD_MAP.get(question_id)
            if target_field:
                answered_fields.add(target_field)

        result: list[FollowUpQuestion] = []
        seen_fields: set[str] = set()
        for question in questions:
            if question.question_id in answered_ids or question.target_field in answered_fields:
                continue
            if question.target_field in seen_fields:
                continue
            seen_fields.add(question.target_field)
            result.append(question)
        return result
