"""Harness verifier for evidence, product, safety, and output schema gates."""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel, ValidationError

from ...retrieval.models.retrieved_chunk import RetrievedChunk
from ...schemas import RiskLevel, SafetyAssessment, UsageGuidance, UsageGuidanceStatus
from .product_match import ProductContext, ProductMatchVerifier
from .tool_failure import McpToolFailure
from .verification_result import (
    HarnessDecision,
    VerificationIssue,
    VerificationIssueCode,
    VerificationResult,
)


class HarnessVerifier:
    VERIFIED_STATUSES = {"official_verified", "team_verified"}

    def verify(
        self,
        *,
        product: ProductContext,
        evidence_chunks: list[RetrievedChunk],
        safety_assessment: SafetyAssessment | None,
        guidance: UsageGuidance | None,
        required_functions: set[str] | None = None,
        output_payload: Any | None = None,
        output_schema: Type[BaseModel] | None = None,
        timed_out: bool = False,
        evidence_required: bool | None = None,
        tool_failure: McpToolFailure | None = None,
    ) -> VerificationResult:
        issues: list[VerificationIssue] = []

        if timed_out:
            issues.append(
                VerificationIssue(
                    code=VerificationIssueCode.AI_PROCESSING_TIMEOUT,
                    message="AI processing exceeded the allowed runtime budget.",
                    retryable=False,
                )
            )
            return VerificationResult(
                passed=False,
                decision=HarnessDecision.ESCALATE,
                evidence_present=bool(evidence_chunks),
                product_match_valid=False,
                product_family_valid=False,
                function_compatibility_valid=False,
                safety_valid=False,
                schema_valid=False,
                rejected_evidence_chunk_ids=[chunk.chunk_id for chunk in evidence_chunks],
                issues=issues,
            )

        if not product.runtime_approved:
            issues.append(
                VerificationIssue(
                    code=VerificationIssueCode.RUNTIME_PRODUCT_NOT_APPROVED,
                    message=(
                        "The exact product is known but is not approved for the current "
                        "customer-facing AI runtime."
                    ),
                    retryable=False,
                )
            )
            return VerificationResult(
                passed=False,
                decision=HarnessDecision.ESCALATE,
                evidence_present=False,
                product_match_valid=False,
                product_family_valid=product.product_family.value != "UNKNOWN",
                function_compatibility_valid=False,
                safety_valid=self._safety_is_consistent(safety_assessment, guidance),
                schema_valid=self._schema_is_valid(guidance, output_payload, output_schema),
                rejected_evidence_chunk_ids=[chunk.chunk_id for chunk in evidence_chunks],
                issues=issues,
            )

        if tool_failure is not None:
            issues.append(
                VerificationIssue(
                    code=VerificationIssueCode.MCP_TOOL_FAILURE,
                    message=(
                        f"MCP Tool failed: {tool_failure.tool_name.value} "
                        f"({tool_failure.kind.value})."
                    ),
                    retryable=tool_failure.retrieval_retry_allowed,
                )
            )
            return VerificationResult(
                passed=False,
                decision=(
                    HarnessDecision.RETRY_RETRIEVAL
                    if tool_failure.retrieval_retry_allowed
                    else HarnessDecision.ESCALATE
                ),
                evidence_present=False,
                product_match_valid=True,
                product_family_valid=product.product_family.value != "UNKNOWN",
                function_compatibility_valid=False,
                safety_valid=self._safety_is_consistent(safety_assessment, guidance),
                schema_valid=self._schema_is_valid(guidance, output_payload, output_schema),
                rejected_evidence_chunk_ids=[chunk.chunk_id for chunk in evidence_chunks],
                issues=issues,
            )

        if evidence_required is None:
            evidence_required = not (
                safety_assessment is not None
                and safety_assessment.risk_level == RiskLevel.DANGER
            )

        eligible: list[RetrievedChunk] = []
        rejected_ids: list[str] = []
        for chunk in evidence_chunks:
            if (
                not chunk.allowed_use
                or not chunk.runtime_eligible
                or chunk.verification_status not in self.VERIFIED_STATUSES
            ):
                rejected_ids.append(chunk.chunk_id)
                issues.append(
                    VerificationIssue(
                        code=VerificationIssueCode.UNVERIFIED_EVIDENCE,
                        message="Evidence is not approved or runtime-eligible for customer guidance.",
                        retryable=True,
                        chunk_id=chunk.chunk_id,
                    )
                )
                continue
            eligible.append(chunk)

        product_result = ProductMatchVerifier().verify(
            product=product,
            evidence_chunks=eligible,
            required_functions=required_functions,
        )
        issues.extend(product_result.issues)
        rejected_ids.extend(product_result.rejected_chunk_ids)

        evidence_present = bool(product_result.accepted_chunk_ids)
        if evidence_required and not evidence_present:
            issues.append(
                VerificationIssue(
                    code=VerificationIssueCode.NO_EVIDENCE,
                    message="No product-matched evidence is available for final guidance.",
                    retryable=True,
                )
            )

        safety_valid = self._safety_is_consistent(safety_assessment, guidance)
        if not safety_valid:
            issues.append(
                VerificationIssue(
                    code=VerificationIssueCode.SAFETY_CONFLICT,
                    message="Generated guidance conflicts with the safety assessment.",
                    retryable=False,
                )
            )

        schema_valid = self._schema_is_valid(guidance, output_payload, output_schema)
        if not schema_valid:
            issues.append(
                VerificationIssue(
                    code=VerificationIssueCode.OUTPUT_SCHEMA_INVALID,
                    message="Generated output does not satisfy the required schema.",
                    retryable=True,
                )
            )

        if not safety_valid:
            decision = HarnessDecision.ESCALATE
        elif not product_result.function_compatibility_valid:
            decision = HarnessDecision.HUMAN_REVIEW
        elif evidence_required and (
            not evidence_present
            or not product_result.model_match_valid
            or not product_result.product_family_valid
        ):
            decision = HarnessDecision.RETRY_RETRIEVAL
        elif not schema_valid:
            decision = HarnessDecision.RETRY_GENERATION
        else:
            decision = HarnessDecision.PASS

        return VerificationResult(
            passed=decision == HarnessDecision.PASS,
            decision=decision,
            evidence_present=evidence_present,
            product_match_valid=product_result.model_match_valid,
            product_family_valid=product_result.product_family_valid,
            function_compatibility_valid=product_result.function_compatibility_valid,
            safety_valid=safety_valid,
            schema_valid=schema_valid,
            accepted_evidence_chunk_ids=product_result.accepted_chunk_ids,
            rejected_evidence_chunk_ids=list(dict.fromkeys(rejected_ids)),
            issues=issues,
        )

    @staticmethod
    def _safety_is_consistent(
        safety_assessment: SafetyAssessment | None,
        guidance: UsageGuidance | None,
    ) -> bool:
        if safety_assessment is None or guidance is None:
            return True
        if safety_assessment.risk_level == RiskLevel.DANGER:
            return guidance.guidance_status in {
                UsageGuidanceStatus.TOTAL_STOP,
                UsageGuidanceStatus.PENDING_CONSULTATION,
            }
        return True

    @staticmethod
    def _schema_is_valid(
        guidance: UsageGuidance | None,
        output_payload: Any | None,
        output_schema: Type[BaseModel] | None,
    ) -> bool:
        if guidance is None:
            return False
        if output_payload is None and output_schema is None:
            return True
        if output_payload is None or output_schema is None:
            return False
        try:
            output_schema.model_validate(output_payload)
        except (ValidationError, TypeError, AttributeError):
            return False
        return True
