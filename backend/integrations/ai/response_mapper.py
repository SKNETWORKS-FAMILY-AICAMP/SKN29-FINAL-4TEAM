"""AI 응답을 검증된 Backend 중간 결과로 변환한다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_validation_errors,
)
from integrations.ai.exceptions import (
    AIIdentifierMismatchError,
    AIResponseValidationError,
)
from integrations.ai.schema_validator import AIContractValidator


@dataclass(frozen=True, slots=True)
class AIAnalysisResult:
    """업무 Model 저장과 State Event 평가 전의 검증된 결과."""

    payload: dict[str, Any]
    event_candidate: str | None
    is_no_evidence: bool

    @property
    def retry_count(self) -> int:
        return int(self.payload["retry_count"])

    @property
    def risk_level(self) -> str:
        return str(self.payload["safety_assessment"]["risk_level"])

    @property
    def usage_guidance_status(self) -> str:
        return str(self.payload["usage_guidance"]["guidance_status"])

    @property
    def requires_consultation(self) -> bool:
        return bool(self.payload["safety_assessment"]["requires_consultation"])

    @property
    def is_fallback(self) -> bool:
        return self.payload["status"] == "FALLBACK"

    @property
    def fallback_reason_code(self) -> str | None:
        value = self.payload.get("fallback_reason_code")
        return str(value) if isinstance(value, str) else None

    @property
    def is_product_validation_failed(self) -> bool:
        return (
            self.is_fallback
            and self.fallback_reason_code
            == "RUNTIME_PRODUCT_NOT_APPROVED"
        )


@dataclass(frozen=True, slots=True)
class AIErrorResult:
    """계약 검증을 통과한 AI 오류 응답."""

    payload: dict[str, Any]

    @property
    def detail(self) -> dict[str, Any]:
        return self.payload["error"]


def map_success_response(
    payload: dict[str, Any],
    *,
    expected_request: dict[str, Any],
    validator: AIContractValidator | None = None,
) -> AIAnalysisResult:
    """성공 응답 Schema·식별자·업무 불변식을 검증한다."""

    contract_validator = validator or AIContractValidator()
    contract_validator.validate_success_response(payload)
    identifier_fields = [
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
    ]
    # Contract 4.0.0 requires model_code. Keeping this conditional lets the
    # Backend-only compatibility commit remain green until the AI contract
    # commit is merged, while the 4.0.0 schema still makes the field mandatory.
    if "model_code" in payload:
        identifier_fields.append("model_code")
    _validate_identifier_echo(
        payload,
        expected_request,
        allow_null=False,
        fields=tuple(identifier_fields),
    )
    _validate_uuid(payload["correlation_id"], "correlation_id")

    safety = payload["safety_assessment"]
    guidance = payload["usage_guidance"]
    evidence = payload["evidence_references"]
    status = payload["status"]
    fallback_reason_code = payload.get("fallback_reason_code")
    has_reason_contract = "fallback_reason_code" in payload

    is_danger = safety["risk_level"] == "danger"
    is_no_evidence = (
        status == "FALLBACK"
        and (
            fallback_reason_code == "NO_EVIDENCE"
            if has_reason_contract
            else payload["failure_stage"] == "RETRIEVING"
        )
        and not evidence
    )
    is_product_validation_failed = (
        status == "FALLBACK"
        and fallback_reason_code == "RUNTIME_PRODUCT_NOT_APPROVED"
    )

    errors = []
    if status == "FALLBACK" and payload["failure_stage"] is None:
        errors.append("failure_stage: FALLBACK에는 실패 단계가 필요합니다.")
    if is_no_evidence and (
        not safety["requires_consultation"]
        or guidance["guidance_status"] != "PENDING_CONSULTATION"
    ):
        errors.append(
            "NO_EVIDENCE: 상담 필요와 PENDING_CONSULTATION이 필요합니다."
        )
    if is_product_validation_failed and (
        "model_code" not in payload
        or evidence
        or not safety["requires_consultation"]
        or (
            not is_danger
            and guidance["guidance_status"] != "PENDING_CONSULTATION"
        )
    ):
        errors.append(
            "RUNTIME_PRODUCT_NOT_APPROVED: 제품 Echo, 근거 미조회, "
            "상담 필요와 안전 안내 상태가 필요합니다."
        )
    if is_danger:
        errors.extend(
            f"danger: {error}"
            for error in danger_assessment_validation_errors(payload)
        )
    if errors:
        raise AIResponseValidationError(
            "AI 응답 업무 불변식 검증에 실패했습니다.",
            payload=payload,
            validation_errors=errors,
        )

    event_candidate = None
    if is_product_validation_failed:
        # Product authorization is the state-transition reason. A leak can
        # still retain danger/TOTAL_STOP in the persisted safety projection.
        event_candidate = "PRODUCT_VALIDATION_FAILED"
    elif is_danger:
        event_candidate = "DANGER_DETECTED"
    elif is_no_evidence:
        event_candidate = "NO_EVIDENCE"
    elif (
        status == "SUCCEEDED"
        and evidence
        and not safety["requires_consultation"]
        and not payload["missing_fields"]
        and not payload["followup_questions"]
    ):
        event_candidate = "SAFE_GUIDANCE_READY"

    return AIAnalysisResult(
        payload=payload,
        event_candidate=event_candidate,
        is_no_evidence=is_no_evidence,
    )


def map_error_response(
    payload: dict[str, Any],
    *,
    expected_request: dict[str, Any],
    validator: AIContractValidator | None = None,
) -> AIErrorResult:
    """오류 응답도 별도 계약과 식별자 Echo를 검증한다."""

    contract_validator = validator or AIContractValidator()
    contract_validator.validate_error_response(payload)
    _validate_identifier_echo(payload, expected_request, allow_null=True)
    correlation_id = payload.get("correlation_id")
    if correlation_id is not None:
        _validate_uuid(correlation_id, "correlation_id")
    return AIErrorResult(payload=payload)


def _validate_identifier_echo(
    payload: dict[str, Any],
    expected: dict[str, Any],
    *,
    allow_null: bool,
    fields: tuple[str, ...] = (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
    ),
) -> None:
    mismatches = []
    for field in fields:
        actual = payload.get(field)
        if allow_null and actual is None:
            continue
        if str(actual) != str(expected[field]):
            mismatches.append(field)
    if mismatches:
        raise AIIdentifierMismatchError(
            "AI 응답 식별자가 요청과 일치하지 않습니다.",
            payload=payload,
            validation_errors=[
                f"identifier mismatch: {field}" for field in mismatches
            ],
        )


def _validate_uuid(value: Any, field: str) -> None:
    try:
        UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AIResponseValidationError(
            f"AI 응답 {field}가 UUID가 아닙니다.",
            validation_errors=[f"{field}: invalid UUID"],
        ) from exc
