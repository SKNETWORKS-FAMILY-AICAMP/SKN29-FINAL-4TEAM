"""T-023 resolution feedback and completion request contracts."""

from __future__ import annotations

import re
from collections.abc import Mapping

from rest_framework import serializers

from apps.inquiries.api.serializers.inquiry_response import (
    AllowedActionSerializer,
)
from apps.inquiries.models import Inquiry


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {
                        field: ["This field is not allowed."]
                        for field in unknown
                    }
                )
        return super().to_internal_value(data)


class ResolutionFeedbackRequestSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)
    resolved = serializers.BooleanField()
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
    )

    def validate_resolved(self, value: bool) -> bool:
        if value is not True:
            raise serializers.ValidationError("This value must be true.")
        return value


class ReportUnresolvedRequestSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)
    resolved = serializers.BooleanField()
    reason_code = serializers.RegexField(
        r"^[A-Z][A-Z0-9_]*$",
        required=False,
        min_length=1,
        max_length=80,
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
    )

    def validate_resolved(self, value: bool) -> bool:
        if value is not False:
            raise serializers.ValidationError("This value must be false.")
        return value


class StateVersionRequestSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    state_version = serializers.IntegerField(min_value=1)


class FinalizeInquiryRequestSerializer(StateVersionRequestSerializer):
    final_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
    )

    _INTERNAL_FIELD_PATTERN = re.compile(
        r"\b(?:system_prompt|developer_prompt|model_internal_reasoning|"
        r"internal_guard_failure_detail|raw_source_storage_path|"
        r"vector_chunk_id|vector_embedding)\b",
        re.IGNORECASE,
    )
    _RAW_STORAGE_PATTERN = re.compile(
        r"\b(?:s3|gs|file)://",
        re.IGNORECASE,
    )

    def validate_final_note(self, value: str) -> str:
        if self._INTERNAL_FIELD_PATTERN.search(value):
            raise serializers.ValidationError(
                "Internal AI fields are not allowed."
            )
        if self._RAW_STORAGE_PATTERN.search(value):
            raise serializers.ValidationError(
                "Raw source storage paths are not allowed."
            )
        return value


class ResolutionTransitionResponseSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=300)
    inquiry_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=Inquiry.Status.values)
    state_version = serializers.IntegerField(min_value=1)
    allowed_actions = AllowedActionSerializer(many=True)
    idempotent_replay = serializers.BooleanField()
    resource = serializers.JSONField(allow_null=True)

    def validate_resource(self, value):
        if value is not None:
            raise serializers.ValidationError(
                "T-023 actions do not expose an internal resource."
            )
        return value
