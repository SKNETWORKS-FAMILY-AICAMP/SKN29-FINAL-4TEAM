"""Official-document applicability to supported product models."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.evidence.models.source_document import SourceDocument
from common.models.base import TimestampedModel


class DocumentModelScope(TimestampedModel):
    """Record a human-verified document-to-product applicability range."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    document = models.ForeignKey(
        SourceDocument,
        on_delete=models.PROTECT,
        related_name="product_model_scopes",
        db_column="document_id",
        db_index=False,
    )
    product_model = models.ForeignKey(
        "products.ProductModel",
        on_delete=models.PROTECT,
        related_name="document_scopes",
        db_column="product_model_id",
        db_index=False,
    )
    applicable_from = models.DateField(null=True, blank=True)
    applicable_to = models.DateField(null=True, blank=True)
    applicability_note = models.TextField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_document_model_scopes",
        db_column="verified_by_id",
        db_index=False,
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_document_model_scope"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "product_model"],
                name="ux_document_model_scope",
            ),
            models.CheckConstraint(
                condition=(
                    Q(applicable_to__isnull=True)
                    | Q(applicable_from__isnull=True)
                    | Q(applicable_to__gte=F("applicable_from"))
                ),
                name="ck_model_scope_period",
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
                name="ck_model_scope_verification",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "product_model",
                    "is_verified",
                    "applicable_from",
                    "applicable_to",
                ],
                name="ix_model_scope_model",
            ),
        ]

    def clean(self) -> None:
        """Mirror database invariants for pre-save validation."""

        super().clean()
        errors: dict[str, str] = {}

        if (
            self.applicable_from is not None
            and self.applicable_to is not None
            and self.applicable_to < self.applicable_from
        ):
            errors["applicable_to"] = (
                "applicable_to must be on or after applicable_from."
            )

        verification_is_complete = (
            self.verified_by_id is not None
            and self.verified_at is not None
        )
        if self.is_verified != verification_is_complete:
            errors["is_verified"] = (
                "Verification flag, verifier, and verified timestamp must "
                "be set or cleared together."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.document.document_code} -> "
            f"{self.product_model.model_code}"
        )
