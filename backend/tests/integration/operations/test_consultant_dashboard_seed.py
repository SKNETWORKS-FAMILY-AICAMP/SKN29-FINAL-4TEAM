"""Local synthetic consultant dashboard seed and API integration tests."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from io import StringIO
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.operations.models import (
    DashboardNotice,
    InquiryDashboardProfile,
    StaffDirectoryEntry,
)
from apps.operations.services import ConsultantDashboardSeedService
from apps.visits.repositories.visit_repository import VisitRepository


pytestmark = pytest.mark.django_db


def test_dashboard_seed_is_idempotent_and_preserves_unrelated_rows():
    unrelated = User.objects.create_user(
        username="UNRELATED-CONSULTANT-001",
        full_name="Unrelated consultant",
        role_code=User.Role.CONSULTANT,
        employee_no="UNRELATED-CNS-001",
        is_synthetic=True,
    )

    first = ConsultantDashboardSeedService().run()
    second = ConsultantDashboardSeedService().run()

    assert first.verification["consultants"] == 8
    assert first.verification["technicians"] == 4
    assert first.verification["customers"] == 30
    assert first.verification["inquiries"] == 90
    assert first.verification["notices"] == 6
    assert second.created_count == 0
    assert second.updated_count == 0
    assert second.unchanged_count > 0
    assert User.objects.filter(pk=unrelated.pk).exists()

    profiles = InquiryDashboardProfile.objects.filter(
        inquiry__scenario_code__startswith="SYN-WEB-DASH-"
    )
    assert profiles.count() == 90
    assert Counter(
        profiles.values_list("inquiry__status_code", flat=True)
    ) == {
        Inquiry.Status.CONSULTATION_REQUIRED: 30,
        Inquiry.Status.CONSULTATION_IN_PROGRESS: 30,
        Inquiry.Status.RESOLVED: 30,
    }
    for status in (
        Inquiry.Status.CONSULTATION_REQUIRED,
        Inquiry.Status.CONSULTATION_IN_PROGRESS,
        Inquiry.Status.RESOLVED,
    ):
        assert Counter(
            profiles.filter(inquiry__status_code=status).values_list(
                "inquiry__risk_level_code",
                flat=True,
            )
        ) == {"danger": 10, "caution": 10, "general": 10}

    assert CustomerProfile.objects.filter(
        customer_no__startswith="SYN-WEB-DASH-CUSTOMER-"
    ).count() == 30
    assert DashboardNotice.objects.filter(
        notice_code__startswith="SYN-WEB-DASH-NOTICE-"
    ).count() == 6
    assert StaffDirectoryEntry.objects.filter(
        user__username__startswith="SYN-WEB-DASH-"
    ).count() == 12


def test_dashboard_seed_accepts_a_replay_stable_inquiry_reference_time():
    reference_at = datetime(
        2026,
        8,
        24,
        14,
        30,
        tzinfo=ZoneInfo("Asia/Seoul"),
    )

    first = ConsultantDashboardSeedService(
        inquiry_reference_at=reference_at
    ).run()
    first_inquiry = Inquiry.objects.get(
        scenario_code="SYN-WEB-DASH-NEW-001"
    )
    second = ConsultantDashboardSeedService(
        inquiry_reference_at=reference_at
    ).run()

    assert first.inquiry_reference_at == reference_at.isoformat()
    assert first_inquiry.created_at == reference_at - timedelta(minutes=3)
    assert second.updated_count == 0
    assert second.unchanged_count > 0


def test_dashboard_seed_command_parses_an_explicit_reference_time():
    output = StringIO()

    call_command(
        "seed_consultant_dashboard",
        dry_run=True,
        reference_at="2026-08-24T14:30:00+09:00",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["dry_run"] is True
    assert payload["inquiry_reference_at"] == (
        "2026-08-24T14:30:00+09:00"
    )
    assert not Inquiry.objects.filter(
        scenario_code__startswith="SYN-WEB-DASH-"
    ).exists()

    with pytest.raises(CommandError):
        call_command(
            "seed_consultant_dashboard",
            dry_run=True,
            reference_at="not-a-date-time",
        )


def test_dashboard_seed_dry_run_rolls_back_all_owned_rows():
    result = ConsultantDashboardSeedService().run(dry_run=True)

    assert result.dry_run is True
    assert result.verification["inquiries"] == 90
    assert not Inquiry.objects.filter(
        scenario_code__startswith="SYN-WEB-DASH-"
    ).exists()
    assert not DashboardNotice.objects.filter(
        notice_code__startswith="SYN-WEB-DASH-NOTICE-"
    ).exists()


def test_dashboard_api_returns_database_projection_for_assigned_consultant():
    ConsultantDashboardSeedService().run()
    consultant = User.objects.get(username="DEMO-CONSULTANT-001")
    client = APIClient()
    client.force_authenticate(consultant)
    correlation_id = uuid4()

    response = client.get(
        "/api/v1/consultant/dashboard",
        HTTP_X_CORRELATION_ID=str(correlation_id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["data_classification"] == "synthetic"
    assert data["summary"] == {
        "total": 90,
        "new": 30,
        "in_progress": 30,
        "completed": 30,
    }
    assert len(data["notices"]) == 6
    assert len(data["consultants"]) == 8
    assert len(data["technicians"]) == 4
    assert response["X-Correlation-ID"] == str(correlation_id)
    assert payload["metadata"]["correlation_id"] == str(correlation_id)
    for contact in data["technicians"]:
        technician = VisitRepository.synthetic_technician(
            UUID(contact["user_id"])
        )
        assert technician is not None
        assert technician.role_code == User.Role.TECHNICIAN
    assert len(data["inquiries"]) == 90
    assert all(
        contact["email"].endswith("@waterbridge.example")
        for contact in data["consultants"] + data["technicians"]
    )
    assert Counter(item["bucket"] for item in data["inquiries"]) == {
        "NEW": 30,
        "IN_PROGRESS": 30,
        "COMPLETED": 30,
    }
    assert Counter(item["warranty_status"] for item in data["inquiries"]) == {
        "IN_WARRANTY": 45,
        "EXPIRED": 45,
    }
    first = data["inquiries"][0]
    assert first["title"]
    assert first["detail"]
    assert first["contact"].startswith("010-****-")
    assert first["address"] == ""
    assert first["customer_name"].endswith(" (합성)")
    assert "*" in first["customer_name"]
    assert first["customer_code"].startswith("SYN-WEB-DASH-CUSTOMER-")
    assert first["product_code"].startswith("SYN-WEB-WP-")


def test_dashboard_api_masks_assignment_and_rejects_other_roles_and_queries():
    ConsultantDashboardSeedService().run()
    other_consultant = User.objects.create_user(
        username="OTHER-SYN-CONSULTANT",
        full_name="Other synthetic consultant",
        role_code=User.Role.CONSULTANT,
        employee_no="OTHER-SYN-CNS-001",
        is_synthetic=True,
    )
    customer = User.objects.get(username="SYN-WEB-DASH-CUSTOMER-001")
    mismatched_directory_user = User.objects.create_user(
        username="MISMATCHED-DIRECTORY-TECHNICIAN",
        full_name="Mismatched directory technician",
        role_code=User.Role.CONSULTANT,
        employee_no="MISMATCHED-DIRECTORY-001",
        email="mismatched@waterbridge.example",
        phone="010-0000-9999",
        is_synthetic=True,
    )
    StaffDirectoryEntry.objects.create(
        user=mismatched_directory_user,
        staff_type=StaffDirectoryEntry.StaffType.TECHNICIAN,
        branch_name="합성 역할 불일치 지사",
        display_order=999,
        is_active=True,
    )
    client = APIClient()

    client.force_authenticate(other_consultant)
    other_response = client.get("/api/v1/consultant/dashboard")
    assert other_response.status_code == 200
    assert other_response.json()["data"]["summary"]["total"] == 0
    assert other_response.json()["data"]["inquiries"] == []
    assert all(
        contact["user_id"] != str(mismatched_directory_user.public_id)
        for contact in other_response.json()["data"]["technicians"]
    )

    query_response = client.get("/api/v1/consultant/dashboard?size=10")
    assert query_response.status_code == 422

    client.force_authenticate(customer)
    forbidden_response = client.get("/api/v1/consultant/dashboard")
    assert forbidden_response.status_code == 403


def test_dashboard_notice_detail_returns_only_currently_published_notice():
    ConsultantDashboardSeedService().run()
    consultant = User.objects.get(username="DEMO-CONSULTANT-001")
    customer = User.objects.get(username="SYN-WEB-DASH-CUSTOMER-001")
    notice = DashboardNotice.objects.order_by("display_order").first()
    assert notice is not None
    client = APIClient()
    client.force_authenticate(consultant)
    correlation_id = uuid4()

    response = client.get(
        f"/api/v1/consultant/notices/{notice.public_id}",
        HTTP_X_CORRELATION_ID=str(correlation_id),
    )

    assert response.status_code == 200
    assert response["X-Correlation-ID"] == str(correlation_id)
    assert response.json()["data"] == {
        "notice_id": str(notice.public_id),
        "notice_code": notice.notice_code,
        "category_code": notice.category_code,
        "category": notice.get_category_code_display(),
        "title": notice.title,
        "content": notice.body,
        "department": notice.department_name,
        "published_on": notice.published_on.isoformat(),
    }

    query_response = client.get(
        f"/api/v1/consultant/notices/{notice.public_id}?preview=true"
    )
    assert query_response.status_code == 422

    notice.is_published = False
    notice.save(update_fields=["is_published", "updated_at"])
    concealed_response = client.get(
        f"/api/v1/consultant/notices/{notice.public_id}"
    )
    assert concealed_response.status_code == 404

    client.force_authenticate(customer)
    forbidden_response = client.get(
        f"/api/v1/consultant/notices/{notice.public_id}"
    )
    assert forbidden_response.status_code == 403
