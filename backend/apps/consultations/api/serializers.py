"""Consultation workflow request serializers."""

from collections.abc import Mapping

from rest_framework import serializers

from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry


class RejectUnknownFieldsMixin:
    """Reject request keys that DRF would otherwise silently ignore."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {
                        field: ["지원하지 않는 필드입니다."]
                        for field in unknown
                    }
                )
        return super().to_internal_value(data)


class StateTransitionRequestSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)


class SaveConsultationRequestSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)
    summary = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=4000,
        trim_whitespace=True,
    )
    consultation_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=8000,
        trim_whitespace=True,
    )
    additional_check = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=4000,
        trim_whitespace=True,
    )
    customer_guidance = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        trim_whitespace=True,
    )
    result_code = serializers.ChoiceField(
        required=False,
        choices=Consultation.Outcome.values,
    )
    usage_guidance_status = serializers.ChoiceField(
        required=False,
        choices=Inquiry.UsageGuidanceStatus.values,
    )

    def validate(self, attrs):
        fields = set(attrs) - {"state_version"}
        if not fields:
            raise serializers.ValidationError(
                "저장할 상담 내용을 한 개 이상 보내야 합니다."
            )
        return attrs


class CompleteConsultationRequestSerializer(
    StateTransitionRequestSerializer,
):
    pass
