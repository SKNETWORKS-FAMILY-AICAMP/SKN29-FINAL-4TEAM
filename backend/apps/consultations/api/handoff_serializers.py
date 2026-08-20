"""Strict internal DTO for sanitized AI consultation handoffs."""

from __future__ import annotations

import re
from collections.abc import Mapping

from rest_framework import serializers


PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:01[016789])[- ]?\d{3,4}[- ]?\d{4}(?!\d)"
)
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)


class RejectUnknownFieldsMixin:
    """Reject keys that DRF serializers would otherwise ignore."""

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


class HandoffQuestionnaireAnswerSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    field_name = serializers.CharField(max_length=100)
    answer = serializers.CharField(max_length=500)


class HandoffEvidenceSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    chunk_id = serializers.CharField(max_length=200)
    document_title = serializers.CharField(max_length=500)
    page = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    summary = serializers.CharField(max_length=2000)


class ConsultationHandoffRequestSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    """Allowlist the PM-owned Handoff result without raw internal fields."""

    # The current AI-owned ConsultationHandoffResult has no schema_version
    # field.  Keep the Backend ledger version explicit without forcing the AI
    # owner to extend an already-approved DTO.
    schema_version = serializers.CharField(
        max_length=30,
        required=False,
        default="1.0.0",
    )
    inquiry_id = serializers.UUIDField()
    correlation_id = serializers.UUIDField()
    ai_request_id = serializers.CharField(max_length=100)
    model_code = serializers.CharField(max_length=100)
    product_family = serializers.CharField(max_length=100)
    customer_symptom_summary = serializers.CharField(max_length=2000)
    questionnaire_answers = HandoffQuestionnaireAnswerSerializer(
        many=True,
        required=False,
        default=list,
    )
    self_help_actions = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        required=False,
        default=list,
    )
    evidence = HandoffEvidenceSerializer(many=True, required=False, default=list)
    safety_level = serializers.CharField(max_length=50)
    safety_requires_consultation = serializers.BooleanField()
    safety_notes = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        required=False,
        default=list,
    )
    escalation_reason = serializers.CharField(max_length=500)
    consultant_priority_checks = serializers.ListField(
        child=serializers.CharField(max_length=1000),
        required=False,
        default=list,
    )
    source_chunk_ids = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        default=list,
    )

    def validate(self, attrs):
        evidence_ids = [item["chunk_id"] for item in attrs["evidence"]]
        source_ids = attrs["source_chunk_ids"]
        if source_ids != evidence_ids or len(source_ids) != len(set(source_ids)):
            raise serializers.ValidationError(
                {
                    "source_chunk_ids": [
                        "Evidence 순서와 일치하는 중복 없는 Chunk ID가 필요합니다."
                    ]
                }
            )

        for value in self._string_values(attrs):
            if PHONE_PATTERN.search(value) or EMAIL_PATTERN.search(value):
                raise serializers.ValidationError(
                    {
                        "handoff": [
                            "전화번호·이메일 원문은 상담 인계에 저장할 수 없습니다."
                        ]
                    }
                )
        return attrs

    @classmethod
    def _string_values(cls, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, Mapping):
            for item in value.values():
                yield from cls._string_values(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from cls._string_values(item)
