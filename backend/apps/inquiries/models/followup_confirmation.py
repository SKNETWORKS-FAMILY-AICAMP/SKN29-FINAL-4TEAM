"""상담·방문 이후 고객 해결 확인 원장."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from common.models.base import TimestampedModel


class FollowupConfirmation(TimestampedModel):
    """후속 확인 응답과 종결·재개 결정을 보존한다."""

    class Channel(models.TextChoices):
        APP = "APP", "App"
        WEB = "WEB", "Web"
        PHONE = "PHONE", "Phone"

    class ResolutionStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RESOLVED = "RESOLVED", "Resolved"
        UNRESOLVED = "UNRESOLVED", "Unresolved"
        REOPENED = "REOPENED", "Reopened"

    class NextAction(models.TextChoices):
        FINALIZE_INQUIRY = "FINALIZE_INQUIRY", "Finalize inquiry"
        RESUME_CONSULTATION = "RESUME_CONSULTATION", "Resume consultation"
        NONE = "NONE", "None"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    followup_code = models.CharField(max_length=60, unique=True)
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="followup_confirmations",
        db_column="inquiry_id",
    )
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.PROTECT,
        related_name="followup_confirmations",
        db_column="consultation_id",
        null=True,
        blank=True,
    )
    visit = models.ForeignKey(
        "visits.Visit",
        on_delete=models.PROTECT,
        related_name="followup_confirmations",
        db_column="visit_id",
        null=True,
        blank=True,
    )
    guidance_public_id = models.UUIDField(null=True, blank=True)
    channel_code = models.CharField(max_length=20, choices=Channel.choices)
    resolution_status_code = models.CharField(
        max_length=40,
        choices=ResolutionStatus.choices,
    )
    state_version = models.PositiveIntegerField(default=1)
    customer_response = models.TextField(null=True, blank=True)
    unresolved_reason = models.TextField(null=True, blank=True)
    next_action = models.CharField(
        max_length=40,
        choices=NextAction.choices,
        default=NextAction.NONE,
    )
    requested_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "support_followup_confirmation"
        constraints = [
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_followup_state_version",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        resolution_status_code="PENDING",
                        responded_at__isnull=True,
                        confirmed_at__isnull=True,
                    )
                    | Q(
                        resolution_status_code__in=[
                            "RESOLVED",
                            "UNRESOLVED",
                            "REOPENED",
                        ],
                        responded_at__isnull=False,
                    )
                ),
                name="ck_followup_response_state",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(
                        resolution_status_code__in=[
                            "UNRESOLVED",
                            "REOPENED",
                        ]
                    )
                    | Q(unresolved_reason__isnull=False)
                ),
                name="ck_followup_unresolved_reason",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(resolution_status_code="RESOLVED")
                    | Q(confirmed_at__isnull=False)
                ),
                name="ck_followup_resolved_confirmed",
            ),
            models.CheckConstraint(
                condition=(
                    Q(responded_at__isnull=True)
                    | Q(responded_at__gte=F("requested_at"))
                ),
                name="ck_followup_response_time",
            ),
            models.CheckConstraint(
                condition=(
                    Q(confirmed_at__isnull=True)
                    | (
                        Q(responded_at__isnull=False)
                        & Q(confirmed_at__gte=F("responded_at"))
                    )
                ),
                name="ck_followup_confirmation_time",
            ),
            models.CheckConstraint(
                condition=(
                    Q(guidance_public_id__isnull=False)
                    | Q(consultation__isnull=False)
                    | Q(visit__isnull=False)
                ),
                name="ck_followup_has_source",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "-requested_at"],
                name="ix_followup_inquiry",
            )
        ]

    def clean(self) -> None:
        super().clean()
        mismatches: list[str] = []
        if (
            self.consultation_id
            and self.consultation.inquiry_id != self.inquiry_id
        ):
            mismatches.append("consultation")
        if self.visit_id and self.visit.inquiry_id != self.inquiry_id:
            mismatches.append("visit")
        if mismatches:
            raise ValidationError(
                {
                    "inquiry": (
                        "후속 확인의 문의와 연결 원본이 일치해야 합니다: "
                        + ", ".join(mismatches)
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.followup_code} ({self.resolution_status_code})"
