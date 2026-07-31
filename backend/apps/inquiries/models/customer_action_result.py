"""Append-only customer submissions for one guidance action step."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


def _is_required_text_nonempty(field_name: str) -> Q:
    """Build a portable non-whitespace database check."""

    return Q(**{f"{field_name}__regex": r".*\S.*"})


class CustomerActionResult(models.Model):
    """Persist one customer action attempt without guessing code meaning."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    guidance_item = models.ForeignKey(
        "inquiries.GuidanceItem",
        on_delete=models.PROTECT,
        related_name="action_results",
        db_column="guidance_item_id",
        db_index=False,
    )
    attempt_no = models.PositiveSmallIntegerField(default=1)
    # ACTION_RESULT has no approved canonical YAML yet. Keep this
    # required code open and do not infer NOT_PERFORMED semantics.
    result_code = models.CharField(max_length=40)
    result_text = models.TextField(null=True, blank=True)
    performed_at = models.DateTimeField(null=True, blank=True)
    customer_comment = models.TextField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_customer_action_results",
        db_column="submitted_by_id",
        db_index=False,
    )
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "support_customer_action_result"
        constraints = [
            models.UniqueConstraint(
                fields=["guidance_item", "attempt_no"],
                name="ux_action_result_attempt",
            ),
            models.UniqueConstraint(
                fields=["idempotency_key"],
                name="ux_action_result_idempotency",
            ),
            models.CheckConstraint(
                condition=Q(attempt_no__gt=0),
                name="ck_action_result_attempt",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty("result_code"),
                name="ck_action_result_code_nonempty",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty(
                    "idempotency_key"
                ),
                name="ck_action_result_idem_nonempty",
            ),
        ]
        indexes = [
            models.Index(
                fields=["guidance_item", "created_at"],
                name="ix_action_result_guidance_item",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.guidance_item_id} attempt {self.attempt_no} "
            f"({self.result_code})"
        )
