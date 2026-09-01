"""Durable Backend ledger for one rejected-review AI resume dispatch."""

from __future__ import annotations

import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q

from common.models.base import TimestampedModel


class HumanReviewResumeDispatch(TimestampedModel):
    """Persist one fail-closed Backend-to-AI resume attempt per review.

    A row is created in the same transaction as the official REJECT.  Workers
    only claim ``PENDING`` rows once.  A started request is never retried
    automatically because a transport failure may have happened after the AI
    Provider was already called.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DISPATCHING = "DISPATCHING", "Dispatching"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED_PRE_SEND = "FAILED_PRE_SEND", "Failed before send"
        OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN", "Outcome unknown"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    human_review = models.OneToOneField(
        "inquiries.HumanReview",
        on_delete=models.PROTECT,
        related_name="resume_dispatch",
        db_column="human_review_id",
    )
    idempotency_key = models.CharField(max_length=128, unique=True)
    source_review_state_version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempt_count = models.PositiveSmallIntegerField(default=0)
    payload_sha256 = models.CharField(
        max_length=64,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9a-f]{64}$",
                message="payload_sha256 must be lowercase SHA-256 hex",
            )
        ],
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=80, blank=True)
    provider_calls = models.PositiveSmallIntegerField(null=True, blank=True)
    context_synthesis_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )
    fallback_reason = models.CharField(max_length=40, null=True, blank=True)
    handoff_delivery_scheduled = models.BooleanField(null=True, blank=True)
    idempotent_replay = models.BooleanField(null=True, blank=True)

    class Meta:
        db_table = "support_human_review_resume_dispatch"
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="ix_hreview_resume_pending",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(source_review_state_version=2),
                name="ck_hreview_resume_source_version",
            ),
            models.CheckConstraint(
                condition=Q(attempt_count__lte=1),
                name="ck_hreview_resume_one_attempt",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="PENDING",
                        attempt_count=0,
                        payload_sha256="",
                        started_at__isnull=True,
                        completed_at__isnull=True,
                        failure_code="",
                        provider_calls__isnull=True,
                        context_synthesis_status__isnull=True,
                        fallback_reason__isnull=True,
                        handoff_delivery_scheduled__isnull=True,
                        idempotent_replay__isnull=True,
                    )
                    | Q(
                        status="DISPATCHING",
                        attempt_count=1,
                        payload_sha256__gt="",
                        started_at__isnull=False,
                        completed_at__isnull=True,
                        failure_code="",
                        provider_calls__isnull=True,
                        context_synthesis_status__isnull=True,
                        fallback_reason__isnull=True,
                        handoff_delivery_scheduled__isnull=True,
                        idempotent_replay__isnull=True,
                    )
                    | Q(
                        status="SUCCEEDED",
                        attempt_count=1,
                        payload_sha256__gt="",
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        failure_code="",
                        provider_calls__in=[0, 1],
                        context_synthesis_status__in=[
                            "SUCCEEDED",
                            "FALLBACK",
                            "UNAVAILABLE",
                        ],
                        handoff_delivery_scheduled__isnull=False,
                        idempotent_replay__isnull=False,
                    )
                    | Q(
                        status="FAILED_PRE_SEND",
                        attempt_count=0,
                        payload_sha256="",
                        started_at__isnull=True,
                        completed_at__isnull=False,
                        failure_code__gt="",
                        provider_calls__isnull=True,
                        context_synthesis_status__isnull=True,
                        fallback_reason__isnull=True,
                        handoff_delivery_scheduled__isnull=True,
                        idempotent_replay__isnull=True,
                    )
                    | Q(
                        status="OUTCOME_UNKNOWN",
                        attempt_count=1,
                        payload_sha256__gt="",
                        started_at__isnull=False,
                        completed_at__isnull=False,
                        failure_code__gt="",
                        provider_calls__isnull=True,
                        context_synthesis_status__isnull=True,
                        fallback_reason__isnull=True,
                        handoff_delivery_scheduled__isnull=True,
                        idempotent_replay__isnull=True,
                    )
                ),
                name="ck_hreview_resume_dispatch_state",
            ),
            models.CheckConstraint(
                condition=(
                    Q(fallback_reason__isnull=True)
                    | Q(context_synthesis_status="FALLBACK")
                ),
                name="ck_hreview_resume_fallback_state",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(context_synthesis_status="FALLBACK")
                    | Q(fallback_reason__isnull=False)
                ),
                name="ck_hreview_resume_fallback_reason",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(context_synthesis_status="SUCCEEDED")
                    | Q(provider_calls=1, fallback_reason__isnull=True)
                ),
                name="ck_hreview_resume_provider_success",
            ),
        ]
