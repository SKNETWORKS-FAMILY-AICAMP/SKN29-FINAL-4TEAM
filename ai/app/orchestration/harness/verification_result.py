"""Harness verification result contracts."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HarnessDecision(str, Enum):
    PASS = "PASS"
    RETRY_RETRIEVAL = "RETRY_RETRIEVAL"
    RETRY_GENERATION = "RETRY_GENERATION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    ESCALATE = "ESCALATE"


class VerificationIssueCode(str, Enum):
    NO_EVIDENCE = "NO_EVIDENCE"
    UNVERIFIED_EVIDENCE = "UNVERIFIED_EVIDENCE"
    WRONG_MODEL_EVIDENCE = "WRONG_MODEL_EVIDENCE"
    PRODUCT_FAMILY_MISMATCH = "PRODUCT_FAMILY_MISMATCH"
    UNSUPPORTED_FUNCTION = "UNSUPPORTED_FUNCTION"
    SAFETY_CONFLICT = "SAFETY_CONFLICT"
    OUTPUT_SCHEMA_INVALID = "OUTPUT_SCHEMA_INVALID"
    AI_PROCESSING_TIMEOUT = "AI_PROCESSING_TIMEOUT"


class VerificationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: VerificationIssueCode
    message: str = Field(..., min_length=1, max_length=500)
    retryable: bool = False
    chunk_id: Optional[str] = Field(None, min_length=1, max_length=200)


class VerificationResult(BaseModel):
    """Fail-closed verification result consumed by the harness runner."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    decision: HarnessDecision
    evidence_present: bool
    product_match_valid: bool
    product_family_valid: bool
    function_compatibility_valid: bool
    safety_valid: bool
    schema_valid: bool
    accepted_evidence_chunk_ids: list[str] = Field(default_factory=list)
    rejected_evidence_chunk_ids: list[str] = Field(default_factory=list)
    issues: list[VerificationIssue] = Field(default_factory=list)
