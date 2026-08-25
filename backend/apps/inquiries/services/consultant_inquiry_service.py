"""Privacy-safe consultant inquiry read projections."""

from __future__ import annotations

from datetime import date, timezone as datetime_timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit.models import AIRun
from apps.consultations.services.consultation_service import (
    ConsultationService,
)
from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.consultant_inquiry_repository import (
    ConsultantInquiryRepository,
)
from apps.visits.services.visit_service import VisitService
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from common.privacy import mask_person_name, mask_phone


BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")
PUBLIC_ACTOR_ROLES = {
    "CUSTOMER",
    "CONSULTANT",
    "TECHNICIAN",
    "OPERATOR",
}
USAGE_GUIDANCE_DISPLAY_LABELS = {
    Inquiry.UsageGuidanceStatus.NORMAL: "정상 사용 가능",
    Inquiry.UsageGuidanceStatus.PARTIAL_STOP: "일부 기능 사용 중단",
    Inquiry.UsageGuidanceStatus.TOTAL_STOP: "제품 사용 중단",
    Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION: "상담 확인 필요",
}


class ConsultantInquiryService:
    """Build the closed list/detail DTO without exposing internal fields."""

    @classmethod
    def list_unassigned_consultations(
        cls,
        *,
        actor: Any,
        q: str | None,
        risk_levels: list[str],
        priorities: list[str],
        from_date: date | None,
        to_date: date | None,
        sort: str,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        inquiries, total = (
            ConsultantInquiryRepository.list_unassigned_page(
                q=q,
                risk_levels=risk_levels,
                priorities=priorities,
                from_date=from_date,
                to_date=to_date,
                sort=sort,
                offset=(page - 1) * size,
                limit=size,
            )
        )
        now = timezone.now()
        return {
            "items": [
                cls._unassigned_list_item(
                    inquiry,
                    actor=actor,
                    now=now,
                )
                for inquiry in inquiries
            ],
            "page_info": {"page": page, "size": size, "total": total},
        }

    @classmethod
    def list_for_consultant(
        cls,
        *,
        actor: Any,
        q: str | None,
        statuses: list[str],
        risk_levels: list[str],
        priorities: list[str],
        from_date: date | None,
        to_date: date | None,
        sort: str,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        inquiries, total, status_counts = ConsultantInquiryRepository.list_page(
            actor=actor,
            q=q,
            statuses=statuses,
            risk_levels=risk_levels,
            priorities=priorities,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            offset=(page - 1) * size,
            limit=size,
        )
        now = timezone.now()
        return {
            "items": [
                cls._list_item(inquiry, actor=actor, now=now)
                for inquiry in inquiries
            ],
            "page_info": {"page": page, "size": size, "total": total},
            "status_counts": status_counts,
        }

    @classmethod
    def detail_for_consultant(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
    ) -> dict[str, Any]:
        inquiry = ConsultantInquiryRepository.find_detail(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if inquiry is None:
            raise NotFound()

        customer = inquiry.subscription.customer
        product = inquiry.subscription.product_model
        latest_guidance = next(
            iter(inquiry.consultant_guidance_versions),
            None,
        )
        latest_consultation = next(
            iter(inquiry.allowed_action_consultations),
            None,
        )
        latest_visit = next(iter(inquiry.consultant_visits), None)
        usage_guidance_status = inquiry.effective_usage_guidance_status
        guidance_usage = cls._validated_guidance_usage(latest_guidance)
        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
            ),
        )
        return {
            "inquiry": {
                "inquiry_id": inquiry.public_id,
                "inquiry_code": inquiry.inquiry_code,
                "status": inquiry.status_code,
                "state_version": inquiry.state_version,
                "risk_level": inquiry.effective_risk_level,
                "priority": inquiry.effective_priority,
                "received_at": inquiry.created_at,
                "updated_at": inquiry.updated_at,
            },
            "customer": {
                "is_synthetic": True,
                "display_name": cls._display_name(customer.customer_name),
                # Keep the legacy key masked while Web migrates to the
                # explicit phone_masked field. Raw phone data never leaves
                # this consultant projection.
                "phone": cls._mask_phone(customer.phone),
                "phone_masked": cls._mask_phone(customer.phone),
            },
            "product_and_care": {
                "product_model": product.model_code,
                "product_model_name": product.model_name.strip()[:150],
                "subscription_status": inquiry.subscription.status_code,
                "management_type": (
                    inquiry.subscription.management_type_code
                ),
                "recent_care_date": cls._recent_care_date(
                    inquiry.subscription
                ),
            },
            "symptom_and_questionnaire": {
                "symptom_summary": inquiry.raw_text.strip()[:2000],
                "answers": cls._questionnaire_answers(inquiry),
            },
            "guidance_and_actions": {
                "usage_guidance_status": usage_guidance_status,
                "usage_guidance_display_label": (
                    cls._usage_guidance_display_label(
                        usage_guidance_status
                    )
                ),
                "usage_guidance_message": (
                    latest_guidance.summary_text.strip()[:2000]
                    if latest_guidance is not None
                    else None
                ),
                "restricted_functions": cls._public_string_list(
                    guidance_usage.get("restricted_functions")
                ),
            },
            "consultation": ConsultationService.build_resource(
                latest_consultation
            ),
            "visit": VisitService.build_resource(latest_visit),
            "state_history": [
                {
                    "from_status": history.from_state,
                    "to_status": history.to_state,
                    "changed_at": history.changed_at,
                    "actor_role": cls._actor_role(history),
                }
                for history in inquiry.consultant_state_history
            ],
            "workflow": {
                "status": inquiry.status_code,
                "state_version": inquiry.state_version,
                "allowed_actions": allowed_actions,
            },
            "section_errors": [],
        }

    @staticmethod
    def _list_item(inquiry: Inquiry, *, actor: Any, now) -> dict[str, Any]:
        customer = inquiry.subscription.customer
        product = inquiry.subscription.product_model
        waiting_seconds = max(
            0,
            int((now - inquiry.created_at).total_seconds()),
        )
        return {
            "inquiry_id": inquiry.public_id,
            "inquiry_code": inquiry.inquiry_code,
            "status": inquiry.status_code,
            "state_version": inquiry.state_version,
            "risk_level": inquiry.effective_risk_level,
            "priority": inquiry.effective_priority,
            "symptom_summary": inquiry.raw_text.strip()[:1000],
            "customer_display_name_masked": (
                ConsultantInquiryService._mask_name(customer.customer_name)
            ),
            "product_model": product.model_code,
            "current_assignee_type": "CONSULTANT",
            "received_at": inquiry.created_at,
            "updated_at": inquiry.updated_at,
            "waiting_seconds": waiting_seconds,
            "allowed_actions": AllowedActionResolver.resolve(
                context=AllowedActionContext.from_models(
                    inquiry=inquiry,
                    actor=actor,
                ),
            ),
        }

    @staticmethod
    def _unassigned_list_item(
        inquiry: Inquiry,
        *,
        actor: Any,
        now,
    ) -> dict[str, Any]:
        customer = inquiry.subscription.customer
        product = inquiry.subscription.product_model
        latest_consultation = next(
            iter(inquiry.allowed_action_consultations),
            None,
        )
        waiting_seconds = max(
            0,
            int((now - inquiry.created_at).total_seconds()),
        )
        return {
            "inquiry_id": inquiry.public_id,
            "inquiry_code": inquiry.inquiry_code,
            "status": inquiry.status_code,
            "state_version": inquiry.state_version,
            "risk_level": inquiry.effective_risk_level,
            "priority": inquiry.effective_priority,
            "symptom_summary": inquiry.raw_text.strip()[:1000],
            "customer_display_name_masked": (
                ConsultantInquiryService._mask_name(customer.customer_name)
            ),
            "product_model": product.model_code,
            "current_assignee_type": "NONE",
            "received_at": inquiry.created_at,
            "updated_at": inquiry.updated_at,
            "waiting_seconds": waiting_seconds,
            "allowed_actions": AllowedActionResolver.resolve(
                context=AllowedActionContext.from_models(
                    inquiry=inquiry,
                    actor=actor,
                    consultation=latest_consultation,
                ),
            ),
        }

    @staticmethod
    def _mask_name(value: str) -> str:
        return mask_person_name(value)

    @staticmethod
    def _display_name(value: str) -> str:
        return value.strip()[:80]

    @staticmethod
    def _mask_phone(value: str) -> str:
        return mask_phone(value)

    @staticmethod
    def _usage_guidance_display_label(status: str | None) -> str | None:
        if status is None:
            return None
        return USAGE_GUIDANCE_DISPLAY_LABELS.get(status)

    @staticmethod
    def _recent_care_date(subscription) -> date | None:
        care_dates: list[date] = []
        for care_record in subscription.consultant_completed_care_records:
            if care_record.performed_on is not None:
                care_dates.append(care_record.performed_on)
                continue
            if care_record.completed_at is None:
                continue
            completed_at = care_record.completed_at
            if timezone.is_naive(completed_at):
                completed_at = completed_at.replace(
                    tzinfo=datetime_timezone.utc
                )
            care_dates.append(
                timezone.localtime(completed_at, BUSINESS_TIMEZONE).date()
            )
        return max(care_dates, default=None)

    @staticmethod
    def _questionnaire_answers(inquiry: Inquiry) -> list[dict[str, str]]:
        answers: list[dict[str, str]] = []
        for entry in inquiry.consultant_answered_qa_entries:
            if entry.question_code is None:
                continue
            try:
                customer_answer = entry.customer_answer
            except ObjectDoesNotExist:
                continue
            answer = (customer_answer.answer_text or "").strip()
            if not answer and isinstance(customer_answer.answer_payload, dict):
                selected_option = customer_answer.answer_payload.get(
                    "selected_option"
                )
                if isinstance(selected_option, str):
                    answer = selected_option.strip()
            if not answer:
                continue
            answers.append(
                {
                    "question_code": entry.question_code,
                    "question_text": entry.question_text.strip()[:500],
                    "answer": answer[:2000],
                }
            )
        return answers

    @staticmethod
    def _validated_guidance_usage(guidance) -> dict[str, Any]:
        if guidance is None or guidance.generated_by_ai_run is None:
            return {}
        ai_run = guidance.generated_by_ai_run
        if (
            ai_run.task_type_code
            not in {
                AIRun.TaskType.ANALYZE_SYMPTOM,
                AIRun.TaskType.GENERATE_GUIDANCE,
            }
            or ai_run.status_code
            not in {AIRun.Status.SUCCEEDED, AIRun.Status.NO_EVIDENCE}
            or ai_run.schema_validation_status_code
            != AIRun.SchemaValidationStatus.PASSED
        ):
            return {}
        payload = ai_run.validated_output_payload
        if not isinstance(payload, dict):
            return {}
        usage = payload.get("usage_guidance")
        return usage if isinstance(usage, dict) else {}

    @staticmethod
    def _public_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            item.strip()[:120]
            for item in value
            if isinstance(item, str) and item.strip()
        ]

    @staticmethod
    def _actor_role(history) -> str:
        if history.changed_by_type_code == "SYSTEM" or history.actor is None:
            return "SYSTEM"
        role_code = history.actor.role_code
        return role_code if role_code in PUBLIC_ACTOR_ROLES else "SYSTEM"
