"""문의 단위 Backend↔AI 실행·저장·State Event 경계."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from apps.audit.models import AIRetrievalHit, AIRetrievalRun, AIRun
from apps.consultations.repositories.consultation_repository import (
    ConsultationRepository,
)
from apps.evidence.models import AIChunkCrosswalk, EvidenceLink
from apps.inquiries.models import (
    Guidance,
    GuidanceItem,
    Inquiry,
    InquiryQA,
    SymptomAssessment,
)
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.inquiries.services.guidance_review_policy import (
    GuidanceReviewPolicy,
)
from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_is_valid,
)
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.guard_evaluator import GuardContext, GuardEvaluator
from apps.workflow.engine.state_machine import StateMachine
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from integrations.ai.client import AIClient
from integrations.ai.exceptions import (
    AIIdempotencyConflictError,
    AIIntegrationError,
    AIResponseValidationError,
    AIServiceResponseError,
    AITimeoutError,
)
from integrations.ai.request_mapper import build_request_from_inquiry
from integrations.ai.response_mapper import (
    AIAnalysisResult,
    map_success_response,
)
from integrations.ai.schema_validator import AIContractValidator


EvidenceVerifier = Callable[[list[dict[str, Any]], Inquiry], list[str]]
ai_trace_logger = logging.getLogger("watercare.ai")


@dataclass(frozen=True, slots=True)
class InquiryAIOutcome:
    """공개 원문을 포함하지 않는 AI 실행 결과."""

    ai_run_id: str
    status: str
    idempotent_replay: bool
    stale: bool
    event_candidate: str | None
    event_applied: str | None
    pending_reason: str | None
    saved_assessment: bool = False
    saved_guidance: bool = False
    saved_questions: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class InquiryAIService:
    """HTTP 호출은 Transaction 밖, 결과 적용은 잠금 Transaction 안에서 수행."""

    AI_PROCESSING_TIMEOUT_EVENT = "AI_PROCESSING_TIMEOUT"

    @classmethod
    def analyze_inquiry(
        cls,
        *,
        inquiry_public_id: UUID,
        correlation_id: UUID,
        ai_request_id: UUID | str,
        client: AIClient | None = None,
        validator: AIContractValidator | None = None,
        evidence_verifier: EvidenceVerifier | None = None,
    ) -> InquiryAIOutcome:
        if evidence_verifier is None:
            from apps.evidence.services import EvidenceReferenceVerifier

            evidence_verifier = EvidenceReferenceVerifier.verify
        contract_validator = validator or AIContractValidator()
        inquiry = (
            Inquiry.objects.select_related("subscription__product_model")
            .prefetch_related(
                Prefetch(
                    "qa_entries",
                    queryset=InquiryQA.objects.select_related(
                        "customer_answer"
                    ).order_by("sequence_no", "public_id"),
                    to_attr="ai_qa_entries",
                )
            )
            .get(public_id=inquiry_public_id)
        )
        request_payload = build_request_from_inquiry(
            inquiry,
            correlation_id=correlation_id,
            ai_request_id=ai_request_id,
            validator=contract_validator,
        )
        trace = {
            # These identifiers have passed the outbound contract validator;
            # arbitrary caller-provided strings never enter structured logs.
            "correlation_id": request_payload["correlation_id"],
            "inquiry_id": request_payload["inquiry_id"],
            "ai_request_id": request_payload["ai_request_id"],
        }
        ai_trace_logger.info(
            "ai_analysis_started",
            extra={**trace, "trace_stage": "ANALYSIS_STARTED"},
        )
        input_digest = cls._input_digest(request_payload)
        existing = AIRun.objects.filter(
            idempotency_key=str(ai_request_id)
        ).first()
        if existing is not None:
            replay_payload = request_payload
            if (
                existing.inquiry_id == inquiry.pk
                and isinstance(existing.input_payload, dict)
                and request_payload.get("state_version")
                != existing.input_payload.get("state_version")
            ):
                # A successful first call can advance Inquiry.state_version.
                # Compare all current request fields against the original
                # version so the same logical retry replays, while changed
                # symptom/answer content still conflicts.
                replay_payload = {
                    **request_payload,
                    "state_version": existing.input_payload.get(
                        "state_version"
                    ),
                }
                input_digest = cls._input_digest(replay_payload)
            outcome = cls._replay_or_conflict(
                existing,
                input_digest=input_digest,
                request_payload=replay_payload,
                validator=contract_validator,
            )
            cls._log_outcome(outcome, trace=trace)
            return outcome

        mode = client.mode if client is not None else settings.AI_SERVICE_MODE
        try:
            run = cls._create_run(
                inquiry=inquiry,
                request_payload=request_payload,
                input_digest=input_digest,
                validator=contract_validator,
                mode=mode,
            )
        except IntegrityError:
            winner = AIRun.objects.filter(
                idempotency_key=str(ai_request_id)
            ).first()
            if winner is None:
                raise
            outcome = cls._replay_or_conflict(
                winner,
                input_digest=input_digest,
                request_payload=request_payload,
                validator=contract_validator,
            )
            cls._log_outcome(outcome, trace=trace)
            return outcome
        if run.status_code == AIRun.Status.CANCELLED or not cls._mark_running(run):
            outcome = cls._cancelled_outcome(run)
            cls._log_outcome(outcome, trace=trace)
            return outcome
        started = time.perf_counter()
        try:
            ai_client = client or AIClient(
                base_url=settings.AI_SERVICE_BASE_URL,
                mode=settings.AI_SERVICE_MODE,
                timeout_seconds=settings.AI_SERVICE_TIMEOUT_SECONDS,
                validator=contract_validator,
            )
            result = ai_client.analyze(request_payload)
        except AIIntegrationError as exc:
            latency_ms = round((time.perf_counter() - started) * 1000)
            if not cls._mark_failed(run, exc=exc, latency_ms=latency_ms):
                outcome = cls._cancelled_outcome(run)
                cls._log_outcome(outcome, trace=trace, latency_ms=latency_ms)
                return outcome
            event_candidate = None
            event_applied = None
            pending_reason = exc.code
            stale = False
            if (
                run.status_code == AIRun.Status.TIMED_OUT
                and run.error_code == "AI-TIMEOUT-01"
            ):
                event_candidate = cls.AI_PROCESSING_TIMEOUT_EVENT
                event_applied, pending_reason = cls._apply_timeout_event(run)
                stale = pending_reason == "STALE_STATE_VERSION"
            outcome = InquiryAIOutcome(
                ai_run_id=str(run.public_id),
                status=run.status_code,
                idempotent_replay=False,
                stale=stale,
                event_candidate=event_candidate,
                event_applied=event_applied,
                pending_reason=pending_reason,
            )
            cls._log_outcome(
                outcome,
                trace=trace,
                latency_ms=latency_ms,
                failure_code=exc.code,
            )
            return outcome

        latency_ms = round((time.perf_counter() - started) * 1000)
        if not cls._mark_succeeded(run, result=result, latency_ms=latency_ms):
            outcome = cls._cancelled_outcome(run)
            cls._log_outcome(outcome, trace=trace, latency_ms=latency_ms)
            return outcome
        outcome = cls._persist_validated_result(
            run=run,
            result=result,
            evidence_verifier=evidence_verifier,
        )
        cls._log_outcome(outcome, trace=trace, latency_ms=latency_ms)
        return outcome

    @staticmethod
    def _log_outcome(
        outcome: InquiryAIOutcome,
        *,
        trace: dict[str, str],
        latency_ms: int | None = None,
        failure_code: str | None = None,
    ) -> None:
        extra: dict[str, Any] = {
            **trace,
            "trace_stage": "ANALYSIS_TERMINAL",
            "ai_run_id": outcome.ai_run_id,
            "ai_status": outcome.status,
            "event_candidate": outcome.event_candidate,
            "event_applied": outcome.event_applied,
            "pending_reason": outcome.pending_reason,
            "idempotent_replay": outcome.idempotent_replay,
            "stale": outcome.stale,
        }
        if latency_ms is not None:
            extra["latency_ms"] = max(latency_ms, 0)
        if failure_code is not None:
            extra["failure_code"] = failure_code
        log_method = (
            ai_trace_logger.warning
            if outcome.status in {AIRun.Status.FAILED, AIRun.Status.TIMED_OUT}
            else ai_trace_logger.info
        )
        log_method("ai_analysis_terminal", extra=extra)

    @classmethod
    def _create_run(
        cls,
        *,
        inquiry: Inquiry,
        request_payload: dict[str, Any],
        input_digest: str,
        validator: AIContractValidator,
        mode: str,
    ) -> AIRun:
        with transaction.atomic():
            locked_inquiry = Inquiry.objects.select_for_update().get(pk=inquiry.pk)
            run = AIRun.objects.create(
            inquiry=locked_inquiry,
            task_type_code=AIRun.TaskType.ANALYZE_SYMPTOM,
            request_schema_version=validator.contract_version("request"),
            response_schema_version=validator.contract_version("success"),
            model_provider=settings.AI_MODEL_PROVIDER,
            model_name=settings.AI_MODEL_NAME,
            model_config_version=validator.contract_version("success"),
            model_config={
                "mode": mode,
                "timeout_seconds": settings.AI_SERVICE_TIMEOUT_SECONDS,
                "backend_max_retries": 0,
            },
            prompt_version=settings.AI_PROMPT_VERSION,
            input_payload=request_payload,
            input_sha256=input_digest,
            idempotency_key=request_payload["ai_request_id"],
            correlation_id=UUID(request_payload["correlation_id"]),
            )
            if (
                locked_inquiry.status_code == Inquiry.Status.CANCELLED
                or locked_inquiry.state_version != request_payload["state_version"]
            ):
                completed_at = timezone.now()
                run.status_code = AIRun.Status.CANCELLED
                run.completed_at = completed_at
                run.error_code = "CANCELLED_OR_STALE_INQUIRY"
                run.save(
                    update_fields=[
                        "status_code",
                        "completed_at",
                        "error_code",
                        "updated_at",
                    ]
                )
            return run

    @staticmethod
    @transaction.atomic
    def _mark_running(run: AIRun) -> bool:
        locked = AIRun.objects.select_for_update().get(pk=run.pk)
        if locked.status_code != AIRun.Status.QUEUED:
            run.refresh_from_db()
            return False
        locked.status_code = AIRun.Status.RUNNING
        locked.started_at = timezone.now()
        locked.save(update_fields=["status_code", "started_at", "updated_at"])
        run.refresh_from_db()
        return True

    @classmethod
    @transaction.atomic
    def _apply_timeout_event(
        cls,
        run: AIRun,
    ) -> tuple[str | None, str | None]:
        """Apply the audited timeout fallback once without creating Consultation."""

        inquiry = (
            Inquiry.objects.select_for_update()
            .select_related("subscription__product_model")
            .get(pk=run.inquiry_id)
        )
        requested_state_version = run.input_payload.get("state_version")
        if (
            inquiry.status_code != Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
            or inquiry.state_version != requested_state_version
        ):
            return None, "STALE_STATE_VERSION"

        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        transition = StateMachine().resolve(
            snapshot=snapshot,
            event_code=cls.AI_PROCESSING_TIMEOUT_EVENT,
        )
        guard_result = GuardEvaluator().evaluate(
            transition=transition,
            snapshot=snapshot,
            context=GuardContext(
                actor_role="SYSTEM",
                is_authenticated=False,
                correlation_id=str(run.correlation_id),
                idempotency_key=None,
                requested_state_version=requested_state_version,
                trusted_internal_actor=True,
                domain_results={
                    "G-AI-PROCESSING-TIMEOUT-VALID": (
                        run.status_code == AIRun.Status.TIMED_OUT
                        and run.error_code == "AI-TIMEOUT-01"
                        and run.retry_count == 0
                        and run.inquiry_id == inquiry.pk
                    )
                },
            ),
        )
        if not guard_result.allowed:
            failure = guard_result.failure
            return None, failure.error_code if failure else "GUARD_REJECTED"

        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
        )
        inquiry.requires_fallback = True
        inquiry.usage_guidance_status = (
            Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
        )
        inquiry.full_clean()
        inquiry.save(
            update_fields=[
                "requires_fallback",
                "usage_guidance_status",
                "updated_at",
            ]
        )
        TransitionHistoryService.record_ai_result(
            inquiry=inquiry,
            transition=transition,
            correlation_id=run.correlation_id,
            ai_request_id=run.idempotency_key,
        )
        return cls.AI_PROCESSING_TIMEOUT_EVENT, None

    @staticmethod
    @transaction.atomic
    def _mark_succeeded(
        run: AIRun,
        *,
        result: AIAnalysisResult,
        latency_ms: int,
    ) -> bool:
        locked = AIRun.objects.select_for_update().get(pk=run.pk)
        if locked.status_code not in {
            AIRun.Status.RUNNING,
            AIRun.Status.RETRYING,
        }:
            run.refresh_from_db()
            return False
        locked.status_code = (
            AIRun.Status.NO_EVIDENCE
            if result.is_no_evidence
            else AIRun.Status.SUCCEEDED
        )
        locked.validated_output_payload = result.payload
        locked.schema_validation_status_code = (
            AIRun.SchemaValidationStatus.PASSED
        )
        locked.schema_validation_errors = []
        locked.completed_at = timezone.now()
        locked.latency_ms = max(latency_ms, 0)
        locked.retry_count = result.retry_count
        locked.full_clean()
        locked.save(
            update_fields=[
                "status_code",
                "validated_output_payload",
                "schema_validation_status_code",
                "schema_validation_errors",
                "completed_at",
                "latency_ms",
                "retry_count",
                "updated_at",
            ]
        )
        run.refresh_from_db()
        return True

    @staticmethod
    @transaction.atomic
    def _mark_failed(
        run: AIRun,
        *,
        exc: AIIntegrationError,
        latency_ms: int,
    ) -> bool:
        locked = AIRun.objects.select_for_update().get(pk=run.pk)
        if locked.status_code not in {
            AIRun.Status.RUNNING,
            AIRun.Status.RETRYING,
        }:
            run.refresh_from_db()
            return False
        timed_out = (
            isinstance(exc, AITimeoutError) or exc.code == "AI-TIMEOUT-01"
        )
        schema_failed = isinstance(exc, AIResponseValidationError)
        error_contract_passed = isinstance(exc, AIServiceResponseError)
        locked.status_code = (
            AIRun.Status.TIMED_OUT if timed_out else AIRun.Status.FAILED
        )
        locked.error_code = exc.code
        locked.error_message = str(exc)
        locked.retry_count = exc.retry_count
        locked.latency_ms = max(latency_ms, 0)
        locked.completed_at = timezone.now()
        if schema_failed:
            errors = exc.validation_errors or ["invalid AI response"]
            locked.schema_validation_status_code = (
                AIRun.SchemaValidationStatus.FAILED
            )
            locked.schema_validation_errors = errors
            locked.raw_output_text = json.dumps(
                exc.payload or {},
                ensure_ascii=False,
                sort_keys=True,
            )
        elif error_contract_passed:
            locked.schema_validation_status_code = (
                AIRun.SchemaValidationStatus.PASSED
            )
            locked.validated_output_payload = exc.payload
        locked.full_clean()
        locked.save(
            update_fields=[
                "status_code",
                "error_code",
                "error_message",
                "retry_count",
                "latency_ms",
                "completed_at",
                "schema_validation_status_code",
                "schema_validation_errors",
                "raw_output_text",
                "validated_output_payload",
                "updated_at",
            ]
        )
        run.refresh_from_db()
        return True

    @staticmethod
    def _cancelled_outcome(run: AIRun) -> InquiryAIOutcome:
        run.refresh_from_db()
        return InquiryAIOutcome(
            ai_run_id=str(run.public_id),
            status=run.status_code,
            idempotent_replay=False,
            stale=run.status_code == AIRun.Status.CANCELLED,
            event_candidate=None,
            event_applied=None,
            pending_reason=run.error_code or "RUN_NOT_ACTIVE",
        )

    @classmethod
    @transaction.atomic
    def _persist_validated_result(
        cls,
        *,
        run: AIRun,
        result: AIAnalysisResult,
        evidence_verifier: EvidenceVerifier | None,
    ) -> InquiryAIOutcome:
        inquiry = (
            Inquiry.objects.select_for_update()
            .select_related("subscription__product_model")
            .get(pk=run.inquiry_id)
        )
        if inquiry.state_version != result.payload["state_version"]:
            return InquiryAIOutcome(
                ai_run_id=str(run.public_id),
                status=run.status_code,
                idempotent_replay=False,
                stale=True,
                event_candidate=result.event_candidate,
                event_applied=None,
                pending_reason="STALE_STATE_VERSION",
            )

        assessment = cls._save_assessment(inquiry, run, result)
        guidance = cls._save_guidance(inquiry, run, result)
        saved_questions = cls._save_followup_questions(inquiry, run, result)
        try:
            verified_evidence_ids = (
                evidence_verifier(result.payload["evidence_references"], inquiry)
                if evidence_verifier is not None
                else []
            )
        except Exception as exc:  # Evidence failures remain fail-closed.
            ai_trace_logger.warning(
                "evidence_verification_failed",
                extra={
                    "trace_stage": "EVIDENCE_VERIFICATION_FAILED",
                    "ai_run_id": str(run.public_id),
                    "inquiry_id": str(inquiry.public_id),
                    "correlation_id": str(run.correlation_id),
                    "failure_type": type(exc).__name__,
                },
            )
            verified_evidence_ids = []
        if verified_evidence_ids:
            try:
                # Keep partial link writes out while preserving the already
                # validated AI result as a reviewable draft.
                with transaction.atomic():
                    cls._save_evidence_links(
                        inquiry=inquiry,
                        run=run,
                        guidance=guidance,
                        references=result.payload["evidence_references"],
                        verified_evidence_ids=verified_evidence_ids,
                    )
            except Exception as exc:
                ai_trace_logger.warning(
                    "evidence_link_persistence_failed",
                    extra={
                        "trace_stage": "EVIDENCE_LINK_PERSISTENCE_FAILED",
                        "ai_run_id": str(run.public_id),
                        "inquiry_id": str(inquiry.public_id),
                        "correlation_id": str(run.correlation_id),
                        "failure_type": type(exc).__name__,
                    },
                )
                verified_evidence_ids = []
        if (
            result.event_candidate == "SAFE_GUIDANCE_READY"
            and not verified_evidence_ids
        ):
            # A schema-valid draft is still not customer-visible when the
            # Backend cannot bind it to canonical official evidence.
            guidance.review_status_code = GuidanceReviewPolicy.REJECTED
            guidance.full_clean()
            guidance.save(update_fields=["review_status_code", "updated_at"])
        cls._update_inquiry_projection(
            inquiry,
            result=result,
            verified_evidence_ids=verified_evidence_ids,
        )
        event_applied, pending_reason = cls._apply_event_if_allowed(
            inquiry,
            result=result,
            verified_evidence_ids=verified_evidence_ids,
        )
        return InquiryAIOutcome(
            ai_run_id=str(run.public_id),
            status=run.status_code,
            idempotent_replay=False,
            stale=False,
            event_candidate=result.event_candidate,
            event_applied=event_applied,
            pending_reason=pending_reason,
            saved_assessment=assessment is not None,
            saved_guidance=guidance is not None,
            saved_questions=saved_questions,
        )

    @classmethod
    def _save_evidence_links(
        cls,
        *,
        inquiry: Inquiry,
        run: AIRun,
        guidance: Guidance,
        references: list[dict[str, Any]],
        verified_evidence_ids: list[str],
    ) -> None:
        """Snapshot only Backend-verified evidence behind one Guidance."""

        canonical_ids = [reference.get("chunk_id") for reference in references]
        if (
            len(canonical_ids) != len(verified_evidence_ids)
            or any(not isinstance(value, str) for value in canonical_ids)
        ):
            raise ValueError("Verified evidence identity bundle is inconsistent.")

        mappings = {
            mapping.canonical_chunk_id: mapping
            for mapping in AIChunkCrosswalk.objects.filter(
                canonical_chunk_id__in=canonical_ids,
                is_active=True,
                is_verified=True,
            )
            .select_related(
                "chunk__page__document",
                "model_scope__product_model",
                "verified_by",
            )
            .prefetch_related("source_pages__page")
        }
        if set(mappings) != set(canonical_ids):
            raise ValueError("Verified evidence mapping disappeared before persistence.")

        lineage_by_chunk = cls._save_retrieval_lineage(
            inquiry=inquiry,
            run=run,
            references=references,
            mappings=mappings,
        )

        for display_order, (reference, public_id) in enumerate(
            zip(references, verified_evidence_ids, strict=True),
            start=1,
        ):
            mapping = mappings[reference["chunk_id"]]
            chunk = mapping.chunk
            document = chunk.page.document
            source_pages = [item.page for item in mapping.source_pages.all()]
            page_numbers = [page.page_no for page in source_pages]
            evidence_summary = str(
                (chunk.metadata or {}).get("evidence_summary") or ""
            ).strip()
            if (
                str(chunk.public_id) != public_id
                or not page_numbers
                or not evidence_summary
                or mapping.verified_by_id is None
                or mapping.verified_at is None
            ):
                raise ValueError("Verified evidence snapshot is incomplete.")

            page_label = ", ".join(str(value) for value in page_numbers)
            retrieval_run, retrieval_hit = lineage_by_chunk.get(
                reference["chunk_id"],
                (None, None),
            )
            link = EvidenceLink(
                inquiry=inquiry,
                guidance=guidance,
                ai_run=run,
                chunk=chunk,
                retrieval_run=retrieval_run,
                retrieval_hit=retrieval_hit,
                selection_origin_code="AUTO_RETRIEVAL",
                evidence_role_code="SUPPORTING",
                display_order=display_order,
                citation_label=f"{document.title} p.{page_label}"[:200],
                document_code_snapshot=document.document_code,
                document_title_snapshot=document.title,
                source_org_snapshot=document.source_org,
                revision_label_snapshot=document.revision_label,
                official_source_url_snapshot=document.official_source_url,
                document_sha256_snapshot=document.sha256_hash,
                evidence_summary=evidence_summary,
                cited_text_snapshot=chunk.chunk_text,
                page_no_snapshot=page_numbers[0],
                section_snapshot=chunk.section_path,
                product_model_codes_snapshot=[
                    mapping.model_scope.product_model.model_code
                ],
                is_verified=True,
                verified_by=mapping.verified_by,
                verified_at=mapping.verified_at,
            )
            link.full_clean()
            link.save()

    @classmethod
    def _save_retrieval_lineage(
        cls,
        *,
        inquiry: Inquiry,
        run: AIRun,
        references: list[dict[str, Any]],
        mappings: dict[str, AIChunkCrosswalk],
    ) -> dict[str, tuple[AIRetrievalRun, AIRetrievalHit]]:
        """Persist only retrieval metadata present in the approved contract.

        The success contract exposes selected evidence order and cosine
        similarity only. Missing scores or inconsistent Crosswalk runtime
        identity therefore keep the legacy EvidenceLink without inventing
        candidates, ranks, or model configuration.
        """

        prepared = cls._prepare_retrieval_lineage(
            run=run,
            references=references,
            mappings=mappings,
        )
        if prepared is None:
            return {}

        try:
            with transaction.atomic():
                return cls._persist_retrieval_lineage(
                    inquiry=inquiry,
                    run=run,
                    prepared=prepared,
                )
        except Exception as exc:
            ai_trace_logger.warning(
                "retrieval_lineage_persistence_failed",
                extra={
                    "trace_stage": "RETRIEVAL_LINEAGE_PERSISTENCE_FAILED",
                    "ai_run_id": str(run.public_id),
                    "inquiry_id": str(inquiry.public_id),
                    "correlation_id": str(run.correlation_id),
                    "failure_type": type(exc).__name__,
                },
            )
            return {}

    @staticmethod
    def _prepare_retrieval_lineage(
        *,
        run: AIRun,
        references: list[dict[str, Any]],
        mappings: dict[str, AIChunkCrosswalk],
    ) -> dict[str, Any] | None:
        """Return a persistence bundle only when observed metadata is complete."""

        query_text = str(run.input_payload.get("raw_symptom") or "").strip()
        if not query_text or not references or len(references) > 100:
            return None

        canonical_ids = [reference.get("chunk_id") for reference in references]
        if len(set(canonical_ids)) != len(canonical_ids):
            return None

        scores: list[Decimal] = []
        try:
            for reference in references:
                raw_score = reference.get("similarity_score")
                if raw_score is None:
                    return None
                score = Decimal(str(raw_score)).quantize(Decimal("0.000001"))
                if not Decimal("-1") <= score <= Decimal("1"):
                    return None
                scores.append(score)
        except (InvalidOperation, TypeError, ValueError):
            return None

        runtime_identities = {
            (
                mapping.embedding_model,
                mapping.embedding_model_version,
                mapping.index_version,
                mapping.chunk_set_sha256,
                mapping.manifest_schema_version,
            )
            for mapping in mappings.values()
        }
        if len(runtime_identities) != 1:
            return None

        (
            embedding_model,
            embedding_model_version,
            index_version,
            chunk_set_sha256,
            manifest_schema_version,
        ) = runtime_identities.pop()
        return {
            "query_text": query_text,
            "scores": scores,
            "references": references,
            "mappings": mappings,
            "embedding_model": embedding_model,
            "embedding_model_version": embedding_model_version,
            "index_version": index_version,
            "chunk_set_sha256": chunk_set_sha256,
            "manifest_schema_version": manifest_schema_version,
        }

    @staticmethod
    def _persist_retrieval_lineage(
        *,
        inquiry: Inquiry,
        run: AIRun,
        prepared: dict[str, Any],
    ) -> dict[str, tuple[AIRetrievalRun, AIRetrievalHit]]:
        """Write one observed retrieval run and its selected evidence hits."""

        query_text = prepared["query_text"]
        completed_at = run.completed_at or timezone.now()
        started_at = run.started_at or completed_at
        retrieval_run = AIRetrievalRun(
            ai_run=run,
            inquiry=inquiry,
            query_text=query_text,
            query_sha256=hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
            filter_payload={
                "model_code": run.input_payload.get("model_code"),
            },
            retrieval_config_version=prepared["index_version"],
            retrieval_config={
                "index_version": prepared["index_version"],
                "chunk_set_sha256": prepared["chunk_set_sha256"],
                "manifest_schema_version": prepared[
                    "manifest_schema_version"
                ],
                "observed_selected_count": len(prepared["references"]),
            },
            embedding_model=prepared["embedding_model"],
            embedding_model_version=prepared["embedding_model_version"],
            distance_metric_code=AIRetrievalRun.DistanceMetric.COSINE,
            top_k=len(prepared["references"]),
            status_code=AIRetrievalRun.Status.SUCCEEDED,
            started_at=started_at,
            completed_at=completed_at,
            correlation_id=run.correlation_id,
        )
        retrieval_run.full_clean()
        retrieval_run.save()

        lineage: dict[str, tuple[AIRetrievalRun, AIRetrievalHit]] = {}
        for rank_no, (reference, score) in enumerate(
            zip(prepared["references"], prepared["scores"], strict=True),
            start=1,
        ):
            mapping = prepared["mappings"][reference["chunk_id"]]
            hit = AIRetrievalHit(
                retrieval_run=retrieval_run,
                chunk=mapping.chunk,
                rank_no=rank_no,
                vector_score=score,
                applicability_status_code=(
                    mapping.canonical_verification_status
                ),
                selected_for_answer=True,
                selected_at=completed_at,
            )
            hit.full_clean()
            hit.save()
            lineage[reference["chunk_id"]] = (retrieval_run, hit)
        return lineage

    @staticmethod
    def _save_assessment(
        inquiry: Inquiry,
        run: AIRun,
        result: AIAnalysisResult,
    ) -> SymptomAssessment:
        next_version = (
            inquiry.symptom_assessments.aggregate(
                value=Max("assessment_version")
            )["value"]
            or 0
        ) + 1
        safety = result.payload["safety_assessment"]
        guidance = result.payload["usage_guidance"]
        assessment = SymptomAssessment(
            inquiry=inquiry,
            assessment_version=next_version,
            ruleset_version=run.response_schema_version,
            risk_level_code=safety["risk_level"],
            priority_code=safety["priority"],
            usage_guidance_status=guidance["guidance_status"],
            requires_consultation=safety["requires_consultation"],
            reason=safety["safety_reason"],
            rule_result=safety,
            assessed_by_type_code="AI",
            ai_run=run,
        )
        assessment.full_clean()
        assessment.save()
        return assessment

    @staticmethod
    def _save_guidance(
        inquiry: Inquiry,
        run: AIRun,
        result: AIAnalysisResult,
    ) -> Guidance:
        next_version = (
            inquiry.guidance_versions.aggregate(value=Max("guidance_version"))[
                "value"
            ]
            or 0
        ) + 1
        guidance_payload = result.payload["usage_guidance"]
        safety = result.payload["safety_assessment"]
        evidence_sufficiency = (
            "CANDIDATE" if result.payload["evidence_references"] else "NONE"
        )
        guidance = Guidance(
            inquiry=inquiry,
            guidance_version=next_version,
            review_status_code=GuidanceReviewPolicy.initial_status(result),
            title="AI 사용 안내 초안",
            summary_text=guidance_payload["message"],
            safety_notice=safety["safety_reason"],
            evidence_sufficiency_code=evidence_sufficiency,
            requires_consultation=safety["requires_consultation"],
            generated_by_ai_run=run,
        )
        guidance.full_clean()
        guidance.save()
        for index, instruction in enumerate(
            guidance_payload["next_actions"],
            start=1,
        ):
            item = GuidanceItem(
                guidance=guidance,
                step_no=index,
                action_type_code="NEXT_ACTION",
                instruction_text=instruction,
                requires_confirmation=True,
            )
            item.full_clean()
            item.save()
        return guidance

    @staticmethod
    def _save_followup_questions(
        inquiry: Inquiry,
        run: AIRun,
        result: AIAnalysisResult,
    ) -> int:
        next_sequence = (
            inquiry.qa_entries.aggregate(value=Max("sequence_no"))["value"]
            or 0
        ) + 1
        created = 0
        for question in result.payload["followup_questions"]:
            if inquiry.qa_entries.filter(
                question_code=question["question_id"]
            ).exists():
                continue
            qa = InquiryQA(
                inquiry=inquiry,
                sequence_no=next_sequence,
                question_code=question["question_id"],
                question_text=question["question_text"],
                answer_type_code=(
                    "SINGLE_CHOICE" if question["options"] else "FREE_TEXT"
                ),
                answer_payload={
                    "question_options": question["options"],
                    "target_field": question["target_field"],
                },
                asked_by_type_code="AI",
                source_ai_run=run,
            )
            qa.full_clean()
            qa.save()
            next_sequence += 1
            created += 1
        return created

    @staticmethod
    def _update_inquiry_projection(
        inquiry: Inquiry,
        *,
        result: AIAnalysisResult,
        verified_evidence_ids: list[str],
    ) -> None:
        safety = result.payload["safety_assessment"]
        guidance = result.payload["usage_guidance"]
        inquiry.risk_level_code = safety["risk_level"]
        inquiry.usage_guidance_status = guidance["guidance_status"]
        references_were_rejected = bool(
            result.payload["evidence_references"]
        ) and not verified_evidence_ids
        inquiry.requires_fallback = (
            result.is_fallback or references_were_rejected
        )
        update_fields = [
            "risk_level_code",
            "usage_guidance_status",
            "requires_fallback",
            "updated_at",
        ]
        if result.is_no_evidence:
            inquiry.evidence_mode = Inquiry.EvidenceMode.NO_EVIDENCE
            inquiry.evidence_ids = []
            update_fields.extend(["evidence_mode", "evidence_ids"])
        elif verified_evidence_ids:
            inquiry.evidence_mode = Inquiry.EvidenceMode.EXACT_MODEL
            inquiry.evidence_ids = verified_evidence_ids
            update_fields.extend(["evidence_mode", "evidence_ids"])
        elif references_were_rejected:
            inquiry.evidence_mode = Inquiry.EvidenceMode.PARTIAL_EVIDENCE
            inquiry.evidence_ids = []
            inquiry.usage_guidance_status = (
                Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
            )
            update_fields.append("usage_guidance_status")
            update_fields.extend(["evidence_mode", "evidence_ids"])
        inquiry.save(update_fields=update_fields)

    @classmethod
    def _apply_event_if_allowed(
        cls,
        inquiry: Inquiry,
        *,
        result: AIAnalysisResult,
        verified_evidence_ids: list[str],
    ) -> tuple[str | None, str | None]:
        event = result.event_candidate
        if event is None:
            return None, "NO_STATE_EVENT_CANDIDATE"
        if event == "SAFE_GUIDANCE_READY" and not verified_evidence_ids:
            # Reuse the existing no-usable-evidence transition when the AI
            # cited evidence but Backend canonical verification rejected it.
            event = "NO_EVIDENCE"

        domain_results = {
            "G-PRODUCT-VALIDATION-FAILED": (
                result.is_product_validation_failed
            ),
            "G-NO-USABLE-EVIDENCE": (
                result.is_no_evidence
                or (
                    bool(result.payload["evidence_references"])
                    and not verified_evidence_ids
                )
            ),
            "G-AI-CONSULTATION-REQUIRED": (
                event == "AI_CONSULTATION_REQUIRED"
                and result.requires_consultation
                and result.risk_level != "danger"
            ),
            "G-SAFE-GUIDANCE-VALID": (
                event == "SAFE_GUIDANCE_READY"
                and not result.payload["safety_assessment"][
                    "requires_consultation"
                ]
            ),
            "G-OFFICIAL-EVIDENCE-AVAILABLE": bool(verified_evidence_ids),
            "G-NO-DANGER-CONFLICT": result.risk_level != "danger",
            "G-DANGER-ASSESSMENT-VALID": danger_assessment_is_valid(
                result.payload
            ),
        }
        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        transition = StateMachine().resolve(
            snapshot=snapshot,
            event_code=event,
        )
        guard_result = GuardEvaluator().evaluate(
            transition=transition,
            snapshot=snapshot,
            context=GuardContext(
                actor_role="SYSTEM",
                is_authenticated=False,
                correlation_id=result.payload["correlation_id"],
                idempotency_key=None,
                requested_state_version=result.payload["state_version"],
                trusted_internal_actor=True,
                domain_results=domain_results,
            ),
        )
        if not guard_result.allowed:
            failure = guard_result.failure
            return None, failure.error_code if failure else "GUARD_REJECTED"

        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
        )
        TransitionHistoryService.record_ai_result(
            inquiry=inquiry,
            transition=transition,
            correlation_id=UUID(result.payload["correlation_id"]),
            ai_request_id=result.payload["ai_request_id"],
        )
        if event == "DANGER_DETECTED":
            # Danger is the one approved path that does not wait for a
            # customer action. Keep the queue row in the same transaction as
            # the Inquiry transition so Web never observes a half-applied
            # emergency handoff.
            ConsultationRepository.request(
                inquiry=inquiry,
                state_version=inquiry.state_version,
                idempotency_key=(
                    f"ai-danger-{result.payload['ai_request_id']}"
                ),
                correlation_id=UUID(result.payload["correlation_id"]),
                current=ConsultationRepository.lock_latest(inquiry),
            )
        return event, None

    @classmethod
    def _replay_or_conflict(
        cls,
        run: AIRun,
        *,
        input_digest: str,
        request_payload: dict[str, Any],
        validator: AIContractValidator,
    ) -> InquiryAIOutcome:
        if run.input_sha256 != input_digest:
            raise AIIdempotencyConflictError(
                "같은 ai_request_id에 다른 Payload가 사용되었습니다."
            )
        event_candidate = None
        if run.validated_output_payload and run.status_code in {
            AIRun.Status.SUCCEEDED,
            AIRun.Status.NO_EVIDENCE,
        }:
            result = map_success_response(
                run.validated_output_payload,
                expected_request=request_payload,
                validator=validator,
            )
            event_candidate = result.event_candidate
        elif (
            run.status_code == AIRun.Status.TIMED_OUT
            and run.error_code == "AI-TIMEOUT-01"
        ):
            event_candidate = cls.AI_PROCESSING_TIMEOUT_EVENT
        current_inquiry = Inquiry.objects.only(
            "status_code",
            "state_version",
        ).get(pk=run.inquiry_id)
        stale = (
            current_inquiry.status_code == Inquiry.Status.CANCELLED
            or current_inquiry.state_version != request_payload["state_version"]
        )
        return InquiryAIOutcome(
            ai_run_id=str(run.public_id),
            status=run.status_code,
            idempotent_replay=True,
            stale=stale,
            event_candidate=event_candidate,
            event_applied=None,
            pending_reason=(
                "STALE_STATE_VERSION"
                if stale
                else (
                    "REPLAYED_EXISTING_RESULT"
                    if run.completed_at is not None
                    else "RUN_ALREADY_IN_PROGRESS"
                )
            ),
        )

    @staticmethod
    def _input_digest(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
