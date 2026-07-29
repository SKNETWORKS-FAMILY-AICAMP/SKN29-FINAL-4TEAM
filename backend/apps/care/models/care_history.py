"""필터 교체·세척·방문 관리 이력 Model."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.subscriptions.models import CustomerSubscription
from common.models.base import TimestampedModel


class CareRecord(TimestampedModel):
    """구독 제품의 케어 일정과 완료·취소 결과를 보존한다."""

    class CareType(models.TextChoices):
        FILTER_REPLACEMENT = "FILTER_REPLACEMENT", "필터 교체"
        PERIODIC_CHECK = "PERIODIC_CHECK", "정기 점검"
        CLEANING = "CLEANING", "세척"
        OTHER = "OTHER", "기타"

    class Status(models.TextChoices):
        DUE = "DUE", "예정"
        SCHEDULED = "SCHEDULED", "예약"
        COMPLETED = "COMPLETED", "완료"
        OVERDUE = "OVERDUE", "기한 초과"
        CANCELLED = "CANCELLED", "취소"

    class Source(models.TextChoices):
        CUSTOMER = "CUSTOMER", "고객"
        CONSULTANT = "CONSULTANT", "상담사"
        TECHNICIAN = "TECHNICIAN", "방문기사"
        SYSTEM = "SYSTEM", "시스템"
        IMPORT = "IMPORT", "가져오기"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    care_code = models.CharField(max_length=50, unique=True)
    subscription = models.ForeignKey(
        CustomerSubscription,
        on_delete=models.PROTECT,
        related_name="care_records",
        db_column="subscription_id",
        db_index=False,
    )
    # Wave 4에서 field_service.VisitResult가 구현되면 실제 FK로 전환한다.
    # 그 전까지는 앱 간 migration 순환을 막는 nullable UUID bridge이다.
    visit_result_public_id = models.UUIDField(
        null=True,
        blank=True,
    )
    care_type_code = models.CharField(
        max_length=40,
        choices=CareType.choices,
    )
    status_code = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    scheduled_on = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="performed_care_records",
        db_column="performed_by_id",
        null=True,
        blank=True,
        db_index=False,
    )
    source_code = models.CharField(
        max_length=40,
        choices=Source.choices,
        default=Source.SYSTEM,
    )

    class Meta:
        db_table = "subscriptions_care_record"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    care_type_code__in=[
                        "FILTER_REPLACEMENT",
                        "PERIODIC_CHECK",
                        "CLEANING",
                        "OTHER",
                    ]
                ),
                name="ck_care_type_code",
            ),
            models.CheckConstraint(
                condition=Q(
                    status_code__in=[
                        "DUE",
                        "SCHEDULED",
                        "COMPLETED",
                        "OVERDUE",
                        "CANCELLED",
                    ]
                ),
                name="ck_care_status_code",
            ),
            models.CheckConstraint(
                condition=Q(
                    source_code__in=[
                        "CUSTOMER",
                        "CONSULTANT",
                        "TECHNICIAN",
                        "SYSTEM",
                        "IMPORT",
                    ]
                ),
                name="ck_care_source_code",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code="COMPLETED")
                    | (
                        Q(completed_at__isnull=False)
                        & Q(performed_by__isnull=False)
                        & Q(cancelled_at__isnull=True)
                        & Q(cancellation_reason__isnull=True)
                    )
                ),
                name="ck_care_completed_state",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status_code="CANCELLED")
                    | (
                        Q(completed_at__isnull=True)
                        & Q(performed_by__isnull=True)
                        & Q(cancelled_at__isnull=False)
                        & Q(cancellation_reason__isnull=False)
                    )
                ),
                name="ck_care_cancelled_state",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(
                        status_code__in=[
                            "DUE",
                            "SCHEDULED",
                            "OVERDUE",
                        ]
                    )
                    | (
                        Q(completed_at__isnull=True)
                        & Q(performed_by__isnull=True)
                        & Q(cancelled_at__isnull=True)
                        & Q(cancellation_reason__isnull=True)
                    )
                ),
                name="ck_care_pending_state",
            ),
            models.CheckConstraint(
                condition=~(
                    Q(completed_at__isnull=False)
                    & Q(cancelled_at__isnull=False)
                ),
                name="ck_care_single_outcome",
            ),
        ]
        indexes = [
            models.Index(
                fields=["subscription", "-completed_at"],
                name="ix_care_record_subscription",
            ),
            models.Index(
                fields=["status_code", "scheduled_on"],
                name="ix_care_record_schedule",
            ),
            models.Index(
                fields=["visit_result_public_id"],
                name="ix_care_record_visit_result",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.care_code} ({self.status_code})"
