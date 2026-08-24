"""Traceable evidence snapshots attached to one support result."""

from __future__ import annotations

import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.evidence.models.document_chunk import SHA256_PATTERN
from common.models.base import TimestampedModel


class IsNonEmptyJSONArray(models.Func):
    """Check for a non-empty top-level array on PostgreSQL and SQLite."""

    output_field = models.BooleanField()

    def as_postgresql(self, compiler, connection, **extra_context):
        expression_sql, expression_params = compiler.compile(
            self.source_expressions[0]
        )
        return (
            "CASE WHEN jsonb_typeof({expression}) = 'array' "
            "THEN jsonb_array_length({expression}) > 0 "
            "ELSE FALSE END".format(expression=expression_sql),
            [*expression_params, *expression_params],
        )

    def as_sqlite(self, compiler, connection, **extra_context):
        return super().as_sql(
            compiler,
            connection,
            template=(
                "CASE WHEN JSON_TYPE(%(expressions)s) = 'array' "
                "THEN JSON_ARRAY_LENGTH(%(expressions)s) > 0 "
                "ELSE 0 END"
            ),
            **extra_context,
        )


def _is_nonblank(field_name: str) -> Q:
    """Build a portable non-whitespace check for required text."""

    return Q(**{f"{field_name}__regex": r".*\S.*"})


class EvidenceLink(TimestampedModel):
    """Preserve the exact evidence used by one downstream work result."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="inquiry_id",
        db_index=False,
    )
    guidance = models.ForeignKey(
        "inquiries.Guidance",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="guidance_id",
        db_index=False,
        null=True,
        blank=True,
    )
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="consultation_id",
        db_index=False,
        null=True,
        blank=True,
    )
    handoff_report = models.ForeignKey(
        "visits.HandoffReport",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="handoff_report_id",
        db_index=False,
        null=True,
        blank=True,
    )
    ai_run = models.ForeignKey(
        "audit.AIRun",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="ai_run_id",
        db_index=False,
        null=True,
        blank=True,
    )
    chunk = models.ForeignKey(
        "evidence.DocumentChunk",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="chunk_id",
        db_index=False,
    )
    retrieval_hit = models.ForeignKey(
        "audit.AIRetrievalHit",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="retrieval_hit_id",
        db_index=False,
        null=True,
        blank=True,
    )
    retrieval_run = models.ForeignKey(
        "audit.AIRetrievalRun",
        on_delete=models.PROTECT,
        related_name="evidence_links",
        db_column="retrieval_run_id",
        db_index=False,
        null=True,
        blank=True,
    )
    # EVIDENCE_SELECTION_ORIGIN and EVIDENCE_ROLE do not yet have
    # approved canonical YAML contracts. Preserve their physical defaults
    # while keeping the stored values open.
    selection_origin_code = models.CharField(
        max_length=40,
        default="AUTO_RETRIEVAL",
    )
    evidence_role_code = models.CharField(
        max_length=40,
        default="SUPPORTING",
    )
    display_order = models.SmallIntegerField(default=1)
    citation_label = models.CharField(max_length=200)
    document_code_snapshot = models.CharField(max_length=80)
    document_title_snapshot = models.CharField(max_length=300)
    source_org_snapshot = models.CharField(max_length=150)
    revision_label_snapshot = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )
    official_source_url_snapshot = models.CharField(max_length=1000)
    document_sha256_snapshot = models.CharField(max_length=64)
    evidence_summary = models.TextField()
    cited_text_snapshot = models.TextField()
    page_no_snapshot = models.IntegerField()
    section_snapshot = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    product_model_codes_snapshot = models.JSONField()
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="verified_evidence_links",
        db_column="verified_by_id",
        db_index=False,
        null=True,
        blank=True,
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "knowledge_evidence_link"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "guidance",
                    "chunk",
                    "evidence_role_code",
                ],
                condition=Q(guidance__isnull=False),
                name="ux_evidence_guidance_chunk",
            ),
            models.UniqueConstraint(
                fields=[
                    "consultation",
                    "chunk",
                    "evidence_role_code",
                ],
                condition=Q(consultation__isnull=False),
                name="ux_evidence_consultation_chunk",
            ),
            models.UniqueConstraint(
                fields=[
                    "handoff_report",
                    "chunk",
                    "evidence_role_code",
                ],
                condition=Q(handoff_report__isnull=False),
                name="ux_evidence_handoff_chunk",
            ),
            models.UniqueConstraint(
                fields=["guidance", "display_order"],
                condition=Q(guidance__isnull=False),
                name="ux_evidence_guidance_order",
            ),
            models.UniqueConstraint(
                fields=["consultation", "display_order"],
                condition=Q(consultation__isnull=False),
                name="ux_evidence_consultation_order",
            ),
            models.UniqueConstraint(
                fields=["handoff_report", "display_order"],
                condition=Q(handoff_report__isnull=False),
                name="ux_evidence_handoff_order",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        guidance__isnull=False,
                        consultation__isnull=True,
                        handoff_report__isnull=True,
                    )
                    | Q(
                        guidance__isnull=True,
                        consultation__isnull=False,
                        handoff_report__isnull=True,
                    )
                    | Q(
                        guidance__isnull=True,
                        consultation__isnull=True,
                        handoff_report__isnull=False,
                    )
                ),
                name="ck_evidence_exactly_one_target",
            ),
            models.CheckConstraint(
                condition=Q(display_order__gt=0),
                name="ck_evidence_display_order",
            ),
            models.CheckConstraint(
                condition=Q(page_no_snapshot__gt=0),
                name="ck_evidence_page_no",
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
                name="ck_evidence_verification",
            ),
            models.CheckConstraint(
                condition=Q(
                    document_sha256_snapshot__regex=SHA256_PATTERN
                ),
                name="ck_evidence_document_hash",
            ),
            models.CheckConstraint(
                condition=Q(
                    IsNonEmptyJSONArray(
                        F("product_model_codes_snapshot")
                    )
                ),
                name="ck_evidence_product_models",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        retrieval_hit__isnull=True,
                        retrieval_run__isnull=True,
                    )
                    | Q(
                        retrieval_hit__isnull=False,
                        retrieval_run__isnull=False,
                        ai_run__isnull=False,
                    )
                ),
                name="ck_evidence_retrieval_bundle",
            ),
            models.CheckConstraint(
                condition=_is_nonblank("selection_origin_code"),
                name="ck_evidence_selection_origin_nonempty",
            ),
            models.CheckConstraint(
                condition=_is_nonblank("evidence_role_code"),
                name="ck_evidence_role_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    _is_nonblank("citation_label")
                    & _is_nonblank("document_code_snapshot")
                    & _is_nonblank("document_title_snapshot")
                    & _is_nonblank("source_org_snapshot")
                    & _is_nonblank("official_source_url_snapshot")
                    & _is_nonblank("evidence_summary")
                    & _is_nonblank("cited_text_snapshot")
                ),
                name="ck_evidence_required_text",
            ),
        ]
        indexes = [
            models.Index(
                fields=["inquiry", "created_at"],
                name="ix_evidence_link_inquiry",
            ),
            models.Index(
                fields=["guidance", "inquiry"],
                name="ix_evidence_link_guidance",
            ),
            models.Index(
                fields=["consultation", "inquiry"],
                name="ix_evidence_link_consultation",
            ),
            models.Index(
                fields=["handoff_report", "inquiry"],
                name="ix_evidence_link_handoff",
            ),
            models.Index(
                fields=["chunk"],
                name="ix_evidence_link_chunk",
            ),
            models.Index(
                fields=["ai_run", "inquiry"],
                name="ix_evidence_link_ai_run",
            ),
            models.Index(
                fields=[
                    "retrieval_hit",
                    "retrieval_run",
                    "chunk",
                ],
                name="ix_evidence_link_retrieval_hit",
            ),
        ]

    def _parent_value(
        self,
        relation_name: str,
        value_name: str,
    ):
        """Read one parent value without relying on a cached relation."""

        relation_id = getattr(self, f"{relation_name}_id")
        if relation_id is None:
            return None
        parent_model = self._meta.get_field(
            relation_name
        ).remote_field.model
        return (
            parent_model._default_manager.filter(pk=relation_id)
            .values_list(value_name, flat=True)
            .first()
        )

    def clean(self) -> None:
        """Mirror portable and cross-row evidence invariants."""

        super().clean()
        errors: dict[str, str] = {}

        target_fields = (
            "guidance",
            "consultation",
            "handoff_report",
        )
        selected_targets = [
            field_name
            for field_name in target_fields
            if getattr(self, f"{field_name}_id") is not None
        ]
        if len(selected_targets) != 1:
            errors["guidance"] = (
                "Exactly one result target must be selected."
            )

        for relation_name in target_fields:
            parent_inquiry_id = self._parent_value(
                relation_name,
                "inquiry_id",
            )
            if (
                parent_inquiry_id is not None
                and self.inquiry_id is not None
                and parent_inquiry_id != self.inquiry_id
            ):
                errors[relation_name] = (
                    "The result target and evidence link must belong "
                    "to the same inquiry."
                )

        ai_run_inquiry_id = self._parent_value(
            "ai_run",
            "inquiry_id",
        )
        if (
            ai_run_inquiry_id is not None
            and self.inquiry_id is not None
            and ai_run_inquiry_id != self.inquiry_id
        ):
            errors["ai_run"] = (
                "The AI run and evidence link must belong to the "
                "same inquiry."
            )

        retrieval_bundle_is_empty = (
            self.retrieval_hit_id is None
            and self.retrieval_run_id is None
        )
        retrieval_bundle_is_complete = (
            self.retrieval_hit_id is not None
            and self.retrieval_run_id is not None
            and self.ai_run_id is not None
        )
        if not (
            retrieval_bundle_is_empty
            or retrieval_bundle_is_complete
        ):
            errors["retrieval_hit"] = (
                "retrieval_hit and retrieval_run must be empty "
                "together or accompanied by ai_run."
            )

        if self.retrieval_run_id is not None:
            run_context = self._parent_value(
                "retrieval_run",
                "ai_run_id",
            )
            run_inquiry_id = self._parent_value(
                "retrieval_run",
                "inquiry_id",
            )
            if (
                run_context is not None
                and run_context != self.ai_run_id
            ):
                errors["retrieval_run"] = (
                    "The retrieval run must belong to the referenced "
                    "AI run."
                )
            if (
                run_inquiry_id is not None
                and self.inquiry_id is not None
                and run_inquiry_id != self.inquiry_id
            ):
                errors["retrieval_run"] = (
                    "The retrieval run and evidence link must belong "
                    "to the same inquiry."
                )

        if self.retrieval_hit_id is not None:
            hit_run_id = self._parent_value(
                "retrieval_hit",
                "retrieval_run_id",
            )
            hit_chunk_id = self._parent_value(
                "retrieval_hit",
                "chunk_id",
            )
            hit_is_selected = self._parent_value(
                "retrieval_hit",
                "selected_for_answer",
            )
            if (
                hit_run_id is not None
                and hit_run_id != self.retrieval_run_id
            ):
                errors["retrieval_hit"] = (
                    "The retrieval hit must belong to the referenced "
                    "retrieval run."
                )
            if (
                hit_chunk_id is not None
                and self.chunk_id is not None
                and hit_chunk_id != self.chunk_id
            ):
                errors["retrieval_hit"] = (
                    "The retrieval hit must reference the evidence "
                    "chunk."
                )
            if hit_is_selected is False:
                errors["retrieval_hit"] = (
                    "Only a hit selected for the answer can be "
                    "linked as automatic evidence."
                )

        verification_bundle_is_complete = (
            self.is_verified is True
            and self.verified_by_id is not None
            and self.verified_at is not None
        )
        verification_bundle_is_empty = (
            self.is_verified is False
            and self.verified_by_id is None
            and self.verified_at is None
        )
        if not (
            verification_bundle_is_complete
            or verification_bundle_is_empty
        ):
            errors["is_verified"] = (
                "Verification flag, verifier, and timestamp must "
                "form a complete bundle."
            )

        if self.verified_by_id is not None:
            verifier_role = self._parent_value(
                "verified_by",
                "role_code",
            )
            if verifier_role not in {
                None,
                "CONSULTANT",
                "OPERATOR",
            }:
                errors["verified_by"] = (
                    "Evidence can be verified only by a CONSULTANT "
                    "or OPERATOR user."
                )

        if self.display_order is not None and self.display_order <= 0:
            errors["display_order"] = (
                "display_order must be greater than zero."
            )
        if (
            self.page_no_snapshot is not None
            and self.page_no_snapshot <= 0
        ):
            errors["page_no_snapshot"] = (
                "page_no_snapshot must be greater than zero."
            )
        if re.fullmatch(
            SHA256_PATTERN,
            self.document_sha256_snapshot or "",
        ) is None:
            errors["document_sha256_snapshot"] = (
                "document_sha256_snapshot must contain 64 lowercase "
                "hexadecimal characters."
            )
        if (
            not isinstance(self.product_model_codes_snapshot, list)
            or not self.product_model_codes_snapshot
        ):
            errors["product_model_codes_snapshot"] = (
                "product_model_codes_snapshot must be a non-empty "
                "JSON array."
            )

        required_text_fields = (
            "selection_origin_code",
            "evidence_role_code",
            "citation_label",
            "document_code_snapshot",
            "document_title_snapshot",
            "source_org_snapshot",
            "official_source_url_snapshot",
            "evidence_summary",
            "cited_text_snapshot",
        )
        for field_name in required_text_fields:
            if not str(getattr(self, field_name) or "").strip():
                errors[field_name] = (
                    f"{field_name} cannot be blank."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.public_id} {self.evidence_role_code} "
            f"for {self.inquiry_id}"
        )
