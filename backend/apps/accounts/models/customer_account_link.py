"""WaterBridge 계정과 합성 계약고객의 연결 이력 Model."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models.customer_profile import CustomerProfile
from common.models.base import TimestampedModel


class CustomerAccountLink(TimestampedModel):
    """User와 계약고객 간 활성 1:1 연결과 연결 근거를 보존한다."""

    class LinkReason(models.TextChoices):
        LEGACY_BACKFILL = "LEGACY_BACKFILL", "기존 1:1 관계 Backfill"
        SIGN_UP_EMAIL_OTP = "SIGN_UP_EMAIL_OTP", "계약 이메일 OTP 회원가입"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_account_links",
        db_column="user_id",
    )
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        related_name="account_links",
        db_column="customer_id",
    )
    is_active = models.BooleanField(default=True)
    linked_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    link_reason = models.CharField(
        max_length=40,
        choices=LinkReason.choices,
    )
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_customer_account_link"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_active=True),
                name="ux_customer_link_active_user",
            ),
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(is_active=True),
                name="ux_customer_link_active_customer",
            ),
            models.CheckConstraint(
                condition=(
                    Q(is_active=True, revoked_at__isnull=True)
                    | Q(is_active=False, revoked_at__isnull=False)
                ),
                name="ck_customer_link_active_revoked",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_customer_link_synthetic_only",
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer", "is_active"],
                name="ix_cust_link_customer_active",
            ),
            models.Index(
                fields=["user", "is_active"],
                name="ix_cust_link_user_active",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.user_id:
            if self.user.role_code != "CUSTOMER":
                raise ValidationError(
                    {"user": "CUSTOMER 역할 사용자만 연결할 수 있습니다."}
                )
            if not self.user.is_synthetic:
                raise ValidationError(
                    {"user": "P1-A에서는 합성 사용자만 허용합니다."}
                )
        if self.customer_id and not self.customer.is_synthetic:
            raise ValidationError(
                {"customer": "P1-A에서는 합성 계약고객만 허용합니다."}
            )
        if self.is_active and self.revoked_at is not None:
            raise ValidationError(
                {"revoked_at": "활성 연결에는 해제 시각이 없어야 합니다."}
            )
        if not self.is_active and self.revoked_at is None:
            raise ValidationError(
                {"revoked_at": "비활성 연결에는 해제 시각이 필요합니다."}
            )

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.customer.customer_no}"
