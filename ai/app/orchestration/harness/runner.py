"""Harness runner that converts verification into bounded runtime actions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Type

from opentelemetry import trace
from pydantic import BaseModel, ConfigDict

from ...common.timeout import PipelineCancelledError
from ...integrations.llm.consultation_summary_client import (
    OpenAIResponsesConsultationContextClient,
)
from ...integrations.llm.llm_client import LLMConfigurationError
from ...retrieval.models.retrieved_chunk import RetrievedChunk
from ...schemas import SafetyAssessment, UsageGuidance
from ..agents.consultation_context_synthesis_agent import (
    ConsultationContextSynthesisAgent,
)
from ..agents.context_synthesis_contracts import (
    ConsultationContextSynthesisInput,
    ContextRoutingReason,
)
from ..handoff import (
    ConsultationHandoffAgent,
    ConsultationHandoffInput,
    ConsultationHandoffResult,
    HandoffContextSynthesis,
)
from ..hitl import HumanReviewExecutionResult, HumanReviewRequest, HumanReviewResume, HumanReviewWorkflow
from .product_match import ProductContext
from .retry_policy import HarnessRetryPolicy, HarnessRetryState
from .tool_failure import McpToolFailure
from .verification_result import HarnessDecision, VerificationResult
from .verifier import HarnessVerifier


_HARNESS_TRACER = trace.get_tracer("waterbridge.ai.harness", "1.0.0")


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
        context_synthesis_agent: ConsultationContextSynthesisAgent | None = None,
    ) -> None:
        self.verifier = verifier or HarnessVerifier()
        self.retry_policy = retry_policy or HarnessRetryPolicy()
        self.hitl_workflow = hitl_workflow or HumanReviewWorkflow()
        self.handoff_agent = handoff_agent or ConsultationHandoffAgent()
        self.context_synthesis_agent = (
            context_synthesis_agent or self._default_context_synthesis_agent()
        )

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
        with _HARNESS_TRACER.start_as_current_span(
            "waterbridge.harness.verify"
        ) as span:
            span.set_attribute("waterbridge.model.code", product.model_code)
            span.set_attribute(
                "waterbridge.product.family",
                product.product_family.value,
            )
            span.set_attribute(
                "waterbridge.harness.evidence.input_count",
                len(evidence_chunks),
            )
            span.set_attribute(
                "waterbridge.harness.retry.retrieval_count",
                state.retrieval_retries,
            )
            span.set_attribute(
                "waterbridge.harness.retry.generation_count",
                state.generation_retries,
            )
            span.set_attribute("waterbridge.harness.timed_out", timed_out)
            span.set_attribute(
                "waterbridge.harness.tool_failure.present",
                tool_failure is not None,
            )
            if tool_failure is not None:
                span.set_attribute(
                    "waterbridge.harness.tool_failure.kind",
                    tool_failure.kind.value,
                )
                span.set_attribute(
                    "waterbridge.harness.tool_failure.tool",
                    tool_failure.tool_name.value,
                )

            result = self._run_untraced(
                product=product,
                evidence_chunks=evidence_chunks,
                safety_assessment=safety_assessment,
                guidance=guidance,
                retry_state=state,
                required_functions=required_functions,
                output_payload=output_payload,
                output_schema=output_schema,
                timed_out=timed_out,
                evidence_required=evidence_required,
                tool_failure=tool_failure,
            )
            issue_codes = [
                issue.code.value for issue in result.verification.issues
            ]
            span.set_attribute(
                "waterbridge.harness.decision",
                result.decision.value,
            )
            span.set_attribute(
                "waterbridge.harness.issue_count",
                len(issue_codes),
            )
            if issue_codes:
                span.set_attribute(
                    "waterbridge.harness.issue_codes",
                    issue_codes,
                )
            span.set_attribute(
                "waterbridge.harness.evidence.accepted_count",
                len(result.verification.accepted_evidence_chunk_ids),
            )
            span.set_attribute(
                "waterbridge.harness.should_retry",
                result.should_retry,
            )
            span.set_attribute(
                "waterbridge.harness.should_escalate",
                result.should_escalate,
            )
            if result.error_code is not None:
                span.set_attribute(
                    "waterbridge.harness.error_code",
                    result.error_code.value,
                )
            return result

    def _run_untraced(
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
        """Trace the full Reliability runtime around verification and routing."""

        with _HARNESS_TRACER.start_as_current_span(
            "waterbridge.harness.runtime"
        ) as span:
            trace_context = getattr(ctx, "trace_context", None)
            inquiry_id = getattr(trace_context, "inquiry_id", None)
            if inquiry_id is not None:
                span.set_attribute(
                    "waterbridge.inquiry.id",
                    str(inquiry_id),
                )
            span.set_attribute("waterbridge.model.code", product.model_code)
            span.set_attribute(
                "waterbridge.product.family",
                product.product_family.value,
            )
            result = self._run_runtime_untraced(
                ctx=ctx,
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
            span.set_attribute(
                "waterbridge.harness.decision",
                result.harness.decision.value,
            )
            span.set_attribute(
                "waterbridge.harness.human_review.present",
                result.human_review is not None,
            )
            span.set_attribute(
                "waterbridge.harness.handoff.present",
                result.handoff is not None,
            )
            return result

    def _run_runtime_untraced(
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
                        accepted_evidence_chunk_ids=(
                            harness.verification.accepted_evidence_chunk_ids
                        ),
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
                    accepted_evidence_chunk_ids=(
                        harness.verification.accepted_evidence_chunk_ids
                    ),
                ),
            )

        if force_handoff_reason:
            return HarnessRuntimeResult(
                harness=harness,
                handoff=self._create_handoff(
                    ctx=ctx,
                    product=product,
                    reason=force_handoff_reason,
                    accepted_evidence_chunk_ids=(
                        harness.verification.accepted_evidence_chunk_ids
                    ),
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
        """Trace review resume without recording reviewer free text."""

        with _HARNESS_TRACER.start_as_current_span(
            "waterbridge.harness.resume_review"
        ) as span:
            trace_context = getattr(ctx, "trace_context", None)
            inquiry_id = getattr(trace_context, "inquiry_id", None)
            if inquiry_id is not None:
                span.set_attribute(
                    "waterbridge.inquiry.id",
                    str(inquiry_id),
                )
            span.set_attribute("waterbridge.model.code", product.model_code)
            span.set_attribute(
                "waterbridge.hitl.thread_id",
                interrupted.checkpoint.thread_id,
            )
            span.set_attribute(
                "waterbridge.hitl.state_version",
                response.state_version,
            )
            span.set_attribute(
                "waterbridge.hitl.decision",
                response.decision.value,
            )
            resolution = self._resume_human_review_untraced(
                ctx=ctx,
                product=product,
                interrupted=interrupted,
                response=response,
            )
            span.set_attribute(
                "waterbridge.harness.handoff.present",
                resolution.handoff is not None,
            )
            span.set_attribute(
                "waterbridge.hitl.guidance.present",
                resolution.guidance is not None,
            )
            return resolution

    def _resume_human_review_untraced(
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
                accepted_evidence_chunk_ids=self._review_evidence_chunk_ids(interrupted),
            ),
        )

    def _create_handoff(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        reason: str,
        accepted_evidence_chunk_ids: list[str] | None = None,
    ) -> ConsultationHandoffResult:
        accepted_ids = list(dict.fromkeys(accepted_evidence_chunk_ids or []))
        routing_reason = self._context_routing_reason(ctx, reason)
        handoff_input = ConsultationHandoffInput.from_pipeline_context(
            ctx=ctx,
            product_family=product.product_family.value,
            escalation_reason=reason,
            accepted_evidence_chunk_ids=accepted_ids,
            routing_reason=routing_reason.value,
        )
        context_synthesis = self._synthesize_handoff_context(
            ctx=ctx,
            product=product,
            reason=reason,
            routing_reason=routing_reason,
            accepted_evidence_chunk_ids=accepted_ids,
        )
        return self.handoff_agent.run(
            handoff_input,
            context_synthesis=context_synthesis,
        )

    def _synthesize_handoff_context(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        reason: str,
        routing_reason: ContextRoutingReason,
        accepted_evidence_chunk_ids: list[str],
    ) -> HandoffContextSynthesis | None:
        """Best-effort context synthesis; synthesis failure must not block handoff."""

        accepted_ids = set(accepted_evidence_chunk_ids)
        accepted_evidence = [
            item
            for item in (getattr(ctx, "evidence_references", []) or [])
            if getattr(item, "chunk_id", None) in accepted_ids
        ]
        try:
            synthesis_input = ConsultationContextSynthesisInput.from_pipeline_context(
                ctx=ctx,
                product_family=product.product_family.value,
                runtime_product_approved=product.runtime_approved,
                routing_reason=routing_reason,
                escalation_reason=reason,
                accepted_evidence=accepted_evidence,
            )
            output = self.context_synthesis_agent.run(synthesis_input)
            return HandoffContextSynthesis.from_agent_output(output)
        except PipelineCancelledError:
            raise
        except Exception:
            # Context synthesis is supplementary; keep the existing handoff path.
            return None

    @staticmethod
    def _context_routing_reason(ctx: Any, reason: str) -> ContextRoutingReason:
        safety = getattr(ctx, "safety_assessment", None)
        risk_level = getattr(getattr(safety, "risk_level", None), "value", None)
        if risk_level == "danger":
            return ContextRoutingReason.DANGER_HANDOFF
        if reason in {
            "HUMAN_REVIEW_REJECTED",
            "HUMAN_REVIEW_WITHOUT_GUIDANCE",
        }:
            return ContextRoutingReason.FAIL_CLOSED_CONSULTATION
        return ContextRoutingReason.HARNESS_ESCALATE

    @staticmethod
    def _review_evidence_chunk_ids(
        interrupted: HumanReviewExecutionResult,
    ) -> list[str]:
        payload = interrupted.interrupt_payload
        if not isinstance(payload, dict):
            return []
        values = payload.get("evidence_chunk_ids", [])
        if not isinstance(values, list):
            return []
        return [
            value
            for value in values
            if isinstance(value, str) and value.strip()
        ]

    @staticmethod
    def _default_context_synthesis_agent() -> ConsultationContextSynthesisAgent:
        try:
            llm_client = OpenAIResponsesConsultationContextClient.from_environment()
        except (LLMConfigurationError, TypeError, ValueError):
            llm_client = None
        return ConsultationContextSynthesisAgent(llm_client=llm_client)

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
