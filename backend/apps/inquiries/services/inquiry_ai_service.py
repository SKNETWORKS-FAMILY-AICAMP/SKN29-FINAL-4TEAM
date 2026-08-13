"""문의 단위 Backend↔AI 실행·저장·State Event 경계."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from apps.audit.models import AIRun
from apps.evidence.services.evidence_validation_service import (
    verify_canonical_evidence,
)
from apps.inquiries.models import (
    Guidance,
    GuidanceItem,
    Inquiry,
    InquiryQA,
    SymptomAssessment,
)
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
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
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SAFETY_RULES_PATH = REPOSITORY_ROOT / "ai" / "configs" / "safety_rules.yaml"


@lru_cache(maxsize=1)
def _configured_safety_rule_ids() -> frozenset[str]:
    """Load the AI runtime's configured safety rule IDs fail-closed."""

    try:
        document = yaml.safe_load(SAFETY_RULES_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        ai_trace_logger.exception("Failed to load configured AI safety rules")
        return frozenset()

    rules = document.get("rules") if isinstance(document, dict) else None
    if not isinstance(rules, dict) or not rules:
        return frozenset()

    rule_ids: set[str] = set()
    for rule in rules.values():
        rule_id = rule.get("rule_id") if isinstance(rule, dict) else None
        if not isinstance(rule_id, str) or not rule_id.strip():
            return frozenset()
        rule_ids.add(rule_id)
    return frozenset(rule_ids)


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
            outcome = cls._replay_or_conflict(
                existing,
                input_digest=input_digest,
                request_payload=request_payload,
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
            outcome = InquiryAIOutcome(
                ai_run_id=str(run.public_id),
                status=run.status_code,
                idempotent_replay=False,
                stale=False,
                event_candidate=None,
                event_applied=None,
                pending_reason=exc.code,
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
        verifier = evidence_verifier or verify_canonical_evidence
        verified_evidence_ids = verifier(
            result.payload["evidence_references"],
            inquiry,
        )
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
            review_status_code="PENDING",
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
        inquiry.requires_fallback = result.is_no_evidence
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
        safety = result.payload["safety_assessment"]
        guidance = result.payload["usage_guidance"]
        matched_safety_rule_ids = safety["matched_safety_rule_ids"]
        if event == "DANGER_DETECTED" and not matched_safety_rule_ids:
            return None, "MATCHED_SAFETY_RULE_IDS_REQUIRED"
        if event == "SAFE_GUIDANCE_READY" and not verified_evidence_ids:
            return None, "CANONICAL_EVIDENCE_VERIFICATION_REQUIRED"

        domain_results = {
            "G-DANGER-ASSESSMENT-VALID": (
                event == "DANGER_DETECTED"
                and result.risk_level == "danger"
                and safety["requires_consultation"] is True
                and guidance["guidance_status"]
                in {"PARTIAL_STOP", "TOTAL_STOP", "PENDING_CONSULTATION"}
                and set(matched_safety_rule_ids).issubset(
                    _configured_safety_rule_ids()
                )
            ),
            "G-NO-USABLE-EVIDENCE": result.is_no_evidence,
            "G-SAFE-GUIDANCE-VALID": (
                event == "SAFE_GUIDANCE_READY"
                and not safety["requires_consultation"]
            ),
            "G-OFFICIAL-EVIDENCE-AVAILABLE": bool(verified_evidence_ids),
            "G-NO-DANGER-CONFLICT": result.risk_level != "danger",
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
