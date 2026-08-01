"""Page-level extraction, review, and RAG eligibility persistence."""

from __future__ import annotations

import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.evidence.models.source_document import SourceDocument
from common.models.base import TimestampedModel


SHA256_PATTERN = r"^[0-9a-f]{64}$"


class DocumentPage(TimestampedModel):
    """Preserve one source-document page and its review evidence."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    document = models.ForeignKey(
        SourceDocument,
        on_delete=models.PROTECT,
        related_name="pages",
        db_column="document_id",
        db_index=False,
    )
    page_no = models.IntegerField()
    extracted_text = models.TextField(null=True, blank=True)
    text_sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )
    # Canonical PARSE_STATUS and REVIEW_STATUS YAML contracts do not yet
    # exist. Keep these as open codes and preserve only the approved defaults.
    parse_status_code = models.CharField(
        max_length=40,
        default="PENDING",
    )
    review_status_code = models.CharField(
        max_length=40,
        default="PENDING",
    )
    is_rag_eligible = models.BooleanField(default=False)
    exclusion_reason = models.TextField(null=True, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_document_pages",
        db_column="reviewer_id",
        db_index=False,
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_document_page"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "page_no"],
                name="ux_document_page_no",
            ),
            models.CheckConstraint(
                condition=Q(page_no__gt=0),
                name="ck_document_page_no",
            ),
            models.CheckConstraint(
                condition=(
                    Q(text_sha256__isnull=True)
                    | Q(text_sha256__regex=SHA256_PATTERN)
                ),
                name="ck_document_page_sha256",
            ),
            models.CheckConstraint(
                condition=(
                    Q(reviewer__isnull=True, reviewed_at__isnull=True)
                    | Q(
                        reviewer__isnull=False,
                        reviewed_at__isnull=False,
                    )
                ),
                name="ck_document_page_review_bundle",
            ),
            models.CheckConstraint(
                condition=(
                    Q(is_rag_eligible=False)
                    | Q(
                        parse_status_code="PARSED",
                        review_status_code="APPROVED",
                        extracted_text__isnull=False,
                        text_sha256__isnull=False,
                        reviewer__isnull=False,
                        reviewed_at__isnull=False,
                        exclusion_reason__isnull=True,
                    )
                ),
                name="ck_document_page_rag_eligibility",
            ),
        ]
        indexes = [
            models.Index(
                fields=["document", "page_no"],
                condition=Q(is_rag_eligible=True),
                name="ix_document_page_rag",
            ),
        ]

    def clean(self) -> None:
        """Mirror portable database invariants before persistence."""

        super().clean()
        errors: dict[str, str] = {}

        if self.page_no is not None and self.page_no <= 0:
            errors["page_no"] = "page_no must be greater than zero."

        if (
            self.text_sha256 is not None
            and re.fullmatch(SHA256_PATTERN, self.text_sha256) is None
        ):
            errors["text_sha256"] = (
                "text_sha256 must contain 64 lowercase hexadecimal "
                "characters when provided."
            )

        review_bundle_is_complete = (
            self.reviewer_id is not None and self.reviewed_at is not None
        )
        review_bundle_is_empty = (
            self.reviewer_id is None and self.reviewed_at is None
        )
        if not (review_bundle_is_complete or review_bundle_is_empty):
            errors["reviewer"] = (
                "reviewer and reviewed_at must be set or cleared together."
            )

        if self.is_rag_eligible:
            if self.parse_status_code != "PARSED":
                errors["parse_status_code"] = (
                    "RAG-eligible pages must have parse status PARSED."
                )
            if self.review_status_code != "APPROVED":
                errors["review_status_code"] = (
                    "RAG-eligible pages must have review status APPROVED."
                )
            if self.extracted_text is None:
                errors["extracted_text"] = (
                    "RAG-eligible pages must contain extracted text."
                )
            if self.text_sha256 is None:
                errors["text_sha256"] = (
                    "RAG-eligible pages must contain a text SHA-256."
                )
            if not review_bundle_is_complete:
                errors["reviewer"] = (
                    "RAG-eligible pages must contain a complete review bundle."
                )
            if self.exclusion_reason is not None:
                errors["exclusion_reason"] = (
                    "RAG-eligible pages cannot contain an exclusion reason."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.document.document_code} page {self.page_no}"
