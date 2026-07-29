import uuid

from django.conf import settings
from django.db import models

from apps.inquiries.models import Inquiry


class VisitRequest(models.Model):
    class Status(models.TextChoices):
        ASSIGNING = "ASSIGNING", "기사 배정 중"
        SCHEDULING = "SCHEDULING", "일정 조율 중"
        CONFIRMED = "CONFIRMED", "방문 확정"
        EN_ROUTE = "EN_ROUTE", "이동 중"
        IN_PROGRESS = "IN_PROGRESS", "방문 진행 중"
        COMPLETED = "COMPLETED", "방문 완료"
        FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED", "추가 방문 필요"
        CANCELLED = "CANCELLED", "취소"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    inquiry = models.OneToOneField(
        Inquiry,
        on_delete=models.CASCADE,
        related_name="visit",
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_visits",
    )
    customer_address = models.CharField(max_length=255)
    customer_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )
    customer_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.ASSIGNING,
    )
    departed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class TechnicianLocation(models.Model):
    visit = models.ForeignKey(
        VisitRequest,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )
    accuracy_meters = models.FloatField(null=True, blank=True)
    speed_mps = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)


class ServiceCall(models.Model):
    """고객 요청부터 기사 수락·이동·완료까지 연결하는 실시간 콜."""

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "기사 수락 대기"
        ACCEPTED = "ACCEPTED", "기사 수락"
        EN_ROUTE = "EN_ROUTE", "기사 이동 중"
        ARRIVED = "ARRIVED", "기사 도착"
        COMPLETED = "COMPLETED", "처리 완료"
        CANCELLED = "CANCELLED", "요청 취소"

    class ResultType(models.TextChoices):
        NORMAL = "NORMAL", "정상 처리"
        PART_REPLACED = "PART_REPLACED", "부품 교체"
        REVISIT = "REVISIT", "재방문 필요"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    customer_device_id = models.CharField(
        max_length=80,
        db_index=True,
    )
    customer_name = models.CharField(max_length=80)
    customer_phone = models.CharField(max_length=30)
    customer_address = models.CharField(max_length=255)
    customer_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )
    customer_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
    )

    product_name = models.CharField(max_length=120)
    product_model = models.CharField(max_length=120)
    symptom = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
        db_index=True,
    )

    technician_device_id = models.CharField(
        max_length=80,
        null=True,
        blank=True,
        db_index=True,
    )
    technician_name = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    technician_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    technician_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
    )
    technician_accuracy_meters = models.FloatField(
        null=True,
        blank=True,
    )
    technician_speed_mps = models.FloatField(
        null=True,
        blank=True,
    )
    technician_heading = models.FloatField(
        null=True,
        blank=True,
    )
    technician_location_updated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    result_type = models.CharField(
        max_length=30,
        choices=ResultType.choices,
        null=True,
        blank=True,
    )
    diagnosis = models.TextField(blank=True)
    action_taken = models.TextField(blank=True)
    parts_used = models.TextField(blank=True)
    customer_note = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)

    requested_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    departed_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-requested_at",)
        indexes = [
            models.Index(
                fields=("status", "requested_at"),
                name="svc_call_status_time_idx",
            ),
            models.Index(
                fields=("technician_device_id", "status"),
                name="svc_call_tech_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.customer_name} / {self.product_model} / "
            f"{self.get_status_display()}"
        )
