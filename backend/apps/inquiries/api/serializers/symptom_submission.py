"""Validated public contracts for SUBMIT_SYMPTOM."""

from collections.abc import Mapping

from rest_framework import serializers

from apps.inquiries.api.serializers.inquiry_response import (
    AllowedActionSerializer,
)
from apps.inquiries.models import Inquiry


class SymptomSubmissionSerializer(serializers.Serializer):
    """Confirm previously stored symptom input without accepting an overwrite."""

    state_version = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unexpected_fields = sorted(set(data) - set(self.fields))
            if unexpected_fields:
                raise serializers.ValidationError(
                    {
                        field: ["지원하지 않는 필드입니다."]
                        for field in unexpected_fields
                    }
                )
        return super().to_internal_value(data)


class SubmitSymptomResponseSerializer(serializers.Serializer):
    """Expose the transition snapshot without internal database keys."""

    inquiry_id = serializers.UUIDField()
    state = serializers.ChoiceField(
        choices=[Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS],
    )
    state_version = serializers.IntegerField(min_value=2)
    idempotent_replay = serializers.BooleanField()
    allowed_actions = AllowedActionSerializer(many=True)
