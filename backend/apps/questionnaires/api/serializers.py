"""Public serializers for the CARE_PRECHECK customer workflow."""

from __future__ import annotations

import math
import re
from typing import Any

from rest_framework import serializers

from apps.questionnaires.models import QuestionnaireSession


QUESTION_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,39}$")
MAX_ANSWER_COUNT = 100
MAX_TEXT_LENGTH = 2000
MAX_LIST_LENGTH = 50


def _validate_answer_value(value: Any, *, field_name: str) -> None:
    """Keep the answer payload portable and bounded across DB clients."""

    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if len(value) > MAX_TEXT_LENGTH:
            raise serializers.ValidationError(
                f"{field_name} 답변은 {MAX_TEXT_LENGTH}자 이하여야 합니다."
            )
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise serializers.ValidationError(
                f"{field_name} 숫자 답변은 유한값이어야 합니다."
            )
        return
    if isinstance(value, list):
        if len(value) > MAX_LIST_LENGTH:
            raise serializers.ValidationError(
                f"{field_name} 복수 답변은 {MAX_LIST_LENGTH}개 이하여야 합니다."
            )
        for item in value:
            if isinstance(item, (dict, list)):
                raise serializers.ValidationError(
                    f"{field_name} 복수 답변은 중첩 구조를 허용하지 않습니다."
                )
            _validate_answer_value(item, field_name=field_name)
        return
    raise serializers.ValidationError(
        f"{field_name} 답변 형식이 지원되지 않습니다."
    )


class CarePrecheckAnswersMixin:
    """Validate a question-code keyed JSON object without mutating values."""

    def validate_answers(self, value: Any) -> dict:
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "answers는 질문 코드별 JSON object여야 합니다."
            )
        if not value:
            raise serializers.ValidationError(
                "하나 이상의 답변이 필요합니다."
            )
        if len(value) > MAX_ANSWER_COUNT:
            raise serializers.ValidationError(
                f"답변은 {MAX_ANSWER_COUNT}개 이하여야 합니다."
            )
        for question_code, answer_value in value.items():
            if not isinstance(question_code, str) or not (
                QUESTION_CODE_PATTERN.fullmatch(question_code)
            ):
                raise serializers.ValidationError(
                    "질문 코드는 영문 대문자로 시작하는 40자 이하의 "
                    "영문 대문자·숫자·밑줄 형식이어야 합니다."
                )
            _validate_answer_value(
                answer_value,
                field_name=question_code,
            )
        return value


class StartCarePrecheckRequestSerializer(serializers.Serializer):
    subscription_id = serializers.UUIDField()


class SaveCarePrecheckRequestSerializer(
    CarePrecheckAnswersMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)
    answers = serializers.JSONField()


class SubmitCarePrecheckRequestSerializer(
    CarePrecheckAnswersMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)
    answers = serializers.JSONField()


class CarePrecheckSessionSerializer(serializers.Serializer):
    questionnaire_session_id = serializers.UUIDField()
    subscription_id = serializers.UUIDField()
    questionnaire_type_code = serializers.ChoiceField(
        choices=QuestionnaireSession.QuestionnaireType.values,
    )
    questionnaire_version = serializers.CharField()
    status_code = serializers.ChoiceField(
        choices=QuestionnaireSession.Status.values,
    )
    state_version = serializers.IntegerField(min_value=1)
    answers = serializers.JSONField()
    started_at = serializers.DateTimeField()
    submitted_at = serializers.DateTimeField(allow_null=True)
    linked_inquiry_id = serializers.UUIDField(allow_null=True)
    idempotent_replay = serializers.BooleanField(required=False)
