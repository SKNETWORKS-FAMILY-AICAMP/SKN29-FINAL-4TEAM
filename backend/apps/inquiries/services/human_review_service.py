"""Atomic HumanReview ledger creation, read projection, and decision runtime."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit.models import AIRun
from apps.consultations.repositories.consultation_handoff_repository import (
    ConsultationHandoffRepository,
)
from apps.consultations.repositories.consultation_repository import (
    ConsultationRepository,
)
from apps.evidence.models import EvidenceLink
from apps.inquiries.models import Guidance, GuidanceItem, HumanReview, Inquiry
from apps.inquiries.repositories.human_review_repository import (
    HumanReviewRepository,
)
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.guard_evaluator import GuardContext, GuardEvaluator
from apps.workflow.engine.state_machine import (
    InvalidStateTransition,
    StateMachine,
)
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import (
    HUMAN_REVIEW_CONSULTATION_LOCKED,
    INTERNAL_ERROR,
    STATE_CONFLICT,
    VALIDATION_ERROR,
)


OPERATION_ID = "decideHumanReview"
PENDING_REASON_CODE = "CAUTION_PRE_SEND_REVIEW"
APPROVED_EVENT = "HUMAN_REVIEW_GUIDANCE_APPROVED"
CONSULTATION_EVENT = "HUMAN_REVIEW_CONSULTATION_REQUIRED"
REJECTED_EVENT = "HUMAN_REVIEW_REJECTED"

CONSULTATION_ESCALATION_REASONS = frozenset(
    {
        HumanReview.ConsultationChangeReason.CONSULTANT_SAFETY_ESCALATION,
        HumanReview.ConsultationChangeReason.PRODUCT_FUNCTION_UNCERTAIN,
        HumanReview.ConsultationChangeReason.CUSTOMER_CONTEXT_INCOMPLETE,
    }
)
CONSULTATION_RESOLUTION_REASONS = frozenset(
    {
        HumanReview.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED,
        HumanReview.ConsultationChangeReason.HARNESS_SCOPE_VERIFIED,
    }
)
REJECTED_CONSULTATION_REASON = (
    HumanReview.ConsultationChangeReason.HUMAN_REVIEW_REJECTED
)
LEDGER_CAUSE_PRIORITY = {
    "DANGER_ASSESSMENT": 0,
    "EXPLICIT_SAFETY_RULE": 1,
    "FAIL_CLOSED_AI_RESULT": 2,
    "UNCLASSIFIED_AI_SIGNAL": 3,
    "HARNESS_UNSUPPORTED_FUNCTION": 4,
    "HARNESS_SCOPE_EXCEEDED": 5,
}
LEDGER_ORIGIN_BY_CAUSE = {
    "DANGER_ASSESSMENT": HumanReview.ConsultationOrigin.SAFETY_LOCKED,
    "EXPLICIT_SAFETY_RULE": HumanReview.ConsultationOrigin.SAFETY_LOCKED,
    "FAIL_CLOSED_AI_RESULT": HumanReview.ConsultationOrigin.FAIL_CLOSED_LOCKED,
    "UNCLASSIFIED_AI_SIGNAL": HumanReview.ConsultationOrigin.UNKNOWN_LOCKED,
    "HARNESS_UNSUPPORTED_FUNCTION": (
        HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
    ),
    "HARNESS_SCOPE_EXCEEDED": (
        HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
    ),
}
LEDGER_LOCK_BY_CAUSE = {
    "DANGER_ASSESSMENT": "SAFETY_LOCKED",
    "EXPLICIT_SAFETY_RULE": "SAFETY_LOCKED",
    "FAIL_CLOSED_AI_RESULT": "FAIL_CLOSED_LOCKED",
    "UNCLASSIFIED_AI_SIGNAL": "UNKNOWN_LOCKED",
    "HARNESS_UNSUPPORTED_FUNCTION": "NON_SAFETY_RESOLVABLE",
    "HARNESS_SCOPE_EXCEEDED": "NON_SAFETY_RESOLVABLE",
}


@dataclass(frozen=True)
class HumanReviewOutcome:
    status_code: int
    data: dict[str, Any]


class HumanReviewService:
    """Own the Backend business ledger; AI owns checkpoint mechanics."""

    @classmethod
    def create_pending(
        cls,
        *,
        guidance: Guidance,
        ai_request_id: str,
        source_inquiry_state_version: int,
    ) -> HumanReview:
        """Create exactly one review for a new fail-closed pending Guidance."""

        thread_id = cls._checkpoint_thread_id(
            inquiry_public_id=guidance.inquiry.public_id,
            ai_request_id=ai_request_id,
            state_version=source_inquiry_state_version,
        )
        origin_code, origin_reason_code = cls._consultation_origin(
            guidance=guidance,
        )
        original_requires_consultation = guidance.requires_consultation
        review = HumanReview(
            inquiry=guidance.inquiry,
            guidance=guidance,
            checkpoint_thread_id=thread_id,
            source_ai_request_id=ai_request_id,
            source_inquiry_state_version=source_inquiry_state_version,
            initial_reason_code=PENDING_REASON_CODE,
            original_requires_consultation=(
                original_requires_consultation
            ),
            effective_requires_consultation=(
                original_requires_consultation
            ),
            consultation_origin_code=origin_code,
            consultation_origin_reason_code=origin_reason_code,
        )
        review.full_clean()
        review.save()
        return review

    @classmethod
    def _consultation_origin(
        cls,
        *,
        guidance: Guidance,
    ) -> tuple[str, str]:
        """Classify consultation authority once and fail closed on ambiguity."""

        if not guidance.requires_consultation:
            return (
                HumanReview.ConsultationOrigin.NOT_REQUIRED,
                HumanReview.ConsultationOriginReason.NOT_REQUIRED,
            )

        run = guidance.generated_by_ai_run
        ledger = (
            getattr(run, "consultation_cause_ledger", None)
            if run is not None
            else None
        )
        if ledger is not None:
            return cls._consultation_origin_from_ledger(ledger.causes)

        payload = (
            run.validated_output_payload
            if run is not None
            and isinstance(run.validated_output_payload, dict)
            else None
        )
        safety = payload.get("safety_assessment") if payload else None
        matched_rules = (
            safety.get("matched_safety_rule_ids")
            if isinstance(safety, dict)
            else None
        )
        if isinstance(safety, dict) and safety.get("risk_level") == "danger":
            return (
                HumanReview.ConsultationOrigin.SAFETY_LOCKED,
                HumanReview.ConsultationOriginReason.DANGER_ASSESSMENT,
            )
        if isinstance(matched_rules, list) and any(
            isinstance(rule_id, str) and rule_id.strip()
            for rule_id in matched_rules
        ):
            return (
                HumanReview.ConsultationOrigin.SAFETY_LOCKED,
                HumanReview.ConsultationOriginReason.EXPLICIT_SAFETY_RULE,
            )

        evidence_links = guidance.evidence_links.all()
        evidence_is_verified = evidence_links.exists() and not evidence_links.filter(
            is_verified=False
        ).exists()
        run_is_usable = bool(
            run is not None
            and run.status_code == AIRun.Status.SUCCEEDED
            and run.schema_validation_status_code
            == AIRun.SchemaValidationStatus.PASSED
            and isinstance(safety, dict)
            and guidance.evidence_sufficiency_code == "VERIFIED"
            and evidence_is_verified
        )
        if not run_is_usable:
            return (
                HumanReview.ConsultationOrigin.FAIL_CLOSED_LOCKED,
                HumanReview.ConsultationOriginReason.FAIL_CLOSED_AI_RESULT,
            )

        # Legacy 4.0.0 responses have no durable cause Ledger. Do not turn an
        # internal caller string or LLM-authored explanation into authority to
        # downgrade consultation.
        return (
            HumanReview.ConsultationOrigin.UNKNOWN_LOCKED,
            HumanReview.ConsultationOriginReason.UNCLASSIFIED_AI_SIGNAL,
        )

    @staticmethod
    def _consultation_origin_from_ledger(
        causes: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Select the strictest durable consultation authority."""

        cause_codes = [
            cause.get("cause_code")
            for cause in causes
            if isinstance(cause, dict)
        ]
        supported_codes = [
            code for code in cause_codes if code in LEDGER_CAUSE_PRIORITY
        ]
        if (
            not supported_codes
            or len(cause_codes) != len(causes)
            or len(supported_codes) != len(cause_codes)
        ):
            return (
                HumanReview.ConsultationOrigin.UNKNOWN_LOCKED,
                HumanReview.ConsultationOriginReason.UNCLASSIFIED_AI_SIGNAL,
            )
        if any(
            cause.get("lock_class")
            != LEDGER_LOCK_BY_CAUSE.get(cause.get("cause_code"))
            for cause in causes
        ):
            return (
                HumanReview.ConsultationOrigin.UNKNOWN_LOCKED,
                HumanReview.ConsultationOriginReason.UNCLASSIFIED_AI_SIGNAL,
            )
        selected = min(
            supported_codes,
            key=LEDGER_CAUSE_PRIORITY.__getitem__,
        )
        return LEDGER_ORIGIN_BY_CAUSE[selected], selected

    @staticmethod
    def _checkpoint_thread_id(
        *,
        inquiry_public_id: UUID,
        ai_request_id: str,
        state_version: int,
    ) -> str:
        raw = (
            f"{inquiry_public_id}:{ai_request_id}:{state_version}"
        ).encode("utf-8")
        return f"hitl-{hashlib.sha256(raw).hexdigest()[:32]}"

    @classmethod
    def list_pending(cls, *, actor: Any) -> dict[str, list[dict[str, Any]]]:
        return {
            "items": [
                cls._projection(review)
                for review in HumanReviewRepository.list_pending(actor)
            ]
        }

    @classmethod
    def retrieve(
        cls,
        *,
        actor: Any,
        review_public_id: UUID,
    ) -> dict[str, Any]:
        review = HumanReviewRepository.retrieve_visible(
            actor=actor,
            review_public_id=review_public_id,
        )
        if review is None:
            raise NotFound()
        return cls._projection(review)

    @classmethod
    @transaction.atomic
    def decide(
        cls,
        *,
        actor: Any,
        review_public_id: UUID,
        validated_data: dict[str, Any],
        idempotency_key: str,
        correlation_id: UUID,
    ) -> HumanReviewOutcome:
        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": {
                    "review_id": review_public_id,
                },
                "normalized_request_body": validated_data,
                "target_public_id": review_public_id,
            }
        )
        review = HumanReviewRepository.lock_visible(
            actor=actor,
            review_public_id=review_public_id,
        )
        if review is None:
            raise NotFound()
        inquiry = InquiryRepository.lock_for_human_review(
            inquiry_id=review.inquiry_id
        )
        if inquiry is None:
            raise NotFound()
        review.inquiry = inquiry

        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return HumanReviewOutcome(status_code, data)

        if (
            review.status_code != HumanReview.Status.PENDING
            or review.review_state_version
            != validated_data["review_state_version"]
            or inquiry.status_code
            != Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
            or inquiry.state_version != review.source_inquiry_state_version
        ):
            cls._raise_state_conflict(review)

        decision = validated_data["decision"]
        verified_evidence = cls._verified_evidence(review)
        consultation_audit = cls._consultation_audit(
            review=review,
            decision=decision,
            requested_disposition=validated_data[
                "consultation_disposition"
            ],
            requested_reason=validated_data.get(
                "consultation_reason_code"
            ),
            requested_evidence_ids=validated_data.get(
                "consultation_evidence_ids",
                [],
            ),
            verified_evidence=verified_evidence,
        )
        event_code = cls._event_code(
            decision=decision,
            effective_requires_consultation=consultation_audit[
                "effective_requires_consultation"
            ],
        )
        evidence_ready = cls._evidence_ready(
            review=review,
            verified_evidence=verified_evidence,
        )
        transition = cls._review_transition(
            inquiry=inquiry,
            event_code=event_code,
            decision=decision,
            evidence_ready=evidence_ready,
            effective_requires_consultation=consultation_audit[
                "effective_requires_consultation"
            ],
            correlation_id=correlation_id,
        )

        try:
            with transaction.atomic():
                idempotency_record = (
                    WorkflowRepository.create_idempotency_record(
                        actor=actor,
                        operation_id=OPERATION_ID,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                )
        except IntegrityError:
            winner = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=OPERATION_ID,
                idempotency_key=idempotency_key,
            )
            if winner is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                winner,
                request_hash=request_hash,
            )
            return HumanReviewOutcome(status_code, data)

        published_guidance = cls._apply_guidance_decision(
            review=review,
            actor=actor,
            decision=decision,
            modified=validated_data.get("modified_guidance"),
            effective_requires_consultation=consultation_audit[
                "effective_requires_consultation"
            ],
            verified_evidence=verified_evidence,
        )
        review.status_code = {
            HumanReview.Decision.APPROVE: HumanReview.Status.APPROVED,
            HumanReview.Decision.MODIFY: HumanReview.Status.MODIFIED,
            HumanReview.Decision.REJECT: HumanReview.Status.REJECTED,
        }[decision]
        review.decision_code = decision
        review.review_state_version += 1
        review.decision_reason_code = validated_data.get(
            "reason_code",
            "APPROVED_AS_IS",
        )
        review.reviewer = actor
        review.decided_at = timezone.now()
        review.decision_idempotency_key = idempotency_key
        review.decision_correlation_id = correlation_id
        review.modified_guidance_payload = (
            validated_data.get("modified_guidance") or {}
        )
        review.published_guidance = published_guidance
        review.effective_requires_consultation = consultation_audit[
            "effective_requires_consultation"
        ]
        review.consultation_disposition_code = consultation_audit[
            "consultation_disposition_code"
        ]
        review.consultation_reason_code = consultation_audit[
            "consultation_reason_code"
        ]
        review.consultation_evidence_snapshot = consultation_audit[
            "consultation_evidence_snapshot"
        ]
        review.full_clean()
        review.save()

        if event_code in {CONSULTATION_EVENT, REJECTED_EVENT}:
            consultation = ConsultationRepository.request(
                inquiry=inquiry,
                state_version=transition.state_version_after,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                current=ConsultationRepository.lock_latest(inquiry),
            )
            ConsultationHandoffRepository.attach_to_latest_consultation(
                inquiry=inquiry,
                consultation=consultation,
            )
        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
        )
        if transition.record_business_event:
            TransitionHistoryService.record_human_review_result(
                inquiry=inquiry,
                transition=transition,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                review_public_id=review.public_id,
                reason_code=review.decision_reason_code,
            )

        data = cls._projection(review)
        data["idempotent_replay"] = False
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=200,
            response_body=data,
            resource_public_id=review.public_id,
        )
        if decision == HumanReview.Decision.REJECT:
            cls._schedule_rejected_review_resume(review.public_id)
        return HumanReviewOutcome(200, data)

    @classmethod
    def _schedule_rejected_review_resume(
        cls,
        review_public_id: UUID,
    ) -> None:
        """Persist an Outbox row, then dispatch only after REJECT commit."""

        if not settings.AI_HUMAN_REVIEW_RESUME_ENABLED:
            return
        from apps.inquiries.services.human_review_resume_dispatch_service import (
            HumanReviewResumeDispatchService,
        )

        review = HumanReview.objects.get(public_id=review_public_id)
        if not HumanReviewResumeDispatchService.is_review_model_approved(
            review
        ):
            return
        dispatch = HumanReviewResumeDispatchService.enqueue(review)
        transaction.on_commit(
            lambda: HumanReviewResumeDispatchService.process_dispatch(
                dispatch.public_id
            ),
            robust=True,
        )

    @staticmethod
    def _event_code(
        *,
        decision: str,
        effective_requires_consultation: bool,
    ) -> str:
        if decision == HumanReview.Decision.REJECT:
            return REJECTED_EVENT
        if effective_requires_consultation:
            return CONSULTATION_EVENT
        return APPROVED_EVENT

    @classmethod
    def _review_transition(
        cls,
        *,
        inquiry: Inquiry,
        event_code: str,
        decision: str,
        evidence_ready: bool,
        effective_requires_consultation: bool,
        correlation_id: UUID,
    ):
        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        try:
            transition = StateMachine().resolve(
                snapshot=snapshot,
                event_code=event_code,
            )
        except InvalidStateTransition as exc:
            if exc.reason in {
                "TERMINAL_STATE",
                "UNLISTED_TRANSITION",
                "VISIT_STATE_MISMATCH",
            }:
                raise BusinessError(
                    STATE_CONFLICT,
                    "문의 상태가 변경되어 검토 결정을 반영할 수 없습니다.",
                    details={
                        "current_status": inquiry.status_code,
                        "current_state_version": inquiry.state_version,
                    },
                    status_code=409,
                ) from exc
            raise BusinessError(
                INTERNAL_ERROR,
                "검토 상태 전환 계약을 확인할 수 없습니다.",
                details={},
                status_code=500,
            ) from exc

        domain_results = {
            "G-HUMAN-REVIEW-GUIDANCE-APPROVED": (
                decision
                in {
                    HumanReview.Decision.APPROVE,
                    HumanReview.Decision.MODIFY,
                }
                and not effective_requires_consultation
                and evidence_ready
            ),
            "G-HUMAN-REVIEW-CONSULTATION-REQUIRED": (
                decision
                in {
                    HumanReview.Decision.APPROVE,
                    HumanReview.Decision.MODIFY,
                }
                and effective_requires_consultation
                and evidence_ready
            ),
            "G-HUMAN-REVIEW-REJECTED": (
                decision == HumanReview.Decision.REJECT
            ),
        }
        guard_result = GuardEvaluator().evaluate(
            transition=transition,
            snapshot=snapshot,
            context=GuardContext(
                actor_role="SYSTEM",
                is_authenticated=False,
                correlation_id=str(correlation_id),
                idempotency_key=None,
                requested_state_version=inquiry.state_version,
                trusted_internal_actor=True,
                domain_results=domain_results,
            ),
        )
        if not guard_result.allowed:
            failure = guard_result.failure
            if failure is not None and failure.guard_id == "G-STATE-VERSION":
                raise BusinessError(
                    STATE_CONFLICT,
                    "문의 상태가 변경되어 검토 결정을 반영할 수 없습니다.",
                    details={
                        "current_status": inquiry.status_code,
                        "current_state_version": inquiry.state_version,
                    },
                    status_code=409,
                )
            raise BusinessError(
                failure.error_code if failure else INTERNAL_ERROR,
                (
                    failure.message
                    if failure
                    else "검토 상태 전환 조건을 확인할 수 없습니다."
                ),
                details={},
                status_code=failure.http_status if failure else 500,
            )
        return transition

    @staticmethod
    def _verified_evidence(review: HumanReview) -> list[EvidenceLink]:
        links = list(
            EvidenceLink.objects.select_for_update()
            .select_related("chunk")
            .filter(guidance=review.guidance)
            .order_by("display_order", "public_id")
        )
        if not links or any(not link.is_verified for link in links):
            return []
        return links

    @staticmethod
    def _evidence_ready(
        *,
        review: HumanReview,
        verified_evidence: list[EvidenceLink],
    ) -> bool:
        run = review.guidance.generated_by_ai_run
        return bool(
            verified_evidence
            and review.guidance.evidence_sufficiency_code == "VERIFIED"
            and run is not None
            and run.status_code == AIRun.Status.SUCCEEDED
            and run.schema_validation_status_code
            == AIRun.SchemaValidationStatus.PASSED
        )

    @classmethod
    def _consultation_audit(
        cls,
        *,
        review: HumanReview,
        decision: str,
        requested_disposition: str,
        requested_reason: str | None,
        requested_evidence_ids: list[UUID],
        verified_evidence: list[EvidenceLink],
    ) -> dict[str, Any]:
        if decision == HumanReview.Decision.REJECT:
            if (
                requested_disposition
                != HumanReview.ConsultationDisposition.PRESERVE
                or requested_reason is not None
                or requested_evidence_ids
            ):
                cls._raise_consultation_validation(
                    "REJECT 결정의 상담 전환은 Backend 정책으로 확정됩니다."
                )
            return {
                "effective_requires_consultation": True,
                "consultation_disposition_code": (
                    HumanReview.ConsultationDisposition.REQUIRE
                ),
                "consultation_reason_code": REJECTED_CONSULTATION_REASON,
                "consultation_evidence_snapshot": [],
            }

        if (
            requested_disposition
            == HumanReview.ConsultationDisposition.PRESERVE
        ):
            if requested_reason is not None or requested_evidence_ids:
                cls._raise_consultation_validation(
                    "PRESERVE 결정에는 상담 변경 사유나 Evidence가 없습니다."
                )
            return {
                "effective_requires_consultation": (
                    review.original_requires_consultation
                ),
                "consultation_disposition_code": (
                    HumanReview.ConsultationDisposition.PRESERVE
                ),
                "consultation_reason_code": None,
                "consultation_evidence_snapshot": [],
            }

        if (
            requested_disposition
            == HumanReview.ConsultationDisposition.REQUIRE
        ):
            if review.original_requires_consultation:
                cls._raise_consultation_validation(
                    "이미 상담이 필요한 건은 PRESERVE로 결정해 주세요."
                )
            if requested_reason not in CONSULTATION_ESCALATION_REASONS:
                cls._raise_consultation_validation(
                    "상담 필요 상향에 허용된 사유 코드가 필요합니다."
                )
            if requested_evidence_ids:
                cls._raise_consultation_validation(
                    "상담 필요 상향에는 해소 Evidence를 제출하지 않습니다."
                )
            return {
                "effective_requires_consultation": True,
                "consultation_disposition_code": (
                    HumanReview.ConsultationDisposition.REQUIRE
                ),
                "consultation_reason_code": requested_reason,
                "consultation_evidence_snapshot": [],
            }

        if (
            requested_disposition
            != HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
        ):
            cls._raise_consultation_validation(
                "지원하지 않는 상담 처리 결정입니다."
            )
        if (
            review.consultation_origin_code
            != HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
        ):
            raise BusinessError(
                HUMAN_REVIEW_CONSULTATION_LOCKED,
                "Safety 또는 미분류 사유의 상담 필요 상태는 해소할 수 없습니다.",
                details={
                    "consultation_origin": review.consultation_origin_code,
                },
                status_code=422,
            )
        if not review.original_requires_consultation:
            cls._raise_consultation_validation(
                "원본 상담 여부가 true인 경우에만 해소할 수 있습니다."
            )
        if requested_reason not in CONSULTATION_RESOLUTION_REASONS:
            cls._raise_consultation_validation(
                "비-Safety 상담 해소에 허용된 사유 코드가 필요합니다."
            )
        run = review.guidance.generated_by_ai_run
        run_payload = run.validated_output_payload if run is not None else None
        usage = (
            run_payload.get("usage_guidance")
            if isinstance(run_payload, dict)
            else None
        )
        if not isinstance(usage, dict) or usage.get(
            "guidance_status"
        ) not in {
            Inquiry.UsageGuidanceStatus.PARTIAL_STOP,
            Inquiry.UsageGuidanceStatus.TOTAL_STOP,
        }:
            raise BusinessError(
                HUMAN_REVIEW_CONSULTATION_LOCKED,
                "검증된 제한 사용 상태가 없어 상담 필요를 해소할 수 없습니다.",
                details={
                    "consultation_origin": review.consultation_origin_code,
                },
                status_code=422,
            )
        if not requested_evidence_ids:
            cls._raise_consultation_validation(
                "상담 해소에는 검증 Evidence가 최소 1개 필요합니다."
            )

        evidence_by_id = {
            str(link.public_id): link for link in verified_evidence
        }
        selected = [
            evidence_by_id.get(str(evidence_id))
            for evidence_id in requested_evidence_ids
        ]
        if any(link is None for link in selected):
            cls._raise_consultation_validation(
                "선택한 Evidence가 검토 Guidance의 검증 근거가 아닙니다."
            )
        return {
            "effective_requires_consultation": False,
            "consultation_disposition_code": (
                HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
            ),
            "consultation_reason_code": requested_reason,
            "consultation_evidence_snapshot": [
                {
                    "evidence_link_id": str(link.public_id),
                    "chunk_id": str(link.chunk.public_id),
                    "document_sha256": link.document_sha256_snapshot,
                }
                for link in selected
                if link is not None
            ],
        }

    @staticmethod
    def _raise_consultation_validation(message: str) -> None:
        raise BusinessError(
            VALIDATION_ERROR,
            message,
            details={},
            status_code=422,
        )

    @staticmethod
    def _apply_guidance_decision(
        *,
        review: HumanReview,
        actor: Any,
        decision: str,
        modified: dict[str, Any] | None,
        effective_requires_consultation: bool,
        verified_evidence: list[EvidenceLink],
    ) -> Guidance | None:
        now = timezone.now()
        original = review.guidance
        if (
            decision == HumanReview.Decision.APPROVE
            and original.requires_consultation
            is effective_requires_consultation
        ):
            original.review_status_code = "APPROVED"
            original.reviewed_by = actor
            original.reviewed_at = now
            original.full_clean()
            original.save()
            return original

        original.review_status_code = "REJECTED"
        original.reviewed_by = actor
        original.reviewed_at = now
        original.full_clean()
        original.save()
        if decision == HumanReview.Decision.REJECT:
            return None

        if decision == HumanReview.Decision.MODIFY:
            title = modified["title"]
            summary_text = modified["summary_text"]
            safety_notice = modified.get("safety_notice")
            item_payloads = modified["items"]
        else:
            title = original.title
            summary_text = original.summary_text
            safety_notice = original.safety_notice
            item_payloads = [
                {
                    "action_type_code": item.action_type_code,
                    "instruction_text": item.instruction_text,
                    "caution_text": item.caution_text,
                    "requires_confirmation": item.requires_confirmation,
                }
                for item in original.items.order_by("step_no", "public_id")
            ]

        latest_version = (
            Guidance.objects.select_for_update()
            .filter(inquiry=review.inquiry)
            .aggregate(value=Max("guidance_version"))["value"]
            or 0
        )
        published = Guidance(
            inquiry=review.inquiry,
            guidance_version=latest_version + 1,
            review_status_code="APPROVED",
            title=title,
            summary_text=summary_text,
            safety_notice=safety_notice,
            evidence_sufficiency_code=original.evidence_sufficiency_code,
            requires_consultation=effective_requires_consultation,
            generated_by_ai_run=original.generated_by_ai_run,
            reviewed_by=actor,
            reviewed_at=now,
        )
        published.full_clean()
        published.save()
        for step_no, item_payload in enumerate(item_payloads, start=1):
            item = GuidanceItem(
                guidance=published,
                step_no=step_no,
                action_type_code=item_payload.get(
                    "action_type_code",
                    "NEXT_ACTION",
                ),
                instruction_text=item_payload["instruction_text"],
                caution_text=item_payload.get("caution_text"),
                requires_confirmation=item_payload.get(
                    "requires_confirmation",
                    True,
                ),
            )
            item.full_clean()
            item.save()
        HumanReviewService._clone_evidence_links(
            sources=verified_evidence,
            guidance=published,
        )
        return published

    @staticmethod
    def _clone_evidence_links(
        *,
        sources: list[EvidenceLink],
        guidance: Guidance,
    ) -> None:
        for source in sources:
            link = EvidenceLink(
                inquiry_id=source.inquiry_id,
                guidance=guidance,
                ai_run_id=source.ai_run_id,
                chunk_id=source.chunk_id,
                retrieval_hit_id=source.retrieval_hit_id,
                retrieval_run_id=source.retrieval_run_id,
                selection_origin_code=source.selection_origin_code,
                evidence_role_code=source.evidence_role_code,
                display_order=source.display_order,
                citation_label=source.citation_label,
                document_code_snapshot=source.document_code_snapshot,
                document_title_snapshot=source.document_title_snapshot,
                source_org_snapshot=source.source_org_snapshot,
                revision_label_snapshot=source.revision_label_snapshot,
                official_source_url_snapshot=(
                    source.official_source_url_snapshot
                ),
                document_sha256_snapshot=(
                    source.document_sha256_snapshot
                ),
                evidence_summary=source.evidence_summary,
                cited_text_snapshot=source.cited_text_snapshot,
                page_no_snapshot=source.page_no_snapshot,
                section_snapshot=source.section_snapshot,
                product_model_codes_snapshot=(
                    source.product_model_codes_snapshot
                ),
                is_verified=source.is_verified,
                verified_by_id=source.verified_by_id,
                verified_at=source.verified_at,
            )
            link.full_clean()
            link.save()

    @classmethod
    @transaction.atomic
    def mark_resume_failed(
        cls,
        *,
        review_public_id: UUID,
        failure_code: str,
    ) -> HumanReview:
        """Record a bounded AI resume failure without persisting raw errors."""

        review = (
            HumanReview.objects.select_for_update()
            .filter(public_id=review_public_id)
            .first()
        )
        if review is None:
            raise NotFound()
        if review.status_code not in {
            HumanReview.Status.APPROVED,
            HumanReview.Status.MODIFIED,
            HumanReview.Status.REJECTED,
        }:
            cls._raise_state_conflict(review)
        review.status_code = HumanReview.Status.RESUME_FAILED
        review.resume_failure_code = failure_code
        review.review_state_version += 1
        review.full_clean()
        review.save()
        return review

    @staticmethod
    def _raise_state_conflict(review: HumanReview) -> None:
        raise BusinessError(
            STATE_CONFLICT,
            "다른 검토 결정이 먼저 반영되었습니다.",
            details={
                "current_status": review.status_code,
                "current_review_state_version": review.review_state_version,
                "allowed_actions": (
                    ["DECIDE_HUMAN_REVIEW"]
                    if review.status_code == HumanReview.Status.PENDING
                    else []
                ),
            },
            status_code=409,
        )

    @classmethod
    def _projection(cls, review: HumanReview) -> dict[str, Any]:
        return {
            "review_id": str(review.public_id),
            "inquiry_id": str(review.inquiry.public_id),
            "inquiry_status": review.inquiry.status_code,
            "inquiry_state_version": review.inquiry.state_version,
            "model_code": review.inquiry.subscription.product_model.model_code,
            "status": review.status_code,
            "decision": review.decision_code,
            "review_state_version": review.review_state_version,
            "source_inquiry_state_version": (
                review.source_inquiry_state_version
            ),
            "reason_code": review.initial_reason_code,
            "decision_reason_code": review.decision_reason_code,
            "consultation_origin": review.consultation_origin_code,
            "consultation_origin_reason": (
                review.consultation_origin_reason_code
            ),
            "original_requires_consultation": (
                review.original_requires_consultation
            ),
            "effective_requires_consultation": (
                review.effective_requires_consultation
            ),
            "consultation_disposition": (
                review.consultation_disposition_code
            ),
            "consultation_reason_code": review.consultation_reason_code,
            "can_resolve_consultation": (
                review.status_code == HumanReview.Status.PENDING
                and review.original_requires_consultation
                and review.consultation_origin_code
                == HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
            ),
            "verified_evidence_ids": [
                str(link.public_id)
                for link in review.guidance.evidence_links.all()
                if link.is_verified
            ],
            "proposed_guidance": cls._guidance_projection(review.guidance),
            "published_guidance": (
                cls._guidance_projection(review.published_guidance)
                if review.published_guidance_id
                else None
            ),
            "allowed_actions": (
                ["DECIDE_HUMAN_REVIEW"]
                if review.status_code == HumanReview.Status.PENDING
                else []
            ),
            "created_at": review.created_at.isoformat(),
            "updated_at": review.updated_at.isoformat(),
        }

    @staticmethod
    def _guidance_projection(guidance: Guidance) -> dict[str, Any]:
        return {
            "guidance_id": str(guidance.public_id),
            "guidance_version": guidance.guidance_version,
            "title": guidance.title,
            "summary_text": guidance.summary_text,
            "safety_notice": guidance.safety_notice,
            "requires_consultation": guidance.requires_consultation,
            "items": [
                {
                    "step_no": item.step_no,
                    "instruction_text": item.instruction_text,
                    "caution_text": item.caution_text,
                    "requires_confirmation": item.requires_confirmation,
                }
                for item in sorted(
                    guidance.items.all(),
                    key=lambda value: (value.step_no, value.public_id),
                )
            ],
        }
