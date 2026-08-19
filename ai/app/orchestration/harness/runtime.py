"""Runtime integration layer for Harness verification, bounded retries, HITL, and handoff."""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel, ConfigDict, Field

from ...common.timeout import (
    CancellationToken,
    PipelineStageTimeoutError,
    get_stage_timeout_policy,
)
from ...integrations.llm import GuidanceLLMClient
from ...retrieval import RetrievalOutcome
from ...schemas import AiStage, RiskLevel, UsageGuidance, UsageGuidanceStatus
from ..stages import execute_generation_stage, execute_retrieval_stage, execute_validation_stage
from .evidence_capture import GuardedEvidenceSearchService
from .product_match import ProductContext
from .retry_policy import HarnessRetryState
from .runner import HarnessRunner, HarnessRuntimeResult
from .verification_result import HarnessDecision


class ReliabilityRuntimeResult(BaseModel):
    """Internal reliability result. It is never serialized into the public AI response."""

    model_config = ConfigDict(extra="forbid")

    harness_runtime: HarnessRuntimeResult
    retrieval_retry_performed: bool = False
    generation_retry_performed: bool = False
    blocked_evidence_chunk_ids: list[str] = Field(default_factory=list)
    timeout_stage: str | None = None


class ReliabilityRuntime:
    """Apply Harness after a pipeline run and perform at most one semantic retry per stage."""

    def __init__(self, runner: HarnessRunner | None = None) -> None:
        self.runner = runner or HarnessRunner()
        self.timeout_policy = get_stage_timeout_policy()

    def run(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        evidence_capture: GuardedEvidenceSearchService | None,
        search_service: Any,
        llm_client: GuidanceLLMClient | None,
        cancellation_token: CancellationToken,
        required_functions: set[str] | None = None,
        output_payload: Any | None = None,
        output_schema: Type[BaseModel] | None = None,
    ) -> ReliabilityRuntimeResult:
        retry_state = HarnessRetryState()
        retrieval_retry_performed = False
        generation_retry_performed = False

        for _ in range(3):
            evidence_chunks = (
                evidence_capture.evidence_for_harness(ctx)
                if evidence_capture is not None
                else []
            )
            harness = self.runner.run(
                product=product,
                evidence_chunks=evidence_chunks,
                safety_assessment=getattr(ctx, "safety_assessment", None),
                guidance=getattr(ctx, "usage_guidance", None),
                retry_state=retry_state,
                required_functions=required_functions,
                output_payload=output_payload,
                output_schema=output_schema,
                evidence_required=self._evidence_required(ctx),
            )
            retry_state = harness.retry_state

            if harness.decision == HarnessDecision.RETRY_RETRIEVAL:
                if retrieval_retry_performed or search_service is None:
                    break
                retrieval_retry_performed = True
                try:
                    self._retry_retrieval(
                        ctx=ctx,
                        evidence_capture=evidence_capture,
                        search_service=search_service,
                        llm_client=llm_client,
                        cancellation_token=cancellation_token,
                    )
                except PipelineStageTimeoutError as exc:
                    return self._timeout_result(
                        ctx=ctx,
                        product=product,
                        evidence_capture=evidence_capture,
                        retry_state=retry_state,
                        retrieval_retry_performed=retrieval_retry_performed,
                        generation_retry_performed=generation_retry_performed,
                        timeout_stage=exc.stage,
                    )
                continue

            if harness.decision == HarnessDecision.RETRY_GENERATION:
                if generation_retry_performed:
                    break
                generation_retry_performed = True
                try:
                    self._retry_generation(
                        ctx=ctx,
                        llm_client=llm_client,
                        cancellation_token=cancellation_token,
                    )
                except PipelineStageTimeoutError as exc:
                    return self._timeout_result(
                        ctx=ctx,
                        product=product,
                        evidence_capture=evidence_capture,
                        retry_state=retry_state,
                        retrieval_retry_performed=retrieval_retry_performed,
                        generation_retry_performed=generation_retry_performed,
                        timeout_stage=exc.stage,
                    )
                continue

            final_runtime = self._route_final(
                ctx=ctx,
                product=product,
                harness=harness,
            )
            return ReliabilityRuntimeResult(
                harness_runtime=final_runtime,
                retrieval_retry_performed=retrieval_retry_performed,
                generation_retry_performed=generation_retry_performed,
                blocked_evidence_chunk_ids=(
                    evidence_capture.rejected_chunk_ids
                    if evidence_capture is not None
                    else []
                ),
            )

        # Defensive fallback: the bounded policy should normally convert the second retry request to ESCALATE.
        evidence_chunks = (
            evidence_capture.evidence_for_harness(ctx)
            if evidence_capture is not None
            else []
        )
        harness = self.runner.run(
            product=product,
            evidence_chunks=evidence_chunks,
            safety_assessment=getattr(ctx, "safety_assessment", None),
            guidance=getattr(ctx, "usage_guidance", None),
            retry_state=retry_state,
            required_functions=required_functions,
            output_payload=output_payload,
            output_schema=output_schema,
            evidence_required=self._evidence_required(ctx),
        )
        final_runtime = self._route_final(ctx=ctx, product=product, harness=harness)
        return ReliabilityRuntimeResult(
            harness_runtime=final_runtime,
            retrieval_retry_performed=retrieval_retry_performed,
            generation_retry_performed=generation_retry_performed,
            blocked_evidence_chunk_ids=(
                evidence_capture.rejected_chunk_ids
                if evidence_capture is not None
                else []
            ),
        )

    def _timeout_result(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        evidence_capture: GuardedEvidenceSearchService | None,
        retry_state: HarnessRetryState,
        retrieval_retry_performed: bool,
        generation_retry_performed: bool,
        timeout_stage: str,
    ) -> ReliabilityRuntimeResult:
        """Convert a Harness-controlled stage timeout into a sanitized counselor handoff."""

        evidence_chunks = (
            evidence_capture.evidence_for_harness(ctx)
            if evidence_capture is not None
            else []
        )
        harness = self.runner.run(
            product=product,
            evidence_chunks=evidence_chunks,
            safety_assessment=getattr(ctx, "safety_assessment", None),
            guidance=getattr(ctx, "usage_guidance", None),
            retry_state=retry_state,
            timed_out=True,
            evidence_required=False,
        )
        final_runtime = self._route_final(
            ctx=ctx,
            product=product,
            harness=harness,
        )
        return ReliabilityRuntimeResult(
            harness_runtime=final_runtime,
            retrieval_retry_performed=retrieval_retry_performed,
            generation_retry_performed=generation_retry_performed,
            blocked_evidence_chunk_ids=(
                evidence_capture.rejected_chunk_ids
                if evidence_capture is not None
                else []
            ),
            timeout_stage=timeout_stage,
        )

    @staticmethod
    def _evidence_required(ctx: Any) -> bool:
        """Require grounding except for intentional no-retrieval runtime states."""
        if bool(getattr(ctx, "awaiting_customer_input", False)):
            return False
        safety = getattr(ctx, "safety_assessment", None)
        return not (
            safety is not None
            and safety.risk_level == RiskLevel.DANGER
        )

    def _retry_retrieval(
        self,
        *,
        ctx: Any,
        evidence_capture: GuardedEvidenceSearchService | None,
        search_service: Any,
        llm_client: GuidanceLLMClient | None,
        cancellation_token: CancellationToken,
    ) -> None:
        cancellation_token.raise_if_cancelled()
        if evidence_capture is not None:
            evidence_capture.begin_attempt()
        ctx.retry_count = 1
        with cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(AiStage.RETRIEVING.value),
            AiStage.RETRIEVING.value,
        ):
            execute_retrieval_stage(
                ctx,
                search_service,
                cancellation_token=cancellation_token,
            )

        # Generation is allowed only after the guarded search returned evidence that survived
        # topic/applicability filtering. Wrong-model evidence therefore never reaches the LLM.
        if getattr(ctx, "evidence_references", None):
            self._retry_generation(
                ctx=ctx,
                llm_client=llm_client,
                cancellation_token=cancellation_token,
            )

    def _retry_generation(
        self,
        *,
        ctx: Any,
        llm_client: GuidanceLLMClient | None,
        cancellation_token: CancellationToken,
    ) -> None:
        cancellation_token.raise_if_cancelled()
        ctx.retry_count = 1
        timeout_seconds = self.timeout_policy.for_stage(AiStage.GENERATING.value)
        with cancellation_token.deadline_scope(
            timeout_seconds,
            AiStage.GENERATING.value,
        ):
            execute_generation_stage(
                ctx,
                llm_client,
                cancellation_token,
                attempt_timeout_seconds=min(7.0, timeout_seconds / 2.0),
            )
        with cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(AiStage.VALIDATING.value),
            AiStage.VALIDATING.value,
        ):
            execute_validation_stage(ctx)

    def _route_final(
        self,
        *,
        ctx: Any,
        product: ProductContext,
        harness: Any,
    ) -> HarnessRuntimeResult:
        original_guidance = getattr(ctx, "usage_guidance", None)

        if harness.decision == HarnessDecision.HUMAN_REVIEW:
            routed = self.runner.route_runtime(
                ctx=ctx,
                product=product,
                harness=harness,
                guidance=original_guidance,
            )
            ctx.usage_guidance = self._safe_blocking_guidance(ctx)
            return routed

        if harness.decision == HarnessDecision.ESCALATE:
            ctx.usage_guidance = self._safe_blocking_guidance(ctx)
            if not harness.verification.accepted_evidence_chunk_ids:
                ctx.evidence_references = []
                if getattr(ctx, "retrieval_outcome", None) == RetrievalOutcome.AVAILABLE:
                    ctx.retrieval_outcome = RetrievalOutcome.NO_MATCH
            return self.runner.route_runtime(
                ctx=ctx,
                product=product,
                harness=harness,
                guidance=ctx.usage_guidance,
            )

        force_handoff_reason = None
        safety = getattr(ctx, "safety_assessment", None)
        if safety is not None and safety.risk_level == RiskLevel.DANGER:
            force_handoff_reason = "DANGER_PRIORITY"
        return self.runner.route_runtime(
            ctx=ctx,
            product=product,
            harness=harness,
            guidance=original_guidance,
            force_handoff_reason=force_handoff_reason,
        )

    @staticmethod
    def _safe_blocking_guidance(ctx: Any) -> UsageGuidance:
        safety = getattr(ctx, "safety_assessment", None)
        if safety is not None and safety.risk_level == RiskLevel.DANGER:
            return UsageGuidance(
                guidance_status=UsageGuidanceStatus.TOTAL_STOP,
                message="안전 확인이 필요하여 제품 사용을 중단하고 상담 연결을 진행합니다.",
                restricted_functions=["전체 제품 사용"],
                next_actions=["제품 사용을 중단하고 전문 상담 연결을 요청해 주세요."],
            )
        return UsageGuidance(
            guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
            message="자동 안내를 확정하지 못해 상담사 검토가 필요합니다.",
            restricted_functions=["검토 전 자가조치 안내"],
            next_actions=["전문 상담 연결을 요청해 주세요."],
        )
