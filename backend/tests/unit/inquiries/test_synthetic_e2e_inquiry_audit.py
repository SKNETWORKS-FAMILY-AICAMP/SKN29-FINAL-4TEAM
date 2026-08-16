"""Read-only synthetic E2E inquiry audit command checks."""

from __future__ import annotations

import json
from datetime import date
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.management.commands.audit_synthetic_e2e_inquiry import (
    stage_blockers,
)
from apps.inquiries.models import Inquiry
from apps.inquiries.services.synthetic_e2e_assignment_service import (
    SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def base_snapshot() -> dict:
    return {
        "inquiry": {
            "inquiry_id": str(uuid4()),
            "inquiry_code": "INQ-AUDIT-001",
            "channel_code": "MOBILE",
            "status_code": "AI_GUIDANCE",
            "state_version": 3,
            "scenario_code": None,
            "owner_code": "DEMO-CUSTOMER-001",
            "owner_role": "CUSTOMER",
            "owner_is_synthetic": True,
            "assigned_role_code": "NONE",
            "assigned_user_code": None,
            "product_model_code": "WPUJAC104DWH",
        },
        "ai": {
            "run_count": 1,
            "runs": [
                {
                    "task_type_code": "ANALYZE_SYMPTOM",
                    "status_code": "SUCCEEDED",
                    "schema_validation_status_code": "PASSED",
                    "correlation_id": "corr-submit",
                }
            ],
            "assessment_count": 1,
            "assessments": [{}],
        },
        "guidance": {"count": 1, "items": [{}]},
        "evidence": {"count": 1, "verified_count": 1, "items": [{}]},
        "consultation": {"count": 0, "items": []},
        "workflow": {
            "history_count": 3,
            "history": [
                {
                    "event_code": "START_INQUIRY",
                    "state_version": 1,
                    "correlation_id": "corr-create",
                },
                {
                    "event_code": "SUBMIT_SYMPTOM",
                    "state_version": 2,
                    "correlation_id": "corr-submit",
                },
                {
                    "event_code": "SAFE_GUIDANCE_READY",
                    "state_version": 3,
                    "correlation_id": "corr-submit",
                },
            ],
            "idempotency_record_count": 2,
            "idempotency_records": [
                {"operation_id": "startInquiry"},
                {"operation_id": "submitSymptom"},
            ],
        },
    }


def test_g1_snapshot_is_ready_and_rejects_unverified_evidence():
    snapshot = base_snapshot()
    assert stage_blockers(snapshot, "G1") == []

    snapshot["evidence"]["verified_count"] = 0
    assert "EVIDENCE_LINK_NOT_ALL_VERIFIED" in stage_blockers(
        snapshot,
        "G1",
    )


def test_g1_accepts_multiple_successful_ai_runs_from_follow_up_answers():
    snapshot = base_snapshot()
    snapshot["inquiry"]["state_version"] = 4
    snapshot["ai"]["run_count"] = 2
    snapshot["ai"]["runs"].append(
        {
            "task_type_code": "ANALYZE_SYMPTOM",
            "status_code": "SUCCEEDED",
            "schema_validation_status_code": "PASSED",
            "correlation_id": "corr-answer",
        }
    )
    snapshot["ai"]["assessment_count"] = 2
    snapshot["guidance"]["count"] = 2
    snapshot["evidence"].update(count=2, verified_count=2)
    snapshot["workflow"]["history"][-1]["state_version"] = 4
    snapshot["workflow"]["history"].insert(
        -1,
        {
            "event_code": "SUBMIT_ANSWERS",
            "state_version": 3,
            "correlation_id": "corr-answer",
        },
    )
    snapshot["workflow"]["idempotency_records"].append(
        {"operation_id": "submitFollowUpAnswers"}
    )

    assert stage_blockers(snapshot, "G1") == []

    snapshot["ai"]["runs"][-1]["status_code"] = "FAILED"
    assert "AI_RUN_NOT_SUCCEEDED" in stage_blockers(snapshot, "G1")


def test_g3_and_g4_stage_boundaries_are_distinct():
    snapshot = base_snapshot()
    snapshot["inquiry"].update(
        status_code="CONSULTATION_REQUIRED",
        state_version=4,
        scenario_code=SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
        assigned_role_code="CONSULTANT",
        assigned_user_code="DEMO-CONSULTANT-001",
    )
    snapshot["workflow"]["history"].append(
        {
            "event_code": "REQUEST_CONSULTATION",
            "state_version": 4,
            "correlation_id": "corr-request",
        }
    )
    snapshot["workflow"]["idempotency_records"].append(
        {"operation_id": "requestConsultation"}
    )
    snapshot["consultation"] = {
        "count": 1,
        "items": [
            {
                "status": "WAITING",
                "consultant__username": None,
            }
        ],
    }
    assert stage_blockers(snapshot, "G3") == []
    assert "G4_STATUS_IS_NOT_COMPLETION_PENDING" in stage_blockers(
        snapshot,
        "G4",
    )

    snapshot["inquiry"].update(
        status_code="COMPLETION_PENDING",
        state_version=8,
    )
    for version, event in enumerate(
        (
            "START_CONSULTATION",
            "UPDATE_CONSULTATION_SUMMARY",
            "CONFIRM_CONSULTATION_SUMMARY",
            "CONSULTATION_COMPLETED",
        ),
        start=5,
    ):
        snapshot["workflow"]["history"].append(
            {
                "event_code": event,
                "state_version": version,
                "correlation_id": f"corr-{version}",
            }
        )
    snapshot["workflow"]["idempotency_records"].extend(
        {"operation_id": operation}
        for operation in (
            "startConsultation",
            "updateConsultationSummary",
            "confirmConsultationSummary",
            "completeConsultation",
        )
    )
    snapshot["consultation"]["items"][0].update(
        status="COMPLETED",
        consultant__username="DEMO-CONSULTANT-001",
        confirmed_summary="합성 상담 완료",
        summary_confirmed_at="2026-08-14T20:00:00+09:00",
        completed_at="2026-08-14T20:01:00+09:00",
    )
    assert stage_blockers(snapshot, "G4") == []
    assert stage_blockers(snapshot, "G5") == []


def test_command_outputs_sanitized_blocked_snapshot_without_raw_text():
    owner = User.objects.create_user(
        username="DEMO-CUSTOMER-001",
        full_name="합성 고객",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    customer = CustomerProfile.objects.create(
        user=owner,
        customer_no="DEMO-CUSTOMER-001",
        customer_name="합성 고객",
        phone="010-0000-0000",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code="WPUJAC104DWH",
        model_name="합성 정수기",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no="AUDIT-E2E-001",
        customer=customer,
        product_model=product,
        serial_no="AUDIT-E2E-SERIAL-001",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=owner,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="출력되면 안 되는 고객 원문",
    )
    output = StringIO()

    call_command(
        "audit_synthetic_e2e_inquiry",
        "--inquiry-id",
        str(inquiry.public_id),
        "--expect-stage",
        "G1",
        stdout=output,
    )

    result = json.loads(output.getvalue())
    assert result["status"] == "BLOCKED"
    assert result["secret_values_printed"] is False
    assert result["raw_customer_text_printed"] is False
    assert "출력되면 안 되는 고객 원문" not in output.getvalue()


def test_require_ready_and_unknown_inquiry_exit_nonzero():
    with pytest.raises(CommandError, match="찾을 수 없습니다"):
        call_command(
            "audit_synthetic_e2e_inquiry",
            "--inquiry-id",
            str(uuid4()),
            "--expect-stage",
            "G1",
        )

    owner = User.objects.create_user(
        username="AUDIT-OTHER-CUSTOMER",
        full_name="Audit other customer",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    customer = CustomerProfile.objects.create(
        user=owner,
        customer_no="AUDIT-OTHER-CUSTOMER",
        customer_name="합성 고객",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code="AUDIT-OTHER-MODEL",
        model_name="다른 제품",
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no="AUDIT-E2E-002",
        customer=customer,
        product_model=product,
        serial_no="AUDIT-E2E-SERIAL-002",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=owner,
        channel_code=Inquiry.Channel.WEB,
        raw_text="합성 감사",
    )
    with pytest.raises(CommandError, match="BLOCKED"):
        call_command(
            "audit_synthetic_e2e_inquiry",
            "--inquiry-id",
            str(inquiry.public_id),
            "--expect-stage",
            "G1",
            "--require-ready",
            stdout=StringIO(),
        )
