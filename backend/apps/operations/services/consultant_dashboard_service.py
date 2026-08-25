"""Read-only consultant dashboard projections over synthetic data."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any
from uuid import UUID

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.inquiries.models import Inquiry
from apps.operations.models import (
    DashboardNotice,
    InquiryDashboardProfile,
    StaffDirectoryEntry,
)
from common.privacy import mask_person_name, mask_phone


STATUS_BUCKETS = {
    Inquiry.Status.CONSULTATION_REQUIRED: "NEW",
    Inquiry.Status.REOPENED: "NEW",
    Inquiry.Status.DRAFT: "IN_PROGRESS",
    Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS: "IN_PROGRESS",
    Inquiry.Status.AI_GUIDANCE: "IN_PROGRESS",
    Inquiry.Status.CONSULTATION_IN_PROGRESS: "IN_PROGRESS",
    Inquiry.Status.VISIT_REVIEW_PENDING: "IN_PROGRESS",
    Inquiry.Status.VISIT_SCHEDULING: "IN_PROGRESS",
    Inquiry.Status.VISIT_SCHEDULED: "IN_PROGRESS",
    Inquiry.Status.COMPLETION_PENDING: "IN_PROGRESS",
    Inquiry.Status.REVISIT_REQUIRED: "IN_PROGRESS",
    Inquiry.Status.RESOLVED: "COMPLETED",
    Inquiry.Status.CANCELLED: "COMPLETED",
}


class ConsultantDashboardService:
    """Build a closed DTO without widening the inquiry Runtime contract."""

    @classmethod
    def snapshot(cls, *, actor: Any) -> dict[str, Any]:
        today = timezone.localdate()
        notice_rows = DashboardNotice.objects.filter(
            is_published=True,
            is_synthetic=True,
            published_on__lte=today,
        ).order_by("display_order", "-published_on", "public_id")
        directory_rows = list(
            StaffDirectoryEntry.objects.filter(
                is_active=True,
                user__is_active=True,
                user__is_synthetic=True,
            )
            .select_related("user")
            .order_by("staff_type", "display_order", "public_id")
        )
        inquiry_rows = list(
            InquiryDashboardProfile.objects.filter(
                is_synthetic=True,
                inquiry__assigned_user=actor,
                inquiry__assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
                inquiry__subscription__customer__is_synthetic=True,
                inquiry__subscription__customer__user__is_synthetic=True,
                inquiry__subscription__customer__deleted_at__isnull=True,
            )
            .select_related(
                "inquiry",
                "inquiry__subscription",
                "inquiry__subscription__customer",
                "inquiry__subscription__product_model",
            )
            .order_by("inquiry__created_at", "inquiry__public_id")
        )
        inquiries = [cls._inquiry_item(row, today=today) for row in inquiry_rows]
        inquiries.sort(
            key=lambda row: (
                {"NEW": 0, "IN_PROGRESS": 1, "COMPLETED": 2}.get(
                    row["bucket"], 9
                ),
                {"danger": 0, "caution": 1, "general": 2}.get(
                    row["risk_level"], 9
                ),
                row["inquiry_code"],
            )
        )
        bucket_counts = Counter(item["bucket"] for item in inquiries)
        return {
            "data_classification": "synthetic",
            "generated_at": timezone.now(),
            "summary": {
                "total": len(inquiries),
                "new": bucket_counts["NEW"],
                "in_progress": bucket_counts["IN_PROGRESS"],
                "completed": bucket_counts["COMPLETED"],
            },
            "notices": [cls._notice_item(notice) for notice in notice_rows],
            "consultants": [
                {
                    "user_id": entry.user.public_id,
                    "name": entry.user.full_name,
                    "department": entry.department_name,
                    "position": entry.position_title,
                    "extension": entry.extension_number,
                    "email": entry.user.email,
                }
                for entry in directory_rows
                if entry.staff_type
                == StaffDirectoryEntry.StaffType.CONSULTANT
                and entry.user.role_code == User.Role.CONSULTANT
            ],
            "technicians": [
                {
                    "user_id": entry.user.public_id,
                    "name": entry.user.full_name,
                    "branch": entry.branch_name,
                    "phone": entry.user.phone,
                    "email": entry.user.email,
                }
                for entry in directory_rows
                if entry.staff_type
                == StaffDirectoryEntry.StaffType.TECHNICIAN
                and entry.user.role_code == User.Role.TECHNICIAN
            ],
            "inquiries": inquiries,
        }

    @classmethod
    def notice_detail(cls, *, notice_public_id: UUID) -> dict[str, Any]:
        """Return one currently published synthetic notice or conceal it."""

        notice = DashboardNotice.objects.filter(
            public_id=notice_public_id,
            is_published=True,
            is_synthetic=True,
            published_on__lte=timezone.localdate(),
        ).first()
        if notice is None:
            raise NotFound()
        return cls._notice_item(notice)

    @staticmethod
    def _notice_item(notice: DashboardNotice) -> dict[str, Any]:
        return {
            "notice_id": notice.public_id,
            "notice_code": notice.notice_code,
            "category_code": notice.category_code,
            "category": notice.get_category_code_display(),
            "title": notice.title,
            "content": notice.body,
            "department": notice.department_name,
            "published_on": notice.published_on,
        }

    @classmethod
    def _inquiry_item(
        cls,
        profile: InquiryDashboardProfile,
        *,
        today: date,
    ) -> dict[str, Any]:
        inquiry = profile.inquiry
        subscription = inquiry.subscription
        customer = subscription.customer
        warranty_status, warranty_label = cls._warranty(
            profile.warranty_ends_on,
            today=today,
        )
        return {
            "inquiry_id": inquiry.public_id,
            "inquiry_code": inquiry.inquiry_code,
            "bucket": STATUS_BUCKETS.get(inquiry.status_code, "IN_PROGRESS"),
            "status": inquiry.status_code,
            "risk_level": inquiry.risk_level_code or Inquiry.RiskLevel.GENERAL,
            "priority": inquiry.priority_code,
            "title": profile.title,
            "detail": inquiry.raw_text.strip()[:4000],
            "contact": mask_phone(customer.phone),
            # Preserve the confirmed DTO shape while suppressing list-level
            # address disclosure.
            "address": "",
            "customer_name": mask_person_name(customer.customer_name),
            "customer_code": customer.customer_no,
            "product_name": subscription.product_model.model_name,
            "product_code": subscription.product_model.model_code,
            "warranty_status": warranty_status,
            "warranty_ends_on": profile.warranty_ends_on,
            "warranty_label": warranty_label,
            "previous_visit_count": profile.previous_visit_count,
            "received_at": inquiry.created_at,
            "updated_at": inquiry.updated_at,
        }

    @staticmethod
    def _warranty(
        warranty_ends_on: date | None,
        *,
        today: date,
    ) -> tuple[str, str]:
        if warranty_ends_on is None:
            return "NOT_REGISTERED", "보증 정보 없음"
        formatted = (
            f"{warranty_ends_on.year}년 {warranty_ends_on.month}월까지"
        )
        if warranty_ends_on >= today:
            return "IN_WARRANTY", f"무상보증 {formatted}"
        return "EXPIRED", f"무상보증 기간 지남 ({formatted})"
