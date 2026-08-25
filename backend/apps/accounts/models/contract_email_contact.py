"""가입 전 합성 계약고객의 보호된 이메일 연락처 Model."""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from apps.accounts.models.customer_profile import CustomerProfile
from common.models.base import TimestampedModel


validate_sha256_hex = RegexValidator(
    regex=r"^[0-9a-f]{64}$",
    message="email_lookup_hmac은 소문자 SHA-256 hex여야 합니다.",
)


class ContractEmailContact(TimestampedModel):
    """계약 이메일의 발송용 암호문과 검색용 HMAC을 분리 보관한다."""

    class DeliveryPolicy(models.TextChoices):
        RUNTIME_REDIRECT_ONLY = (
            "RUNTIME_REDIRECT_ONLY",
            "시험 Runtime Redirect 전용",
        )

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        related_name="contract_email_contacts",
        db_column="customer_id",
    )
    encrypted_email = models.TextField()
    email_lookup_hmac = models.CharField(
        max_length=64,
        validators=[validate_sha256_hex],
    )
    key_version = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=True)
    delivery_policy = models.CharField(
        max_length=40,
        choices=DeliveryPolicy.choices,
        default=DeliveryPolicy.RUNTIME_REDIRECT_ONLY,
    )
    source_system = models.CharField(
        max_length=40,
        default="P1_ACCOUNT_LINK_FIXTURE",
    )
    data_classification = models.CharField(
        max_length=20,
        default="synthetic",
        editable=False,
    )

    class Meta:
        db_table = "accounts_contract_email_contact"
        constraints = [
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(is_active=True, is_primary=True),
                name="ux_contract_email_active_primary_customer",
            ),
            models.UniqueConstraint(
                fields=["customer", "email_lookup_hmac"],
                condition=Q(is_active=True),
                name="ux_contract_email_active_customer_hmac",
            ),
            models.CheckConstraint(
                condition=(Q(is_primary=False) | Q(is_active=True)),
                name="ck_contract_email_primary_active",
            ),
            models.CheckConstraint(
                condition=Q(data_classification="synthetic"),
                name="ck_contract_email_synthetic_only",
            ),
        ]
        indexes = [
            models.Index(
                fields=["email_lookup_hmac", "is_active"],
                name="ix_contract_email_hmac_active",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if self.customer_id and not self.customer.is_synthetic:
            raise ValidationError(
                {"customer": "P1-A에서는 합성 계약고객만 허용합니다."}
            )
        if not self.encrypted_email.strip():
            raise ValidationError(
                {"encrypted_email": "계약 이메일 암호문은 필수입니다."}
            )
        if "@" in self.encrypted_email:
            raise ValidationError(
                {"encrypted_email": "평문 이메일을 저장할 수 없습니다."}
            )
        if self.is_primary and not self.is_active:
            raise ValidationError(
                {"is_primary": "대표 연락처는 활성 상태여야 합니다."}
            )

    def __str__(self) -> str:
        return f"{self.customer.customer_no} ({self.key_version})"
