"""Versioned internal analysis and consultation-cause ledger contracts."""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .common import ContractModel
from .pipeline import SymptomAnalysisResult


SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"
COMMIT_SHA_PATTERN = r"^[0-9a-f]{40}$"
CODE_PATTERN = r"^[A-Z][A-Z0-9_]{2,99}$"
RULE_ID_PATTERN = r"^SAFETY-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{3}$"


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


__all__ = [
    "AnalysisConsultationEnvelope",
    "CauseOrigin",
    "CauseStatus",
    "ConsultationCause",
    "ConsultationCauseCode",
    "ConsultationCauseLedger",
    "ConsultationLockClass",
    "LedgerEvidenceReference",
    "LedgerExecutionIdentity",
    "canonical_payload_sha256",
]
