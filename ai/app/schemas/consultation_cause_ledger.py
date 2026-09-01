"""Versioned internal analysis and consultation-cause ledger contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Iterable
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field, ValidationError, model_validator

from .common import (
    AiExecutionStatus,
    ContractModel,
    RiskLevel,
    VerificationStatus,
)
from .pipeline import SymptomAnalysisResult


SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"
COMMIT_SHA_PATTERN = r"^[0-9a-f]{40}$"
CODE_PATTERN = r"^[A-Z][A-Z0-9_]{2,99}$"
RULE_ID_PATTERN = r"^SAFETY-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{3}$"
POLICY_VERSION = "consultation-cause-ledger/1.0.0"
_LEDGER_NAMESPACE = uuid5(
    NAMESPACE_URL,
    "https://waterbridge.site/contracts/ai/consultation-cause-ledger/1.0.0",
)
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_FAIL_CLOSED_HARNESS_ISSUES = frozenset(
    {
        "NO_EVIDENCE",
        "UNVERIFIED_EVIDENCE",
        "WRONG_MODEL_EVIDENCE",
        "PRODUCT_FAMILY_MISMATCH",
        "SAFETY_CONFLICT",
        "OUTPUT_SCHEMA_INVALID",
        "AI_PROCESSING_TIMEOUT",
        "RUNTIME_PRODUCT_NOT_APPROVED",
        "MCP_TOOL_FAILURE",
    }
)


class ConsultationCauseCode(str, Enum):
    DANGER_ASSESSMENT = "DANGER_ASSESSMENT"
    EXPLICIT_SAFETY_RULE = "EXPLICIT_SAFETY_RULE"
    FAIL_CLOSED_AI_RESULT = "FAIL_CLOSED_AI_RESULT"
    HARNESS_UNSUPPORTED_FUNCTION = "HARNESS_UNSUPPORTED_FUNCTION"
    HARNESS_SCOPE_EXCEEDED = "HARNESS_SCOPE_EXCEEDED"
    UNCLASSIFIED_AI_SIGNAL = "UNCLASSIFIED_AI_SIGNAL"


class ConsultationLockClass(str, Enum):
    SAFETY_LOCKED = "SAFETY_LOCKED"
    FAIL_CLOSED_LOCKED = "FAIL_CLOSED_LOCKED"
    NON_SAFETY_RESOLVABLE = "NON_SAFETY_RESOLVABLE"
    UNKNOWN_LOCKED = "UNKNOWN_LOCKED"


class CauseOrigin(str, Enum):
    AI_SAFETY = "AI_SAFETY"
    AI_RUNTIME = "AI_RUNTIME"
    HARNESS = "HARNESS"


class CauseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLUTION_PROPOSED = "RESOLUTION_PROPOSED"


class ConsultationCauseLedgerBuildError(RuntimeError):
    """Sanitized fail-closed signal for deterministic Runtime construction."""


EXPECTED_LOCK_CLASS = {
    ConsultationCauseCode.DANGER_ASSESSMENT: ConsultationLockClass.SAFETY_LOCKED,
    ConsultationCauseCode.EXPLICIT_SAFETY_RULE: ConsultationLockClass.SAFETY_LOCKED,
    ConsultationCauseCode.FAIL_CLOSED_AI_RESULT: ConsultationLockClass.FAIL_CLOSED_LOCKED,
    ConsultationCauseCode.HARNESS_UNSUPPORTED_FUNCTION: ConsultationLockClass.NON_SAFETY_RESOLVABLE,
    ConsultationCauseCode.HARNESS_SCOPE_EXCEEDED: ConsultationLockClass.NON_SAFETY_RESOLVABLE,
    ConsultationCauseCode.UNCLASSIFIED_AI_SIGNAL: ConsultationLockClass.UNKNOWN_LOCKED,
}


class LedgerExecutionIdentity(ContractModel):
    execution_commit_sha: str = Field(pattern=COMMIT_SHA_PATTERN)
    runtime_name: Literal["single_rag", "multi_agent"]
    model_provider: str | None = Field(default=None, min_length=1, max_length=100)
    model_name: str | None = Field(default=None, min_length=1, max_length=200)
    prompt_version: str | None = Field(default=None, min_length=1, max_length=100)
    prompt_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)


class LedgerEvidenceReference(ContractModel):
    chunk_id: str = Field(min_length=1, max_length=200)
    document_id: str = Field(min_length=1, max_length=200)
    model_code: str = Field(min_length=1, max_length=100)
    index_version: str = Field(min_length=1, max_length=50)
    chunk_set_sha256: str = Field(pattern=SHA256_PATTERN)
    source_file_sha256: str = Field(pattern=SHA256_PATTERN)
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    scenario_id: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def reject_evaluation_oracle_id(self) -> "LedgerEvidenceReference":
        if self.scenario_id.startswith("REF-"):
            raise ValueError("평가 전용 REF-* ID는 Runtime Ledger에 사용할 수 없습니다.")
        return self


class ConsultationCause(ContractModel):
    cause_id: UUID
    cause_code: ConsultationCauseCode
    origin: CauseOrigin
    lock_class: ConsultationLockClass
    verification_code: str = Field(pattern=CODE_PATTERN)
    matched_safety_rule_ids: list[str] = Field(default_factory=list, max_length=20)
    required_fact_codes: list[str] = Field(default_factory=list, max_length=20)
    evidence_refs: list[LedgerEvidenceReference] = Field(default_factory=list, max_length=20)
    status: CauseStatus = CauseStatus.ACTIVE
    supersedes_cause_id: UUID | None = None

    @model_validator(mode="after")
    def validate_authority_mapping(self) -> "ConsultationCause":
        if self.lock_class != EXPECTED_LOCK_CLASS[self.cause_code]:
            raise ValueError("원인 코드와 상담 잠금 분류가 일치하지 않습니다.")
        if len(set(self.matched_safety_rule_ids)) != len(self.matched_safety_rule_ids):
            raise ValueError("Safety Rule ID는 중복될 수 없습니다.")
        if any(
            not re.fullmatch(RULE_ID_PATTERN, rule_id)
            for rule_id in self.matched_safety_rule_ids
        ):
            raise ValueError("Safety Rule ID 형식이 잘못되었습니다.")
        if len(set(self.required_fact_codes)) != len(self.required_fact_codes):
            raise ValueError("필수 사실 코드는 중복될 수 없습니다.")
        if self.lock_class == ConsultationLockClass.SAFETY_LOCKED and not self.matched_safety_rule_ids:
            raise ValueError("Safety 잠금 원인에는 승인 Rule ID가 필요합니다.")
        if (
            self.status == CauseStatus.RESOLUTION_PROPOSED
            and self.lock_class != ConsultationLockClass.NON_SAFETY_RESOLVABLE
        ):
            raise ValueError("비-Safety 원인만 해소를 제안할 수 있습니다.")
        if self.status == CauseStatus.RESOLUTION_PROPOSED and (
            not self.required_fact_codes or not self.evidence_refs
        ):
            raise ValueError("해소 제안에는 필수 사실 코드와 검증 Evidence가 필요합니다.")
        return self


def canonical_payload_sha256(payload: object, *, excluded_key: str | None = None) -> str:
    if hasattr(payload, "model_dump"):
        document = payload.model_dump(mode="json")
    else:
        document = dict(payload)  # type: ignore[arg-type]
    if excluded_key is not None:
        document.pop(excluded_key, None)
    canonical = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class ConsultationCauseLedger(ContractModel):
    contract_version: Literal["1.0.0"] = "1.0.0"
    ledger_id: UUID
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(min_length=1, max_length=100)
    state_version: int = Field(ge=1)
    model_code: str = Field(min_length=1, max_length=100)
    producer: Literal["AI_HARNESS"] = "AI_HARNESS"
    policy_version: str = Field(min_length=1, max_length=100)
    execution_identity: LedgerExecutionIdentity
    analysis_result_sha256: str = Field(pattern=SHA256_PATTERN)
    causes: list[ConsultationCause] = Field(default_factory=list, max_length=20)
    ledger_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_ledger_hash(self) -> "ConsultationCauseLedger":
        cause_ids = [cause.cause_id for cause in self.causes]
        if len(set(cause_ids)) != len(cause_ids):
            raise ValueError("원인 ID는 Ledger 안에서 중복될 수 없습니다.")
        for cause in self.causes:
            evidence_model_codes = {
                evidence.model_code for evidence in cause.evidence_refs
            }
            if evidence_model_codes.difference({self.model_code}):
                raise ValueError("원인 Evidence의 제품 코드가 Ledger와 일치하지 않습니다.")
            if (
                cause.status == CauseStatus.RESOLUTION_PROPOSED
                and len({evidence.scenario_id for evidence in cause.evidence_refs}) != 1
            ):
                raise ValueError("해소 Evidence는 하나의 Runtime 시나리오를 가리켜야 합니다.")
        expected = canonical_payload_sha256(self, excluded_key="ledger_sha256")
        if self.ledger_sha256.casefold() != expected:
            raise ValueError("ledger_sha256가 Canonical Ledger 본문과 일치하지 않습니다.")
        return self


class AnalysisConsultationEnvelope(ContractModel):
    contract_version: Literal["1.0.0"] = "1.0.0"
    analysis_result: SymptomAnalysisResult
    consultation_cause_ledger: ConsultationCauseLedger

    @model_validator(mode="after")
    def validate_atomic_identity(self) -> "AnalysisConsultationEnvelope":
        analysis = self.analysis_result
        ledger = self.consultation_cause_ledger
        identity_pairs = (
            (analysis.inquiry_id, ledger.inquiry_id),
            (analysis.correlation_id, ledger.correlation_id),
            (analysis.ai_request_id, ledger.ai_request_id),
            (analysis.state_version, ledger.state_version),
            (analysis.model_code, ledger.model_code),
        )
        if any(str(left) != str(right) for left, right in identity_pairs):
            raise ValueError("분석 결과와 원인 Ledger 식별자가 일치하지 않습니다.")
        result_hash = canonical_payload_sha256(analysis)
        if ledger.analysis_result_sha256.casefold() != result_hash:
            raise ValueError("analysis_result_sha256가 분석 결과와 일치하지 않습니다.")
        consultation_required = analysis.safety_assessment.requires_consultation
        if consultation_required != bool(ledger.causes):
            raise ValueError("상담 필요 여부와 활성 원인 Ledger 존재 여부가 일치해야 합니다.")
        return self


@lru_cache(maxsize=4)
def resolve_execution_commit_sha(release_sha: str | None = None) -> str:
    """Resolve the immutable release identity without inventing a commit SHA."""

    candidate = (release_sha or "").strip().lower()
    if candidate:
        if re.fullmatch(COMMIT_SHA_PATTERN, candidate):
            return candidate
        raise ConsultationCauseLedgerBuildError(
            "EXECUTION_COMMIT_SHA_INVALID"
        )
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConsultationCauseLedgerBuildError(
            "EXECUTION_COMMIT_SHA_UNAVAILABLE"
        ) from exc
    candidate = completed.stdout.strip().lower()
    if not re.fullmatch(COMMIT_SHA_PATTERN, candidate):
        raise ConsultationCauseLedgerBuildError(
            "EXECUTION_COMMIT_SHA_INVALID"
        )
    return candidate


def build_analysis_consultation_envelope(
    analysis_result: SymptomAnalysisResult,
    *,
    runtime_name: Literal["single_rag", "multi_agent"],
    harness_issue_codes: Iterable[str] = (),
    execution_commit_sha: str | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    prompt_version: str | None = None,
    prompt_sha256: str | None = None,
) -> AnalysisConsultationEnvelope:
    """Build the internal Envelope from deterministic Runtime decisions only."""

    if any(
        evidence.verification_status
        != VerificationStatus.OFFICIAL_VERIFIED
        for evidence in analysis_result.evidence_references
    ):
        raise ConsultationCauseLedgerBuildError(
            "UNVERIFIED_EVIDENCE_NOT_ALLOWED"
        )

    commit_sha = resolve_execution_commit_sha(
        execution_commit_sha or os.getenv("RELEASE_SHA")
    )
    analysis_hash = canonical_payload_sha256(analysis_result)
    ledger_identity = json.dumps(
        {
            "inquiry_id": str(analysis_result.inquiry_id),
            "correlation_id": str(analysis_result.correlation_id),
            "ai_request_id": analysis_result.ai_request_id,
            "state_version": analysis_result.state_version,
            "model_code": analysis_result.model_code,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    ledger_id = uuid5(
        _LEDGER_NAMESPACE,
        ledger_identity,
    )
    issue_codes = {
        str(getattr(code, "value", code)).strip().upper()
        for code in harness_issue_codes
        if str(getattr(code, "value", code)).strip()
    }
    causes = _deterministic_causes(
        analysis_result,
        ledger_id=ledger_id,
        issue_codes=issue_codes,
    )
    consultation_required = bool(
        analysis_result.safety_assessment.requires_consultation
    )
    if consultation_required != bool(causes):
        raise ConsultationCauseLedgerBuildError(
            "CONSULTATION_CAUSE_AUTHORITY_MISMATCH"
        )

    execution_identity = LedgerExecutionIdentity(
        execution_commit_sha=commit_sha,
        runtime_name=runtime_name,
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=prompt_version,
        prompt_sha256=prompt_sha256,
    )
    ledger_payload = {
        "contract_version": "1.0.0",
        "ledger_id": str(ledger_id),
        "inquiry_id": str(analysis_result.inquiry_id),
        "correlation_id": str(analysis_result.correlation_id),
        "ai_request_id": analysis_result.ai_request_id,
        "state_version": analysis_result.state_version,
        "model_code": analysis_result.model_code,
        "producer": "AI_HARNESS",
        "policy_version": POLICY_VERSION,
        "execution_identity": execution_identity.model_dump(mode="json"),
        "analysis_result_sha256": analysis_hash,
        "causes": [cause.model_dump(mode="json") for cause in causes],
    }
    ledger_payload["ledger_sha256"] = canonical_payload_sha256(
        ledger_payload
    )
    try:
        ledger = ConsultationCauseLedger.model_validate(ledger_payload)
        return AnalysisConsultationEnvelope(
            analysis_result=analysis_result,
            consultation_cause_ledger=ledger,
        )
    except ValidationError as exc:
        raise ConsultationCauseLedgerBuildError(
            "CONSULTATION_CAUSE_LEDGER_INVALID"
        ) from exc


def _deterministic_causes(
    analysis_result: SymptomAnalysisResult,
    *,
    ledger_id: UUID,
    issue_codes: set[str],
) -> list[ConsultationCause]:
    safety = analysis_result.safety_assessment
    rule_ids = sorted(set(safety.matched_safety_rule_ids))
    if safety.risk_level == RiskLevel.DANGER and not rule_ids:
        raise ConsultationCauseLedgerBuildError(
            "DANGER_RULE_ID_MISSING"
        )

    causes: list[ConsultationCause] = []
    cause_keys: set[tuple[str, str]] = set()

    def add_cause(
        *,
        code: ConsultationCauseCode,
        origin: CauseOrigin,
        verification_code: str,
        matched_rule_ids: list[str] | None = None,
    ) -> None:
        key = (code.value, verification_code)
        if key in cause_keys:
            return
        cause_keys.add(key)
        cause = ConsultationCause(
            cause_id=uuid5(
                _LEDGER_NAMESPACE,
                f"{ledger_id}|{code.value}|{verification_code}",
            ),
            cause_code=code,
            origin=origin,
            lock_class=EXPECTED_LOCK_CLASS[code],
            verification_code=verification_code,
            matched_safety_rule_ids=matched_rule_ids or [],
            required_fact_codes=[],
            # Public EvidenceReference intentionally lacks the canonical
            # document/source/content hashes required by LedgerEvidenceReference.
            # Never fabricate those values; active v1 causes do not require them.
            evidence_refs=[],
            status=CauseStatus.ACTIVE,
            supersedes_cause_id=None,
        )
        causes.append(cause)

    if safety.risk_level == RiskLevel.DANGER:
        add_cause(
            code=ConsultationCauseCode.DANGER_ASSESSMENT,
            origin=CauseOrigin.AI_SAFETY,
            verification_code="DETERMINISTIC_DANGER_ASSESSMENT",
            matched_rule_ids=rule_ids,
        )
    if rule_ids and (
        safety.risk_level == RiskLevel.DANGER
        or (
            safety.requires_consultation
            and analysis_result.status == AiExecutionStatus.SUCCEEDED
        )
    ):
        add_cause(
            code=ConsultationCauseCode.EXPLICIT_SAFETY_RULE,
            origin=CauseOrigin.AI_SAFETY,
            verification_code="APPROVED_SAFETY_RULE_MATCH",
            matched_rule_ids=rule_ids,
        )

    if analysis_result.status == AiExecutionStatus.FALLBACK:
        fallback_reason = analysis_result.fallback_reason_code
        if fallback_reason is None:
            raise ConsultationCauseLedgerBuildError(
                "FALLBACK_REASON_MISSING"
            )
        add_cause(
            code=ConsultationCauseCode.FAIL_CLOSED_AI_RESULT,
            origin=CauseOrigin.AI_RUNTIME,
            verification_code=f"FALLBACK_{fallback_reason.value}",
        )

    if "UNSUPPORTED_FUNCTION" in issue_codes:
        add_cause(
            code=ConsultationCauseCode.HARNESS_UNSUPPORTED_FUNCTION,
            origin=CauseOrigin.HARNESS,
            verification_code="HARNESS_UNSUPPORTED_FUNCTION",
        )
    if "PRODUCT_FAMILY_MISMATCH" in issue_codes:
        add_cause(
            code=ConsultationCauseCode.HARNESS_SCOPE_EXCEEDED,
            origin=CauseOrigin.HARNESS,
            verification_code="HARNESS_PRODUCT_FAMILY_SCOPE_EXCEEDED",
        )
    for issue_code in sorted(issue_codes & _FAIL_CLOSED_HARNESS_ISSUES):
        add_cause(
            code=ConsultationCauseCode.FAIL_CLOSED_AI_RESULT,
            origin=CauseOrigin.HARNESS,
            verification_code=f"HARNESS_{issue_code}",
        )

    if safety.requires_consultation and not causes:
        add_cause(
            code=ConsultationCauseCode.UNCLASSIFIED_AI_SIGNAL,
            origin=CauseOrigin.AI_RUNTIME,
            verification_code="CONSULTATION_REQUIRED_UNCLASSIFIED",
        )
    return causes


__all__ = [
    "AnalysisConsultationEnvelope",
    "CauseOrigin",
    "CauseStatus",
    "ConsultationCause",
    "ConsultationCauseCode",
    "ConsultationCauseLedger",
    "ConsultationCauseLedgerBuildError",
    "ConsultationLockClass",
    "LedgerEvidenceReference",
    "LedgerExecutionIdentity",
    "build_analysis_consultation_envelope",
    "canonical_payload_sha256",
    "resolve_execution_commit_sha",
]
