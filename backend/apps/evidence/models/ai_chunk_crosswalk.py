"""Verified AI canonical chunk to Backend evidence identity mapping."""

from __future__ import annotations

import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.evidence.models.document_chunk import SHA256_PATTERN, DocumentChunk
from apps.evidence.models.document_model_scope import DocumentModelScope
from apps.evidence.models.document_page import DocumentPage
from common.models.base import TimestampedModel


CANONICAL_CHUNK_ID_PATTERN = r"^(?:RAG|CHILD)-[A-Z0-9]+(?:-[A-Z0-9]+)*$"


class AIChunkCrosswalk(TimestampedModel):
    """Bind one AI canonical chunk ID to one reviewed Backend chunk."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    canonical_chunk_id = models.CharField(max_length=160, unique=True)
    chunk = models.OneToOneField(
        DocumentChunk,
        on_delete=models.PROTECT,
        related_name="ai_crosswalk",
        db_column="chunk_id",
    )
    model_scope = models.ForeignKey(
        DocumentModelScope,
        on_delete=models.PROTECT,
        related_name="ai_chunk_crosswalks",
        db_column="model_scope_id",
    )
    manifest_schema_version = models.CharField(max_length=40)
    identity_manifest_sha256 = models.CharField(max_length=64)
    canonical_verification_status = models.CharField(max_length=60)
    source_file_sha256 = models.CharField(max_length=64)
    chunk_text_sha256 = models.CharField(max_length=64)
    embedding_model = models.CharField(max_length=120)
    embedding_model_version = models.CharField(max_length=80)
    index_version = models.CharField(max_length=40)
    chunk_set_sha256 = models.CharField(max_length=64)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_ai_chunk_crosswalks",
        db_column="verified_by_id",
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        db_table = "knowledge_ai_chunk_crosswalk"
        constraints = [
            models.CheckConstraint(
                condition=Q(canonical_chunk_id__regex=CANONICAL_CHUNK_ID_PATTERN),
                name="ck_ai_crosswalk_canonical_id",
            ),
            models.CheckConstraint(
                condition=Q(identity_manifest_sha256__regex=SHA256_PATTERN),
                name="ck_ai_crosswalk_manifest_hash",
            ),
            models.CheckConstraint(
                condition=Q(source_file_sha256__regex=SHA256_PATTERN),
                name="ck_ai_crosswalk_source_hash",
            ),
            models.CheckConstraint(
                condition=Q(chunk_text_sha256__regex=SHA256_PATTERN),
                name="ck_ai_crosswalk_chunk_hash",
            ),
            models.CheckConstraint(
                condition=Q(chunk_set_sha256__regex=SHA256_PATTERN),
                name="ck_ai_crosswalk_set_hash",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        is_verified=True,
                        verified_by__isnull=False,
                        verified_at__isnull=False,
                    )
                    | Q(
                        is_verified=False,
                        verified_by__isnull=True,
                        verified_at__isnull=True,
                    )
                ),
                name="ck_ai_crosswalk_verified_bundle",
            ),
            models.CheckConstraint(
                condition=Q(is_active=False) | Q(is_verified=True),
                name="ck_ai_crosswalk_active_verified",
            ),
        ]
        indexes = [
            models.Index(
                fields=["is_active", "is_verified"],
                name="ix_ai_crosswalk_active",
            ),
            models.Index(
                fields=["embedding_model", "embedding_model_version"],
                name="ix_ai_crosswalk_embedding",
            ),
        ]

    def clean(self) -> None:
        """Validate portable identity and official-document invariants."""

        super().clean()
        errors: dict[str, str] = {}
        if re.fullmatch(CANONICAL_CHUNK_ID_PATTERN, self.canonical_chunk_id or "") is None:
            errors["canonical_chunk_id"] = (
                "canonical_chunk_id must use an approved RAG-* or CHILD-* format."
            )

        for field in (
            "identity_manifest_sha256",
            "source_file_sha256",
            "chunk_text_sha256",
            "chunk_set_sha256",
        ):
            value = getattr(self, field, "")
            if re.fullmatch(SHA256_PATTERN, value or "") is None:
                errors[field] = "SHA-256 values must contain 64 lowercase hexadecimal characters."

        verified_bundle = self.verified_by_id is not None and self.verified_at is not None
        if self.is_verified != verified_bundle:
            errors["is_verified"] = (
                "Verification flag, verifier, and timestamp must be set together."
            )
        if self.is_active and not self.is_verified:
            errors["is_active"] = "Only a verified crosswalk can be active."

        if self.chunk_id is not None and self.model_scope_id is not None:
            if self.chunk.page.document_id != self.model_scope.document_id:
                errors["model_scope"] = "Chunk and model scope must reference the same document."
            if self.source_file_sha256 != self.chunk.page.document.sha256_hash:
                errors["source_file_sha256"] = (
                    "Crosswalk source hash must match the official document."
                )
            if self.chunk_text_sha256 != self.chunk.chunk_text_sha256:
                errors["chunk_text_sha256"] = "Crosswalk chunk hash must match the Backend chunk."

        for field in (
            "manifest_schema_version",
            "canonical_verification_status",
            "embedding_model",
            "embedding_model_version",
            "index_version",
        ):
            if not str(getattr(self, field, "") or "").strip():
                errors[field] = f"{field} cannot be blank."

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.canonical_chunk_id} -> {self.chunk.public_id}"


class AIChunkCrosswalkPage(TimestampedModel):
    """Preserve every reviewed source page behind a canonical AI chunk."""

    id = models.BigAutoField(primary_key=True)
    crosswalk = models.ForeignKey(
        AIChunkCrosswalk,
        on_delete=models.CASCADE,
        related_name="source_pages",
        db_column="crosswalk_id",
    )
    page = models.ForeignKey(
        DocumentPage,
        on_delete=models.PROTECT,
        related_name="ai_chunk_crosswalk_pages",
        db_column="page_id",
    )
    display_order = models.PositiveIntegerField()

    class Meta:
        db_table = "knowledge_ai_chunk_crosswalk_page"
        constraints = [
            models.UniqueConstraint(
                fields=["crosswalk", "page"],
                name="ux_ai_crosswalk_page",
            ),
            models.UniqueConstraint(
                fields=["crosswalk", "display_order"],
                name="ux_ai_crosswalk_page_order",
            ),
            models.CheckConstraint(
                condition=Q(display_order__gt=0),
                name="ck_ai_crosswalk_page_order",
            ),
        ]
        ordering = ["display_order", "id"]

    def clean(self) -> None:
        """Reject source pages that do not belong to the mapped document."""

        super().clean()
        errors: dict[str, str] = {}
        if self.display_order is not None and self.display_order <= 0:
            errors["display_order"] = "display_order must be greater than zero."
        if self.crosswalk_id is not None and self.page_id is not None:
            if self.page.document_id != self.crosswalk.chunk.page.document_id:
                errors["page"] = "Every crosswalk page must belong to the mapped document."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.crosswalk.canonical_chunk_id} page {self.page.page_no}"
