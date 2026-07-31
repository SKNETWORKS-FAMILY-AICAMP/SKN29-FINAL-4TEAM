"""Reviewed document chunks used by keyword and vector retrieval."""

from __future__ import annotations

import re
import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.evidence.models.document_page import DocumentPage
from common.models.base import TimestampedModel


SHA256_PATTERN = r"^[0-9a-f]{64}$"


class IsJSONArray(models.Func):
    """Check the top-level JSON value without sacrificing SQLite tests."""

    output_field = models.BooleanField()

    def as_postgresql(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="jsonb_typeof(%(expressions)s) = 'array'",
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_TYPE(%(expressions)s) = 'array'",
            **extra_context,
        )


class IsJSONObject(models.Func):
    """Check that a JSON value is an object on supported databases."""

    output_field = models.BooleanField()

    def as_postgresql(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="jsonb_typeof(%(expressions)s) = 'object'",
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_TYPE(%(expressions)s) = 'object'",
            **extra_context,
        )


class SimpleSearchVector(models.Func):
    """Generate a simple-config tsvector with a SQLite-safe equivalent."""

    output_field = SearchVectorField()

    def as_postgresql(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template=(
                "to_tsvector('simple'::regconfig, "
                "COALESCE(%(expressions)s, ''))"
            ),
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="COALESCE(%(expressions)s, '')",
            **extra_context,
        )


class DocumentChunk(TimestampedModel):
    """Store one immutable chunking-version slice of a reviewed page."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    page = models.ForeignKey(
        DocumentPage,
        on_delete=models.PROTECT,
        related_name="chunks",
        db_column="page_id",
        db_index=False,
    )
    chunk_no = models.IntegerField()
    # CHUNK_TYPE has no canonical YAML contract yet.
    chunk_type_code = models.CharField(
        max_length=40,
        default="PARAGRAPH",
    )
    section_path = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    chunk_text = models.TextField()
    chunk_text_sha256 = models.CharField(max_length=64)
    start_offset = models.IntegerField(null=True, blank=True)
    end_offset = models.IntegerField(null=True, blank=True)
    token_count = models.IntegerField(null=True, blank=True)
    tokenizer_name = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )
    tokenizer_version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    symptom_tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    search_vector = models.GeneratedField(
        expression=SimpleSearchVector(F("chunk_text")),
        output_field=SearchVectorField(),
        db_persist=True,
    )
    chunking_version = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "knowledge_document_chunk"
        constraints = [
            models.UniqueConstraint(
                fields=["page", "chunk_no", "chunking_version"],
                name="ux_document_chunk_version",
            ),
            models.UniqueConstraint(
                fields=["id", "chunk_text_sha256"],
                name="ux_document_chunk_id_hash",
            ),
            models.UniqueConstraint(
                fields=["page", "chunk_no"],
                condition=Q(is_active=True),
                name="ux_document_chunk_active_position",
            ),
            models.CheckConstraint(
                condition=Q(chunk_no__gt=0),
                name="ck_document_chunk_no",
            ),
            models.CheckConstraint(
                condition=Q(chunk_text__regex=r"\S"),
                name="ck_document_chunk_text",
            ),
            models.CheckConstraint(
                condition=Q(
                    chunk_text_sha256__regex=SHA256_PATTERN
                ),
                name="ck_document_chunk_hash",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        start_offset__isnull=True,
                        end_offset__isnull=True,
                    )
                    | Q(
                        start_offset__isnull=False,
                        end_offset__isnull=False,
                        start_offset__gte=0,
                        end_offset__gt=F("start_offset"),
                    )
                ),
                name="ck_document_chunk_offsets",
            ),
            models.CheckConstraint(
                condition=(
                    Q(token_count__isnull=True)
                    | Q(token_count__gte=0)
                ),
                name="ck_document_chunk_token_count",
            ),
            models.CheckConstraint(
                condition=(
                    IsJSONArray(F("symptom_tags"))
                    & IsJSONObject(F("metadata"))
                ),
                name="ck_document_chunk_json",
            ),
        ]
        indexes = [
            models.Index(
                fields=["page", "is_active"],
                name="ix_document_chunk_active",
            ),
            GinIndex(
                fields=["search_vector"],
                name="ix_document_chunk_fts",
            ),
        ]

    def clean(self) -> None:
        """Mirror portable constraints before persistence."""

        super().clean()
        errors: dict[str, str] = {}

        if self.chunk_no is not None and self.chunk_no <= 0:
            errors["chunk_no"] = "chunk_no must be greater than zero."

        if not self.chunk_text or not self.chunk_text.strip():
            errors["chunk_text"] = "chunk_text cannot be blank."

        if re.fullmatch(
            SHA256_PATTERN,
            self.chunk_text_sha256 or "",
        ) is None:
            errors["chunk_text_sha256"] = (
                "chunk_text_sha256 must contain 64 lowercase "
                "hexadecimal characters."
            )

        offsets_are_empty = (
            self.start_offset is None and self.end_offset is None
        )
        offsets_are_valid = (
            self.start_offset is not None
            and self.end_offset is not None
            and self.start_offset >= 0
            and self.end_offset > self.start_offset
        )
        if not (offsets_are_empty or offsets_are_valid):
            errors["start_offset"] = (
                "Offsets must both be empty or form a positive range."
            )

        if self.token_count is not None and self.token_count < 0:
            errors["token_count"] = "token_count cannot be negative."

        if not isinstance(self.symptom_tags, list):
            errors["symptom_tags"] = "symptom_tags must be a JSON array."
        if not isinstance(self.metadata, dict):
            errors["metadata"] = "metadata must be a JSON object."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.page.document.document_code} "
            f"page {self.page.page_no} chunk {self.chunk_no}"
        )
