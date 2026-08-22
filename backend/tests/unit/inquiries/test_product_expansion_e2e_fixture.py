"""Run-scoped product-expansion E2E fixture checks."""

from __future__ import annotations

from copy import deepcopy
import json
from io import StringIO
from uuid import UUID

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.inquiries.models import Inquiry, SymptomEntry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory
from apps.workflow.models.idempotency_record import IdempotencyRecord
from apps.inquiries.management.commands import (
    create_product_expansion_e2e_fixture as fixture_module,
)


pytestmark = pytest.mark.django_db


PRODUCT_IDS = {
    "WPUIAC425SNW": UUID("f6789e6b-cdb6-5550-b535-e73e746561bb"),
    "WPUIAC606SNW": UUID("c092ea36-fbc3-53dd-98dc-a17e22ef83dc"),
}


def seed_customer() -> None:
    call_command("seed_demo_accounts", verbosity=0)


def create_product(model_code: str, *, supported: bool) -> ProductModel:
    return ProductModel.objects.create(
        public_id=PRODUCT_IDS[model_code],
        model_code=model_code,
        model_name=f"합성 {model_code} 정수기",
        generation_code=(
            "IAC425" if model_code == "WPUIAC425SNW" else "IAC606"
        ),
        manufacturer="SK매직",
        features={"synthetic": True},
        is_supported_mvp=supported,
        is_active=True,
    )


def invoke(
    model_code: str,
    run_id: str,
    *extra: str,
) -> dict:
    output = StringIO()
    call_command(
        "create_product_expansion_e2e_fixture",
        "--model-code",
        model_code,
        "--run-id",
        run_id,
        *extra,
        "--json",
        stdout=output,
    )
    return json.loads(output.getvalue())


def test_default_check_reports_runtime_activation_blocker_without_writes():
    seed_customer()
    create_product("WPUIAC425SNW", supported=False)

    result = invoke("WPUIAC425SNW", "iac425-readiness-001")

    assert result["fixture_readiness"] == "BLOCKED"
    assert result["known_blockers"] == [
        "PRODUCT_MODEL_RUNTIME_NOT_ENABLED"
    ]
    assert result["candidate_case_id"] == "E2E-IAC425-001"
    assert result["evidence_group_id"] == (
        "EVD-WPUIAC425SNW-HOT-WATER-STOPPED-001"
    )
    assert CustomerSubscription.objects.count() == 0
    assert Inquiry.objects.count() == 0


def test_apply_creates_iac425_inquiry_through_start_inquiry_runtime():
    seed_customer()
    product = create_product("WPUIAC425SNW", supported=True)

    result = invoke(
        "WPUIAC425SNW",
        "iac425-runtime-001",
        "--apply",
    )

    assert result["fixture_readiness"] == "READY_FOR_ISOLATED_E2E"
    assert result["created"] is True
    assert result["persisted"] is True
    assert result["status"] == Inquiry.Status.DRAFT
    assert result["state_version"] == 1
    assert result["allowed_actions"] == [
        "SUBMIT_SYMPTOM",
        "CANCEL_INQUIRY",
    ]
    assert result["topic_code"] == "hot_water_stopped"
    assert result["expected_resolution_mode"] == "CONSULTANT_HANDOFF"

    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    subscription = CustomerSubscription.objects.get(
        public_id=result["subscription_id"]
    )
    symptom = SymptomEntry.objects.get(inquiry=inquiry)
    assert subscription.product_model == product
    assert subscription.next_care_on is None
    assert inquiry.subscription == subscription
    assert inquiry.raw_text == "온수가 나오다가 중간에 멈췄어요."
    assert symptom.symptom_type_code == "hot_water_stopped"
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="START_INQUIRY",
        to_state=Inquiry.Status.DRAFT,
        state_version=1,
    ).exists()


def test_same_run_replays_without_duplicate_and_different_run_is_independent():
    seed_customer()
    create_product("WPUIAC425SNW", supported=True)

    first = invoke("WPUIAC425SNW", "iac425-replay-001", "--apply")
    replay = invoke("WPUIAC425SNW", "iac425-replay-001", "--apply")
    second = invoke("WPUIAC425SNW", "iac425-replay-002", "--apply")

    assert first["created"] is True
    assert replay["created"] is False
    assert replay["inquiry_id"] == first["inquiry_id"]
    assert second["inquiry_id"] != first["inquiry_id"]
    assert Inquiry.objects.count() == 2
    assert CustomerSubscription.objects.count() == 2
    assert IdempotencyRecord.objects.filter(
        operation_id="startInquiry"
    ).count() == 2


def test_iac606_uses_exact_model_case_and_keeps_care_schedule_disabled():
    seed_customer()
    create_product("WPUIAC606SNW", supported=True)

    result = invoke(
        "WPUIAC606SNW",
        "iac606-runtime-001",
        "--apply",
    )

    assert result["candidate_case_id"] == "E2E-IAC606-001"
    assert result["topic_code"] == "no_ice"
    assert result["expected_resolution_mode"] == "SELF_RESOLUTION"
    assert result["evidence_group_id"] == (
        "EVD-WPUIAC606SNW-NO-ICE-001"
    )
    subscription = CustomerSubscription.objects.get(
        public_id=result["subscription_id"]
    )
    assert subscription.product_model.model_code == "WPUIAC606SNW"
    assert subscription.next_care_on is None


def test_consumed_run_fails_closed_and_does_not_reset_history():
    seed_customer()
    create_product("WPUIAC425SNW", supported=True)
    result = invoke("WPUIAC425SNW", "iac425-consumed-001", "--apply")
    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    inquiry.status_code = Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    inquiry.state_version = 2
    inquiry.save(update_fields=["status_code", "state_version", "updated_at"])

    with pytest.raises(CommandError, match="새 run_id"):
        invoke("WPUIAC425SNW", "iac425-consumed-001", "--apply")

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == 2


def test_dry_run_executes_runtime_then_rolls_back_every_write():
    seed_customer()
    create_product("WPUIAC425SNW", supported=True)

    result = invoke(
        "WPUIAC425SNW",
        "iac425-dry-run-001",
        "--dry-run",
    )

    assert result["fixture_readiness"] == "DRY_RUN_ROLLED_BACK"
    assert result["persisted"] is False
    assert Inquiry.objects.count() == 0
    assert CustomerSubscription.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


@pytest.mark.parametrize(
    ("model_code", "run_id", "message"),
    [
        ("WPUJAC104DWH", "valid-run", "model_code"),
        ("WPUIAC425SNW", "contains space", "run_id"),
        ("WPUIAC425SNW", "../escape", "run_id"),
        ("WPUIAC425SNW", "a" * 65, "run_id"),
    ],
)
def test_invalid_scope_is_rejected(model_code: str, run_id: str, message: str):
    seed_customer()
    with pytest.raises(CommandError, match=message):
        invoke(model_code, run_id)


def test_missing_or_identity_mismatched_product_fails_closed():
    seed_customer()
    with pytest.raises(CommandError, match="db-product-expansion"):
        invoke("WPUIAC425SNW", "iac425-missing-product")

    ProductModel.objects.create(
        model_code="WPUIAC425SNW",
        model_name="잘못된 후보 제품",
        is_supported_mvp=True,
        is_active=True,
    )
    with pytest.raises(CommandError, match="public_id"):
        invoke("WPUIAC425SNW", "iac425-wrong-product")


def test_candidate_cross_model_evidence_mismatch_is_rejected():
    candidate = deepcopy(
        fixture_module.Command._load_candidate("WPUIAC425SNW")
    )
    candidate["evidence"]["exact_sales_code"] = "WPUIAC606SNW"
    with pytest.raises(CommandError, match="후보 계약"):
        fixture_module.Command._validate_candidate_contract(
            candidate,
            model_code="WPUIAC425SNW",
        )


def test_enable_candidate_requires_apply_and_never_runs_in_check_mode():
    seed_customer()
    create_product("WPUIAC425SNW", supported=False)

    with pytest.raises(CommandError, match="--apply"):
        invoke(
            "WPUIAC425SNW",
            "iac425-enable-without-apply",
            "--enable-candidate-product",
        )

    product = ProductModel.objects.get(model_code="WPUIAC425SNW")
    assert product.is_supported_mvp is False


def test_explicit_candidate_activation_is_limited_to_isolated_test_database(
    monkeypatch,
):
    seed_customer()
    create_product("WPUIAC425SNW", supported=False)
    monkeypatch.setitem(connection.settings_dict, "NAME", "test_waterbridge")

    result = invoke(
        "WPUIAC425SNW",
        "iac425-isolated-activation",
        "--apply",
        "--enable-candidate-product",
    )

    assert result["fixture_readiness"] == "READY_FOR_ISOLATED_E2E"
    product = ProductModel.objects.get(model_code="WPUIAC425SNW")
    assert product.is_supported_mvp is True


@pytest.mark.parametrize(
    (
        "scenario_id",
        "model_code",
        "case_name",
        "topic_code",
        "risk_level",
        "guidance_status",
        "raw_symptom",
    ),
    [
        (
            "SYN-IAC425-101",
            "WPUIAC425SNW",
            "IAC425_GENERAL",
            "symptom_cold_lock",
            "caution",
            "PENDING_CONSULTATION",
            (
                "WPU-IAC425에서 냉수 버튼을 누르면 소리가 나고 잠금 표시가 "
                "깜빡입니다. 정수는 나옵니다."
            ),
        ),
        (
            "SYN-IAC425-108",
            "WPUIAC425SNW",
            "IAC425_LEAK",
            "symptom_leak",
            "danger",
            "TOTAL_STOP",
            (
                "물받이 밖으로 물이 새고 버튼을 누를 때마다 띵띵띵 소리가 "
                "계속 납니다. 바닥에 물이 번지고 있어요."
            ),
        ),
        (
            "SYN-IAC606-101",
            "WPUIAC606SNW",
            "IAC606_GENERAL",
            "symptom_cold_lock",
            "caution",
            "PENDING_CONSULTATION",
            (
                "WPU-IAC606인데 냉수 버튼을 누르면 부저음이 나고 잠금 표시가 "
                "깜빡여요. 물은 정수로는 나옵니다."
            ),
        ),
        (
            "SYN-IAC606-107",
            "WPUIAC606SNW",
            "IAC606_LEAK",
            "symptom_leak",
            "danger",
            "TOTAL_STOP",
            (
                "물받이는 넘치지 않았는데 제품 밑으로 물이 번지고, 버튼을 "
                "누를 때마다 띵띵띵 소리가 납니다."
            ),
        ),
    ],
)
def test_approved_product_validation_scenario_creates_exact_runtime_fixture(
    scenario_id,
    model_code,
    case_name,
    topic_code,
    risk_level,
    guidance_status,
    raw_symptom,
):
    seed_customer()
    create_product(model_code, supported=True)

    result = invoke(
        model_code,
        f"{case_name.lower()}-001",
        "--scenario-id",
        scenario_id,
        "--apply",
    )

    assert result["scenario_id"] == scenario_id
    assert result["case_name"] == case_name
    assert result["model_code"] == model_code
    assert result["topic_code"] == topic_code
    assert result["symptom_description"] == raw_symptom
    assert result["expected_fallback_reason_code"] == (
        "RUNTIME_PRODUCT_NOT_APPROVED"
    )
    assert result["expected_risk_level"] == risk_level
    assert result["expected_usage_guidance_status"] == guidance_status
    assert result["expected_runtime_evidence_count"] == 0
    assert result["expected_vector_call_count"] == 0
    assert result["expected_provider_call_count"] == 0

    inquiry = Inquiry.objects.get(public_id=result["inquiry_id"])
    symptom = SymptomEntry.objects.get(inquiry=inquiry)
    assert inquiry.raw_text == raw_symptom
    assert symptom.symptom_type_code == topic_code


def test_same_scenario_run_replays_without_duplicate():
    seed_customer()
    create_product("WPUIAC425SNW", supported=True)

    args = (
        "--scenario-id",
        "SYN-IAC425-101",
        "--apply",
    )
    first = invoke("WPUIAC425SNW", "iac425-general-replay", *args)
    replay = invoke("WPUIAC425SNW", "iac425-general-replay", *args)

    assert first["created"] is True
    assert replay["created"] is False
    assert replay["inquiry_id"] == first["inquiry_id"]
    assert Inquiry.objects.count() == 1
    assert IdempotencyRecord.objects.filter(
        operation_id="startInquiry"
    ).count() == 1


def test_same_model_and_run_with_different_scenario_stays_independent():
    seed_customer()
    create_product("WPUIAC425SNW", supported=True)

    general = invoke(
        "WPUIAC425SNW",
        "iac425-shared-run",
        "--scenario-id",
        "SYN-IAC425-101",
        "--apply",
    )
    leak = invoke(
        "WPUIAC425SNW",
        "iac425-shared-run",
        "--scenario-id",
        "SYN-IAC425-108",
        "--apply",
    )

    assert general["inquiry_id"] != leak["inquiry_id"]
    assert general["request_correlation_id"] != leak["request_correlation_id"]
    assert Inquiry.objects.count() == 2


def test_product_validation_scenario_rejects_model_mismatch():
    seed_customer()
    create_product("WPUIAC606SNW", supported=True)

    with pytest.raises(CommandError, match="scenario_id와 model_code"):
        invoke(
            "WPUIAC606SNW",
            "cross-model-scenario",
            "--scenario-id",
            "SYN-IAC425-101",
            "--apply",
        )


def test_product_validation_scenario_fails_closed_on_oracle_drift():
    payload = json.loads(
        fixture_module.MANUAL_SCENARIO_FILE.read_text(encoding="utf-8")
    )
    scenario = deepcopy(
        next(
            item
            for item in payload["scenarios"]
            if item["scenario_id"] == "SYN-IAC606-101"
        )
    )
    scenario["runtime_profiles"]["mvp"]["current_runtime"]["ai"][
        "risk_level"
    ] = "danger"

    with pytest.raises(CommandError, match="승인된 MVP Oracle"):
        fixture_module.Command._validate_product_validation_scenario(
            scenario,
            policy=fixture_module.APPROVED_PRODUCT_VALIDATION_SCENARIOS[
                "SYN-IAC606-101"
            ],
        )
