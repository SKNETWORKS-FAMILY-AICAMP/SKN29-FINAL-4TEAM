"""Privacy-safe consultant inquiry read projections."""

from __future__ import annotations

from datetime import date, timezone as datetime_timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.consultant_inquiry_repository import (
    ConsultantInquiryRepository,
)
from apps.workflow.engine.allowed_action_resolver import AllowedActionResolver


BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")
PUBLIC_ACTOR_ROLES = {
    "CUSTOMER",
    "CONSULTANT",
    "TECHNICIAN",
    "OPERATOR",
}


class ConsultantInquiryService:
    """Build the closed list/detail DTO without exposing internal fields."""

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
            "items": [cls._list_item(inquiry, now=now) for inquiry in inquiries],
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
        allowed_actions = AllowedActionResolver.resolve(
            state_code=inquiry.status_code,
            role_code="CONSULTANT",
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
                "phone": customer.phone,
            },
            "product_and_care": {
                "product_model": product.model_code,
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
                "usage_guidance_status": (
                    inquiry.effective_usage_guidance_status
                ),
                "usage_guidance_message": (
                    latest_guidance.summary_text.strip()[:2000]
                    if latest_guidance is not None
                    else None
                ),
                "restricted_functions": [],
            },
            # These nullable sections belong to later confirmed write slices.
            # Keep them closed rather than guessing another owner's projection.
            "consultation": None,
            "visit": None,
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
    def _list_item(inquiry: Inquiry, *, now) -> dict[str, Any]:
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
                state_code=inquiry.status_code,
                role_code="CONSULTANT",
            ),
        }

    @staticmethod
    def _mask_name(value: str) -> str:
        normalized = ConsultantInquiryService._display_name(value)
        if len(normalized) <= 1:
            return "*"
        return f"{normalized[:-1]}*"

    @staticmethod
    def _display_name(value: str) -> str:
        return value.strip()[:80]

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
                    "answer": answer[:2000],
                }
            )
        return answers

    @staticmethod
    def _actor_role(history) -> str:
        if history.changed_by_type_code == "SYSTEM" or history.actor is None:
            return "SYSTEM"
        role_code = history.actor.role_code
        return role_code if role_code in PUBLIC_ACTOR_ROLES else "SYSTEM"
