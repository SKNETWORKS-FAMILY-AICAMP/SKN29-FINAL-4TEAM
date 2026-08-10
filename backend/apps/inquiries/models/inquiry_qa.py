"""Ordered follow-up questions and answers for a support inquiry."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


def public_question_options(raw_options) -> list[str]:
    """Return the single normalized option set used by GET and POST."""

    if not isinstance(raw_options, list):
        return []
    return [
        option.strip()[:200]
        for option in raw_options[:10]
        if isinstance(option, str) and option.strip()
    ]


def question_metadata(raw_payload) -> dict:
    """Read only the legacy JSON keys owned by question metadata."""

    if not isinstance(raw_payload, dict):
        return {}
    return {
        key: raw_payload[key]
        for key in ("question_options", "target_field")
        if key in raw_payload
    }


class InquiryQA(TimestampedModel):
    """Persist one follow-up question and its contract-compatible fields."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="qa_entries",
        db_column="inquiry_id",
        db_index=False,
    )
    sequence_no = models.PositiveSmallIntegerField()
    question_code = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    question_text = models.TextField()
    answer_type_code = models.CharField(
        max_length=40,
        default="FREE_TEXT",
    )
    # These four legacy columns remain part of the immutable T-005 table
    # contract. New Runtime writes use FollowUpAnswer, but the columns are
    # retained for schema compatibility and reversible data migration.
    answer_text = models.TextField(null=True, blank=True)
    answer_payload = models.JSONField(null=True, blank=True)
    asked_by_type_code = models.CharField(
        max_length=40,
        default="RULE",
    )
    source_ai_run = models.ForeignKey(
        "audit.AIRun",
        on_delete=models.PROTECT,
        related_name="generated_inquiry_qa_entries",
        db_column="source_ai_run_id",
        db_index=False,
        null=True,
        blank=True,
    )
    answered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="answered_inquiry_qa_entries",
        db_column="answered_by_id",
        db_index=False,
        null=True,
        blank=True,
    )
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "support_inquiry_qa"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "sequence_no"],
                name="ux_inquiry_qa_sequence",
            ),
            models.UniqueConstraint(
                fields=["inquiry", "question_code"],
                condition=Q(question_code__isnull=False),
                name="ux_inquiry_qa_question",
            ),
            models.CheckConstraint(
                condition=(
                    Q(answered_at__isnull=True)
                    | (
                        Q(answered_by__isnull=False)
                        & (
                            Q(answer_text__isnull=False)
                            | Q(answer_payload__isnull=False)
                        )
                    )
                ),
                name="ck_inquiry_qa_answer_consistency",
            ),
            models.CheckConstraint(
                condition=Q(sequence_no__gt=0),
                name="ck_inquiry_qa_sequence",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        asked_by_type_code="AI",
                        source_ai_run__isnull=False,
                    )
                    | (
                        ~Q(asked_by_type_code="AI")
                        & Q(source_ai_run__isnull=True)
                    )
                ),
                name="ck_inquiry_qa_ai_origin",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "answered_at"],
                name="ix_inquiry_qa_answered",
            ),
            models.Index(
                fields=["source_ai_run", "inquiry"],
                name="ix_inquiry_qa_ai_run",
            ),
        ]

    def clean(self) -> None:
        """Validate the cross-row AI generation policy."""

        super().clean()
        errors: dict[str, str] = {}

        if self.asked_by_type_code == "AI":
            if self.source_ai_run_id is None:
                errors["source_ai_run"] = (
                    "An AI-generated question requires an AI run."
                )
            else:
                ai_run = self.source_ai_run
                if (
                    self.inquiry_id is not None
                    and ai_run.inquiry_id != self.inquiry_id
                ):
                    errors["source_ai_run"] = (
                        "The question and AI run must belong to the same "
                        "inquiry."
                    )
                elif (
                    ai_run.task_type_code
                    not in {"GENERATE_QUESTIONS", "ANALYZE_SYMPTOM"}
                    or ai_run.schema_validation_status_code != "PASSED"
                ):
                    errors["source_ai_run"] = (
                        "An AI-generated question can use only a "
                        "schema-validated question or integrated analysis "
                        "AI run."
                    )
        elif self.source_ai_run_id is not None:
            errors["source_ai_run"] = (
                "A non-AI question cannot reference an AI run."
            )

        options = self.question_options
        if not isinstance(options, list):
            errors["question_options"] = "질문 선택지는 배열이어야 합니다."
        elif len(options) > 10:
            errors["question_options"] = "질문 선택지는 10개 이하여야 합니다."
        elif any(
            not isinstance(option, str)
            or not option.strip()
            or len(option) > 200
            for option in options
        ):
            errors["question_options"] = (
                "각 질문 선택지는 1~200자 문자열이어야 합니다."
            )
        else:
            payload = (
                dict(self.answer_payload)
                if isinstance(self.answer_payload, dict)
                else {}
            )
            payload["question_options"] = public_question_options(options)
            if self.target_field:
                payload["target_field"] = self.target_field
            self.answer_payload = payload or None

        if errors:
            raise ValidationError(errors)

    @property
    def question_options(self) -> list:
        """Compatibility view over the immutable T-005 JSON column."""

        value = question_metadata(self.answer_payload).get(
            "question_options", []
        )
        return value if isinstance(value, list) else []

    @property
    def target_field(self) -> str | None:
        """Return the internal AI target without adding a contract column."""

        value = question_metadata(self.answer_payload).get("target_field")
        return value if isinstance(value, str) else None

    def __str__(self) -> str:
        return (
            f"{self.public_id} #{self.sequence_no} "
            f"({self.asked_by_type_code})"
        )
