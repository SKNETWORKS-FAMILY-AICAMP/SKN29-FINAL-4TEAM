"""Ordered customer action steps for one guidance version."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


def _is_required_text_nonempty(field_name: str) -> Q:
    """Build a portable non-whitespace database check."""

    return Q(**{f"{field_name}__regex": r".*\S.*"})


class GuidanceItem(TimestampedModel):
    """Persist one ordered instruction within a guidance version."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    guidance = models.ForeignKey(
        "inquiries.Guidance",
        on_delete=models.PROTECT,
        related_name="items",
        db_column="guidance_id",
        db_index=False,
    )
    step_no = models.PositiveSmallIntegerField()
    # GUIDANCE_ACTION has no approved canonical YAML yet. Keep this
    # required code open until the owning team approves the code set.
    action_type_code = models.CharField(max_length=40)
    instruction_text = models.TextField()
    caution_text = models.TextField(null=True, blank=True)
    requires_confirmation = models.BooleanField(default=True)

    class Meta:
        db_table = "support_guidance_item"
        constraints = [
            models.UniqueConstraint(
                fields=["guidance", "step_no"],
                name="ux_guidance_item_step",
            ),
            models.CheckConstraint(
                condition=Q(step_no__gt=0),
                name="ck_guidance_item_step",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty(
                    "action_type_code"
                ),
                name="ck_guidance_action_nonempty",
            ),
            models.CheckConstraint(
                condition=_is_required_text_nonempty(
                    "instruction_text"
                ),
                name="ck_guidance_item_instruction",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.guidance_id} step {self.step_no} "
            f"({self.action_type_code})"
        )
