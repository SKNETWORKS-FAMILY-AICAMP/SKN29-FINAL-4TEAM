"""Field-visit result persistence aligned with the active T-005 contract."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.visits.models.visit import Visit
from common.models.base import TimestampedModel


class VisitResult(TimestampedModel):
    """Persist the technician-confirmed outcome for exactly one visit."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    visit = models.OneToOneField(
        Visit,
        on_delete=models.PROTECT,
        related_name="result",
        db_column="visit_id",
        db_index=False,
    )
    cause_category_code = models.CharField(
        max_length=40,
        null=True,
        blank=True,
    )
    inspection_summary = models.TextField()
    action_summary = models.TextField()
    parts_used_text = models.TextField(null=True, blank=True)
    customer_guidance = models.TextField(null=True, blank=True)
    resolved_on_site = models.BooleanField(default=False)
    revisit_required = models.BooleanField(default=False)
    revisit_reason = models.TextField(null=True, blank=True)
    technician_note = models.TextField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_visit_results",
        db_column="submitted_by_id",
        db_index=False,
        limit_choices_to={"role_code": "TECHNICIAN"},
    )
    idempotency_key = models.CharField(max_length=128)
    completed_at = models.DateTimeField(default=timezone.now)
    next_care_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "field_service_visit_result"
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                name="ux_visit_result_idempotency",
            ),
            models.CheckConstraint(
                condition=(
                    Q(revisit_required=False)
                    | Q(revisit_reason__isnull=False)
                ),
                name="ck_visit_result_revisit_reason",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "resolved_on_site",
                    "revisit_required",
                    "completed_at",
                ],
                name="ix_visit_result_resolution",
            ),
        ]

    def clean(self) -> None:
        """Validate the portable half of the assigned-technician contract."""

        super().clean()
        errors: dict[str, str] = {}

        if self.submitted_by_id is not None:
            user_model = self._meta.get_field(
                "submitted_by"
            ).remote_field.model
            submitted_role = (
                user_model._default_manager.filter(
                    pk=self.submitted_by_id
                )
                .values_list("role_code", flat=True)
                .first()
            )
            if (
                submitted_role is not None
                and submitted_role != "TECHNICIAN"
            ):
                errors["submitted_by"] = (
                    "Visit results must be submitted by a TECHNICIAN user."
                )

        if self.visit_id is not None:
            assigned_technician_id = (
                Visit.objects.filter(pk=self.visit_id)
                .values_list("technician_id", flat=True)
                .first()
            )
            if assigned_technician_id is None:
                errors["visit"] = (
                    "A visit result requires an assigned technician."
                )
            elif (
                self.submitted_by_id is not None
                and self.submitted_by_id != assigned_technician_id
            ):
                errors["submitted_by"] = (
                    "The submitting technician must match the visit "
                    "assignment."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.visit.visit_code} result"
