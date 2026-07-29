"""Minimum normalized representative symptom row."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


class SymptomEntry(TimestampedModel):
    """One normalized representative symptom attached to an inquiry."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.OneToOneField(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="representative_symptom",
        db_column="inquiry_id",
    )
    symptom_type_code = models.CharField(max_length=40)
    structured_payload = models.JSONField(default=dict)
    schema_version = models.CharField(max_length=30, default="v1")
    is_customer_confirmed = models.BooleanField(default=True)

    class Meta:
        db_table = "support_inquiry_symptom"
        constraints = [
            models.CheckConstraint(
                condition=~Q(symptom_type_code=""),
                name="ck_inquiry_symptom_code_nonempty",
            )
        ]

    def __str__(self) -> str:
        return self.symptom_type_code
