"""Harness runner that converts verification into bounded runtime actions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Type

from pydantic import BaseModel, ConfigDict

from ...retrieval.models.retrieved_chunk import RetrievedChunk
from ...schemas import SafetyAssessment, UsageGuidance
from .product_match import ProductContext
from .retry_policy import HarnessRetryPolicy, HarnessRetryState
from .verification_result import HarnessDecision, VerificationResult
from .verifier import HarnessVerifier


class HarnessErrorCode(str, Enum):
    NO_EVIDENCE = "NO_EVIDENCE"
    AI_PROCESSING_TIMEOUT = "AI_PROCESSING_TIMEOUT"


class HarnessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: HarnessDecision
    verification: VerificationResult
    retry_state: HarnessRetryState
    error_code: HarnessErrorCode | None = None
    should_retry: bool = False
    should_escalate: bool = False


class HarnessRunner:
    def __init__(
        self,
        verifier: HarnessVerifier | None = None,
        retry_policy: HarnessRetryPolicy | None = None,
    ) -> None:
        self.verifier = verifier or HarnessVerifier()
        self.retry_policy = retry_policy or HarnessRetryPolicy()

    def run(
        self,
        *,
        product: ProductContext,
        evidence_chunks: list[RetrievedChunk],
        safety_assessment: SafetyAssessment | None,
        guidance: UsageGuidance | None,
        retry_state: HarnessRetryState | None = None,
        required_functions: set[str] | None = None,
        output_payload: Any | None = None,
        output_schema: Type[BaseModel] | None = None,
        timed_out: bool = False,
    ) -> HarnessResult:
        state = retry_state or HarnessRetryState()
        verification = self.verifier.verify(
            product=product,
            evidence_chunks=evidence_chunks,
            safety_assessment=safety_assessment,
            guidance=guidance,
            required_functions=required_functions,
            output_payload=output_payload,
            output_schema=output_schema,
            timed_out=timed_out,
        )

        if timed_out:
            return HarnessResult(
                decision=HarnessDecision.ESCALATE,
                verification=verification,
                retry_state=state,
                error_code=HarnessErrorCode.AI_PROCESSING_TIMEOUT,
                should_escalate=True,
            )

        policy = self.retry_policy.apply(verification.decision, state)
        if policy.exhausted:
            return HarnessResult(
                decision=HarnessDecision.ESCALATE,
                verification=verification,
                retry_state=policy.state,
                error_code=HarnessErrorCode.NO_EVIDENCE,
                should_escalate=True,
            )

        return HarnessResult(
            decision=policy.decision,
            verification=verification,
            retry_state=policy.state,
            should_retry=policy.decision in {
                HarnessDecision.RETRY_RETRIEVAL,
                HarnessDecision.RETRY_GENERATION,
            },
            should_escalate=policy.decision == HarnessDecision.ESCALATE,
        )
