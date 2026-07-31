"""CARE_PRECHECK 사전 문진 세션 Model."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.common_codes.db_expressions import IsJSONObject
from common.models.base import TimestampedModel


class QuestionnaireSession(TimestampedModel):
    """문의 생성 전 CARE_PRECHECK 응답과 이후 문의 연결을 보존한다."""

    class QuestionnaireType(models.TextChoices):
        CARE_PRECHECK = "CARE_PRECHECK", "Care precheck"

    class Status(models.TextChoices):
        UNANSWERED = "UNANSWERED", "Unanswered"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        SUBMITTED = "SUBMITTED", "Submitted"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    session_no = models.CharField(max_length=40, unique=True)
    subscription = models.ForeignKey(
        "subscriptions.CustomerSubscription",
        on_delete=models.PROTECT,
        related_name="questionnaire_sessions",
        db_column="subscription_id",
        db_index=False,
    )
    inquiry = models.OneToOneField(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="questionnaire_session",
        db_column="inquiry_id",
        null=True,
        blank=True,
    )
    questionnaire_type_code = models.CharField(
        max_length=40,
        choices=QuestionnaireType.choices,
        default=QuestionnaireType.CARE_PRECHECK,
    )
    status_code = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.UNANSWERED,
    )
    questionnaire_version = models.CharField(max_length=40)
    answers_payload = models.JSONField(default=dict)
    state_version = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    linked_at = models.DateTimeField(null=True, blank=True)
    creation_idempotency_key = models.CharField(
        max_length=128,
        unique=True,
    )

    class Meta:
        db_table = "support_questionnaire_session"
        constraints = [
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_qsession_state_version",
            ),
            models.CheckConstraint(
                condition=IsJSONObject(models.F("answers_payload")),
                name="ck_questionnaire_answers_object",
            ),
            models.CheckConstraint(
                condition=Q(
                    questionnaire_type_code__in=["CARE_PRECHECK"]
                ),
                name="ck_qsession_type_code",
            ),
            models.CheckConstraint(
                condition=Q(
                    status_code__in=[
                        "UNANSWERED",
                        "IN_PROGRESS",
                        "SUBMITTED",
                    ]
                ),
                name="ck_qsession_status_code",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status_code__in=[
                            "UNANSWERED",
                            "IN_PROGRESS",
                        ],
                        submitted_at__isnull=True,
                    )
                    | Q(
                        status_code="SUBMITTED",
                        submitted_at__isnull=False,
                        submitted_at__gte=F("started_at"),
                    )
                ),
                name="ck_qsession_submission",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        inquiry__isnull=True,
                        linked_at__isnull=True,
                    )
                    | Q(
                        status_code="SUBMITTED",
                        inquiry__isnull=False,
                        submitted_at__isnull=False,
                        linked_at__isnull=False,
                        linked_at__gte=F("submitted_at"),
                    )
                ),
                name="ck_qsession_inquiry_link",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "subscription",
                    "status_code",
                    "-created_at",
                ],
                name="ix_qsession_sub_status",
            )
        ]

    def clean(self) -> None:
        """DB 간 공통으로 표현하기 어려운 JSON·관계 규칙을 검증한다."""

        super().clean()
        errors: dict[str, str] = {}

        if not isinstance(self.answers_payload, dict):
            errors["answers_payload"] = (
                "answers_payload는 질문 코드별 JSON object여야 합니다."
            )

        if self.status_code in {
            self.Status.UNANSWERED,
            self.Status.IN_PROGRESS,
        }:
            if self.submitted_at is not None:
                errors["submitted_at"] = (
                    "제출 전 상태에는 submitted_at을 저장할 수 없습니다."
                )
        elif self.status_code == self.Status.SUBMITTED:
            if self.submitted_at is None:
                errors["submitted_at"] = (
                    "SUBMITTED 상태에는 submitted_at이 필요합니다."
                )
            elif (
                self.started_at is not None
                and self.submitted_at < self.started_at
            ):
                errors["submitted_at"] = (
                    "submitted_at은 started_at보다 빠를 수 없습니다."
                )

        if self.inquiry_id is None:
            if self.linked_at is not None:
                errors["linked_at"] = (
                    "문의가 연결되지 않은 세션에는 linked_at을 "
                    "저장할 수 없습니다."
                )
        else:
            if self.status_code != self.Status.SUBMITTED:
                errors["inquiry"] = (
                    "SUBMITTED 세션만 문의에 연결할 수 있습니다."
                )
            if self.linked_at is None:
                errors["linked_at"] = (
                    "문의 연결 시 linked_at이 필요합니다."
                )
            elif (
                self.submitted_at is not None
                and self.linked_at < self.submitted_at
            ):
                errors["linked_at"] = (
                    "linked_at은 submitted_at보다 빠를 수 없습니다."
                )
            if (
                self.subscription_id is not None
                and self.inquiry.subscription_id
                != self.subscription_id
            ):
                errors["inquiry"] = (
                    "문진 세션과 문의는 같은 구독에 속해야 합니다."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.session_no} ({self.status_code})"
