"""Synthetic-only consultant dashboard projection models."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models.base import TimestampedModel


class StaffDirectoryEntry(TimestampedModel):
    """Public synthetic staff contact metadata for the consultant UI."""

    class StaffType(models.TextChoices):
        CONSULTANT = "CONSULTANT", "Consultant"
        TECHNICIAN = "TECHNICIAN", "Technician"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="staff_directory_entry",
        db_column="user_id",
    )
    staff_type = models.CharField(max_length=20, choices=StaffType.choices)
    department_name = models.CharField(max_length=100, blank=True)
    position_title = models.CharField(max_length=80, blank=True)
    extension_number = models.CharField(max_length=30, blank=True)
    branch_name = models.CharField(max_length=100, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "operations_staff_directory_entry"
        constraints = [
            models.CheckConstraint(
                condition=Q(staff_type__in=["CONSULTANT", "TECHNICIAN"]),
                name="ck_ops_staff_directory_type",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        staff_type="CONSULTANT",
                        branch_name="",
                    )
                    & ~Q(department_name="")
                    & ~Q(position_title="")
                    & ~Q(extension_number="")
                )
                | (
                    Q(
                        staff_type="TECHNICIAN",
                        department_name="",
                        position_title="",
                        extension_number="",
                    )
                    & ~Q(branch_name="")
                ),
                name="ck_ops_staff_directory_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=["staff_type", "is_active", "display_order"],
                name="ix_ops_staff_directory",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username} ({self.staff_type})"


class DashboardNotice(TimestampedModel):
    """Published synthetic notice content shown on the consultant dashboard."""

    class Category(models.TextChoices):
        EMERGENCY = "EMERGENCY", "긴급"
        EVENT = "EVENT", "이벤트"
        SYSTEM = "SYSTEM", "시스템"
        WORK = "WORK", "근무"
        WELFARE = "WELFARE", "복지"
        TRAINING = "TRAINING", "교육"

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    notice_code = models.CharField(max_length=50, unique=True)
    category_code = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=160)
    body = models.TextField()
    department_name = models.CharField(max_length=100)
    published_on = models.DateField()
    display_order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    is_synthetic = models.BooleanField(default=True)

    class Meta:
        db_table = "operations_dashboard_notice"
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    category_code__in=[
                        "EMERGENCY",
                        "EVENT",
                        "SYSTEM",
                        "WORK",
                        "WELFARE",
                        "TRAINING",
                    ]
                ),
                name="ck_ops_dashboard_notice_category",
            ),
            models.CheckConstraint(
                condition=Q(is_synthetic=True),
                name="ck_ops_dashboard_notice_synthetic",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(notice_code="")
                    & ~Q(title="")
                    & ~Q(body="")
                    & ~Q(department_name="")
                ),
                name="ck_ops_dashboard_notice_content",
            ),
        ]
        indexes = [
            models.Index(
                fields=["is_published", "published_on", "display_order"],
                name="ix_ops_dashboard_notice",
            )
        ]

    def __str__(self) -> str:
        return f"{self.notice_code} ({self.title})"


class InquiryDashboardProfile(TimestampedModel):
    """Synthetic presentation metadata kept outside the inquiry contract."""

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    inquiry = models.OneToOneField(
        "inquiries.Inquiry",
        on_delete=models.PROTECT,
        related_name="dashboard_profile",
        db_column="inquiry_id",
    )
    title = models.CharField(max_length=160)
    warranty_ends_on = models.DateField(null=True, blank=True)
    previous_visit_count = models.PositiveIntegerField(default=0)
    is_synthetic = models.BooleanField(default=True)

    class Meta:
        db_table = "operations_inquiry_dashboard_profile"
        constraints = [
            models.CheckConstraint(
                condition=~Q(title=""),
                name="ck_ops_inquiry_dashboard_title",
            ),
            models.CheckConstraint(
                condition=Q(is_synthetic=True),
                name="ck_ops_inquiry_dashboard_synthetic",
            ),
        ]
        indexes = [
            models.Index(
                fields=["warranty_ends_on"],
                name="ix_ops_inquiry_warranty_end",
            )
        ]

    def __str__(self) -> str:
        return f"{self.inquiry.inquiry_code} ({self.title})"
