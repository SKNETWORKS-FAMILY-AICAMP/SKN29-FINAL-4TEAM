"""Versioned customer guidance for a support inquiry."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


def _is_required_text_nonempty(field_name: str) -> Q:
    """Build a portable non-whitespace database check."""

    return Q(**{f"{field_name}__regex": r".*\S.*"})


class Guidance(TimestampedModel):
    """Persist one reviewable guidance version for an inquiry."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="guidance_versions",
        db_column="inquiry_id",
        db_index=False,
    )
    guidance_version = models.IntegerField(default=1)
    # GUIDANCE_REVIEW_STATUS and EVIDENCE_SUFFICIENCY canonical YAML
    # contracts do not yet exist. Keep both fields open until approval.
    review_status_code = models.CharField(
        max_length=40,
        default="PENDING",
    )
    title = models.CharField(max_length=200)
    summary_text = models.TextField()
    safety_notice = models.TextField(null=True, blank=True)
    evidence_sufficiency_code = models.CharField(max_length=40)
    requires_consultation = models.BooleanField(default=False)
    generated_by_ai_run = models.ForeignKey(
        "audit.AIRun",
        on_delete=models.PROTECT,
        related_name="generated_guidance_versions",
        db_column="generated_by_ai_run_id",
        db_index=False,
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_guidance_versions",
        db_column="reviewed_by_id",
        db_index=False,
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "support_guidance"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "guidance_version"],
                name="ux_guidance_version",
            ),
            models.UniqueConstraint(
                fields=["id", "inquiry"],
                name="ux_guidance_id_inquiry",
            ),
            models.CheckConstraint(
                condition=Q(guidance_version__gt=0),
                name="ck_guidance_version_positive",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty(
                    "review_status_code"
                ),
                name="ck_guidance_review_status_nonempty",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty("title"),
                name="ck_guidance_title_nonempty",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty("summary_text"),
                name="ck_guidance_summary_nonempty",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty(
                    "evidence_sufficiency_code"
                ),
                name="ck_guidance_evidence_code_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        reviewed_by__isnull=True,
                        reviewed_at__isnull=True,
                    )
                    | Q(
                        reviewed_by__isnull=False,
                        reviewed_at__isnull=False,
                    )
                ),
                name="ck_guidance_review_pair",
            ),
        ]
        indexes = [
            models.Index(
                fields=["review_status_code", "created_at"],
                condition=Q(review_status_code="PENDING"),
                name="ix_guidance_review_queue",
            ),
            models.Index(
                fields=["generated_by_ai_run", "inquiry"],
                name="ix_guidance_ai_run",
            ),
        ]

    def clean(self) -> None:
        """Validate the cross-row AI generation policy."""

        super().clean()
        if self.generated_by_ai_run_id is None:
            return

        ai_run = self.generated_by_ai_run
        if (
            self.inquiry_id is not None
            and ai_run.inquiry_id != self.inquiry_id
        ):
            raise ValidationError(
                {
                    "generated_by_ai_run": (
                        "The guidance and AI run must belong to the "
                        "same inquiry."
                    )
                }
            )

        if (
            ai_run.task_type_code != "GENERATE_GUIDANCE"
            or ai_run.schema_validation_status_code != "PASSED"
        ):
            raise ValidationError(
                {
                    "generated_by_ai_run": (
                        "AI-generated guidance can use only a "
                        "schema-validated GENERATE_GUIDANCE AI run."
                    )
                }
            )

    def __str__(self) -> str:
        return (
            f"{self.public_id} v{self.guidance_version} "
            f"({self.review_status_code})"
        )
