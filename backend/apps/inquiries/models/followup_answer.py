"""Customer answers stored separately from AI question metadata."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from common.models.base import TimestampedModel


class FollowUpAnswer(TimestampedModel):
    """Persist one customer answer for one public follow-up question."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    question = models.OneToOneField(
        "inquiries.InquiryQA",
        on_delete=models.PROTECT,
        related_name="customer_answer",
        db_column="question_id",
    )
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_followup_answers",
        db_column="answered_by_id",
        db_index=False,
    )
    answer_text = models.TextField(null=True, blank=True)
    answer_payload = models.JSONField(null=True, blank=True)
    accepted_state_version = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text=(
            "SUBMIT_ANSWERS 요청이 수락될 때의 Inquiry state_version; "
            "0011 이전 이관 데이터는 알 수 없어 null"
        ),
    )
    answered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "support_followup_answer"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        answer_text__isnull=False,
                        answer_payload__isnull=True,
                    )
                    | Q(
                        answer_text__isnull=True,
                        answer_payload__isnull=False,
                    )
                ),
                name="ck_followup_answer_value_xor",
            ),
            models.CheckConstraint(
                condition=(
                    Q(accepted_state_version__isnull=True)
                    | Q(accepted_state_version__gt=0)
                ),
                name="ck_followup_answer_version",
            ),
        ]
        indexes = [
            models.Index(
                fields=["answered_by", "answered_at"],
                name="ix_followup_answer_actor",
            ),
        ]

    def clean(self) -> None:
        """Protect the ownership and one-value public contract."""

        super().clean()
        errors: dict[str, str] = {}
        has_text = self.answer_text is not None
        has_payload = self.answer_payload is not None
        if has_text == has_payload:
            errors["answer_text"] = (
                "answer_text와 answer_payload 중 하나만 필요합니다."
            )
        elif has_text:
            normalized = self.answer_text.strip()
            if not normalized:
                errors["answer_text"] = "공백만 입력할 수 없습니다."
            else:
                self.answer_text = normalized
        elif not isinstance(self.answer_payload, dict) or not self.answer_payload:
            errors["answer_payload"] = "비어 있지 않은 객체여야 합니다."

        if self.question_id is not None and self.answered_by_id is not None:
            owner_id = (
                self.question.inquiry.subscription.customer.user_id
            )
            if owner_id != self.answered_by_id:
                errors["answered_by"] = "문의 소유 고객만 답변할 수 있습니다."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.public_id} -> {self.question_id}"
