"""Versioned technician handoff report persistence."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from common.models.base import TimestampedModel


class IsJSONArray(models.Func):
    """Return whether a JSON expression is an array on supported DBs."""

    output_field = models.BooleanField()

    def as_postgresql(
        self,
        compiler,
        connection,
        **extra_context,
    ):
        return super().as_sql(
            compiler,
            connection,
            template="jsonb_typeof(%(expressions)s) = 'array'",
            **extra_context,
        )

    def as_sqlite(
        self,
        compiler,
        connection,
        **extra_context,
    ):
        return super().as_sql(
            compiler,
            connection,
            template="JSON_TYPE(%(expressions)s) = 'array'",
            **extra_context,
        )


class HandoffReport(TimestampedModel):
    """Persist one version of a consultation-to-technician handoff."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.ForeignKey(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="handoff_reports",
        db_column="inquiry_id",
        db_index=False,
    )
    consultation = models.ForeignKey(
        "consultations.Consultation",
        on_delete=models.PROTECT,
        related_name="handoff_reports",
        db_column="consultation_id",
        db_index=False,
    )
    report_version = models.PositiveIntegerField(default=1)
    report_status_code = models.CharField(max_length=40)
    product_summary = models.TextField()
    symptom_summary = models.TextField()
    action_summary = models.TextField()
    risk_summary = models.TextField()
    evidence_summary = models.TextField(null=True, blank=True)
    priority_check_items = models.JSONField(
        default=list,
        blank=True,
    )
    ai_draft = models.TextField(null=True, blank=True)
    consultant_final = models.TextField(null=True, blank=True)
    generated_by_ai_run = models.ForeignKey(
        "audit.AIRun",
        on_delete=models.PROTECT,
        related_name="generated_handoff_reports",
        db_column="generated_by_ai_run_id",
        null=True,
        blank=True,
        db_index=False,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="confirmed_handoff_reports",
        db_column="confirmed_by_id",
        null=True,
        blank=True,
        db_index=False,
        limit_choices_to={"role_code": "CONSULTANT"},
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "support_handoff_report"
        constraints = [
            models.UniqueConstraint(
                fields=["inquiry", "report_version"],
                name="ux_handoff_report_version",
            ),
            models.UniqueConstraint(
                fields=["id", "inquiry"],
                name="ux_handoff_id_inquiry",
            ),
            models.CheckConstraint(
                condition=Q(report_version__gt=0),
                name="ck_handoff_report_version",
            ),
            models.CheckConstraint(
                condition=~Q(report_status_code=""),
                name="ck_handoff_status_nonempty",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        confirmed_by__isnull=True,
                        confirmed_at__isnull=True,
                    )
                    | Q(
                        confirmed_by__isnull=False,
                        confirmed_at__isnull=False,
                        consultant_final__isnull=False,
                    )
                ),
                name="ck_handoff_report_confirmation",
            ),
            models.CheckConstraint(
                condition=Q(
                    IsJSONArray(F("priority_check_items"))
                ),
                name="ck_handoff_priority_items_array",
            ),
        ]
        indexes = [
            models.Index(
                fields=["consultation", "inquiry"],
                name="ix_handoff_consultation",
            ),
            models.Index(
                fields=["report_status_code", "created_at"],
                name="ix_handoff_status",
            ),
            models.Index(
                fields=["generated_by_ai_run", "inquiry"],
                name="ix_handoff_ai_run",
            ),
        ]

    def clean(self) -> None:
        """Validate portable relationship and reviewer-role contracts."""

        super().clean()
        errors: dict[str, str] = {}

        if self.consultation_id is not None:
            consultation_model = self._meta.get_field(
                "consultation"
            ).remote_field.model
            consultation_inquiry_id = (
                consultation_model._default_manager.filter(
                    pk=self.consultation_id
                )
                .values_list("inquiry_id", flat=True)
                .first()
            )
            if (
                consultation_inquiry_id is not None
                and self.inquiry_id is not None
                and consultation_inquiry_id != self.inquiry_id
            ):
                errors["consultation"] = (
                    "The consultation and handoff report must belong "
                    "to the same inquiry."
                )

        if self.generated_by_ai_run_id is not None:
            ai_run_model = self._meta.get_field(
                "generated_by_ai_run"
            ).remote_field.model
            ai_run_inquiry_id = (
                ai_run_model._default_manager.filter(
                    pk=self.generated_by_ai_run_id
                )
                .values_list("inquiry_id", flat=True)
                .first()
            )
            if (
                ai_run_inquiry_id is not None
                and self.inquiry_id is not None
                and ai_run_inquiry_id != self.inquiry_id
            ):
                errors["generated_by_ai_run"] = (
                    "The AI run and handoff report must belong to "
                    "the same inquiry."
                )

        if self.confirmed_by_id is not None:
            user_model = self._meta.get_field(
                "confirmed_by"
            ).remote_field.model
            reviewer_role = (
                user_model._default_manager.filter(
                    pk=self.confirmed_by_id
                )
                .values_list("role_code", flat=True)
                .first()
            )
            if (
                reviewer_role is not None
                and reviewer_role != "CONSULTANT"
            ):
                errors["confirmed_by"] = (
                    "Handoff reports must be confirmed by a "
                    "CONSULTANT user."
                )

        if not isinstance(self.priority_check_items, list):
            errors["priority_check_items"] = (
                "priority_check_items must be a JSON array."
            )

        if not str(self.report_status_code).strip():
            errors["report_status_code"] = (
                "report_status_code must not be blank."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return (
            f"{self.public_id} v{self.report_version} "
            f"({self.report_status_code})"
        )
