"""Local synthetic consultant dashboard seed and API integration tests."""

from __future__ import annotations

from collections import Counter

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.operations.models import (
    DashboardNotice,
    InquiryDashboardProfile,
    StaffDirectoryEntry,
)
from apps.operations.services import ConsultantDashboardSeedService


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

    response = client.get("/api/v1/consultant/dashboard")

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
    assert first["contact"].startswith("010-0001-")
    assert "합성" in first["address"]
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
    client = APIClient()

    client.force_authenticate(other_consultant)
    other_response = client.get("/api/v1/consultant/dashboard")
    assert other_response.status_code == 200
    assert other_response.json()["data"]["summary"]["total"] == 0
    assert other_response.json()["data"]["inquiries"] == []

    query_response = client.get("/api/v1/consultant/dashboard?size=10")
    assert query_response.status_code == 422

    client.force_authenticate(customer)
    forbidden_response = client.get("/api/v1/consultant/dashboard")
    assert forbidden_response.status_code == 403
