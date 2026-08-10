"""Consultation assignment, progress, and completion persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.inquiries.models import Inquiry
from common.models.base import TimestampedModel


class Consultation(TimestampedModel):
    """A role-bound consultation attached to one protected inquiry."""

    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Outcome(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED_NO_VISIT = (
            "COMPLETED_NO_VISIT",
            "Completed without visit",
        )
        VISIT_REQUIRED = "VISIT_REQUIRED", "Visit required"
        REOPENED_FOLLOWUP = "REOPENED_FOLLOWUP", "Reopened follow-up"

    class DataClassification(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic"
        OPERATIONAL = "operational", "Operational"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    consultation_code = models.CharField(max_length=50, unique=True)
    inquiry = models.ForeignKey(
        Inquiry,
        on_delete=models.PROTECT,
        related_name="consultations",
        db_column="inquiry_id",
        db_index=False,
    )
    sequence = models.PositiveIntegerField()
    consultant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_consultations",
        db_column="consultant_id",
        null=True,
        blank=True,
        db_index=False,
        limit_choices_to={"role_code": "CONSULTANT"},
    )
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.WAITING,
    )
    outcome = models.CharField(
        max_length=40,
        choices=Outcome.choices,
        default=Outcome.PENDING,
    )
    summary = models.TextField(blank=True, default="")
    ai_draft_summary = models.TextField(null=True, blank=True)
    confirmed_summary = models.TextField(null=True, blank=True)
    summary_confirmed_at = models.DateTimeField(null=True, blank=True)
    consultation_note = models.TextField(null=True, blank=True)
    additional_check = models.TextField(null=True, blank=True)
    customer_guidance = models.TextField(null=True, blank=True)
    usage_guidance_status = models.CharField(
        max_length=40,
        choices=Inquiry.UsageGuidanceStatus.choices,
        null=True,
        blank=True,
    )
    visit_review_reason_code = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    visit_review_reason_detail = models.TextField(null=True, blank=True)
    visit_not_needed_reason_code = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    visit_not_needed_reason_detail = models.TextField(
        null=True,
        blank=True,
    )
    state_version = models.PositiveIntegerField(default=1)
    idempotency_key = models.CharField(max_length=128)
    correlation_id = models.UUIDField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    data_classification = models.CharField(
        max_length=40,
        choices=DataClassification.choices,
        default=DataClassification.OPERATIONAL,
    )
    # Synthetic consultation timestamps are authoritative during import.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "support_consultation"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "sequence"],
                name="ux_consult_inquiry_sequence",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gt=0),
                name="ck_consult_sequence_positive",
            ),
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_consult_state_version",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "WAITING",
                        "ASSIGNED",
                        "IN_PROGRESS",
                        "COMPLETED",
                        "CANCELLED",
                    ]
                ),
                name="ck_consult_status",
            ),
            models.CheckConstraint(
                condition=Q(
                    outcome__in=[
                        "PENDING",
                        "COMPLETED_NO_VISIT",
                        "VISIT_REQUIRED",
                        "REOPENED_FOLLOWUP",
                    ]
                ),
                name="ck_consult_outcome",
            ),
            models.CheckConstraint(
                condition=Q(
                    data_classification__in=[
                        "synthetic",
                        "operational",
                    ],
                ),
                name="ck_consult_data_class",
            ),
            models.CheckConstraint(
                condition=~Q(idempotency_key=""),
                name="ck_consult_idempotency_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="WAITING",
                        consultant__isnull=True,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status="ASSIGNED",
                        consultant__isnull=False,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status="IN_PROGRESS",
                        consultant__isnull=False,
                        started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status="COMPLETED",
                        consultant__isnull=False,
                        started_at__isnull=False,
                        completed_at__isnull=False,
                    )
                    | Q(
                        status="CANCELLED",
                        completed_at__isnull=True,
                    )
                ),
                name="ck_consult_lifecycle",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="COMPLETED",
                        outcome__in=[
                            "COMPLETED_NO_VISIT",
                            "VISIT_REQUIRED",
                            "REOPENED_FOLLOWUP",
                        ],
                    )
                    | Q(
                        status="IN_PROGRESS",
                        outcome__in=[
                            "PENDING",
                            "COMPLETED_NO_VISIT",
                            "VISIT_REQUIRED",
                            "REOPENED_FOLLOWUP",
                        ],
                    )
                    | Q(
                        status__in=["WAITING", "ASSIGNED", "CANCELLED"],
                        outcome="PENDING",
                    )
                ),
                name="ck_consult_outcome_lifecycle",
            ),
            models.CheckConstraint(
                condition=(
                    Q(started_at__isnull=True)
                    | Q(started_at__gte=F("created_at"))
                ),
                name="ck_consult_start_order",
            ),
            models.CheckConstraint(
                condition=(
                    Q(completed_at__isnull=True)
                    | Q(completed_at__gte=F("started_at"))
                ),
                name="ck_consult_complete_order",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "-created_at"],
                name="ix_consult_inquiry_created",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="ix_consult_queue",
            ),
            models.Index(
                fields=["consultant", "status"],
                name="ix_consult_staff_status",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_consult_correlation",
            ),
        ]

    def clean(self) -> None:
        """Reject assignment to a user outside the consultant role."""

        super().clean()
        if (
            self.consultant_id is not None
            and self.consultant.role_code != "CONSULTANT"
        ):
            raise ValidationError(
                {
                    "consultant": (
                        "Assigned consultation staff must have the "
                        "CONSULTANT role."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.consultation_code} ({self.status})"
