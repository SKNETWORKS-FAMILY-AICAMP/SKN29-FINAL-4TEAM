"""고객·제품·관리 유형·사용 시작일 Model."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import F, Q

from apps.accounts.models import CustomerProfile
from apps.products.models import ProductModel
from common.models.base import TimestampedModel


class CustomerSubscription(TimestampedModel):
    """고객과 구독 중인 정수기 모델·관리 상태를 연결한다."""

    class ManagementType(models.TextChoices):
        SELF_MANAGED = "SELF_MANAGED", "자가관리"
        VISIT_CARE = "VISIT_CARE", "방문관리"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "이용 중"
        SUSPENDED = "SUSPENDED", "일시 중지"
        CANCELLED = "CANCELLED", "해지"
        EXPIRED = "EXPIRED", "만료"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    contract_no = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        db_column="customer_id",
        db_index=False,
    )
    product_model = models.ForeignKey(
        ProductModel,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        db_column="product_model_id",
        db_index=False,
    )
    serial_no = models.CharField(max_length=80)
    management_type_code = models.CharField(
        max_length=40,
        choices=ManagementType.choices,
        default=ManagementType.VISIT_CARE,
    )
    status_code = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    started_on = models.DateField()
    ended_on = models.DateField(null=True, blank=True)
    installed_at = models.DateTimeField(null=True, blank=True)
    installed_on = models.DateField(
        null=True,
        blank=True,
        help_text="원본이 날짜 정밀도만 제공할 때 사용하는 설치일",
    )
    source_customer_product_public_id = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
        help_text="CustomerProduct fixture를 별도 테이블 없이 투영한 원본 UUID",
    )
    installation_address = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )
    next_care_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "subscriptions_customer_subscription"
        constraints = [
            models.UniqueConstraint(
                fields=["serial_no"],
                condition=Q(
                    status_code__in=[
                        "ACTIVE",
                        "SUSPENDED",
                    ]
                ),
                name="ux_sub_active_serial",
            ),
            models.CheckConstraint(
                condition=(
                    Q(ended_on__isnull=True)
                    | Q(ended_on__gte=F("started_on"))
                ),
                name="ck_subscription_period",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code__in=["CANCELLED", "EXPIRED"])
                    | Q(ended_on__isnull=False)
                ),
                name="ck_subscription_ended_status",
            ),
            models.CheckConstraint(
                condition=Q(
                    management_type_code__in=[
                        "SELF_MANAGED",
                        "VISIT_CARE",
                    ]
                ),
                name="ck_sub_management_type",
            ),
            models.CheckConstraint(
                condition=Q(
                    status_code__in=[
                        "ACTIVE",
                        "SUSPENDED",
                        "CANCELLED",
                        "EXPIRED",
                    ]
                ),
                name="ck_sub_status_code",
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer", "status_code"],
                name="ix_sub_customer_status",
            ),
            models.Index(
                fields=["next_care_on"],
                condition=(
                    Q(status_code="ACTIVE")
                    & Q(next_care_on__isnull=False)
                ),
                name="ix_sub_next_care",
            ),
            models.Index(
                fields=["product_model"],
                name="ix_sub_product_model",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.contract_no} ({self.status_code})"
