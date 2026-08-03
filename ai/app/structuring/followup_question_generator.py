"""누락 정보 확인을 위한 추가 질문 생성."""

from ..schemas import FollowUpQuestion, MissingField


class FollowUpQuestionGenerator:
    """누락 필드별 결정적인 질문 DTO를 생성한다."""

    _QUESTIONS = {
        "occurrence_time": ("증상은 언제부터 시작됐나요?", ["오늘", "어제", "2~3일 전", "일주일 이상 전"]),
        "target_water_type": ("어떤 출수에서 증상이 발생하나요?", ["냉수", "온수", "정수", "전체"]),
        "occurrence_condition": (
            "증상은 언제 또는 어떤 조건에서 발생하나요?",
            ["항상", "간헐적으로", "출수 버튼을 누를 때", "특정 기능 사용 중"],
        ),
        "actions_taken": (
            "이미 확인하거나 조치해 본 내용이 있나요?",
            ["없음", "전원 재부팅", "원수 밸브 확인", "필터 확인"],
        ),
    }

    def generate(self, missing_fields: list[MissingField]) -> list[FollowUpQuestion]:
        questions: list[FollowUpQuestion] = []
        for missing in missing_fields:
            definition = self._QUESTIONS.get(missing.field_name)
            if definition is None:
                continue
            question_text, options = definition
            questions.append(
                FollowUpQuestion(
                    question_id=f"followup-{missing.field_name.replace('_', '-')}",
                    question_text=question_text,
                    options=options,
                    target_field=missing.field_name,
                )
            )
        return questions
