"""Privacy-safe CUSTOMER inquiry Snapshot and question projections."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.exceptions import NotFound

from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.inquiries.models import HumanReview, Inquiry
from apps.inquiries.models.inquiry_qa import public_question_options
from apps.inquiries.repositories.customer_inquiry_repository import (
    CustomerInquiryRepository,
)
from apps.inquiries.services.guidance_review_policy import (
    GuidanceReviewPolicy,
)
from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_is_valid,
)
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import (
    AI_GUIDANCE_NOT_READY,
    CONSULTATION_RESULT_NOT_READY,
)


class CustomerInquiryService:
    """Build only the fields required by the Mobile CUSTOMER read slice."""

    AI_PROCESSING_TIMEOUT_NOTICE = (
        "AI 안내 생성이 지연되어 상담으로 연결합니다."
    )

    PUBLIC_GUIDANCE_STATES = frozenset(
        {
            Inquiry.Status.AI_GUIDANCE,
            Inquiry.Status.CONSULTATION_REQUIRED,
            Inquiry.Status.CONSULTATION_IN_PROGRESS,
            Inquiry.Status.VISIT_REVIEW_PENDING,
            Inquiry.Status.VISIT_SCHEDULING,
            Inquiry.Status.VISIT_SCHEDULED,
            Inquiry.Status.COMPLETION_PENDING,
            Inquiry.Status.REVISIT_REQUIRED,
            Inquiry.Status.RESOLVED,
        }
    )
    PUBLIC_CONSULTATION_RESULT_STATES = frozenset(
        {
            Inquiry.Status.VISIT_REVIEW_PENDING,
            Inquiry.Status.VISIT_SCHEDULING,
            Inquiry.Status.VISIT_SCHEDULED,
            Inquiry.Status.COMPLETION_PENDING,
            Inquiry.Status.REVISIT_REQUIRED,
            Inquiry.Status.REOPENED,
            Inquiry.Status.RESOLVED,
        }
    )
    CONSULTATION_RESULT_LABELS = {
        Consultation.Outcome.COMPLETED_NO_VISIT: "상담 처리 완료",
        Consultation.Outcome.VISIT_REQUIRED: "방문 점검 필요",
        Consultation.Outcome.REOPENED_FOLLOWUP: "추가 상담 필요",
    }
    USAGE_GUIDANCE_LABELS = {
        Inquiry.UsageGuidanceStatus.NORMAL: "정상 사용 가능",
        Inquiry.UsageGuidanceStatus.PARTIAL_STOP: "일부 기능 사용 중단",
        Inquiry.UsageGuidanceStatus.TOTAL_STOP: "제품 사용 중단",
        Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION: "상담 확인 필요",
    }

    @classmethod
    def latest_active_for_customer(cls, *, actor: Any) -> dict[str, Any]:
        inquiry = CustomerInquiryRepository.find_latest_active(actor=actor)
        return {
            "active_inquiry": (
                None
                if inquiry is None
                else cls._snapshot(inquiry, actor=actor)
            )
        }

    @classmethod
    def snapshot_for_customer(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> dict[str, Any]:
        inquiry = CustomerInquiryRepository.find_snapshot(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if inquiry is None:
            raise NotFound()
        snapshot = cls._snapshot(inquiry, actor=actor)
        snapshot["system_notice"] = cls._system_notice(inquiry)
        return snapshot

    @classmethod
    def _system_notice(cls, inquiry: Inquiry) -> str | None:
        if (
            inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
            and getattr(inquiry, "latest_state_change_event", None)
            == "AI_PROCESSING_TIMEOUT"
        ):
            return cls.AI_PROCESSING_TIMEOUT_NOTICE
        return None

    @classmethod
    def _snapshot(cls, inquiry: Inquiry, *, actor: Any) -> dict[str, Any]:
        allowed_actions = cls._allowed_actions(inquiry, actor=actor)
        return {
            "inquiry_id": inquiry.public_id,
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "subscription_id": inquiry.subscription.public_id,
            "product": {
                "model_code": inquiry.subscription.product_model.model_code,
            },
            "allowed_actions": allowed_actions,
            "updated_at": inquiry.updated_at,
        }

    @classmethod
    def questions_for_customer(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> dict[str, Any]:
        inquiry = CustomerInquiryRepository.find_with_questions(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if inquiry is None:
            raise NotFound()
        questions = []
        for question in inquiry.customer_read_questions:
            projected = cls._question(question)
            if projected is not None:
                questions.append(projected)
        return {
            "inquiry_id": inquiry.public_id,
            "state_version": inquiry.state_version,
            # Deliberately return question metadata only. Answer persistence
            # belongs to the separate customer_answer relation/write slice.
            "questions": questions,
        }

    @classmethod
    def guidance_for_customer(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> dict[str, Any]:
        """Return the latest customer-safe guidance or a retryable 409."""

        inquiry = CustomerInquiryRepository.find_with_guidance(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if inquiry is None:
            raise NotFound()

        allowed_actions = cls._allowed_actions(inquiry, actor=actor)
        if inquiry.status_code not in cls.PUBLIC_GUIDANCE_STATES:
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        guidance = next(iter(inquiry.customer_guidance_versions), None)
        if guidance is None:
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        ai_run = guidance.generated_by_ai_run
        payload = ai_run.validated_output_payload
        if not isinstance(payload, dict):
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        is_no_evidence = ai_run.status_code == AIRun.Status.NO_EVIDENCE
        if (
            inquiry.evidence_mode == Inquiry.EvidenceMode.PARTIAL_EVIDENCE
            or (inquiry.requires_fallback and not is_no_evidence)
            or (
                not is_no_evidence
                and inquiry.evidence_mode == Inquiry.EvidenceMode.NO_EVIDENCE
            )
        ):
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        safety = payload.get("safety_assessment")
        usage = payload.get("usage_guidance")
        if not isinstance(safety, dict) or not isinstance(usage, dict):
            raise cls._guidance_not_ready(inquiry, allowed_actions)

        risk_level = safety.get("risk_level")
        ai_requires_consultation = safety.get("requires_consultation")
        usage_status = usage.get("guidance_status")
        if not GuidanceReviewPolicy.is_customer_visible(
            risk_level=risk_level,
            review_status=guidance.review_status_code,
        ):
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        # The approved Guidance row is the customer-facing source of truth.
        # A HumanReview MODIFY decision creates a new approved Guidance while
        # preserving the original AI payload for audit purposes. Reading the
        # message/actions from that old payload would leak the rejected draft.
        usage_message = guidance.summary_text
        restricted_functions = cls._validated_public_string_list(
            usage.get("restricted_functions")
        )
        safe_actions = cls._validated_public_string_list(
            [
                item.instruction_text
                for item in getattr(guidance, "customer_public_items", ())
            ]
        )
        symptom_summary = inquiry.raw_text.strip()[:2000]
        if (
            risk_level not in set(inquiry.RiskLevel.values)
            or not isinstance(ai_requires_consultation, bool)
            or usage_status not in set(inquiry.UsageGuidanceStatus.values)
            or not isinstance(usage_message, str)
            or not usage_message.strip()
            or len(usage_message.strip()) > 3000
            or restricted_functions is None
            or safe_actions is None
            or not safe_actions
            or not symptom_summary
        ):
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        if not cls._effective_consultation_is_valid(
            guidance=guidance,
            ai_requires_consultation=ai_requires_consultation,
            require_human_approval=(
                risk_level == Inquiry.RiskLevel.CAUTION
            ),
        ):
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        if is_no_evidence and (
            inquiry.requires_fallback is not True
            or inquiry.evidence_mode != Inquiry.EvidenceMode.NO_EVIDENCE
            or ai_requires_consultation is not True
            or usage_status
            != Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
        ):
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        if (
            risk_level == Inquiry.RiskLevel.DANGER
            and not danger_assessment_is_valid(payload)
        ):
            raise cls._guidance_not_ready(inquiry, allowed_actions)

        return {
            "inquiry_id": inquiry.public_id,
            "inquiry_code": inquiry.inquiry_code,
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "symptom_summary": symptom_summary,
            "risk_level": risk_level,
            "usage_guidance_status": usage_status,
            "usage_guidance_message": usage_message.strip(),
            "restricted_functions": restricted_functions,
            "safe_actions": safe_actions,
            # The current AI response contract has no public fields for these.
            # Do not infer new safety instructions in the Backend projection.
            "escalation_conditions": [],
            "prohibited_actions": [],
            "next_action": safe_actions[0],
            "requires_consultation": guidance.requires_consultation,
            # Public Evidence is outside this P0. Internal chunks, scores,
            # paths, prompts, and trace data must never cross this boundary.
            "evidence": [],
            "allowed_actions": allowed_actions,
        }

    @staticmethod
    def _effective_consultation_is_valid(
        *,
        guidance,
        ai_requires_consultation: bool,
        require_human_approval: bool,
    ) -> bool:
        if (
            not require_human_approval
            and guidance.requires_consultation is ai_requires_consultation
        ):
            return True

        publications = list(
            HumanReview.objects.filter(
                published_guidance=guidance,
            ).select_related("guidance")
        )
        if not publications:
            return False

        # An APPROVED string alone is not publication provenance. Every
        # customer-visible CAUTION must retain at least one EvidenceLink and
        # every link must carry a completed verification record.
        evidence_links = list(
            guidance.evidence_links.select_related("chunk").all()
        )
        verified_evidence_links = [
            link
            for link in evidence_links
            if (
                link.is_verified
                and link.verified_by_id is not None
                and link.verified_at is not None
            )
        ]
        verified_evidence_fingerprints = {
            (
                str(link.chunk.public_id),
                link.document_sha256_snapshot,
            )
            for link in verified_evidence_links
        }
        if (
            guidance.evidence_sufficiency_code != "VERIFIED"
            or not evidence_links
            or len(verified_evidence_links) != len(evidence_links)
        ):
            return False

        for review in publications:
            if review.status_code not in {
                HumanReview.Status.APPROVED,
                HumanReview.Status.MODIFIED,
                HumanReview.Status.RESUME_FAILED,
            }:
                continue
            if review.decision_code not in {
                HumanReview.Decision.APPROVE,
                HumanReview.Decision.MODIFY,
            }:
                continue
            if (
                review.reviewer_id is None
                or review.decided_at is None
                or not review.decision_reason_code
                or not review.decision_idempotency_key
                or review.decision_correlation_id is None
                or review.guidance.generated_by_ai_run_id
                != guidance.generated_by_ai_run_id
            ):
                continue
            if (
                review.original_requires_consultation
                is not ai_requires_consultation
                or review.effective_requires_consultation
                is not guidance.requires_consultation
            ):
                continue
            if (
                ai_requires_consultation
                is guidance.requires_consultation
            ):
                if (
                    review.consultation_disposition_code
                    == HumanReview.ConsultationDisposition.PRESERVE
                    and review.consultation_reason_code is None
                    and not review.consultation_evidence_snapshot
                ):
                    return True
                continue
            if (
                review.consultation_disposition_code
                == HumanReview.ConsultationDisposition.REQUIRE
                and not ai_requires_consultation
                and guidance.requires_consultation
                and review.consultation_reason_code
                in {
                    HumanReview.ConsultationChangeReason.CONSULTANT_SAFETY_ESCALATION,
                    HumanReview.ConsultationChangeReason.PRODUCT_FUNCTION_UNCERTAIN,
                    HumanReview.ConsultationChangeReason.CUSTOMER_CONTEXT_INCOMPLETE,
                }
                and not review.consultation_evidence_snapshot
            ):
                return True
            if (
                review.consultation_disposition_code
                == HumanReview.ConsultationDisposition.RESOLVE_NON_SAFETY
                and ai_requires_consultation
                and not guidance.requires_consultation
                and review.consultation_origin_code
                == HumanReview.ConsultationOrigin.NON_SAFETY_RESOLVABLE
                and review.consultation_origin_reason_code
                in {
                    HumanReview.ConsultationOriginReason.HARNESS_UNSUPPORTED_FUNCTION,
                    HumanReview.ConsultationOriginReason.HARNESS_SCOPE_EXCEEDED,
                }
                and review.consultation_reason_code
                in {
                    HumanReview.ConsultationChangeReason.PRODUCT_CAPABILITY_VERIFIED,
                    HumanReview.ConsultationChangeReason.HARNESS_SCOPE_VERIFIED,
                }
                and CustomerInquiryService._resolution_snapshot_matches_evidence(
                    review.consultation_evidence_snapshot,
                    verified_evidence_fingerprints=(
                        verified_evidence_fingerprints
                    ),
                )
            ):
                return True
        return False

    @staticmethod
    def _resolution_snapshot_matches_evidence(
        snapshot: Any,
        *,
        verified_evidence_fingerprints: set[tuple[str, str]],
    ) -> bool:
        if not isinstance(snapshot, list) or not snapshot:
            return False
        snapshot_fingerprints: set[tuple[str, str]] = set()
        for item in snapshot:
            if not isinstance(item, dict):
                return False
            if not isinstance(item.get("evidence_link_id"), str):
                return False
            chunk_id = item.get("chunk_id")
            if not isinstance(chunk_id, str):
                return False
            document_hash = item.get("document_sha256")
            if not isinstance(document_hash, str) or not document_hash:
                return False
            snapshot_fingerprints.add((chunk_id, document_hash))
        return snapshot_fingerprints.issubset(
            verified_evidence_fingerprints
        )

    @classmethod
    def consultation_result_for_customer(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> dict[str, Any]:
        """Return the latest completed consultation's customer-safe result."""

        inquiry = CustomerInquiryRepository.find_with_consultation_result(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if inquiry is None:
            raise NotFound()

        allowed_actions = cls._allowed_actions(inquiry, actor=actor)
        if inquiry.status_code not in cls.PUBLIC_CONSULTATION_RESULT_STATES:
            raise cls._consultation_result_not_ready(inquiry, allowed_actions)

        consultation = next(
            iter(inquiry.customer_completed_consultations),
            None,
        )
        if consultation is None:
            raise cls._consultation_result_not_ready(inquiry, allowed_actions)

        customer_guidance = consultation.customer_guidance
        result_label = cls.CONSULTATION_RESULT_LABELS.get(
            consultation.outcome
        )
        usage_label = cls.USAGE_GUIDANCE_LABELS.get(
            consultation.usage_guidance_status
        )
        if (
            not isinstance(customer_guidance, str)
            or not customer_guidance.strip()
            or len(customer_guidance.strip()) > 2000
            or result_label is None
            or usage_label is None
        ):
            raise cls._consultation_result_not_ready(inquiry, allowed_actions)

        return {
            "inquiry_id": inquiry.public_id,
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "result_code": consultation.outcome,
            "result_display_label": result_label,
            "customer_guidance": customer_guidance.strip(),
            "usage_guidance_status": consultation.usage_guidance_status,
            "usage_guidance_display_label": usage_label,
            "completed_at": consultation.completed_at,
            "allowed_actions": allowed_actions,
        }

    @classmethod
    def _allowed_actions(
        cls,
        inquiry,
        *,
        actor: Any,
        completion_facts: Any = None,
    ) -> list[dict]:
        open_followup_questions = any(
            cls._question(question) is not None
            for question in inquiry.allowed_action_open_questions
        )
        if completion_facts is None and hasattr(
            inquiry,
            "allowed_action_latest_resolved_feedback_at",
        ):
            completion_facts = cls._completion_facts_from_annotations(inquiry)
        return AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
                consultation=None,
                visit=None,
                open_followup_questions=open_followup_questions,
                **(
                    {"completion_facts": completion_facts}
                    if completion_facts is not None
                    else {}
                ),
            )
        )

    @staticmethod
    def _completion_facts_from_annotations(inquiry) -> dict[str, Any]:
        completed_consultation_at = getattr(
            inquiry,
            "allowed_action_latest_completed_consultation_at",
            None,
        )
        completed_visit_at = getattr(
            inquiry,
            "allowed_action_latest_completed_visit_at",
            None,
        )
        completion_source = None
        last_handler_id = None
        last_handling_completed_at = None
        if completed_visit_at is not None and (
            completed_consultation_at is None
            or completed_visit_at >= completed_consultation_at
        ):
            completion_source = "VISIT"
            last_handler_id = getattr(
                inquiry,
                "allowed_action_latest_completed_visit_handler_id",
                None,
            )
            last_handling_completed_at = completed_visit_at
        elif completed_consultation_at is not None:
            completion_source = "CONSULTATION"
            last_handler_id = getattr(
                inquiry,
                "allowed_action_latest_completed_consultation_handler_id",
                None,
            )
            last_handling_completed_at = completed_consultation_at

        latest_feedback_at = getattr(
            inquiry,
            "allowed_action_latest_resolved_feedback_at",
            None,
        )
        return {
            "completion_source": completion_source,
            "last_handler_id": last_handler_id,
            "fresh_resolved_feedback_exists": bool(
                latest_feedback_at is not None
                and last_handling_completed_at is not None
                and latest_feedback_at > last_handling_completed_at
            ),
        }

    @staticmethod
    def _validated_public_string_list(value: Any) -> list[str] | None:
        if not isinstance(value, list) or len(value) > 20:
            return None
        projected: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                return None
            normalized = item.strip()
            if len(normalized) > 1000:
                return None
            projected.append(normalized)
        return projected

    @staticmethod
    def _guidance_not_ready(inquiry, allowed_actions) -> BusinessError:
        return BusinessError(
            AI_GUIDANCE_NOT_READY,
            "AI 안내가 아직 준비되지 않았습니다. 상담 검토가 필요합니다.",
            details={
                "inquiry_id": str(inquiry.public_id),
                "current_status": inquiry.status_code,
                "current_state_version": inquiry.state_version,
                "allowed_actions": allowed_actions,
            },
            status_code=409,
        )

    @staticmethod
    def _consultation_result_not_ready(
        inquiry,
        allowed_actions,
    ) -> BusinessError:
        return BusinessError(
            CONSULTATION_RESULT_NOT_READY,
            "상담 처리 결과가 아직 준비되지 않았습니다.",
            details={
                "inquiry_id": str(inquiry.public_id),
                "current_status": inquiry.status_code,
                "current_state_version": inquiry.state_version,
                "allowed_actions": allowed_actions,
            },
            status_code=409,
        )

    @staticmethod
    def _question(question) -> dict[str, Any] | None:
        options = public_question_options(question.question_options)
        if question.answer_type_code == "FREE_TEXT":
            question_type = "FREE_TEXT"
            options = []
        elif question.answer_type_code == "SINGLE_CHOICE" and options:
            question_type = "SINGLE_CHOICE"
        else:
            # Do not advertise a required question that the POST contract
            # cannot accept (for example MULTI_CHOICE or optionless choice).
            return None
        return {
            "question_id": question.public_id,
            "question_type": question_type,
            "prompt": question.question_text.strip()[:500],
            "required": True,
            "options": [
                {"value": option, "label": option} for option in options
            ],
        }
