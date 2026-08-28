"""Run an explicit, protected Consultation Context Provider Canary.

This script is not a production resume endpoint.  It manually bridges the
already-existing PRE_SEND_HUMAN_REVIEW decision to the in-process HITL
checkpoint, applies REJECT in the same Python process, and calls the real
consultation-context Provider only after that rejection.

The input fixture and generated report must stay outside Git or under an
ignored path such as ``.runtime/``.  The report contains identifiers, hashes,
status codes, and counts only; it never emits the input text, Evidence bodies,
Provider prompts, credentials, or the generated counselor brief.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ai.app.generation.consultation_summary.context_synthesizer import (
    ConsultationContextSynthesizer,
)
from ai.app.integrations.backend.handoff_client import (
    BACKEND_BASE_URL_ENV,
    HANDOFF_TIMEOUT_ENV,
    HANDOFF_TOKEN_ENV,
    HandoffPublishResult,
    HandoffPublishStatus,
    handoff_delivery_enabled,
    publish_consultation_handoff,
)
from ai.app.integrations.llm import (
    ConsultationContextLLMClient,
    OpenAIResponsesConsultationContextClient,
)
from ai.app.orchestration.agents import (
    ConsultationContextSynthesisAgent,
    ConsultationContextSynthesisInput,
    ContextRoutingReason,
)
from ai.app.orchestration.handoff import (
    ConsultationHandoffResult,
    ConsultationHandoffV2Request,
)
from ai.app.orchestration.harness import (
    HarnessDecision,
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.hitl import (
    HumanReviewDecision,
    HumanReviewRequest,
    HumanReviewResume,
    HumanReviewStatus,
    build_hitl_thread_id,
)
from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.retrieval import RetrievalOutcome
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import (
    AiExecutionStatus,
    EvidenceReference,
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    StructuredSymptom,
    SymptomAnalysisResult,
    TraceContext,
    UsageGuidance,
    UsageGuidanceStatus,
)
from ai.app.validation.routing import (
    ResponseRoutingDisposition,
    ResponseRoutingPolicy,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
INPUT_SCHEMA_VERSION = "1.0.0"
REPORT_SCHEMA_VERSION = "1.0.0"
TARGET_MODEL_CODE = "WPUJAC104DWH"
TARGET_PRODUCT_FAMILY = ProductFamily.DIRECT_WATER_PURIFIER
TARGET_SUPPORTED_FUNCTIONS = frozenset(
    {"cold_water", "hot_water", "purified_water"}
)
REVIEW_REASON = "CAUTION_PRE_SEND_REVIEW"
REJECT_ESCALATION_REASON = "HUMAN_REVIEW_REJECTED"
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class _CanaryModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        revalidate_instances="always",
    )


class CanaryPreviousAnswer(_CanaryModel):
    field_name: str = Field(min_length=1, max_length=100)
    answer_text: str = Field(min_length=1, max_length=500)


class CanaryEvidenceInput(_CanaryModel):
    chunk_id: str = Field(min_length=1, max_length=200)
    document_title: str = Field(min_length=1, max_length=500)
    page: int = Field(ge=1)
    model_code: str = Field(pattern=r"^[A-Z0-9-]{1,100}$")
    content: str = Field(min_length=1, max_length=4000)
    summary: str = Field(min_length=1, max_length=2000)
    source_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    similarity_score: float = Field(ge=0.0, le=1.0)
    verification_status: Literal["official_verified"] = "official_verified"
    allowed_use: Literal[True] = True
    runtime_eligible: Literal[True] = True


class ConsultationContextProviderCanaryInput(_CanaryModel):
    """Protected fixture contract; fixture instances must never be committed."""

    schema_version: Literal[INPUT_SCHEMA_VERSION]
    environment_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{2,99}$")
    data_classification: Literal["synthetic"]
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(min_length=1, max_length=100)
    state_version: int = Field(ge=1)
    backend_review_id: UUID
    backend_review_state_version_after_reject: int = Field(ge=2)
    checkpoint_thread_id: str = Field(pattern=r"^hitl-[a-f0-9]{32}$")
    model_code: Literal[TARGET_MODEL_CODE]
    product_family: Literal["DIRECT_WATER_PURIFIER"]
    runtime_product_approved: Literal[True] = True
    structured_symptom: StructuredSymptom
    previous_answers: list[CanaryPreviousAnswer] = Field(
        default_factory=list,
        max_length=30,
    )
    safety_assessment: SafetyAssessment
    guidance: UsageGuidance
    evidence: list[CanaryEvidenceInput] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_canary_boundary(self) -> "ConsultationContextProviderCanaryInput":
        if self.safety_assessment.risk_level != RiskLevel.CAUTION:
            raise ValueError("Provider Canary는 caution 입력만 허용합니다.")
        if not self.safety_assessment.requires_consultation:
            raise ValueError("Provider Canary는 상담 필요 판정이 필요합니다.")
        if self.safety_assessment.priority != SafetyPriority.CONSULTATION_RECOMMENDED:
            raise ValueError("Provider Canary 우선순위가 고정 계약과 다릅니다.")
        if self.safety_assessment.matched_safety_rule_ids:
            raise ValueError("caution Provider Canary에는 danger Rule ID를 둘 수 없습니다.")
        if self.guidance.guidance_status != UsageGuidanceStatus.PARTIAL_STOP:
            raise ValueError("Provider Canary 안내는 PARTIAL_STOP이어야 합니다.")

        chunk_ids = [item.chunk_id for item in self.evidence]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("Provider Canary Evidence chunk_id는 중복될 수 없습니다.")
        if any(item.model_code != self.model_code for item in self.evidence):
            raise ValueError("Provider Canary Evidence 제품이 문의 제품과 다릅니다.")
        expected_thread_id = build_hitl_thread_id(
            inquiry_id=self.inquiry_id,
            ai_request_id=self.ai_request_id,
            state_version=self.state_version,
        )
        if self.checkpoint_thread_id != expected_thread_id:
            raise ValueError("Backend와 AI의 HITL checkpoint_thread_id가 다릅니다.")
        return self


class DeliveryAttemptEvidence(_CanaryModel):
    status: str
    attempts: int = Field(ge=0)
    status_code: int | None = None
    failure_kind: str | None = None


class HandoffDeliveryEvidence(_CanaryModel):
    requested: bool = False
    replay_requested: bool = False
    first: DeliveryAttemptEvidence | None = None
    replay: DeliveryAttemptEvidence | None = None


class ConsultationContextProviderCanaryReport(_CanaryModel):
    report_schema_version: Literal[REPORT_SCHEMA_VERSION] = REPORT_SCHEMA_VERSION
    overall_status: Literal["INSPECTED", "AI_COMPONENT_PASS", "PASS", "FAIL"]
    failure_stage: str | None = None
    failure_code: str | None = None
    environment_id: str
    git_branch: str
    git_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    origin_main_sha: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    git_dirty: bool
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_binding_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str
    state_version: int
    backend_review_id: UUID
    backend_review_state_version_after_reject: int
    checkpoint_thread_id: str = Field(pattern=r"^hitl-[a-f0-9]{32}$")
    model_code: str
    harness_decision: str | None = None
    harness_issue_codes: list[str] = Field(default_factory=list)
    routing_disposition: str | None = None
    accepted_evidence_chunk_ids: list[str] = Field(default_factory=list)
    initial_review_status: str | None = None
    initial_context_agent_calls: int = 0
    initial_provider_calls: int = 0
    initial_handoff_present: bool = False
    resolved_review_status: str | None = None
    review_decision: str | None = None
    context_agent_calls: int = 0
    provider_calls: int = 0
    provider_source_count: int = 0
    provider_input_explicitly_allowed: bool = False
    context_synthesis_status: str | None = None
    context_synthesis_fallback_reason: str | None = None
    provider_called: bool | None = None
    provider_model: str | None = None
    prompt_version: str | None = None
    tokens_used: int | None = Field(default=None, ge=0)
    routing_reason: str | None = None
    escalation_reason: str | None = None
    handoff_schema_version: str | None = None
    handoff_source_chunk_ids: list[str] = Field(default_factory=list)
    context_evidence_chunk_ids: list[str] = Field(default_factory=list)
    handoff_delivery: HandoffDeliveryEvidence = Field(
        default_factory=HandoffDeliveryEvidence
    )


class CanaryExecutionError(RuntimeError):
    """Sanitized Canary stop signal; never include fixture or Provider text."""

    def __init__(
        self,
        code: str,
        *,
        stage: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.details = details or {}


class _CountingProviderClient:
    def __init__(self, delegate: ConsultationContextLLMClient) -> None:
        self.delegate = delegate
        self.call_count = 0
        self.source_count = 0

    def synthesize_context(self, request, *, timeout_seconds: float):
        self.call_count += 1
        self.source_count = len(request.sources)
        return self.delegate.synthesize_context(
            request,
            timeout_seconds=timeout_seconds,
        )


class _RecordingContextSynthesisAgent:
    def __init__(self, delegate: ConsultationContextSynthesisAgent) -> None:
        self.delegate = delegate
        self.call_count = 0
        self.accepted_evidence_chunk_ids: list[str] = []

    def run(self, synthesis_input, *, timeout_seconds: float = 5.0):
        self.call_count += 1
        self.accepted_evidence_chunk_ids = [
            item.chunk_id for item in synthesis_input.evidence
        ]
        return self.delegate.run(
            synthesis_input,
            timeout_seconds=timeout_seconds,
        )


class _ForbiddenContextSynthesisAgent:
    def __init__(self) -> None:
        self.call_count = 0

    def run(self, synthesis_input, *, timeout_seconds: float = 5.0):
        del synthesis_input, timeout_seconds
        self.call_count += 1
        raise CanaryExecutionError(
            "CONTEXT_AGENT_CALLED_DURING_INITIAL_REVIEW",
            stage="INITIAL_REVIEW",
        )


def _canonical_json_sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def input_hashes(
    canary_input: ConsultationContextProviderCanaryInput,
) -> tuple[str, str]:
    """Bind approval to the full validated input and exact Evidence bodies."""

    payload = canary_input.model_dump(mode="json")
    evidence_binding = [
        {
            "chunk_id": item.chunk_id,
            "model_code": item.model_code,
            "document_title_sha256": hashlib.sha256(
                item.document_title.encode("utf-8")
            ).hexdigest(),
            "page": item.page,
            "content_sha256": hashlib.sha256(
                item.content.encode("utf-8")
            ).hexdigest(),
            "summary_sha256": hashlib.sha256(
                item.summary.encode("utf-8")
            ).hexdigest(),
            "source_hash": item.source_hash.lower(),
            "verification_status": item.verification_status,
            "allowed_use": item.allowed_use,
            "runtime_eligible": item.runtime_eligible,
        }
        for item in sorted(canary_input.evidence, key=lambda value: value.chunk_id)
    ]
    return _canonical_json_sha256(payload), _canonical_json_sha256(evidence_binding)


def _build_runtime_objects(
    canary_input: ConsultationContextProviderCanaryInput,
) -> tuple[PipelineContext, ProductContext, list[RetrievedChunk]]:
    evidence_references = [
        EvidenceReference(
            document_title=item.document_title,
            page=item.page,
            page_refs=[item.page],
            chunk_id=item.chunk_id,
            summary=item.summary,
            similarity_score=item.similarity_score,
            verification_status=item.verification_status,
        )
        for item in canary_input.evidence
    ]
    evidence_chunks = [
        RetrievedChunk(
            chunk_id=item.chunk_id,
            document_title=item.document_title,
            page=item.page,
            page_refs=[item.page],
            manual_model=item.model_code,
            model_code=item.model_code,
            content=item.content,
            similarity_score=item.similarity_score,
            verification_status=item.verification_status,
            allowed_use=item.allowed_use,
            source_hash=item.source_hash,
            runtime_eligible=item.runtime_eligible,
        )
        for item in canary_input.evidence
    ]
    ctx = PipelineContext(
        trace_context=TraceContext(
            inquiry_id=canary_input.inquiry_id,
            correlation_id=canary_input.correlation_id,
            ai_request_id=canary_input.ai_request_id,
            state_version=canary_input.state_version,
        ),
        raw_symptom="SYNTHETIC_PROVIDER_CANARY",
        model_code=canary_input.model_code,
        selected_symptoms=[canary_input.structured_symptom.symptom_type],
        previous_answers=[
            item.model_dump(mode="json") for item in canary_input.previous_answers
        ],
        structured_symptom=canary_input.structured_symptom,
        safety_assessment=canary_input.safety_assessment,
        evidence_references=evidence_references,
        retrieval_outcome=RetrievalOutcome.AVAILABLE,
        usage_guidance=canary_input.guidance,
        awaiting_customer_input=False,
    )
    product = ProductContext(
        model_code=canary_input.model_code,
        product_family=TARGET_PRODUCT_FAMILY,
        runtime_approved=canary_input.runtime_product_approved,
        supported_functions=set(TARGET_SUPPORTED_FUNCTIONS),
    )
    return ctx, product, evidence_chunks


def _prepare_initial_review(
    canary_input: ConsultationContextProviderCanaryInput,
    *,
    runner: HarnessRunner,
) -> tuple[PipelineContext, ProductContext, Any, list[str], list[str]]:
    ctx, product, evidence_chunks = _build_runtime_objects(canary_input)
    harness = runner.run(
        product=product,
        evidence_chunks=evidence_chunks,
        safety_assessment=ctx.safety_assessment,
        guidance=ctx.usage_guidance,
        evidence_required=True,
    )
    issue_codes = [item.code.value for item in harness.verification.issues]
    if harness.decision != HarnessDecision.PASS:
        raise CanaryExecutionError(
            "INITIAL_HARNESS_NOT_PASS",
            stage="INITIAL_REVIEW",
            details={
                "harness_decision": harness.decision.value,
                "harness_issue_codes": issue_codes,
            },
        )

    accepted_ids = list(harness.verification.accepted_evidence_chunk_ids)
    expected_ids = [item.chunk_id for item in canary_input.evidence]
    if set(accepted_ids) != set(expected_ids):
        raise CanaryExecutionError(
            "HARNESS_ACCEPTED_EVIDENCE_MISMATCH",
            stage="INITIAL_REVIEW",
            details={"harness_issue_codes": issue_codes},
        )

    public_result = SymptomAnalysisResult(
        inquiry_id=canary_input.inquiry_id,
        correlation_id=canary_input.correlation_id,
        ai_request_id=canary_input.ai_request_id,
        state_version=canary_input.state_version,
        model_code=canary_input.model_code,
        status=AiExecutionStatus.SUCCEEDED,
        fallback_reason_code=None,
        failure_stage=None,
        retry_count=0,
        structured_symptom=canary_input.structured_symptom,
        missing_fields=[],
        followup_questions=[],
        safety_assessment=canary_input.safety_assessment,
        usage_guidance=canary_input.guidance,
        evidence_references=list(ctx.evidence_references),
    )
    _, routing_disposition = ResponseRoutingPolicy().apply(
        public_result,
        accepted_evidence_chunk_ids=accepted_ids,
    )
    if routing_disposition != ResponseRoutingDisposition.PRE_SEND_HUMAN_REVIEW:
        raise CanaryExecutionError(
            "INITIAL_ROUTE_NOT_PRE_SEND_HUMAN_REVIEW",
            stage="INITIAL_REVIEW",
            details={"routing_disposition": routing_disposition.value},
        )

    accepted_id_set = set(accepted_ids)
    accepted_evidence = [
        item for item in ctx.evidence_references if item.chunk_id in accepted_id_set
    ]
    synthesis_input = ConsultationContextSynthesisInput.from_pipeline_context(
        ctx=ctx,
        product_family=product.product_family.value,
        runtime_product_approved=product.runtime_approved,
        routing_reason=ContextRoutingReason.FAIL_CLOSED_CONSULTATION,
        escalation_reason=REJECT_ESCALATION_REASON,
        accepted_evidence=accepted_evidence,
    )
    prepared = ConsultationContextSynthesizer().prepare(synthesis_input)
    if prepared.request is None:
        raise CanaryExecutionError(
            "PROVIDER_INPUT_NOT_ELIGIBLE",
            stage="INITIAL_REVIEW",
            details={
                "provider_bypass_reason": prepared.provider_bypass_reason,
            },
        )

    review = runner.hitl_workflow.start(
        HumanReviewRequest(
            inquiry_id=canary_input.inquiry_id,
            correlation_id=canary_input.correlation_id,
            ai_request_id=canary_input.ai_request_id,
            state_version=canary_input.state_version,
            model_code=canary_input.model_code,
            product_family=canary_input.product_family,
            review_reason=REVIEW_REASON,
            verification_issue_codes=issue_codes,
            evidence_chunk_ids=accepted_ids,
            proposed_guidance=canary_input.guidance,
        )
    )
    if review.status != HumanReviewStatus.WAITING_FOR_REVIEW:
        raise CanaryExecutionError(
            "INITIAL_REVIEW_NOT_WAITING",
            stage="INITIAL_REVIEW",
        )
    if review.checkpoint.thread_id != canary_input.checkpoint_thread_id:
        raise CanaryExecutionError(
            "CHECKPOINT_THREAD_ID_MISMATCH",
            stage="INITIAL_REVIEW",
        )
    return ctx, product, review, accepted_ids, issue_codes


def _base_report(
    canary_input: ConsultationContextProviderCanaryInput,
    *,
    git_identity: dict[str, Any],
    overall_status: Literal["INSPECTED", "AI_COMPONENT_PASS", "PASS", "FAIL"],
) -> ConsultationContextProviderCanaryReport:
    input_sha256, evidence_sha256 = input_hashes(canary_input)
    return ConsultationContextProviderCanaryReport(
        overall_status=overall_status,
        environment_id=canary_input.environment_id,
        git_branch=str(git_identity["branch"]),
        git_sha=str(git_identity["git_sha"]),
        origin_main_sha=git_identity.get("origin_main_sha"),
        git_dirty=bool(git_identity["git_dirty"]),
        input_sha256=input_sha256,
        evidence_binding_sha256=evidence_sha256,
        inquiry_id=canary_input.inquiry_id,
        correlation_id=canary_input.correlation_id,
        ai_request_id=canary_input.ai_request_id,
        state_version=canary_input.state_version,
        backend_review_id=canary_input.backend_review_id,
        backend_review_state_version_after_reject=(
            canary_input.backend_review_state_version_after_reject
        ),
        checkpoint_thread_id=canary_input.checkpoint_thread_id,
        model_code=canary_input.model_code,
    )


def _apply_failure(
    report: ConsultationContextProviderCanaryReport,
    error: CanaryExecutionError,
) -> ConsultationContextProviderCanaryReport:
    update: dict[str, Any] = {
        "overall_status": "FAIL",
        "failure_stage": error.stage,
        "failure_code": error.code,
    }
    allowed_details = {
        "harness_decision",
        "harness_issue_codes",
        "routing_disposition",
        "context_synthesis_status",
        "context_synthesis_fallback_reason",
        "provider_called",
        "context_agent_calls",
        "provider_calls",
        "provider_source_count",
    }
    update.update(
        {
            key: value
            for key, value in error.details.items()
            if key in allowed_details
        }
    )
    return report.model_copy(update=update)


def inspect_canary(
    canary_input: ConsultationContextProviderCanaryInput,
    *,
    git_identity: dict[str, Any],
) -> ConsultationContextProviderCanaryReport:
    """Validate hashes, Harness Evidence, PRE_SEND routing, and input eligibility."""

    report = _base_report(
        canary_input,
        git_identity=git_identity,
        overall_status="INSPECTED",
    )
    forbidden_agent = _ForbiddenContextSynthesisAgent()
    runner = HarnessRunner(context_synthesis_agent=forbidden_agent)
    try:
        _, _, review, accepted_ids, issue_codes = _prepare_initial_review(
            canary_input,
            runner=runner,
        )
        if forbidden_agent.call_count != 0:
            raise CanaryExecutionError(
                "CONTEXT_AGENT_CALLED_DURING_INITIAL_REVIEW",
                stage="INITIAL_REVIEW",
            )
    except CanaryExecutionError as exc:
        return _apply_failure(report, exc)
    except Exception:
        return _apply_failure(
            report,
            CanaryExecutionError(
                "UNEXPECTED_INSPECTION_ERROR",
                stage="INITIAL_REVIEW",
            ),
        )

    return report.model_copy(
        update={
            "harness_decision": HarnessDecision.PASS.value,
            "harness_issue_codes": issue_codes,
            "routing_disposition": (
                ResponseRoutingDisposition.PRE_SEND_HUMAN_REVIEW.value
            ),
            "accepted_evidence_chunk_ids": accepted_ids,
            "initial_review_status": review.status.value,
            "initial_context_agent_calls": 0,
            "initial_provider_calls": 0,
            "initial_handoff_present": False,
        }
    )


def _delivery_attempt(result: HandoffPublishResult) -> DeliveryAttemptEvidence:
    return DeliveryAttemptEvidence(
        status=result.status.value,
        attempts=result.attempts,
        status_code=result.status_code,
        failure_kind=(
            result.failure_kind.value if result.failure_kind is not None else None
        ),
    )


def execute_canary(
    canary_input: ConsultationContextProviderCanaryInput,
    *,
    provider_client: ConsultationContextLLMClient,
    git_identity: dict[str, Any],
    provider_input_explicitly_allowed: bool,
    send_handoff: bool = False,
    verify_replay: bool = False,
    publisher: Callable[[ConsultationHandoffResult], HandoffPublishResult] = (
        publish_consultation_handoff
    ),
) -> ConsultationContextProviderCanaryReport:
    """Run initial review and rejected review with one actual Provider boundary."""

    report = _base_report(
        canary_input,
        git_identity=git_identity,
        overall_status="AI_COMPONENT_PASS",
    )
    if verify_replay and not send_handoff:
        return _apply_failure(
            report,
            CanaryExecutionError(
                "REPLAY_REQUIRES_HANDOFF_DELIVERY",
                stage="ARGUMENTS",
            ),
        )
    if not provider_input_explicitly_allowed:
        return _apply_failure(
            report,
            CanaryExecutionError(
                "PROVIDER_INPUT_NOT_EXPLICITLY_ALLOWED",
                stage="ARGUMENTS",
            ),
        )
    report = report.model_copy(
        update={"provider_input_explicitly_allowed": True}
    )

    counting_provider = _CountingProviderClient(provider_client)
    recording_agent = _RecordingContextSynthesisAgent(
        ConsultationContextSynthesisAgent(llm_client=counting_provider)
    )
    runner = HarnessRunner(context_synthesis_agent=recording_agent)

    try:
        ctx, product, review, accepted_ids, issue_codes = _prepare_initial_review(
            canary_input,
            runner=runner,
        )
        if recording_agent.call_count != 0 or counting_provider.call_count != 0:
            raise CanaryExecutionError(
                "PROVIDER_OR_AGENT_CALLED_DURING_INITIAL_REVIEW",
                stage="INITIAL_REVIEW",
                details={
                    "context_agent_calls": recording_agent.call_count,
                    "provider_calls": counting_provider.call_count,
                },
            )

        report = report.model_copy(
            update={
                "harness_decision": HarnessDecision.PASS.value,
                "harness_issue_codes": issue_codes,
                "routing_disposition": (
                    ResponseRoutingDisposition.PRE_SEND_HUMAN_REVIEW.value
                ),
                "accepted_evidence_chunk_ids": accepted_ids,
                "initial_review_status": review.status.value,
                "initial_context_agent_calls": 0,
                "initial_provider_calls": 0,
                "initial_handoff_present": False,
            }
        )

        resolved = runner.resume_human_review(
            ctx=ctx,
            product=product,
            interrupted=review,
            response=HumanReviewResume(
                decision=HumanReviewDecision.REJECT,
                state_version=canary_input.state_version,
            ),
        )
        handoff = resolved.handoff
        context_synthesis = (
            handoff.context_synthesis if handoff is not None else None
        )
        report = report.model_copy(
            update={
                "resolved_review_status": resolved.review.status.value,
                "review_decision": HumanReviewDecision.REJECT.value,
                "context_agent_calls": recording_agent.call_count,
                "provider_calls": counting_provider.call_count,
                "provider_source_count": counting_provider.source_count,
                "context_synthesis_status": (
                    context_synthesis.status
                    if context_synthesis is not None
                    else None
                ),
                "context_synthesis_fallback_reason": (
                    context_synthesis.fallback_reason
                    if context_synthesis is not None
                    else None
                ),
                "provider_called": (
                    context_synthesis.provider_called
                    if context_synthesis is not None
                    else None
                ),
                "provider_model": (
                    context_synthesis.model_name
                    if context_synthesis is not None
                    else None
                ),
                "prompt_version": (
                    context_synthesis.prompt_version
                    if context_synthesis is not None
                    else None
                ),
                "tokens_used": (
                    context_synthesis.tokens_used
                    if context_synthesis is not None
                    else None
                ),
                "routing_reason": (
                    handoff.routing_reason if handoff is not None else None
                ),
                "escalation_reason": (
                    handoff.escalation_reason if handoff is not None else None
                ),
                "handoff_source_chunk_ids": (
                    list(handoff.source_chunk_ids) if handoff is not None else []
                ),
            }
        )

        if handoff is None or context_synthesis is None:
            raise CanaryExecutionError(
                "REJECTED_REVIEW_DID_NOT_CREATE_CONTEXT_HANDOFF",
                stage="REJECTED_REVIEW",
                details={
                    "context_agent_calls": recording_agent.call_count,
                    "provider_calls": counting_provider.call_count,
                },
            )
        if (
            recording_agent.call_count != 1
            or counting_provider.call_count != 1
        ):
            raise CanaryExecutionError(
                "PROVIDER_OR_AGENT_CALL_COUNT_MISMATCH",
                stage="REJECTED_REVIEW",
                details={
                    "context_agent_calls": recording_agent.call_count,
                    "provider_calls": counting_provider.call_count,
                    "provider_source_count": counting_provider.source_count,
                },
            )
        if (
            context_synthesis.status != "SUCCEEDED"
            or context_synthesis.fallback_reason is not None
            or not context_synthesis.provider_called
        ):
            raise CanaryExecutionError(
                "CONTEXT_SYNTHESIS_NOT_SUCCEEDED",
                stage="PROVIDER",
                details={
                    "context_synthesis_status": context_synthesis.status,
                    "context_synthesis_fallback_reason": (
                        context_synthesis.fallback_reason
                    ),
                    "provider_called": context_synthesis.provider_called,
                    "context_agent_calls": recording_agent.call_count,
                    "provider_calls": counting_provider.call_count,
                    "provider_source_count": counting_provider.source_count,
                },
            )
        if (
            handoff.routing_reason != "FAIL_CLOSED_CONSULTATION"
            or handoff.escalation_reason != REJECT_ESCALATION_REASON
        ):
            raise CanaryExecutionError(
                "REJECTED_HANDOFF_ROUTE_MISMATCH",
                stage="HANDOFF_MAPPING",
            )
        if set(recording_agent.accepted_evidence_chunk_ids) != set(accepted_ids):
            raise CanaryExecutionError(
                "CONTEXT_AGENT_EVIDENCE_MISMATCH",
                stage="HANDOFF_MAPPING",
            )

        outbound = ConsultationHandoffV2Request.from_internal(handoff)
        external_context = outbound.context_synthesis
        if external_context is None or external_context.status != "SUCCEEDED":
            raise CanaryExecutionError(
                "EXTERNAL_CONTEXT_SYNTHESIS_MISSING",
                stage="HANDOFF_MAPPING",
            )
        nested_evidence_ids = sorted(
            {
                chunk_id
                for finding in external_context.brief.evidence_based_findings
                for chunk_id in finding.source_chunk_ids
            }
        )
        if not nested_evidence_ids or not set(nested_evidence_ids).issubset(
            set(accepted_ids)
        ):
            raise CanaryExecutionError(
                "EXTERNAL_CONTEXT_EVIDENCE_MISMATCH",
                stage="HANDOFF_MAPPING",
            )
        report = report.model_copy(
            update={
                "handoff_schema_version": outbound.schema_version,
                "context_evidence_chunk_ids": nested_evidence_ids,
            }
        )

        delivery = HandoffDeliveryEvidence(
            requested=send_handoff,
            replay_requested=verify_replay,
        )
        if send_handoff:
            first = publisher(handoff)
            delivery = delivery.model_copy(
                update={"first": _delivery_attempt(first)}
            )
            report = report.model_copy(update={"handoff_delivery": delivery})
            if first.status != HandoffPublishStatus.DELIVERED:
                raise CanaryExecutionError(
                    "HANDOFF_DELIVERY_FAILED",
                    stage="HANDOFF_DELIVERY",
                )
            if verify_replay:
                replay = publisher(handoff)
                delivery = delivery.model_copy(
                    update={"replay": _delivery_attempt(replay)}
                )
                report = report.model_copy(update={"handoff_delivery": delivery})
                if replay.status != HandoffPublishStatus.DELIVERED:
                    raise CanaryExecutionError(
                        "HANDOFF_REPLAY_FAILED",
                        stage="HANDOFF_REPLAY",
                    )
            report = report.model_copy(update={"overall_status": "PASS"})
        else:
            report = report.model_copy(update={"handoff_delivery": delivery})
        return report
    except CanaryExecutionError as exc:
        return _apply_failure(report, exc)
    except Exception:
        return _apply_failure(
            report,
            CanaryExecutionError(
                "UNEXPECTED_EXECUTION_ERROR",
                stage="CANARY_EXECUTION",
            ),
        )


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def git_identity() -> dict[str, Any]:
    try:
        origin_main_sha = _git_output("rev-parse", "origin/main")
    except (OSError, subprocess.CalledProcessError):
        origin_main_sha = None
    return {
        "branch": _git_output("branch", "--show-current") or "DETACHED",
        "git_sha": _git_output("rev-parse", "HEAD"),
        "origin_main_sha": origin_main_sha,
        "git_dirty": bool(_git_output("status", "--porcelain")),
    }


def _is_within_repository(path: Path) -> bool:
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        return False
    return True


def _require_protected_path(path: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not _is_within_repository(resolved):
        return resolved
    relative = resolved.relative_to(REPOSITORY_ROOT).as_posix()
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative],
        cwd=REPOSITORY_ROOT,
        check=False,
    ).returncode == 0
    if not ignored:
        raise CanaryExecutionError(
            f"{label}_PATH_IS_NOT_GIT_IGNORED",
            stage="PROTECTED_PATH",
        )
    return resolved


def load_canary_input(path: Path) -> ConsultationContextProviderCanaryInput:
    protected_path = _require_protected_path(path, label="INPUT")
    try:
        if protected_path.stat().st_size > 256_000:
            raise CanaryExecutionError(
                "INPUT_FILE_TOO_LARGE",
                stage="INPUT",
            )
        payload = json.loads(protected_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise CanaryExecutionError(
                "INPUT_IS_NOT_JSON_OBJECT",
                stage="INPUT",
            )
        return ConsultationContextProviderCanaryInput.model_validate(payload)
    except CanaryExecutionError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise CanaryExecutionError(
            "INPUT_VALIDATION_FAILED",
            stage="INPUT",
        ) from exc


def _normalized_sha256(value: str | None, *, field_name: str) -> str:
    normalized = (value or "").strip().lower()
    if not _SHA256_PATTERN.fullmatch(normalized):
        raise CanaryExecutionError(
            f"INVALID_{field_name}",
            stage="ARGUMENTS",
        )
    return normalized


def _require_handoff_configuration_ready() -> None:
    base_url = os.getenv(BACKEND_BASE_URL_ENV, "").strip().rstrip("/")
    token = os.getenv(HANDOFF_TOKEN_ENV, "").strip()
    raw_timeout = os.getenv(HANDOFF_TIMEOUT_ENV, "2.0").strip()
    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as exc:
        raise CanaryExecutionError(
            "HANDOFF_CONFIGURATION_INVALID",
            stage="HANDOFF_CONFIGURATION",
        ) from exc
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or not token
        or not 0.1 <= timeout_seconds <= 10.0
    ):
        raise CanaryExecutionError(
            "HANDOFF_CONFIGURATION_INVALID",
            stage="HANDOFF_CONFIGURATION",
        )


def _write_report(
    path: Path,
    report: ConsultationContextProviderCanaryReport,
) -> None:
    protected_path = _require_protected_path(path, label="REPORT")
    if protected_path.exists():
        raise CanaryExecutionError(
            "REPORT_ALREADY_EXISTS",
            stage="REPORT",
        )
    protected_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = protected_path.with_suffix(protected_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(protected_path)


def _print_report(report: ConsultationContextProviderCanaryReport) -> None:
    print(
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Protected Consultation Context Provider Canary",
    )
    parser.add_argument(
        "--mode",
        choices=("schema", "inspect", "execute"),
        required=True,
    )
    parser.add_argument("--input", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--expected-git-sha")
    parser.add_argument("--expected-input-sha256")
    parser.add_argument("--expected-evidence-sha256")
    parser.add_argument("--allow-provider-input", action="store_true")
    parser.add_argument("--send-handoff", action="store_true")
    parser.add_argument("--verify-replay", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _argument_parser().parse_args(argv)
    if args.mode == "schema":
        print(
            json.dumps(
                ConsultationContextProviderCanaryInput.model_json_schema(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    try:
        if args.input is None:
            raise CanaryExecutionError("INPUT_PATH_REQUIRED", stage="ARGUMENTS")
        canary_input = load_canary_input(args.input)
        identity = git_identity()
        input_sha256, evidence_sha256 = input_hashes(canary_input)

        if args.mode == "inspect":
            report = inspect_canary(canary_input, git_identity=identity)
        else:
            if args.report is None:
                raise CanaryExecutionError(
                    "REPORT_PATH_REQUIRED",
                    stage="ARGUMENTS",
                )
            if not args.allow_provider_input:
                raise CanaryExecutionError(
                    "PROVIDER_INPUT_NOT_EXPLICITLY_ALLOWED",
                    stage="ARGUMENTS",
                )
            expected_git_sha = (args.expected_git_sha or "").strip().lower()
            if not re.fullmatch(r"[a-f0-9]{40}", expected_git_sha):
                raise CanaryExecutionError(
                    "INVALID_EXPECTED_GIT_SHA",
                    stage="ARGUMENTS",
                )
            if expected_git_sha != identity["git_sha"]:
                raise CanaryExecutionError(
                    "GIT_SHA_MISMATCH",
                    stage="IDENTITY",
                )
            if identity["git_dirty"]:
                raise CanaryExecutionError(
                    "GIT_WORKTREE_DIRTY",
                    stage="IDENTITY",
                )
            expected_input_sha = _normalized_sha256(
                args.expected_input_sha256,
                field_name="EXPECTED_INPUT_SHA256",
            )
            expected_evidence_sha = _normalized_sha256(
                args.expected_evidence_sha256,
                field_name="EXPECTED_EVIDENCE_SHA256",
            )
            if expected_input_sha != input_sha256:
                raise CanaryExecutionError(
                    "INPUT_SHA256_MISMATCH",
                    stage="IDENTITY",
                )
            if expected_evidence_sha != evidence_sha256:
                raise CanaryExecutionError(
                    "EVIDENCE_SHA256_MISMATCH",
                    stage="IDENTITY",
                )
            if args.verify_replay and not args.send_handoff:
                raise CanaryExecutionError(
                    "REPLAY_REQUIRES_HANDOFF_DELIVERY",
                    stage="ARGUMENTS",
                )
            if args.send_handoff and not handoff_delivery_enabled():
                raise CanaryExecutionError(
                    "HANDOFF_DELIVERY_NOT_ENABLED",
                    stage="ARGUMENTS",
                )
            if args.send_handoff:
                _require_handoff_configuration_ready()
            try:
                provider_client = (
                    OpenAIResponsesConsultationContextClient.from_environment()
                )
            except Exception as exc:
                raise CanaryExecutionError(
                    "PROVIDER_CONFIGURATION_INVALID",
                    stage="PROVIDER_CONFIGURATION",
                ) from exc
            report = execute_canary(
                canary_input,
                provider_client=provider_client,
                git_identity=identity,
                provider_input_explicitly_allowed=(
                    args.allow_provider_input
                ),
                send_handoff=args.send_handoff,
                verify_replay=args.verify_replay,
            )

        if args.report is not None:
            _write_report(args.report, report)
        _print_report(report)
        return 0 if report.overall_status != "FAIL" else 1
    except CanaryExecutionError as exc:
        # Never print exception text or validation details because they may
        # contain protected fixture content. Only fixed error codes are public.
        print(
            json.dumps(
                {
                    "report_schema_version": REPORT_SCHEMA_VERSION,
                    "overall_status": "FAIL",
                    "failure_stage": exc.stage,
                    "failure_code": exc.code,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "report_schema_version": REPORT_SCHEMA_VERSION,
                    "overall_status": "FAIL",
                    "failure_stage": "CANARY_EXECUTION",
                    "failure_code": "UNEXPECTED_CANARY_ERROR",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
