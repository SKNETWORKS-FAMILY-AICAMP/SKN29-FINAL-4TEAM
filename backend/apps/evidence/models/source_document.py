"""Official source-document lineage and integrity persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.evidence.models.ingestion_batch import IngestionBatch
from common.models.base import TimestampedModel
from common.models.soft_delete import SoftDeleteModel


class SourceDocument(TimestampedModel, SoftDeleteModel):
    """Preserve one immutable official-document revision and its lineage."""

    class DatasetScope(models.TextChoices):
        MVP = "MVP", "MVP"
        EXPANSION = "EXPANSION", "Expansion"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    ingestion_batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.PROTECT,
        related_name="source_documents",
        db_column="ingestion_batch_id",
        db_index=False,
    )
    document_code = models.CharField(max_length=80)
    dataset_scope_code = models.CharField(
        max_length=30,
        choices=DatasetScope.choices,
        default=DatasetScope.MVP,
    )
    supersedes_document = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="superseding_documents",
        db_column="supersedes_document_id",
        db_index=False,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=300)
    source_org = models.CharField(max_length=150)
    document_type_code = models.CharField(max_length=40)
    official_source_url = models.CharField(max_length=1000)
    usage_terms_url = models.CharField(max_length=1000)
    license_note = models.TextField()
    original_file_uri = models.CharField(max_length=1000)
    file_name = models.CharField(
        max_length=300,
        null=True,
        blank=True,
    )
    mime_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    sha256_hash = models.CharField(max_length=64)
    revision_label = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    published_on = models.DateField(null=True, blank=True)
    collected_at = models.DateTimeField(default=timezone.now)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="collected_source_documents",
        db_column="collected_by_id",
        db_index=False,
    )
    status_code = models.CharField(
        max_length=40,
        default="COLLECTED",
    )
    parser_version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="deleted_source_documents",
        db_column="deleted_by_id",
        db_index=False,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "knowledge_source_document"
        constraints = [
            models.UniqueConstraint(
                fields=["document_code"],
                name="ux_source_document_code",
            ),
            models.UniqueConstraint(
                fields=["sha256_hash"],
                name="ux_source_document_sha256",
            ),
            models.UniqueConstraint(
                fields=["id", "dataset_scope_code"],
                name="ux_source_document_id_scope",
            ),
            models.CheckConstraint(
                condition=Q(file_size_bytes__isnull=True)
                | Q(file_size_bytes__gte=0),
                name="ck_source_document_file_size",
            ),
            models.CheckConstraint(
                condition=Q(
                    sha256_hash__regex=r"^[0-9a-f]{64}$"
                ),
                name="ck_source_document_sha256",
            ),
            models.CheckConstraint(
                condition=Q(supersedes_document__isnull=True)
                | ~Q(supersedes_document=models.F("id")),
                name="ck_source_document_not_self_supersede",
            ),
            models.CheckConstraint(
                condition=(
                    Q(deleted_at__isnull=True, deleted_by__isnull=True)
                    | Q(
                        deleted_at__isnull=False,
                        deleted_by__isnull=False,
                    )
                ),
                name="ck_source_document_deleted_pair",
            ),
            models.CheckConstraint(
                condition=Q(
                    dataset_scope_code__in=["MVP", "EXPANSION"]
                ),
                name=(
                    "ck_knowledge_source_document_"
                    "dataset_scope_code_allowed"
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "document_type_code",
                    "status_code",
                    "-collected_at",
                ],
                name="ix_source_document_status",
            ),
            models.Index(
                fields=["official_source_url", "revision_label"],
                name="ix_source_document_revision",
            ),
            models.Index(
                fields=["supersedes_document"],
                name="ix_source_document_supersedes",
            ),
            models.Index(
                fields=["status_code", "-collected_at"],
                condition=Q(deleted_at__isnull=True),
                name="ix_source_doc_active_status",
            ),
            models.Index(
                fields=["ingestion_batch"],
                name="ix_source_document_batch",
            ),
        ]

    def clean(self) -> None:
        """Validate scope and soft-delete rules on every supported database."""

        super().clean()
        errors: dict[str, str] = {}

        if self.ingestion_batch_id is not None:
            batch_scope = (
                IngestionBatch.objects.filter(
                    pk=self.ingestion_batch_id
                )
                .values_list("dataset_scope_code", flat=True)
                .first()
            )
            if (
                batch_scope is not None
                and batch_scope != self.dataset_scope_code
            ):
                errors["dataset_scope_code"] = (
                    "Document scope must match its ingestion batch."
                )

        if self.supersedes_document_id is not None:
            superseded_scope = (
                type(self).objects.filter(
                    pk=self.supersedes_document_id
                )
                .values_list("dataset_scope_code", flat=True)
                .first()
            )
            if (
                superseded_scope is not None
                and superseded_scope != self.dataset_scope_code
            ):
                errors["supersedes_document"] = (
                    "A document can supersede only a revision in the "
                    "same dataset scope."
                )

        if (
            self.pk is not None
            and self.supersedes_document_id == self.pk
        ):
            errors["supersedes_document"] = (
                "A document cannot supersede itself."
            )

        if (self.deleted_at is None) != (self.deleted_by_id is None):
            errors["deleted_at"] = (
                "deleted_at and deleted_by must be set or cleared "
                "together."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.document_code} ({self.title})"
