"""고객 합성 프로필 Model."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.identifiers import (
    generate_customer_profile_id,
    validate_domain_id,
)
from common.models.base import TimestampedModel
from common.models.soft_delete import SoftDeleteModel


class CustomerProfile(TimestampedModel, SoftDeleteModel):
    """실제 개인정보를 배제한 고객 업무 프로필."""

    id = models.CharField(
        primary_key=True,
        max_length=48,
        default=generate_customer_profile_id,
        editable=False,
        validators=[validate_domain_id],
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_profile",
        db_column="user_id",
    )
    customer_no = models.CharField(max_length=40, unique=True)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    consent_version = models.CharField(max_length=40, blank=True)
    consented_at = models.DateTimeField(null=True, blank=True)
    is_synthetic = models.BooleanField(default=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deleted_customer_profiles",
        db_column="deleted_by_id",
    )

    class Meta:
        db_table = "customers_customer_profile"
        constraints = [
            models.CheckConstraint(
                condition=Q(is_synthetic=True),
                name="customer_profile_synthetic_only",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.user_id
            and getattr(self.user, "role_code", None) != "CUSTOMER"
        ):
            raise ValidationError(
                {"user": "CUSTOMER 역할 사용자만 고객 프로필을 가질 수 있습니다."}
            )

    def __str__(self) -> str:
        return f"{self.customer_no} ({self.customer_name})"
