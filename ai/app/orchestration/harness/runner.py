"""Harness runner that converts verification into bounded runtime actions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Type

from pydantic import BaseModel, ConfigDict

from ...retrieval.models.retrieved_chunk import RetrievedChunk
from ...schemas import SafetyAssessment, UsageGuidance
from ..handoff import ConsultationHandoffAgent, ConsultationHandoffInput, ConsultationHandoffResult
from ..hitl import HumanReviewExecutionResult, HumanReviewRequest, HumanReviewResume, HumanReviewWorkflow
from .product_match import ProductContext
from .retry_policy import HarnessRetryPolicy, HarnessRetryState
from .tool_failure import McpToolFailure
from .verification_result import HarnessDecision, VerificationResult
from .verifier import HarnessVerifier


class HarnessErrorCode(str, Enum):
    NO_EVIDENCE = "NO_EVIDENCE"
    AI_PROCESSING_TIMEOUT = "AI_PROCESSING_TIMEOUT"
    MCP_TOOL_FAILURE = "MCP_TOOL_FAILURE"


class HarnessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: HarnessDecision
    verification: VerificationResult
    retry_state: HarnessRetryState
    error_code: HarnessErrorCode | None = None
    should_retry: bool = False
    should_escalate: bool = False


class HarnessRuntimeResult(BaseModel):
    """Harness decision plus optional HITL or counselor handoff side effect."""

    model_config = ConfigDict(extra="forbid")

    harness: HarnessResult
    human_review: HumanReviewExecutionResult | None = None
    handoff: ConsultationHandoffResult | None = None


class HumanReviewResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review: HumanReviewExecutionResult
    guidance: UsageGuidance | None = None
    handoff: ConsultationHandoffResult | None = None


class HarnessRunner:
    def __init__(
        self,
        verifier: HarnessVerifier | None = None,
        retry_policy: HarnessRetryPolicy | None = None,
        hitl_workflow: HumanReviewWorkflow | None = None,
        handoff_agent: ConsultationHandoffAgent | None = None,
    ) -> None:
        self.verifier = verifier or HarnessVerifier()
        self.retry_policy = retry_policy or HarnessRetryPolicy()
        self.hitl_workflow = hitl_workflow or HumanReviewWorkflow()
        self.handoff_agent = handoff_agent or ConsultationHandoffAgent()

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
        evidence_required: bool | None = None,
        tool_failure: McpToolFailure | None = None,
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
            evidence_required=evidence_required,
            tool_failure=tool_failure,
        )

        if timed_out:
            return HarnessResult(
                decision=HarnessDecision.ESCALATE,
                verification=verification,
                retry_state=state,
                error_code=HarnessErrorCode.AI_PROCESSING_TIMEOUT,
                should_escalate=True,
            )

        if tool_failure is not None and verification.decision == HarnessDecision.ESCALATE:
            return HarnessResult(
                decision=HarnessDecision.ESCALATE,
                verification=verification,
                retry_state=state,
                error_code=HarnessErrorCode.MCP_TOOL_FAILURE,
                should_escalate=True,
            )

        policy = self.retry_policy.apply(verification.decision, state)
        if policy.exhausted:
            return HarnessResult(
                decision=HarnessDecision.ESCALATE,
                verification=verification,
                retry_state=policy.state,
                error_code=self._exhausted_error_code(verification),
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

    def run_runtime(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        evidence_chunks: list[RetrievedChunk],
        safety_assessment: SafetyAssessment | None,
        guidance: UsageGuidance | None,
        retry_state: HarnessRetryState | None = None,
        required_functions: set[str] | None = None,
        output_payload: Any | None = None,
        output_schema: Type[BaseModel] | None = None,
        timed_out: bool = False,
        evidence_required: bool | None = None,
        tool_failure: McpToolFailure | None = None,
    ) -> HarnessRuntimeResult:
        """Run Harness and route HUMAN_REVIEW/ESCALATE without re-running the LLM pipeline."""

        harness = self.run(
            product=product,
            evidence_chunks=evidence_chunks,
            safety_assessment=safety_assessment,
            guidance=guidance,
            retry_state=retry_state,
            required_functions=required_functions,
            output_payload=output_payload,
            output_schema=output_schema,
            timed_out=timed_out,
            evidence_required=evidence_required,
            tool_failure=tool_failure,
        )
        return self.route_runtime(
            ctx=ctx,
            product=product,
            harness=harness,
            guidance=guidance,
        )

    def route_runtime(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        harness: HarnessResult,
        guidance: UsageGuidance | None,
        force_handoff_reason: str | None = None,
    ) -> HarnessRuntimeResult:
        """Route an already-verified HarnessResult to HITL/Handoff without re-verification."""

        if harness.decision == HarnessDecision.HUMAN_REVIEW:
            if guidance is None:
                return HarnessRuntimeResult(
                    harness=harness,
                    handoff=self._create_handoff(
                        ctx=ctx,
                        product=product,
                        reason="HUMAN_REVIEW_WITHOUT_GUIDANCE",
                    ),
                )
            trace = ctx.trace_context
            issue_codes = [issue.code.value for issue in harness.verification.issues]
            review = self.hitl_workflow.start(
                HumanReviewRequest(
                    inquiry_id=trace.inquiry_id,
                    correlation_id=trace.correlation_id,
                    ai_request_id=trace.ai_request_id,
                    state_version=trace.state_version,
                    model_code=product.model_code,
                    product_family=product.product_family.value,
                    review_reason=self._review_reason(issue_codes),
                    verification_issue_codes=issue_codes,
                    evidence_chunk_ids=harness.verification.accepted_evidence_chunk_ids,
                    proposed_guidance=guidance,
                )
            )
            return HarnessRuntimeResult(harness=harness, human_review=review)

        if harness.should_escalate:
            return HarnessRuntimeResult(
                harness=harness,
                handoff=self._create_handoff(
                    ctx=ctx,
                    product=product,
                    reason=self._escalation_reason(harness),
                ),
            )

        if force_handoff_reason:
            return HarnessRuntimeResult(
                harness=harness,
                handoff=self._create_handoff(
                    ctx=ctx,
                    product=product,
                    reason=force_handoff_reason,
                ),
            )

        return HarnessRuntimeResult(harness=harness)

    def resume_human_review(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        interrupted: HumanReviewExecutionResult,
        response: HumanReviewResume,
    ) -> HumanReviewResolution:
        """Resume only the checkpointed review graph; prior retrieval/generation is not called again."""

        review = self.hitl_workflow.resume(
            checkpoint=interrupted.checkpoint,
            response=response,
        )
        outcome = review.outcome
        if outcome is None:
            raise RuntimeError("human review resume did not produce an outcome")
        if outcome.approved:
            return HumanReviewResolution(review=review, guidance=outcome.guidance)
        return HumanReviewResolution(
            review=review,
            handoff=self._create_handoff(
                ctx=ctx,
                product=product,
                reason="HUMAN_REVIEW_REJECTED",
            ),
        )

    def _create_handoff(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        reason: str,
    ) -> ConsultationHandoffResult:
        handoff_input = ConsultationHandoffInput.from_pipeline_context(
            ctx=ctx,
            product_family=product.product_family.value,
            escalation_reason=reason,
        )
        return self.handoff_agent.run(handoff_input)

    @staticmethod
    def _exhausted_error_code(verification: VerificationResult) -> HarnessErrorCode:
        issue_codes = {issue.code.value for issue in verification.issues}
        if "MCP_TOOL_FAILURE" in issue_codes:
            return HarnessErrorCode.MCP_TOOL_FAILURE
        return HarnessErrorCode.NO_EVIDENCE

    @staticmethod
    def _review_reason(issue_codes: list[str]) -> str:
        suffix = ",".join(issue_codes) if issue_codes else "UNSPECIFIED"
        return f"HARNESS_HUMAN_REVIEW:{suffix}"

    @staticmethod
    def _escalation_reason(harness: HarnessResult) -> str:
        if harness.error_code is not None:
            return harness.error_code.value
        issue_codes = [issue.code.value for issue in harness.verification.issues]
        suffix = ",".join(issue_codes) if issue_codes else "UNSPECIFIED"
        return f"HARNESS_ESCALATE:{suffix}"
