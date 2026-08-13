"""Privacy-safe CUSTOMER inquiry Snapshot and question projections."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.exceptions import NotFound

from apps.inquiries.models.inquiry_qa import public_question_options
from apps.inquiries.repositories.customer_inquiry_repository import (
    CustomerInquiryRepository,
)
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import AI_GUIDANCE_NOT_READY


class CustomerInquiryService:
    """Build only the fields required by the Mobile CUSTOMER read slice."""

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
        inquiry = CustomerInquiryRepository.find_with_guidance(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if inquiry is None:
            raise NotFound()

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
        guidance = next(iter(inquiry.customer_guidance_versions), None)
        if guidance is None:
            raise cls._guidance_not_ready(inquiry, allowed_actions)

        run = guidance.generated_by_ai_run
        payload = run.validated_output_payload
        if not isinstance(payload, dict):
            raise cls._guidance_not_ready(inquiry, allowed_actions)
        safety = payload.get("safety_assessment")
        usage = payload.get("usage_guidance")
        if not isinstance(safety, dict) or not isinstance(usage, dict):
            raise cls._guidance_not_ready(inquiry, allowed_actions)

        risk_level = safety.get("risk_level")
        usage_status = usage.get("guidance_status")
        usage_message = usage.get("message")
        if (
            risk_level not in set(inquiry.RiskLevel.values)
            or usage_status not in set(inquiry.UsageGuidanceStatus.values)
            or not isinstance(usage_message, str)
            or not usage_message.strip()
        ):
            raise cls._guidance_not_ready(inquiry, allowed_actions)

        restricted_functions = cls._public_string_list(
            usage.get("restricted_functions")
        )
        safe_actions = cls._public_string_list(usage.get("next_actions"))
        return {
            "inquiry_id": inquiry.public_id,
            "inquiry_code": inquiry.inquiry_code,
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "symptom_summary": inquiry.raw_text.strip()[:2000],
            "risk_level": risk_level,
            "usage_guidance_status": usage_status,
            "usage_guidance_message": usage_message.strip()[:3000],
            "restricted_functions": restricted_functions,
            "safe_actions": safe_actions,
            # These fields are not part of the current AI response contract.
            # Returning empty arrays is safer than deriving new instructions.
            "escalation_conditions": [],
            "prohibited_actions": [],
            "next_action": (
                safe_actions[0] if safe_actions else "상담 검토 필요"
            ),
            "requires_consultation": bool(
                safety.get("requires_consultation")
                or guidance.requires_consultation
                or inquiry.requires_fallback
            ),
            # Public EvidenceCard Runtime is outside this P0. Never expose
            # internal chunk identifiers, scores, paths, or AI traces here.
            "evidence": [],
            "allowed_actions": allowed_actions,
        }

    @staticmethod
    def _public_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            item.strip()[:1000]
            for item in value
            if isinstance(item, str) and item.strip()
        ][:20]

    @staticmethod
    def _guidance_not_ready(inquiry, allowed_actions) -> BusinessError:
        return BusinessError(
            AI_GUIDANCE_NOT_READY,
            "AI 안내가 아직 준비되지 않았습니다. 상담 검토가 필요합니다.",
            details={
                "inquiry_id": str(inquiry.public_id),
                "status_code": inquiry.status_code,
                "state_version": inquiry.state_version,
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
