"""Privacy-safe CUSTOMER inquiry Snapshot and question projections."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from rest_framework.exceptions import NotFound

from apps.inquiries.models.inquiry_qa import public_question_options
from apps.inquiries.repositories.customer_inquiry_repository import (
    CustomerInquiryRepository,
)


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
        return {
            "inquiry_id": inquiry.public_id,
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "subscription_id": inquiry.subscription.public_id,
            "product": {
                "model_code": inquiry.subscription.product_model.model_code,
            },
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
