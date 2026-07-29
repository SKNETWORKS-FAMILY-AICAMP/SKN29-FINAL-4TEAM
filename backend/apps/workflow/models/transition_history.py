"""Append-only inquiry transition history."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


class TransitionHistory(TimestampedModel):
    """Auditable state transition produced by the workflow runtime."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="transition_history",
        db_column="inquiry_id",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workflow_transitions",
        db_column="actor_id",
    )
    event_code = models.CharField(max_length=80)
    from_state = models.CharField(max_length=40, null=True, blank=True)
    to_state = models.CharField(max_length=40)
    state_version = models.PositiveIntegerField()
    correlation_id = models.UUIDField()
    idempotency_key = models.CharField(max_length=128)

    class Meta:
        db_table = "workflow_transition_history"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "state_version"],
                name="ux_transition_inquiry_version",
            ),
            models.CheckConstraint(
                condition=Q(state_version__gt=0),
                name="ck_transition_state_version_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["correlation_id"],
                name="ix_transition_correlation",
            )
        ]
