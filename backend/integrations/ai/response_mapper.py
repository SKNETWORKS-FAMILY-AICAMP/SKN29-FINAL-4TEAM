"""AI 응답을 검증된 Backend 중간 결과로 변환한다."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import re
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
from common.json_integrity import canonical_json_sha256


INTERNAL_ENVELOPE_KEYS = frozenset(
    {
        "contract_version",
        "analysis_result",
        "consultation_cause_ledger",
    }
)
SENSITIVE_LEDGER_PATTERNS = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("phone", re.compile(r"(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)")),
    ("resident_id", re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "named_secret",
        re.compile(
            r"(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S+",
            re.I,
        ),
    ),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


@dataclass(frozen=True, slots=True)
class AIAnalysisResult:
    """업무 Model 저장과 State Event 평가 전의 검증된 결과."""

    payload: dict[str, Any]
    event_candidate: str | None
    is_no_evidence: bool
    consultation_cause_ledger: dict[str, Any] | None = None
    envelope_contract_version: str | None = None

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

    @property
    def has_consultation_cause_ledger(self) -> bool:
        return self.consultation_cause_ledger is not None


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
    """Validate either legacy 4.0.0 or internal Envelope 1.0.0."""

    contract_validator = validator or AIContractValidator()
    if INTERNAL_ENVELOPE_KEYS.intersection(payload):
        validate_internal = getattr(
            contract_validator,
            "validate_internal_success_response",
            None,
        )
        if not callable(validate_internal):
            raise AIResponseValidationError(
                "Backend가 AI 내부 Envelope 검증을 지원하지 않습니다.",
                payload=payload,
                validation_errors=[
                    "internal envelope validator is unavailable"
                ],
            )
        validate_internal(payload)
        analysis_payload = payload["analysis_result"]
        ledger_payload = payload["consultation_cause_ledger"]
        result = _map_public_success_response(
            analysis_payload,
            expected_request=expected_request,
            validator=contract_validator,
        )
        _validate_consultation_cause_ledger(
            analysis_payload=analysis_payload,
            ledger_payload=ledger_payload,
            expected_request=expected_request,
        )
        return AIAnalysisResult(
            payload=result.payload,
            event_candidate=result.event_candidate,
            is_no_evidence=result.is_no_evidence,
            consultation_cause_ledger=deepcopy(ledger_payload),
            envelope_contract_version=str(payload["contract_version"]),
        )

    return _map_public_success_response(
        payload,
        expected_request=expected_request,
        validator=contract_validator,
    )


def _map_public_success_response(
    payload: dict[str, Any],
    *,
    expected_request: dict[str, Any],
    validator: AIContractValidator,
) -> AIAnalysisResult:
    """Validate the unchanged public SymptomAnalysisResponse 4.0.0."""

    contract_validator = validator
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
        and safety["risk_level"] == "general"
        and not safety["requires_consultation"]
        and guidance["guidance_status"] == "NORMAL"
        and not payload["missing_fields"]
        and not payload["followup_questions"]
    ):
        event_candidate = "SAFE_GUIDANCE_READY"

    return AIAnalysisResult(
        payload=payload,
        event_candidate=event_candidate,
        is_no_evidence=is_no_evidence,
    )


def _validate_consultation_cause_ledger(
    *,
    analysis_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
    expected_request: dict[str, Any],
) -> None:
    """Apply Backend-owned identity, hash, and privacy invariants."""

    errors: list[str] = []
    identity_fields = (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
        "model_code",
    )
    for field in identity_fields:
        if str(ledger_payload.get(field)) != str(analysis_payload.get(field)):
            errors.append(f"consultation_cause_ledger.{field}: analysis mismatch")
        if str(ledger_payload.get(field)) != str(expected_request.get(field)):
            errors.append(f"consultation_cause_ledger.{field}: request mismatch")

    expected_analysis_hash = canonical_json_sha256(analysis_payload)
    if str(ledger_payload.get("analysis_result_sha256", "")).casefold() != (
        expected_analysis_hash
    ):
        errors.append(
            "consultation_cause_ledger.analysis_result_sha256: mismatch"
        )

    hash_payload = deepcopy(ledger_payload)
    supplied_ledger_hash = str(hash_payload.pop("ledger_sha256", ""))
    expected_ledger_hash = canonical_json_sha256(hash_payload)
    if supplied_ledger_hash.casefold() != expected_ledger_hash:
        errors.append("consultation_cause_ledger.ledger_sha256: mismatch")

    causes = ledger_payload.get("causes", [])
    cause_ids = [cause.get("cause_id") for cause in causes]
    if len(cause_ids) != len(set(cause_ids)):
        errors.append("consultation_cause_ledger.causes: duplicate cause_id")
    consultation_required = bool(
        analysis_payload["safety_assessment"]["requires_consultation"]
    )
    if consultation_required != bool(causes):
        errors.append(
            "consultation_cause_ledger.causes: consultation authority mismatch"
        )

    safety = analysis_payload["safety_assessment"]
    cause_codes = {cause.get("cause_code") for cause in causes}
    is_danger = safety["risk_level"] == "danger"
    if is_danger and "DANGER_ASSESSMENT" not in cause_codes:
        errors.append(
            "consultation_cause_ledger.causes: danger assessment cause is required"
        )
    if not is_danger and "DANGER_ASSESSMENT" in cause_codes:
        errors.append(
            "consultation_cause_ledger.causes: danger assessment cause is inconsistent"
        )

    analysis_rule_ids = set(safety["matched_safety_rule_ids"])
    for index, cause in enumerate(causes):
        if cause.get("lock_class") != "SAFETY_LOCKED":
            continue
        cause_rule_ids = set(cause.get("matched_safety_rule_ids", []))
        if not cause_rule_ids or not cause_rule_ids.issubset(analysis_rule_ids):
            errors.append(
                f"consultation_cause_ledger.causes.{index}."
                "matched_safety_rule_ids: analysis mismatch"
            )

    ledger_model_code = ledger_payload.get("model_code")
    for index, cause in enumerate(causes):
        evidence_refs = cause.get("evidence_refs", [])
        if any(
            evidence.get("model_code") != ledger_model_code
            for evidence in evidence_refs
        ):
            errors.append(
                f"consultation_cause_ledger.causes.{index}.evidence_refs: "
                "model mismatch"
            )
        if cause.get("status") == "RESOLUTION_PROPOSED" and len(
            {evidence.get("scenario_id") for evidence in evidence_refs}
        ) != 1:
            errors.append(
                f"consultation_cause_ledger.causes.{index}.evidence_refs: "
                "one runtime scenario is required"
            )

    sensitive_paths = _sensitive_ledger_paths(ledger_payload)
    if sensitive_paths:
        errors.extend(
            f"consultation_cause_ledger.{path}: sensitive value rejected"
            for path in sensitive_paths
        )

    if errors:
        raise AIResponseValidationError(
            "AI 상담 원인 Ledger 무결성 검증에 실패했습니다.",
            payload={
                "contract_version": "1.0.0",
                "redacted": True,
            },
            validation_errors=errors,
        )


def _sensitive_ledger_paths(payload: object, path: str = "$") -> list[str]:
    """Return paths containing high-confidence PII or secret patterns."""

    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            findings.extend(_sensitive_ledger_paths(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_sensitive_ledger_paths(value, f"{path}.{index}"))
    elif isinstance(payload, str):
        if any(pattern.search(payload) for _name, pattern in SENSITIVE_LEDGER_PATTERNS):
            findings.append(path)
    return findings


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
