"""Technician assignment and field-visit lifecycle persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.inquiries.models import Inquiry
from common.models.base import TimestampedModel


class Visit(TimestampedModel):
    """A role-bound field visit attached to one protected inquiry."""

    class Status(models.TextChoices):
        ASSIGNING = "ASSIGNING", "Assigning"
        SCHEDULING = "SCHEDULING", "Scheduling"
        CONFIRMED = "CONFIRMED", "Confirmed"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        FOLLOW_UP_REQUIRED = (
            "FOLLOW_UP_REQUIRED",
            "Follow-up required",
        )
        CANCELLED = "CANCELLED", "Cancelled"

    class DataClassification(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic"
        OPERATIONAL = "operational", "Operational"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    visit_code = models.CharField(max_length=50, unique=True)
    inquiry = models.ForeignKey(
        Inquiry,
        on_delete=models.PROTECT,
        related_name="visits",
        db_column="inquiry_id",
        db_index=False,
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_visits",
        db_column="technician_id",
        null=True,
        blank=True,
        db_index=False,
        limit_choices_to={"role_code": "TECHNICIAN"},
    )
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.ASSIGNING,
    )
    requested_at = models.DateTimeField()
    scheduled_at = models.DateTimeField(null=True, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    confirmed_date = models.DateField(null=True, blank=True)
    visit_reason = models.TextField(null=True, blank=True)
    usage_guidance_status = models.CharField(
        max_length=40,
        choices=Inquiry.UsageGuidanceStatus.choices,
        null=True,
        blank=True,
    )
    handoff_payload = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    confirmed_cause = models.TextField(null=True, blank=True)
    action_taken = models.TextField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=1)
    idempotency_key = models.CharField(max_length=128)
    correlation_id = models.UUIDField()
    data_classification = models.CharField(
        max_length=40,
        choices=DataClassification.choices,
        default=DataClassification.OPERATIONAL,
    )

    class Meta:
        db_table = "field_service_visit"
        constraints = [
            models.UniqueConstraint(
                fields=["id", "technician"],
                name="ux_visit_id_technician",
            ),
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_visit_state_version",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "ASSIGNING",
                        "SCHEDULING",
                        "CONFIRMED",
                        "IN_PROGRESS",
                        "COMPLETED",
                        "FOLLOW_UP_REQUIRED",
                        "CANCELLED",
                    ]
                ),
                name="ck_visit_status",
            ),
            models.CheckConstraint(
                condition=Q(
                    data_classification__in=[
                        "synthetic",
                        "operational",
                    ],
                ),
                name="ck_visit_data_class",
            ),
            models.CheckConstraint(
                condition=~Q(idempotency_key=""),
                name="ck_visit_idempotency_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="ASSIGNING",
                        technician__isnull=True,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status="SCHEDULING",
                        technician__isnull=False,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status="CONFIRMED",
                        technician__isnull=False,
                        scheduled_at__isnull=False,
                        started_at__isnull=True,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status="IN_PROGRESS",
                        technician__isnull=False,
                        started_at__isnull=False,
                        completed_at__isnull=True,
                    )
                    | Q(
                        status__in=[
                            "COMPLETED",
                            "FOLLOW_UP_REQUIRED",
                        ],
                        technician__isnull=False,
                        started_at__isnull=False,
                        completed_at__isnull=False,
                    )
                    | Q(
                        status="CANCELLED",
                        completed_at__isnull=True,
                    )
                ),
                name="ck_visit_lifecycle",
            ),
            models.CheckConstraint(
                condition=(
                    Q(completed_at__isnull=True)
                    | Q(completed_at__gte=F("started_at"))
                ),
                name="ck_visit_complete_order",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=[
                            "COMPLETED",
                            "FOLLOW_UP_REQUIRED",
                        ],
                        confirmed_cause__isnull=False,
                        action_taken__isnull=False,
                    )
                    | (
                        ~Q(
                            status__in=[
                                "COMPLETED",
                                "FOLLOW_UP_REQUIRED",
                            ]
                        )
                        & Q(confirmed_cause__isnull=True)
                        & Q(action_taken__isnull=True)
                    )
                ),
                name="ck_visit_result_lifecycle",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "-requested_at"],
                name="ix_visit_inquiry_requested",
            ),
            models.Index(
                fields=["technician", "status"],
                name="ix_visit_staff_status",
            ),
            models.Index(
                fields=["status", "scheduled_at"],
                name="ix_visit_schedule",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_visit_correlation",
            ),
        ]

    def clean(self) -> None:
        """Reject assignment to a user outside the technician role."""

        super().clean()
        if (
            self.technician_id is not None
            and self.technician.role_code != "TECHNICIAN"
        ):
            raise ValidationError(
                {
                    "technician": (
                        "Assigned visit staff must have the TECHNICIAN role."
                    )
                }
            )

    def __str__(self) -> str:
        return f"{self.visit_code} ({self.status})"
