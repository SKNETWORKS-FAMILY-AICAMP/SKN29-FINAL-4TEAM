"""Persist one sanitized AI-to-consultant handoff before consultation creation."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.audit.models import AIRun
from apps.inquiries.models import Inquiry
from common.models.base import TimestampedModel


SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ConsultationHandoff(TimestampedModel):
    """Append-only, sanitized bridge from one AI run to a consultation."""

    class DataClassification(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic"
        OPERATIONAL = "operational", "Operational"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    inquiry = models.ForeignKey(
        Inquiry,
        on_delete=models.PROTECT,
        related_name="consultation_handoffs",
        db_column="inquiry_id",
    )
    ai_run = models.OneToOneField(
        AIRun,
        on_delete=models.PROTECT,
        related_name="consultation_handoff",
        db_column="ai_run_id",
    )
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.PROTECT,
        related_name="ai_handoffs",
        db_column="consultation_id",
        null=True,
        blank=True,
    )
    ai_request_id = models.CharField(max_length=128)
    correlation_id = models.UUIDField()
    model_code_snapshot = models.CharField(max_length=100)
    product_family_snapshot = models.CharField(max_length=100)
    schema_version = models.CharField(max_length=30)
    sanitized_payload = models.JSONField(default=dict)
    payload_sha256 = models.CharField(max_length=64)
    ai_draft_summary = models.TextField()
    data_classification = models.CharField(
        max_length=40,
        choices=DataClassification.choices,
        default=DataClassification.OPERATIONAL,
    )

    class Meta:
        db_table = "support_consultation_handoff"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "ai_request_id"],
                name="ux_handoff_inquiry_ai_request",
            ),
            models.CheckConstraint(
                condition=~Q(ai_request_id=""),
                name="ck_handoff_ai_request_nonempty",
            ),
            models.CheckConstraint(
                condition=Q(payload_sha256__regex=SHA256_PATTERN),
                name="ck_handoff_payload_sha256",
            ),
            models.CheckConstraint(
                condition=~Q(ai_draft_summary=""),
                name="ck_handoff_draft_nonempty",
            ),
            models.CheckConstraint(
                condition=Q(
                    data_classification__in=["synthetic", "operational"]
                ),
                name="ck_handoff_data_class",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "-created_at"],
                name="ix_handoff_inquiry_created",
            ),
            models.Index(
                fields=["correlation_id"],
                name="ix_handoff_correlation",
            ),
        ]

    def clean(self) -> None:
        """Keep every stored identity on the same Inquiry and AI run."""

        super().clean()
        errors: dict[str, str] = {}
        if self.ai_run_id is not None:
            if self.inquiry_id != self.ai_run.inquiry_id:
                errors["ai_run"] = "AI run and handoff must use the same inquiry."
            if self.correlation_id != self.ai_run.correlation_id:
                errors["correlation_id"] = (
                    "AI run and handoff must use the same correlation ID."
                )
            if self.ai_request_id != self.ai_run.idempotency_key:
                errors["ai_request_id"] = (
                    "AI request ID must match the persisted AI run identity."
                )
        if (
            self.consultation_id is not None
            and self.consultation.inquiry_id != self.inquiry_id
        ):
            errors["consultation"] = (
                "Consultation and handoff must use the same inquiry."
            )
        if self.inquiry_id is not None:
            expected_model = self.inquiry.subscription.product_model.model_code
            if self.model_code_snapshot != expected_model:
                errors["model_code_snapshot"] = (
                    "Handoff model must match the inquiry subscription product."
                )
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.ai_request_id} -> {self.inquiry.public_id}"
