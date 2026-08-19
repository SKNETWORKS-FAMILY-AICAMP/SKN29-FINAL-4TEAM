"""Fail-closed product/evidence matching for Harness verification."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from ...retrieval.models.retrieved_chunk import RetrievedChunk
from .verification_result import VerificationIssue, VerificationIssueCode


class ProductFamily(str, Enum):
    UNKNOWN = "UNKNOWN"
    DIRECT_WATER_PURIFIER = "DIRECT_WATER_PURIFIER"
    ICE_WATER_PURIFIER = "ICE_WATER_PURIFIER"


class ProductContext(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    model_code: str = Field(..., min_length=1, max_length=100)
    product_family: ProductFamily
    supported_functions: set[str] = Field(default_factory=set)


class ProductMatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_match_valid: bool
    product_family_valid: bool
    function_compatibility_valid: bool
    accepted_chunk_ids: list[str] = Field(default_factory=list)
    rejected_chunk_ids: list[str] = Field(default_factory=list)
    issues: list[VerificationIssue] = Field(default_factory=list)


def normalize_model_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", value.upper())
    return normalized or None


def infer_product_family(model_code: str | None) -> ProductFamily | None:
    normalized = normalize_model_code(model_code)
    if normalized is None:
        return None
    if "IAC425" in normalized or "IAC606" in normalized:
        return ProductFamily.ICE_WATER_PURIFIER
    if "JAC104" in normalized or "JCC104" in normalized:
        return ProductFamily.DIRECT_WATER_PURIFIER
    return None


class ProductMatchVerifier:
    """Reject evidence unless its concrete model matches the customer product."""

    def verify(
        self,
        *,
        product: ProductContext,
        evidence_chunks: list[RetrievedChunk],
        required_functions: set[str] | None = None,
    ) -> ProductMatchResult:
        issues: list[VerificationIssue] = []
        accepted: list[str] = []
        rejected: list[str] = []
        model_match_valid = True
        family_valid = True

        expected_model = normalize_model_code(product.model_code)
        for chunk in evidence_chunks:
            chunk_model = normalize_model_code(chunk.model_code)
            if chunk_model is None or chunk_model != expected_model:
                model_match_valid = False
                rejected.append(chunk.chunk_id)
                issues.append(
                    VerificationIssue(
                        code=VerificationIssueCode.WRONG_MODEL_EVIDENCE,
                        message="Evidence model_code does not exactly match the customer model.",
                        retryable=True,
                        chunk_id=chunk.chunk_id,
                    )
                )
                continue

            evidence_family = infer_product_family(chunk.model_code)
            if evidence_family is not None and evidence_family != product.product_family:
                family_valid = False
                rejected.append(chunk.chunk_id)
                issues.append(
                    VerificationIssue(
                        code=VerificationIssueCode.PRODUCT_FAMILY_MISMATCH,
                        message="Evidence product family conflicts with the customer product family.",
                        retryable=True,
                        chunk_id=chunk.chunk_id,
                    )
                )
                continue
            accepted.append(chunk.chunk_id)

        required = {item.strip().lower() for item in (required_functions or set()) if item.strip()}
        supported = {item.strip().lower() for item in product.supported_functions if item.strip()}
        missing_functions = sorted(required - supported)
        function_valid = not missing_functions
        if missing_functions:
            issues.append(
                VerificationIssue(
                    code=VerificationIssueCode.UNSUPPORTED_FUNCTION,
                    message=(
                        "Requested function is not supported by the customer product: "
                        + ", ".join(missing_functions)
                    ),
                    retryable=False,
                )
            )

        return ProductMatchResult(
            model_match_valid=model_match_valid,
            product_family_valid=family_valid,
            function_compatibility_valid=function_valid,
            accepted_chunk_ids=accepted,
            rejected_chunk_ids=rejected,
            issues=issues,
        )
