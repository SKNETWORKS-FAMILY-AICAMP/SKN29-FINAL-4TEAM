"""Privacy-safe CUSTOMER inquiry Snapshot and question projections."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.exceptions import NotFound

from apps.audit.models import AIRun
from apps.inquiries.models import Inquiry
from apps.inquiries.models.inquiry_qa import public_question_options
from apps.inquiries.repositories.customer_inquiry_repository import (
    CustomerInquiryRepository,
)
from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_is_valid,
)
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import AI_GUIDANCE_NOT_READY


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
    PUBLIC_GUIDANCE_REVIEW_STATUSES = frozenset({"APPROVED", "CONFIRMED"})

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
        open_followup_questions = any(
            cls._question(question) is not None
            for question in inquiry.allowed_action_open_questions
        )
        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
                consultation=None,
                visit=None,
                open_followup_questions=open_followup_questions,
            )
        )
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
        if (
            guidance.review_status_code
            not in cls.PUBLIC_GUIDANCE_REVIEW_STATUSES
        ):
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
        requires_consultation = safety.get("requires_consultation")
        usage_status = usage.get("guidance_status")
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
            or not isinstance(requires_consultation, bool)
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
        if guidance.requires_consultation is not requires_consultation:
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        if is_no_evidence and (
            inquiry.requires_fallback is not True
            or inquiry.evidence_mode != Inquiry.EvidenceMode.NO_EVIDENCE
            or requires_consultation is not True
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
            "requires_consultation": requires_consultation,
            # Public Evidence is outside this P0. Internal chunks, scores,
            # paths, prompts, and trace data must never cross this boundary.
            "evidence": [],
            "allowed_actions": allowed_actions,
        }

    @classmethod
    def _allowed_actions(cls, inquiry, *, actor: Any) -> list[dict]:
        open_followup_questions = any(
            cls._question(question) is not None
            for question in inquiry.allowed_action_open_questions
        )
        return AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
                consultation=None,
                visit=None,
                open_followup_questions=open_followup_questions,
            )
        )

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
