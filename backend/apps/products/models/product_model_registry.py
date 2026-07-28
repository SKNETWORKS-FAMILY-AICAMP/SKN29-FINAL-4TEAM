"""판매 코드·모델·세대·지원 범위 Model."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import F, Q

from common.models.base import TimestampedModel


class ProductModel(TimestampedModel):
    """구독과 공식 문서가 참조하는 정수기 제품 모델."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    model_code = models.CharField(max_length=60, unique=True)
    model_name = models.CharField(max_length=150)
    generation_code = models.CharField(
        max_length=40,
        null=True,
        blank=True,
    )
    manufacturer = models.CharField(
        max_length=100,
        default="SK매직",
    )
    launched_on = models.DateField(null=True, blank=True)
    discontinued_on = models.DateField(null=True, blank=True)
    features = models.JSONField(default=dict, blank=True)
    is_supported_mvp = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "catalog_product_model"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(discontinued_on__isnull=True)
                    | Q(launched_on__isnull=True)
                    | Q(discontinued_on__gte=F("launched_on"))
                ),
                name="ck_product_lifecycle_dates",
            )
        ]
        indexes = [
            models.Index(
                fields=["is_supported_mvp", "is_active"],
                name="ix_product_supported_active",
            )
        ]

    def __str__(self) -> str:
        return f"{self.model_code} ({self.model_name})"
