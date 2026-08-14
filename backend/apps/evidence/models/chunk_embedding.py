"""Versioned pgvector embeddings for reviewed document chunks."""

from __future__ import annotations

import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from pgvector.django import VectorField

from apps.evidence.models.document_chunk import (
    DocumentChunk,
    SHA256_PATTERN,
)
from common.models.base import TimestampedModel


EMBEDDING_DIMENSION = 1024


class VectorDimensions(models.Func):
    """Return vector dimensions on PostgreSQL and SQLite test databases."""

    output_field = models.IntegerField()

    def as_postgresql(self, compiler, connection, **extra_context):
        # Constraint validation replaces F("embedding") with a bound value.
        # PostgreSQL then sees an untyped parameter and cannot choose between
        # vector_dims(vector) and vector_dims(halfvec).  The explicit cast
        # keeps both model.full_clean() and the database constraint strict.
        return super().as_sql(
            compiler,
            connection,
            template="vector_dims((%(expressions)s)::vector)",
            **extra_context,
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_ARRAY_LENGTH(%(expressions)s)",
            **extra_context,
        )


class ChunkEmbedding(TimestampedModel):
    """Store one fixed-model-version embedding for a reviewed chunk."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    chunk = models.ForeignKey(
        DocumentChunk,
        on_delete=models.PROTECT,
        related_name="embeddings",
        db_column="chunk_id",
        db_index=False,
    )
    embedding_model = models.CharField(max_length=120)
    embedding_model_version = models.CharField(max_length=80)
    embedding_dimension = models.PositiveIntegerField()
    source_text_sha256 = models.CharField(max_length=64)
    embedding = VectorField(dimensions=EMBEDDING_DIMENSION)
    embedded_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "knowledge_chunk_embedding"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "chunk",
                    "embedding_model",
                    "embedding_model_version",
                ],
                name="ux_chunk_embedding_model",
            ),
            models.CheckConstraint(
                condition=(
                    Q(embedding_dimension=EMBEDDING_DIMENSION)
                    & Q(
                        embedding_dimension=VectorDimensions(
                            F("embedding")
                        )
                    )
                ),
                name="ck_chunk_embedding_dimension",
            ),
            models.CheckConstraint(
                condition=Q(
                    source_text_sha256__regex=SHA256_PATTERN
                ),
                name="ck_chunk_embedding_source_hash",
            ),
            models.CheckConstraint(
                condition=Q(embedding_model__regex=r"\S"),
                name="ck_chunk_embedding_model_name",
            ),
            models.CheckConstraint(
                condition=Q(
                    embedding_model_version__regex=r"\S"
                ),
                name="ck_chunk_embedding_model_version",
            ),
        ]
        indexes = [
            models.Index(
                fields=["embedding_model", "is_active"],
                name="ix_chunk_embedding_active",
            ),
        ]

    def clean(self) -> None:
        """Mirror the fixed-dimension and source-hash contract."""

        super().clean()
        errors: dict[str, str] = {}

        if not self.embedding_model or not self.embedding_model.strip():
            errors["embedding_model"] = (
                "embedding_model cannot be blank."
            )
        if (
            not self.embedding_model_version
            or not self.embedding_model_version.strip()
        ):
            errors["embedding_model_version"] = (
                "embedding_model_version cannot be blank."
            )
        if self.embedding_dimension != EMBEDDING_DIMENSION:
            errors["embedding_dimension"] = (
                f"embedding_dimension must be {EMBEDDING_DIMENSION}."
            )
        if self.embedding is not None and (
            len(self.embedding) != EMBEDDING_DIMENSION
        ):
            errors["embedding"] = (
                f"embedding must contain {EMBEDDING_DIMENSION} values."
            )
        if re.fullmatch(
            SHA256_PATTERN,
            self.source_text_sha256 or "",
        ) is None:
            errors["source_text_sha256"] = (
                "source_text_sha256 must contain 64 lowercase "
                "hexadecimal characters."
            )
        if (
            self.chunk_id is not None
            and self.source_text_sha256
            and self.chunk.chunk_text_sha256
            != self.source_text_sha256
        ):
            errors["source_text_sha256"] = (
                "source_text_sha256 must match the referenced "
                "chunk_text_sha256."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.chunk_id}:"
            f"{self.embedding_model}@{self.embedding_model_version}"
        )
