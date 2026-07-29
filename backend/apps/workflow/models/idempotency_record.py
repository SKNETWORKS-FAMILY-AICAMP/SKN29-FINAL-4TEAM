"""Persisted idempotency scope and cached response."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from common.models.base import TimestampedModel


class IdempotencyRecord(TimestampedModel):
    """One external write result keyed by actor, operation, and client key."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="idempotency_records",
        db_column="actor_id",
    )
    operation_id = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    response_body = models.JSONField(default=dict, blank=True)
    resource_public_id = models.UUIDField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "workflow_idempotency_record"
        constraints = [
            models.UniqueConstraint(
                fields=["actor", "operation_id", "idempotency_key"],
                name="ux_workflow_idempotency_scope",
            )
        ]
        indexes = [
            models.Index(
                fields=["resource_public_id"],
                name="ix_idempotency_resource",
            )
        ]
