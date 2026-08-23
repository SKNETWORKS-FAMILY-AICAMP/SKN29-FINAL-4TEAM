"""Run-scoped Web G4 consultant-visibility boundary checks."""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.workflow.models import TransitionHistory


pytestmark = pytest.mark.django_db


def seed_dependencies() -> None:
    call_command("seed_demo_accounts", verbosity=0)
    call_command("seed_demo_products", verbosity=0)
    call_command("seed_demo_subscriptions", verbosity=0)


def create_fixture(run_id: str) -> dict:
    output = StringIO()
    call_command(
        "create_web_concealed_e2e_fixture",
        "--run-id",
        run_id,
        "--json",
        stdout=output,
    )
    return json.loads(output.getvalue())


def test_command_creates_other_consultant_assignment():
    seed_dependencies()

    result = create_fixture("playwright-concealed-001")

    assert result == {
        "allowed_actions_for_assignee": ["START_CONSULTATION"],
        "assigned_consultant": "SYN-WEB-G4-CONSULTANT-404",
        "concealed_from": "DEMO-CONSULTANT-001",
        "consultation_status": "ASSIGNED",
        "created": True,
        "expected_error_code": "RESOURCE_NOT_FOUND",
        "expected_http_status": 404,
        "fixture_readiness": "READY",
        "fixture_scope": "WEB_G4_CONCEALED_404",
        "inquiry_code": result["inquiry_code"],
        "inquiry_id": result["inquiry_id"],
        "run_id": "playwright-concealed-001",
        "state_version": 3,
        "status": "CONSULTATION_REQUIRED",
    }
    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    concealed_consultant = User.objects.get(
        username="SYN-WEB-G4-CONSULTANT-404"
    )
    assert inquiry.assigned_user == concealed_consultant
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    consultation = Consultation.objects.get(inquiry=inquiry)
    assert consultation.status == Consultation.Status.ASSIGNED
    assert consultation.consultant == concealed_consultant
    assert consultation.started_at is None
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="CLAIM_CONSULTATION",
        from_state=Inquiry.Status.CONSULTATION_REQUIRED,
        to_state=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
    ).exists()


def test_demo_consultant_get_and_start_are_concealed_as_404():
    seed_dependencies()
    result = create_fixture("playwright-concealed-boundary-001")
    visible_consultant = User.objects.get(username="DEMO-CONSULTANT-001")
    concealed_consultant = User.objects.get(
        username="SYN-WEB-G4-CONSULTANT-404"
    )

    client = APIClient()
    client.force_authenticate(user=visible_consultant)
    detail = client.get(f"/api/v1/inquiries/{result['inquiry_id']}")
    start = client.post(
        f"/api/v1/inquiries/{result['inquiry_id']}/start-consultation",
        {"state_version": result["state_version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="concealed-boundary-start",
    )

    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert start.status_code == 404
    assert start.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    client.force_authenticate(user=concealed_consultant)
    assignee_detail = client.get(
        f"/api/v1/inquiries/{result['inquiry_id']}"
    )
    assert assignee_detail.status_code == 200


def test_same_unconsumed_run_id_is_idempotent():
    seed_dependencies()

    first = create_fixture("playwright-concealed-replay-001")
    second = create_fixture("playwright-concealed-replay-001")

    assert first["created"] is True
    assert second["created"] is False
    assert second["inquiry_id"] == first["inquiry_id"]
    assert Inquiry.objects.filter(public_id=first["inquiry_id"]).count() == 1
    assert Consultation.objects.filter(
        inquiry__public_id=first["inquiry_id"]
    ).count() == 1


@pytest.mark.parametrize(
    "run_id",
    ["", "contains space", "한글-run", "a" * 65, "../escape"],
)
def test_invalid_run_id_is_rejected(run_id: str):
    seed_dependencies()

    with pytest.raises(CommandError, match="run_id"):
        create_fixture(run_id)


def test_missing_demo_dependencies_fails_closed():
    with pytest.raises(CommandError, match="seed_demo_accounts"):
        create_fixture("playwright-concealed-missing")
