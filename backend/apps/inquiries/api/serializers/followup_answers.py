"""Validated public contracts for SUBMIT_ANSWERS."""

from collections.abc import Mapping

from rest_framework import serializers

from apps.inquiries.api.serializers.inquiry_response import (
    AllowedActionSerializer,
)
from apps.inquiries.models import Inquiry


class FollowUpAnswerItemSerializer(serializers.Serializer):
    """Accept exactly one text or one approved single-choice value."""

    question_id = serializers.UUIDField()
    answer_text = serializers.CharField(
        required=False,
        allow_blank=False,
        trim_whitespace=True,
        max_length=1000,
    )
    answer_payload = serializers.JSONField(required=False)

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unexpected = sorted(set(data) - set(self.fields))
            if unexpected:
                raise serializers.ValidationError(
                    {field: ["This field is not allowed."] for field in unexpected}
                )
        return super().to_internal_value(data)

    def validate(self, attrs):
        has_text = "answer_text" in attrs
        has_payload = "answer_payload" in attrs
        if has_text == has_payload:
            raise serializers.ValidationError(
                "Provide exactly one of answer_text or answer_payload."
            )
        if has_payload:
            payload = attrs["answer_payload"]
            if not isinstance(payload, dict) or set(payload) != {
                "selected_option"
            }:
                raise serializers.ValidationError(
                    {
                        "answer_payload": [
                            "Only selected_option is allowed."
                        ]
                    }
                )
            option = payload.get("selected_option")
            if (
                not isinstance(option, str)
                or not option.strip()
                or len(option.strip()) > 200
            ):
                raise serializers.ValidationError(
                    {
                        "answer_payload": [
                            "selected_option must contain 1 to 200 characters."
                        ]
                    }
                )
            attrs["answer_payload"] = {
                "selected_option": option.strip(),
            }
        return attrs


class SubmitFollowUpAnswersSerializer(serializers.Serializer):
    state_version = serializers.IntegerField(min_value=1)
    answers = FollowUpAnswerItemSerializer(
        many=True,
        allow_empty=False,
        min_length=1,
        max_length=50,
    )

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unexpected = sorted(set(data) - set(self.fields))
            if unexpected:
                raise serializers.ValidationError(
                    {field: ["This field is not allowed."] for field in unexpected}
                )
        return super().to_internal_value(data)

    def validate_answers(self, answers):
        question_ids = [answer["question_id"] for answer in answers]
        if len(question_ids) != len(set(question_ids)):
            raise serializers.ValidationError(
                "The same question_id cannot be submitted twice."
            )
        return answers


class SubmitFollowUpAnswersResponseSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=300)
    inquiry_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=[Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS]
    )
    state_version = serializers.IntegerField(min_value=2)
    allowed_actions = AllowedActionSerializer(many=True)
    idempotent_replay = serializers.BooleanField()
    resource = serializers.JSONField(allow_null=True)

    def validate_resource(self, value):
        if value is not None:
            raise serializers.ValidationError(
                "SUBMIT_ANSWERS does not return a resource."
            )
        return value
