"""Repeatable run-scoped Web consultation fixture checks."""

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
        "create_web_consultation_e2e_fixture",
        "--run-id",
        run_id,
        "--json",
        stdout=output,
    )
    return json.loads(output.getvalue())


def test_command_creates_ready_consultation_boundary_through_runtime():
    seed_dependencies()

    result = create_fixture("playwright-20260819-001")

    assert result == {
        "allowed_actions": ["START_CONSULTATION"],
        "assigned_consultant": "DEMO-CONSULTANT-001",
        "consultation_status": "WAITING",
        "created": True,
        "fixture_readiness": "READY",
        "fixture_scope": "WEB_G4_CONSULTATION",
        "g3_audit_result": "NOT_APPLICABLE",
        "inquiry_code": result["inquiry_code"],
        "inquiry_id": result["inquiry_id"],
        "known_blocker": "NONE",
        "request_correlation_id": result["request_correlation_id"],
        "run_id": "playwright-20260819-001",
        "state_version": 2,
        "status": "CONSULTATION_REQUIRED",
    }
    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    consultant = User.objects.get(username="DEMO-CONSULTANT-001")
    consultation = Consultation.objects.get(inquiry=inquiry)
    assert inquiry.assigned_user == consultant
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert consultation.status == Consultation.Status.WAITING
    assert consultation.consultant is None
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="REQUEST_CONSULTATION",
        from_state=Inquiry.Status.AI_GUIDANCE,
        to_state=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=2,
    ).exists()


def test_same_unconsumed_run_id_is_idempotent():
    seed_dependencies()

    first = create_fixture("playwright-replay-001")
    second = create_fixture("playwright-replay-001")

    assert first["created"] is True
    assert second["created"] is False
    assert second["inquiry_id"] == first["inquiry_id"]
    assert second["request_correlation_id"] == first["request_correlation_id"]
    assert Inquiry.objects.filter(
        public_id=first["inquiry_id"],
    ).count() == 1
    assert Consultation.objects.filter(
        inquiry__public_id=first["inquiry_id"],
    ).count() == 1


def test_different_run_ids_create_independent_active_inquiries():
    seed_dependencies()

    first = create_fixture("playwright-worker-001")
    second = create_fixture("playwright-worker-002")

    assert first["inquiry_id"] != second["inquiry_id"]
    assert first["inquiry_code"] != second["inquiry_code"]
    assert first["request_correlation_id"] != second["request_correlation_id"]
    assert Inquiry.objects.filter(
        public_id__in=[first["inquiry_id"], second["inquiry_id"]],
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
    ).count() == 2


def test_created_fixture_completes_real_web_runtime_and_requires_new_run_id():
    seed_dependencies()
    result = create_fixture("playwright-runtime-001")
    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    consultant = User.objects.get(username="DEMO-CONSULTANT-001")
    client = APIClient()
    client.force_authenticate(user=consultant)

    def request(method: str, path: str, body: dict, key: str):
        return getattr(client, method)(
            path,
            body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    started = request(
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": inquiry.state_version},
        "fixture-runtime-start",
    )
    assert started.status_code == 200, started.json()
    inquiry.refresh_from_db()

    saved = request(
        "patch",
        f"/api/v1/inquiries/{inquiry.public_id}/consultation-summary",
        {
            "state_version": inquiry.state_version,
            "summary": "합성 문의를 확인하고 방문 없이 해결했습니다.",
            "consultation_note": "Web Playwright 반복 Fixture 검증",
            "result_code": "COMPLETED_NO_VISIT",
            "usage_guidance_status": "NORMAL",
        },
        "fixture-runtime-save",
    )
    assert saved.status_code == 200, saved.json()
    inquiry.refresh_from_db()

    confirmed = request(
        "post",
        (
            f"/api/v1/inquiries/{inquiry.public_id}"
            "/consultation-summary/confirm"
        ),
        {"state_version": inquiry.state_version},
        "fixture-runtime-confirm",
    )
    assert confirmed.status_code == 200, confirmed.json()
    inquiry.refresh_from_db()

    completed = request(
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/complete-consultation",
        {"state_version": inquiry.state_version},
        "fixture-runtime-complete",
    )
    assert completed.status_code == 200, completed.json()
    assert completed.json()["data"]["status"] == "COMPLETION_PENDING"

    with pytest.raises(CommandError, match="새 run_id"):
        create_fixture("playwright-runtime-001")

    next_result = create_fixture("playwright-runtime-002")
    assert next_result["inquiry_id"] != result["inquiry_id"]
    assert next_result["status"] == "CONSULTATION_REQUIRED"
    assert next_result["allowed_actions"] == ["START_CONSULTATION"]


def test_consumed_run_id_fails_closed_without_resetting_history():
    seed_dependencies()
    result = create_fixture("playwright-consumed-001")
    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    inquiry.status_code = Inquiry.Status.CONSULTATION_IN_PROGRESS
    inquiry.state_version = 3
    inquiry.save(update_fields=["status_code", "state_version", "updated_at"])

    with pytest.raises(CommandError, match="새 run_id"):
        create_fixture("playwright-consumed-001")

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_IN_PROGRESS
    assert inquiry.state_version == 3


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
        create_fixture("playwright-missing-dependency")
