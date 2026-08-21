"""Run-scoped Backend AI Context fixture checks."""

from __future__ import annotations

from datetime import date
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory
from apps.workflow.models.idempotency_record import IdempotencyRecord


pytestmark = pytest.mark.django_db


def seed_canonical_dependency(*, model_code: str = "WPUJAC104DWH") -> None:
    owner = User.objects.create_user(
        username="CUS-0001",
        password=None,
        full_name="합성 Context 고객",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    customer = CustomerProfile.objects.create(
        user=owner,
        customer_no="CUS-0001",
        customer_name="합성 Context 고객",
        phone="010-0000-0000",
        address_line1="합성 검증 주소",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=model_code,
        model_name="JAC104 합성 정수기",
        generation_code="D",
        manufacturer="SK매직",
        features={"model_family": "WPU-JAC104"},
        is_supported_mvp=True,
        is_active=True,
    )
    CustomerSubscription.objects.create(
        contract_no="SUB-SYN-0001",
        customer=customer,
        product_model=product,
        serial_no="SYN-SERIAL-0001",
        management_type_code=(
            CustomerSubscription.ManagementType.VISIT_CARE
        ),
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
        installation_address="합성 검증 주소",
    )


def invoke(run_id: str, *extra: str) -> dict:
    output = StringIO()
    call_command(
        "create_ai_context_e2e_fixture",
        "--run-id",
        run_id,
        *extra,
        "--json",
        stdout=output,
    )
    return json.loads(output.getvalue())


def test_check_mode_reports_readiness_without_writes():
    seed_canonical_dependency()

    result = invoke("context-check-001")

    assert result["fixture_readiness"] == "READY_FOR_APPLY"
    assert result["model_code"] == "WPUJAC104DWH"
    assert Inquiry.objects.count() == 0


def test_apply_creates_exact_jac104_context_through_runtime():
    seed_canonical_dependency()

    result = invoke("context-runtime-001", "--apply")

    assert result["fixture_readiness"] == "READY_FOR_CONTEXT_E2E"
    assert result["created"] is True
    assert result["model_code"] == "WPUJAC104DWH"
    assert result["status"] == Inquiry.Status.DRAFT
    assert result["state_version"] == 1
    assert result["allowed_actions"] == [
        "SUBMIT_SYMPTOM",
        "CANCEL_INQUIRY",
    ]

    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    assert inquiry.subscription.product_model.model_code == "WPUJAC104DWH"
    assert SymptomEntry.objects.filter(
        inquiry=inquiry,
        symptom_type_code="LOW_FLOW",
        is_customer_confirmed=True,
    ).count() == 1
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="START_INQUIRY",
        to_state=Inquiry.Status.DRAFT,
        state_version=1,
    ).exists()


def test_same_run_replays_without_duplicate_and_new_run_is_independent():
    seed_canonical_dependency()

    first = invoke("context-replay-001", "--apply")
    replay = invoke("context-replay-001", "--apply")
    second = invoke("context-replay-002", "--apply")

    assert first["created"] is True
    assert replay["created"] is False
    assert replay["inquiry_id"] == first["inquiry_id"]
    assert second["inquiry_id"] != first["inquiry_id"]
    assert Inquiry.objects.count() == 2
    assert IdempotencyRecord.objects.filter(
        operation_id="startInquiry"
    ).count() == 2


def test_consumed_run_fails_closed_without_resetting_history():
    seed_canonical_dependency()
    result = invoke("context-consumed-001", "--apply")
    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    inquiry.status_code = Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    inquiry.state_version = 2
    inquiry.save(update_fields=["status_code", "state_version", "updated_at"])

    with pytest.raises(CommandError, match="새 run_id"):
        invoke("context-consumed-001", "--apply")

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 2


@pytest.mark.parametrize(
    "run_id",
    ["", "contains space", "한글-run", "a" * 65, "../escape"],
)
def test_invalid_run_id_is_rejected(run_id: str):
    seed_canonical_dependency()
    with pytest.raises(CommandError, match="run_id"):
        invoke(run_id)


def test_missing_or_wrong_canonical_dependency_fails_closed():
    with pytest.raises(CommandError, match="db-smoke"):
        invoke("context-missing-001")

    seed_canonical_dependency(model_code="WRONG-MODEL")
    with pytest.raises(CommandError, match="JAC104"):
        invoke("context-wrong-001")
