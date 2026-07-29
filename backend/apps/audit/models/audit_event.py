"""Append-only audit event linked to one workflow transition."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


class AuditEvent(TimestampedModel):
    """Immutable-facing trace of a synthetic inquiry or visit transition."""

    class EntityType(models.TextChoices):
        INQUIRY = "INQUIRY", "Inquiry"
        VISIT = "VISIT", "Visit"

    class ActorRole(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        CONSULTANT = "CONSULTANT", "Consultant"
        TECHNICIAN = "TECHNICIAN", "Technician"
        SYSTEM = "SYSTEM", "System"

    class DataClassification(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    audit_code = models.CharField(max_length=80, unique=True)
    transition = models.OneToOneField(
        "workflow.TransitionHistory",
        on_delete=models.PROTECT,
        related_name="audit_event",
        db_column="transition_history_id",
    )
    entity_type = models.CharField(
        max_length=20,
        choices=EntityType.choices,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="audit_events",
        db_column="inquiry_id",
        null=True,
        blank=True,
    )
    visit = models.ForeignKey(
        "visits.Visit",
        on_delete=models.PROTECT,
        related_name="audit_events",
        db_column="visit_id",
        null=True,
        blank=True,
    )
    event_code = models.CharField(max_length=80)
    actor_role = models.CharField(
        max_length=20,
        choices=ActorRole.choices,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_events",
        db_column="actor_id",
        null=True,
        blank=True,
    )
    state_version = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=128)
    correlation_id = models.UUIDField()
    occurred_at = models.DateTimeField()
    data_classification = models.CharField(
        max_length=20,
        choices=DataClassification.choices,
        default=DataClassification.SYNTHETIC,
    )

    class Meta:
        db_table = "audit_event"
        constraints = [
            models.CheckConstraint(
                condition=Q(entity_type__in=["INQUIRY", "VISIT"]),
                name="ck_audit_entity_type",
            ),
            models.CheckConstraint(
                condition=Q(
                    actor_role__in=[
                        "CUSTOMER",
                        "CONSULTANT",
                        "TECHNICIAN",
                        "SYSTEM",
                    ]
                ),
                name="ck_audit_actor_role",
            ),
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_audit_state_version_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        entity_type="INQUIRY",
                        inquiry__isnull=False,
                        visit__isnull=True,
                    )
                    | Q(
                        entity_type="VISIT",
                        inquiry__isnull=True,
                        visit__isnull=False,
                    )
                ),
                name="ck_audit_entity_target_match",
            ),
            models.CheckConstraint(
                condition=(
                    Q(actor_role="SYSTEM", actor__isnull=True)
                    | Q(
                        actor_role__in=[
                            "CUSTOMER",
                            "CONSULTANT",
                            "TECHNICIAN",
                        ],
                        actor__isnull=False,
                    )
                ),
                name="ck_audit_actor_presence",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_audit_data_synthetic",
            ),
        ]
        indexes = [
            models.Index(
                fields=["entity_type", "occurred_at"],
                name="ix_audit_entity_time",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_audit_correlation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.audit_code} ({self.entity_type})"
