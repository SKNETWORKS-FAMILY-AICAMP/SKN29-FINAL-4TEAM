"""Strict, versioned serializers for the internal AI consultation handoff."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from rest_framework import serializers


PHONE_PATTERN = re.compile(r"(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)")
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
)
HANDOFF_CONTRACT_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "ai"
    / "handoff"
    / "ConsultationHandoffRequest.schema.json"
)
V1_SCHEMA_VERSION = "1.0.0"
V2_SCHEMA_VERSION = "2.0.0"


class RejectUnknownFieldsMixin:
    """Reject payload keys that are not explicitly allowlisted."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                raise serializers.ValidationError(
                    {key: ["허용되지 않은 필드입니다."] for key in unknown}
                )
        return super().to_internal_value(data)


class HandoffQuestionnaireAnswerSerializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    field_name = serializers.CharField(max_length=100)
    answer = serializers.CharField(max_length=500)


class HandoffEvidenceV1Serializer(
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    chunk_id = serializers.CharField(max_length=200)
    document_title = serializers.CharField(max_length=500)
    page = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    summary = serializers.CharField(max_length=2000)


class HandoffEvidenceV2Serializer(HandoffEvidenceV1Serializer):
    page = serializers.IntegerField(min_value=1, allow_null=True, required=True)


class HandoffPayloadValidationMixin:
    """Apply privacy and source-binding checks shared by both versions."""

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

        context = attrs.get("context_synthesis")
        if isinstance(context, Mapping):
            allowed_ids = set(source_ids)
            findings = context["brief"]["evidence_based_findings"]
            if any(
                not set(item["source_chunk_ids"]).issubset(allowed_ids)
                for item in findings
            ):
                raise serializers.ValidationError(
                    {
                        "context_synthesis": [
                            "합성 맥락의 근거는 최상위 Evidence에 포함되어야 합니다."
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


class ConsultationHandoffV1RequestSerializer(
    HandoffPayloadValidationMixin,
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    """Preserve the exact legacy v1 acceptance boundary."""

    schema_version = serializers.CharField(default=V1_SCHEMA_VERSION)
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
    evidence = HandoffEvidenceV1Serializer(many=True, required=False, default=list)
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


class ConsultationHandoffV2RequestSerializer(
    HandoffPayloadValidationMixin,
    RejectUnknownFieldsMixin,
    serializers.Serializer,
):
    """Normalize the strict v2 envelope after JSON Schema validation."""

    schema_version = serializers.CharField()
    inquiry_id = serializers.UUIDField()
    correlation_id = serializers.UUIDField()
    ai_request_id = serializers.CharField(max_length=100)
    state_version = serializers.IntegerField(min_value=1)
    model_code = serializers.CharField(max_length=100)
    product_family = serializers.CharField(max_length=100)
    routing_reason = serializers.ChoiceField(
        choices=(
            "DANGER_HANDOFF",
            "FAIL_CLOSED_CONSULTATION",
            "HARNESS_ESCALATE",
        )
    )
    customer_symptom_summary = serializers.CharField(max_length=2000)
    questionnaire_answers = HandoffQuestionnaireAnswerSerializer(many=True)
    self_help_actions = serializers.ListField(
        child=serializers.CharField(max_length=1000),
    )
    evidence = HandoffEvidenceV2Serializer(many=True)
    safety_level = serializers.ChoiceField(
        choices=("general", "caution", "danger", "unknown")
    )
    safety_requires_consultation = serializers.BooleanField()
    safety_notes = serializers.ListField(
        child=serializers.CharField(max_length=1000),
    )
    escalation_reason = serializers.CharField(max_length=500)
    consultant_priority_checks = serializers.ListField(
        child=serializers.CharField(max_length=1000),
    )
    source_chunk_ids = serializers.ListField(
        child=serializers.CharField(max_length=200),
    )
    context_synthesis = serializers.JSONField(allow_null=True)


@lru_cache(maxsize=2)
def _contract_validator(schema_version: str) -> Draft202012Validator:
    try:
        contract = json.loads(HANDOFF_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("상담 Handoff 계약을 읽을 수 없습니다.") from exc

    definition = {
        V1_SCHEMA_VERSION: "v1Request",
        V2_SCHEMA_VERSION: "v2Request",
    }[schema_version]
    selected_schema: dict[str, Any] = {
        "$schema": contract["$schema"],
        "$defs": contract["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    Draft202012Validator.check_schema(selected_schema)
    return Draft202012Validator(
        selected_schema,
        format_checker=FormatChecker(),
    )


def _validate_contract(data: Mapping[str, Any], schema_version: str) -> None:
    errors = sorted(
        _contract_validator(schema_version).iter_errors(dict(data)),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return

    messages: list[str] = []
    for error in errors[:5]:
        location = ".".join(str(item) for item in error.absolute_path) or "$"
        messages.append(f"{location}: Handoff 계약 형식이 올바르지 않습니다.")
    raise serializers.ValidationError({"handoff": messages})


class ConsultationHandoffRequestSerializer(serializers.Serializer):
    """Dispatch only by the explicit version; never infer v2 from extra keys."""

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError(
                {"handoff": ["JSON 객체 형식이 필요합니다."]}
            )

        raw_version = data.get("schema_version")
        schema_version = V1_SCHEMA_VERSION if raw_version is None else raw_version
        serializer_class = {
            V1_SCHEMA_VERSION: ConsultationHandoffV1RequestSerializer,
            V2_SCHEMA_VERSION: ConsultationHandoffV2RequestSerializer,
        }.get(schema_version)
        if serializer_class is None:
            raise serializers.ValidationError(
                {"schema_version": ["지원하지 않는 Handoff 버전입니다."]}
            )

        _validate_contract(data, schema_version)
        serializer = serializer_class(data=data, context=self.context)
        serializer.is_valid(raise_exception=True)
        return dict(serializer.validated_data)
