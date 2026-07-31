"""Knowledge-pipeline data-quality issue persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.evidence.models.document_chunk import (
    DocumentChunk,
    IsJSONObject,
)
from apps.evidence.models.document_page import DocumentPage
from apps.evidence.models.ingestion_batch import IngestionBatch
from apps.evidence.models.source_document import SourceDocument
from common.models.base import TimestampedModel


class DataQualityIssue(TimestampedModel):
    """Track one quality failure against exactly one knowledge target."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    ingestion_batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.PROTECT,
        related_name="data_quality_issues",
        db_column="ingestion_batch_id",
        db_index=False,
        null=True,
        blank=True,
    )
    document = models.ForeignKey(
        SourceDocument,
        on_delete=models.PROTECT,
        related_name="data_quality_issues",
        db_column="document_id",
        db_index=False,
        null=True,
        blank=True,
    )
    page = models.ForeignKey(
        DocumentPage,
        on_delete=models.PROTECT,
        related_name="data_quality_issues",
        db_column="page_id",
        db_index=False,
        null=True,
        blank=True,
    )
    chunk = models.ForeignKey(
        DocumentChunk,
        on_delete=models.PROTECT,
        related_name="data_quality_issues",
        db_column="chunk_id",
        db_index=False,
        null=True,
        blank=True,
    )
    # These code groups have no approved canonical YAML contracts yet.
    issue_type_code = models.CharField(max_length=40)
    validation_rule_code = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    validator_version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    severity_code = models.CharField(
        max_length=40,
        default="ERROR",
    )
    issue_message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(
        max_length=40,
        default="OPEN",
    )
    detected_at = models.DateTimeField(default=timezone.now)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="resolved_data_quality_issues",
        db_column="resolved_by_id",
        db_index=False,
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_data_quality_issue"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        document__isnull=False,
                        page__isnull=True,
                        chunk__isnull=True,
                    )
                    | Q(
                        document__isnull=True,
                        page__isnull=False,
                        chunk__isnull=True,
                    )
                    | Q(
                        document__isnull=True,
                        page__isnull=True,
                        chunk__isnull=False,
                    )
                ),
                name="ck_quality_issue_target",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        resolved_by__isnull=True,
                        resolved_at__isnull=True,
                        resolution_note__isnull=True,
                    )
                    | Q(
                        resolved_by__isnull=False,
                        resolved_at__isnull=False,
                        resolution_note__isnull=False,
                    )
                ),
                name="ck_quality_issue_resolution_bundle",
            ),
            models.CheckConstraint(
                condition=IsJSONObject(F("details")),
                name="ck_quality_issue_details_object",
            ),
        ]
        indexes = [
            models.Index(
                fields=["severity_code", "detected_at"],
                condition=Q(
                    status_code__in=["OPEN", "IN_REVIEW"]
                ),
                name="ix_quality_issue_open",
            ),
            models.Index(
                fields=["document", "page"],
                name="ix_quality_issue_document",
            ),
            models.Index(
                fields=["page"],
                name="ix_quality_issue_page",
            ),
            models.Index(
                fields=["chunk"],
                name="ix_quality_issue_chunk",
            ),
        ]

    def clean(self) -> None:
        """Mirror portable structural constraints before persistence."""

        super().clean()
        errors: dict[str, str] = {}

        target_count = sum(
            target_id is not None
            for target_id in (
                self.document_id,
                self.page_id,
                self.chunk_id,
            )
        )
        if target_count != 1:
            errors["document"] = (
                "Exactly one of document, page, or chunk must be set."
            )

        if not isinstance(self.details, dict):
            errors["details"] = "details must be a JSON object."

        resolution_values = (
            self.resolved_by_id,
            self.resolved_at,
            self.resolution_note,
        )
        resolution_count = sum(
            value is not None for value in resolution_values
        )
        if resolution_count not in (0, len(resolution_values)):
            errors["resolved_by"] = (
                "resolved_by, resolved_at, and resolution_note must "
                "be set or cleared together."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.issue_type_code} "
            f"({self.severity_code}/{self.status_code})"
        )
