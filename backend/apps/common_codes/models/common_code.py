"""공통코드 표시·정렬·메타데이터 Model."""

from __future__ import annotations

import uuid

from django.db import models

from apps.common_codes.db_expressions import IsJSONObject
from apps.common_codes.models.common_code_group import CommonCodeGroup
from apps.common_codes.validators import validate_json_object
from common.models.base import TimestampedModel


class CommonCode(TimestampedModel):
    """업무 ``*_code``와 분리된 공통코드 레지스트리."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    group = models.ForeignKey(
        CommonCodeGroup,
        on_delete=models.PROTECT,
        related_name="codes",
        db_column="group_code",
        to_field="group_code",
    )
    code = models.CharField(max_length=40)
    code_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_json_object],
    )

    class Meta:
        db_table = "common_code"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "code"],
                name="ux_common_code_group_code",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    code__regex=r"^[A-Z][A-Z0-9_]*$"
                ),
                name="ck_common_code_code_format",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__gte=0),
                name="ck_common_code_order_nonnegative",
            ),
            models.CheckConstraint(
                condition=IsJSONObject(models.F("metadata")),
                name="ck_common_code_metadata_object",
            ),
        ]
        indexes = [
            models.Index(
                fields=["group", "is_active", "display_order"],
                name="ix_common_code_active",
            )
        ]

    def __str__(self) -> str:
        return f"{self.group_id}.{self.code} ({self.code_name})"
