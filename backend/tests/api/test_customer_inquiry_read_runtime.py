"""Runtime checks for CUSTOMER-owned inquiry and question reads."""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
from uuid import UUID, uuid4

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.inquiries.models import (
    FollowUpAnswer,
    Guidance,
    GuidanceItem,
    Inquiry,
    InquiryQA,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory


pytestmark = pytest.mark.django_db


def create_user(sequence: int, *, role: str = User.Role.CUSTOMER) -> User:
    user = User.objects.create_user(
        username=f"CUSTOMER-INQUIRY-READ-{role}-{sequence:03d}",
        full_name=f"Customer inquiry read {role} {sequence}",
        role_code=role,
        employee_no=(None if role == User.Role.CUSTOMER else f"EMP-{sequence:03d}"),
        is_synthetic=True,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"CUSTOMER-INQUIRY-READ-{sequence:03d}",
            customer_name=f"합성 고객 {sequence}",
            phone=f"010-9999-{sequence:04d}",
            address_line1="고객 읽기 API에 노출하면 안 되는 주소",
            is_synthetic=True,
        )
    return user


def create_subscription(owner: User, sequence: int) -> CustomerSubscription:
    product = ProductModel.objects.create(
        model_code=f"CUSTOMER-READ-MODEL-{sequence:03d}",
        model_name=f"고객 조회 제품 {sequence}",
        generation_code="D",
        manufacturer="SK매직",
        features={"private": "must-not-leak"},
        is_supported_mvp=True,
        is_active=True,
    )
    return CustomerSubscription.objects.create(
        contract_no=f"CUSTOMER-READ-CONTRACT-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"CUSTOMER-READ-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 7, 1),
        installation_address="고객 조회 API에 노출하면 안 되는 설치 주소",
    )


def create_inquiry(
    owner: User,
    sequence: int,
    *,
    public_id: UUID | None = None,
) -> Inquiry:
    return Inquiry.objects.create(
        public_id=public_id or uuid4(),
        inquiry_code=f"CUSTOMER-READ-INQ-{sequence:03d}",
        subscription=create_subscription(owner, sequence),
        initiated_by=owner,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="고객 원문은 Snapshot에 노출하지 않습니다.",
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=2,
        risk_level_code=Inquiry.RiskLevel.CAUTION,
        evidence_ids=["INTERNAL-EVIDENCE-ID"],
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def guidance_payload(
    *,
    message: str = "온수 기능은 잠시 중지하고 냉수 출수 상태를 확인해 주세요.",
) -> dict:
    return {
        "safety_assessment": {
            "risk_level": "caution",
            "requires_consultation": False,
        },
        "usage_guidance": {
            "guidance_status": "PARTIAL_STOP",
            "message": message,
            "restricted_functions": ["온수 출수"],
            "next_actions": ["냉수 출수량을 확인해 주세요."],
        },
        "evidence_references": [
            {
                "chunk_id": "INTERNAL-CHUNK-MUST-NOT-LEAK",
                "similarity_score": 0.99,
            }
        ],
    }


def create_ai_guidance(
    inquiry: Inquiry,
    sequence: int,
    *,
    guidance_version: int = 1,
    payload: dict | None = None,
    run_status: str = AIRun.Status.SUCCEEDED,
    schema_status: str = AIRun.SchemaValidationStatus.PASSED,
    task_type: str = AIRun.TaskType.ANALYZE_SYMPTOM,
) -> Guidance:
    now = timezone.now()
    validated_payload = guidance_payload() if payload is None else payload
    run_kwargs = {
        "inquiry": inquiry,
        "task_type_code": task_type,
        "request_schema_version": "3.0.0",
        "response_schema_version": "3.0.0",
        "model_provider": "local",
        "model_name": "baseline-guidance-test",
        "model_config_version": "3.0.0",
        "model_config": {"mode": "local"},
        "prompt_version": "baseline-guidance-v1",
        "input_payload": {"inquiry_id": str(inquiry.public_id)},
        "input_sha256": hashlib.sha256(
            f"{inquiry.public_id}:{sequence}".encode("utf-8")
        ).hexdigest(),
        "idempotency_key": f"customer-guidance-read-{sequence:03d}",
        "correlation_id": uuid4(),
        "validated_output_payload": validated_payload,
        "schema_validation_status_code": schema_status,
        "schema_validation_errors": [],
        "status_code": run_status,
        "started_at": now,
        "completed_at": now,
    }
    if run_status in {AIRun.Status.FAILED, AIRun.Status.TIMED_OUT}:
        run_kwargs.update(
            validated_output_payload=None,
            raw_output_text="invalid output",
            schema_validation_errors=[
                {"path": "usage_guidance", "message": "invalid"}
            ],
            error_code="AI-FAILED-01",
            error_message="AI failed",
        )
    run = AIRun.objects.create(**run_kwargs)
    usage = validated_payload.get("usage_guidance", {})
    summary = usage.get("message")
    if not isinstance(summary, str) or not summary.strip():
        summary = "검증 대기 Guidance"
    guidance = Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=guidance_version,
        review_status_code="PENDING",
        title="AI 사용 안내 초안",
        summary_text=summary,
        safety_notice="상태가 악화되면 상담을 요청해 주세요.",
        evidence_sufficiency_code="CANDIDATE",
        requires_consultation=(
            validated_payload.get("safety_assessment", {}).get(
                "requires_consultation"
            )
            is True
        ),
        generated_by_ai_run=run,
    )
    GuidanceItem.objects.create(
        guidance=guidance,
        step_no=1,
        action_type_code="NEXT_ACTION",
        instruction_text="냉수 출수량을 확인해 주세요.",
    )
    return guidance


def test_customer_snapshot_returns_exact_owned_projection(
    django_assert_num_queries,
):
    owner = create_user(1)
    inquiry = create_inquiry(owner, 1)

    with django_assert_num_queries(2):
        response = authenticated_client(owner).get(
            f"/api/v1/me/inquiries/{inquiry.public_id}"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["metadata"]["correlation_id"] == response[
        "X-Correlation-ID"
    ]
    data = payload["data"]
    projection = dict(data)
    updated_at = projection.pop("updated_at")
    assert projection == {
        "inquiry_id": str(inquiry.public_id),
        "status_code": Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        "state_version": 2,
        "subscription_id": str(inquiry.subscription.public_id),
        "product": {
            "model_code": inquiry.subscription.product_model.model_code,
        },
        "allowed_actions": [
            {
                "code": "CANCEL_INQUIRY",
                "label": "문의 취소",
                "operation_id": "cancelInquiry",
                "style": "DESTRUCTIVE",
                "requires_confirmation": True,
                "confirmation_message": "문의를 취소하시겠습니까?",
            }
        ],
        "system_notice": None,
    }
    assert parse_datetime(updated_at) == inquiry.updated_at

    serialized = str(data)
    for forbidden in (
        inquiry.inquiry_code,
        inquiry.raw_text,
        inquiry.subscription.contract_no,
        inquiry.subscription.serial_no,
        inquiry.subscription.installation_address,
        owner.customer_profile.customer_name,
        owner.customer_profile.phone,
        "INTERNAL-EVIDENCE-ID",
        "features",
        "risk_level_code",
        "assigned_user",
    ):
        assert forbidden not in serialized


def test_customer_snapshot_projects_timeout_notice_until_next_state_change(
    django_assert_num_queries,
):
    owner = create_user(2)
    inquiry = create_inquiry(owner, 2)
    correlation_id = uuid4()
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
    )
    TransitionHistory.objects.create(
        inquiry=inquiry,
        actor=None,
        changed_by_type_code=TransitionHistory.ChangedByType.SYSTEM,
        event_code="AI_PROCESSING_TIMEOUT",
        from_state=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        to_state=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
        correlation_id=correlation_id,
        idempotency_key="customer-timeout-notice-001",
    )

    with django_assert_num_queries(2):
        timeout_response = authenticated_client(owner).get(
            f"/api/v1/me/inquiries/{inquiry.public_id}"
        )

    assert timeout_response.status_code == 200
    assert timeout_response.json()["data"]["system_notice"] == (
        "AI 안내 생성이 지연되어 상담으로 연결합니다."
    )

    TransitionHistory.objects.create(
        inquiry=inquiry,
        actor=owner,
        event_code="REQUEST_CONSULTATION",
        from_state=Inquiry.Status.CONSULTATION_REQUIRED,
        to_state=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=4,
        correlation_id=uuid4(),
        idempotency_key="customer-timeout-notice-002",
    )
    Inquiry.objects.filter(pk=inquiry.pk).update(state_version=4)
    same_state_response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}"
    )
    assert same_state_response.json()["data"]["system_notice"] == (
        "AI 안내 생성이 지연되어 상담으로 연결합니다."
    )

    TransitionHistory.objects.create(
        inquiry=inquiry,
        actor=None,
        changed_by_type_code=TransitionHistory.ChangedByType.SYSTEM,
        event_code="START_CONSULTATION",
        from_state=Inquiry.Status.CONSULTATION_REQUIRED,
        to_state=Inquiry.Status.CONSULTATION_IN_PROGRESS,
        state_version=5,
        correlation_id=uuid4(),
        idempotency_key="customer-timeout-notice-003",
    )
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_IN_PROGRESS,
        state_version=5,
    )
    progressed_response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}"
    )
    assert progressed_response.json()["data"]["system_notice"] is None


def test_customer_active_inquiry_returns_latest_owned_non_terminal_snapshot(
    django_assert_num_queries,
):
    owner = create_user(60)
    other = create_user(61)
    older = create_inquiry(owner, 60)
    latest = create_inquiry(owner, 61)
    terminal = create_inquiry(owner, 62)
    other_inquiry = create_inquiry(other, 63)
    now = timezone.now()

    Inquiry.objects.filter(pk=older.pk).update(
        status_code=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
        updated_at=now - timedelta(minutes=3),
    )
    Inquiry.objects.filter(pk=latest.pk).update(
        status_code=Inquiry.Status.COMPLETION_PENDING,
        state_version=9,
        updated_at=now - timedelta(minutes=2),
    )
    Inquiry.objects.filter(pk=terminal.pk).update(
        status_code=Inquiry.Status.RESOLVED,
        state_version=10,
        updated_at=now,
    )
    Inquiry.objects.filter(pk=other_inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=5,
        updated_at=now + timedelta(minutes=1),
    )

    with django_assert_num_queries(2):
        response = authenticated_client(owner).get(
            "/api/v1/me/inquiries/active"
        )

    assert response.status_code == 200
    data = response.json()["data"]["active_inquiry"]
    assert data["inquiry_id"] == str(latest.public_id)
    assert data["status_code"] == Inquiry.Status.COMPLETION_PENDING
    assert data["state_version"] == 9
    assert data["subscription_id"] == str(latest.subscription.public_id)
    assert [action["code"] for action in data["allowed_actions"]] == [
        "REQUEST_CONSULTATION"
    ]

    serialized = str(data)
    for forbidden in (
        latest.inquiry_code,
        latest.raw_text,
        latest.subscription.contract_no,
        latest.subscription.serial_no,
        latest.subscription.installation_address,
        owner.customer_profile.customer_name,
        owner.customer_profile.phone,
        "INTERNAL-EVIDENCE-ID",
        "assigned_user",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    "terminal_status",
    [Inquiry.Status.CANCELLED, Inquiry.Status.RESOLVED],
)
def test_customer_active_inquiry_returns_null_when_only_terminal_rows_exist(
    terminal_status,
):
    owner = create_user(64)
    inquiry = create_inquiry(owner, 64)
    terminal_fields = {
        "status_code": terminal_status,
        "state_version": 3,
    }
    if terminal_status == Inquiry.Status.CANCELLED:
        terminal_fields.update(
            cancelled_at=timezone.now(),
            cancellation_reason_code=Inquiry.CancellationReason.CUSTOMER_REQUEST,
        )
    Inquiry.objects.filter(pk=inquiry.pk).update(**terminal_fields)

    response = authenticated_client(owner).get(
        "/api/v1/me/inquiries/active"
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"active_inquiry": None}


def test_customer_active_inquiry_enforces_auth_role_and_query_boundaries():
    owner = create_user(65)
    consultant = create_user(66, role=User.Role.CONSULTANT)
    create_inquiry(owner, 65)
    path = "/api/v1/me/inquiries/active"

    assert APIClient().get(path).status_code == 401
    assert authenticated_client(consultant).get(path).status_code == 403
    invalid_query = authenticated_client(owner).get(f"{path}?expand=all")
    assert invalid_query.status_code == 422
    assert invalid_query.json()["error"]["code"] == "VALIDATION_ERROR"


def test_customer_guidance_returns_latest_safe_projection_without_evidence(
    django_assert_num_queries,
):
    owner = create_user(50)
    inquiry = create_inquiry(owner, 50)
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
        risk_level_code=Inquiry.RiskLevel.CAUTION,
        usage_guidance_status=Inquiry.UsageGuidanceStatus.PARTIAL_STOP,
    )
    inquiry.refresh_from_db()
    create_ai_guidance(
        inquiry,
        50,
        guidance_version=1,
        payload=guidance_payload(message="이전 안내"),
    )
    create_ai_guidance(
        inquiry,
        51,
        guidance_version=2,
        payload=guidance_payload(),
    )

    with django_assert_num_queries(3):
        response = authenticated_client(owner).get(
            f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "inquiry_id": str(inquiry.public_id),
        "inquiry_code": inquiry.inquiry_code,
        "status_code": Inquiry.Status.AI_GUIDANCE,
        "state_version": 3,
        "symptom_summary": inquiry.raw_text,
        "risk_level": "caution",
        "usage_guidance_status": "PARTIAL_STOP",
        "usage_guidance_message": (
            "온수 기능은 잠시 중지하고 냉수 출수 상태를 확인해 주세요."
        ),
        "restricted_functions": ["온수 출수"],
        "safe_actions": ["냉수 출수량을 확인해 주세요."],
        "escalation_conditions": [],
        "prohibited_actions": [],
        "next_action": "냉수 출수량을 확인해 주세요.",
        "requires_consultation": False,
        "evidence": [],
        "allowed_actions": data["allowed_actions"],
    }
    assert [item["code"] for item in data["allowed_actions"]] == [
        "REQUEST_CONSULTATION"
    ]
    serialized = str(data)
    for forbidden in (
        "이전 안내",
        "INTERNAL-CHUNK-MUST-NOT-LEAK",
        "similarity_score",
        "validated_output_payload",
        "model_config",
        "correlation_id",
    ):
        assert forbidden not in serialized


def test_customer_guidance_uses_latest_workflow_state_after_completion():
    owner = create_user(52)
    inquiry = create_inquiry(owner, 52)
    create_ai_guidance(inquiry, 52)
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.RESOLVED,
        state_version=9,
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status_code"] == Inquiry.Status.RESOLVED
    assert data["state_version"] == 9
    assert data["allowed_actions"] == []


def test_customer_guidance_accepts_valid_no_evidence_fallback():
    owner = create_user(56)
    inquiry = create_inquiry(owner, 56)
    payload = guidance_payload(message="공식 근거가 없어 상담이 필요합니다.")
    payload["safety_assessment"]["requires_consultation"] = True
    payload["usage_guidance"].update(
        guidance_status="PENDING_CONSULTATION",
        restricted_functions=["임의 자가조치"],
        next_actions=["상담을 요청해 주세요."],
    )
    create_ai_guidance(
        inquiry,
        56,
        payload=payload,
        run_status=AIRun.Status.NO_EVIDENCE,
    )
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
        requires_fallback=True,
        evidence_mode=Inquiry.EvidenceMode.NO_EVIDENCE,
        usage_guidance_status=(
            Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
        ),
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["requires_consultation"] is True
    assert data["usage_guidance_status"] == "PENDING_CONSULTATION"
    assert data["evidence"] == []
    assert [action["code"] for action in data["allowed_actions"]] == [
        "REQUEST_CONSULTATION"
    ]


def test_customer_guidance_rejects_provisional_guidance_before_state_event():
    owner = create_user(57)
    inquiry = create_inquiry(owner, 57)
    create_ai_guidance(inquiry, 57)

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AI_GUIDANCE_NOT_READY"
    assert response.json()["error"]["details"]["current_status"] == (
        Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    )


def test_customer_guidance_rejects_evidence_verification_fallback():
    owner = create_user(58)
    inquiry = create_inquiry(owner, 58)
    create_ai_guidance(inquiry, 58)
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
        requires_fallback=True,
        evidence_mode=Inquiry.EvidenceMode.PARTIAL_EVIDENCE,
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 409
    serialized = str(response.json())
    assert "온수 기능은 잠시 중지" not in serialized
    assert "냉수 출수량" not in serialized


def test_customer_guidance_preserves_danger_total_stop_without_public_evidence():
    owner = create_user(59)
    inquiry = create_inquiry(owner, 59)
    payload = guidance_payload(message="제품 사용을 즉시 중지해 주세요.")
    payload["safety_assessment"].update(
        risk_level="danger",
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-LEAK-001"],
    )
    payload["usage_guidance"].update(
        guidance_status="TOTAL_STOP",
        restricted_functions=["전체 제품 사용"],
        next_actions=["즉시 상담을 요청해 주세요."],
    )
    create_ai_guidance(inquiry, 59, payload=payload)
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
        risk_level_code=Inquiry.RiskLevel.DANGER,
        usage_guidance_status=Inquiry.UsageGuidanceStatus.TOTAL_STOP,
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["risk_level"] == "danger"
    assert data["usage_guidance_status"] == "TOTAL_STOP"
    assert data["usage_guidance_message"] == (
        "제품 사용을 즉시 중지해 주세요."
    )
    assert data["requires_consultation"] is True
    assert data["evidence"] == []


@pytest.mark.parametrize(
    ("evidence_mode", "requires_fallback", "guidance_status"),
    [
        (None, True, "PENDING_CONSULTATION"),
        (Inquiry.EvidenceMode.PARTIAL_EVIDENCE, True, "PENDING_CONSULTATION"),
        (Inquiry.EvidenceMode.NO_EVIDENCE, False, "PENDING_CONSULTATION"),
        (Inquiry.EvidenceMode.NO_EVIDENCE, True, "PARTIAL_STOP"),
    ],
)
def test_customer_guidance_rejects_inconsistent_no_evidence_projection(
    evidence_mode,
    requires_fallback,
    guidance_status,
):
    sequence = 590 + len(str(evidence_mode)) + len(guidance_status)
    owner = create_user(sequence)
    inquiry = create_inquiry(owner, sequence)
    payload = guidance_payload(message="공식 근거가 없어 상담이 필요합니다.")
    payload["safety_assessment"]["requires_consultation"] = True
    payload["usage_guidance"].update(
        guidance_status=guidance_status,
        restricted_functions=["임의 자가조치"],
        next_actions=["상담을 요청해 주세요."],
    )
    create_ai_guidance(
        inquiry,
        sequence,
        payload=payload,
        run_status=AIRun.Status.NO_EVIDENCE,
    )
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
        requires_fallback=requires_fallback,
        evidence_mode=evidence_mode,
        usage_guidance_status=guidance_status,
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AI_GUIDANCE_NOT_READY"
    assert "공식 근거가 없어 상담이 필요합니다." not in str(response.json())


@pytest.mark.parametrize(
    ("guidance_status", "requires_consultation", "matched_rule_ids"),
    [
        ("PARTIAL_STOP", True, ["SAFETY-LEAK-001"]),
        ("TOTAL_STOP", False, ["SAFETY-LEAK-001"]),
        ("TOTAL_STOP", True, []),
        ("TOTAL_STOP", True, ["SAFETY-UNKNOWN-001"]),
    ],
)
def test_customer_guidance_rejects_invalid_danger_assessment(
    guidance_status,
    requires_consultation,
    matched_rule_ids,
):
    sequence = 650 + len(guidance_status) + len(matched_rule_ids)
    owner = create_user(sequence)
    inquiry = create_inquiry(owner, sequence)
    payload = guidance_payload(message="검증되지 않은 위험 안내")
    payload["safety_assessment"].update(
        risk_level="danger",
        requires_consultation=requires_consultation,
        matched_safety_rule_ids=matched_rule_ids,
    )
    payload["usage_guidance"].update(
        guidance_status=guidance_status,
        restricted_functions=["전체 제품 사용"],
        next_actions=["즉시 상담을 요청해 주세요."],
    )
    create_ai_guidance(inquiry, sequence, payload=payload)
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=3,
        risk_level_code=Inquiry.RiskLevel.DANGER,
        usage_guidance_status=guidance_status,
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AI_GUIDANCE_NOT_READY"
    assert "검증되지 않은 위험 안내" not in str(response.json())


def test_customer_guidance_not_ready_and_ownership_fail_closed():
    owner = create_user(53)
    other = create_user(54)
    consultant = create_user(55, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(owner, 53)
    path = f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"

    not_ready = authenticated_client(owner).get(path)
    hidden = authenticated_client(other).get(path)
    forbidden = authenticated_client(consultant).get(path)

    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["code"] == "AI_GUIDANCE_NOT_READY"
    details = not_ready.json()["error"]["details"]
    assert details["inquiry_id"] == str(inquiry.public_id)
    assert details["current_status"] == (
        Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    )
    assert details["current_state_version"] == 2
    assert [action["code"] for action in details["allowed_actions"]] == [
        "CANCEL_INQUIRY"
    ]
    assert hidden.status_code == 404
    assert forbidden.status_code == 403


@pytest.mark.parametrize(
    ("run_status", "schema_status", "task_type"),
    [
        (
            AIRun.Status.FAILED,
            AIRun.SchemaValidationStatus.FAILED,
            AIRun.TaskType.ANALYZE_SYMPTOM,
        ),
        (
            AIRun.Status.SUCCEEDED,
            AIRun.SchemaValidationStatus.PASSED,
            AIRun.TaskType.SUMMARIZE_CONSULTATION,
        ),
    ],
)
def test_customer_guidance_rejects_untrusted_ai_runs(
    run_status,
    schema_status,
    task_type,
):
    sequence = 60 if run_status == AIRun.Status.FAILED else 61
    owner = create_user(sequence)
    inquiry = create_inquiry(owner, sequence)
    create_ai_guidance(
        inquiry,
        sequence,
        run_status=run_status,
        schema_status=schema_status,
        task_type=task_type,
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AI_GUIDANCE_NOT_READY"


@pytest.mark.parametrize(
    "invalid_usage",
    [
        {"guidance_status": "PARTIAL_STOP", "message": "ok"},
        {
            "guidance_status": "PARTIAL_STOP",
            "message": "ok",
            "restricted_functions": [False],
            "next_actions": ["확인"],
        },
        {
            "guidance_status": "PARTIAL_STOP",
            "message": "ok",
            "restricted_functions": [],
            "next_actions": "확인",
        },
        {
            "guidance_status": "PARTIAL_STOP",
            "message": "ok",
            "restricted_functions": [],
            "next_actions": [],
        },
        {
            "guidance_status": "PARTIAL_STOP",
            "message": "x" * 3001,
            "restricted_functions": [],
            "next_actions": ["확인"],
        },
        {
            "guidance_status": "PARTIAL_STOP",
            "message": "ok",
            "restricted_functions": ["x" * 1001],
            "next_actions": ["확인"],
        },
    ],
)
def test_customer_guidance_rejects_malformed_validated_payload(
    invalid_usage,
):
    sequence = 70 + len(str(invalid_usage))
    owner = create_user(sequence)
    inquiry = create_inquiry(owner, sequence)
    payload = guidance_payload()
    payload["usage_guidance"] = invalid_usage
    create_ai_guidance(inquiry, sequence, payload=payload)

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AI_GUIDANCE_NOT_READY"


def test_customer_snapshot_recalculates_actions_before_after_and_answered():
    owner = create_user(2)
    inquiry = create_inquiry(owner, 2)
    client = authenticated_client(owner)
    path = f"/api/v1/me/inquiries/{inquiry.public_id}"

    before = client.get(path)
    assert before.status_code == 200
    assert [
        action["code"]
        for action in before.json()["data"]["allowed_actions"]
    ] == ["CANCEL_INQUIRY"]

    question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="DYNAMIC_SNAPSHOT_QUESTION",
        question_text="언제부터 증상이 시작되었나요?",
        answer_type_code="FREE_TEXT",
        asked_by_type_code="RULE",
    )
    after_question = client.get(path)
    assert after_question.status_code == 200
    assert [
        action["code"]
        for action in after_question.json()["data"]["allowed_actions"]
    ] == ["SUBMIT_ANSWERS", "CANCEL_INQUIRY"]

    FollowUpAnswer.objects.create(
        question=question,
        answered_by=owner,
        answer_text="어제부터 시작되었습니다.",
    )
    after_answer = client.get(path)
    assert after_answer.status_code == 200
    assert [
        action["code"]
        for action in after_answer.json()["data"]["allowed_actions"]
    ] == ["CANCEL_INQUIRY"]


def test_customer_snapshot_hides_submit_answers_for_unsupported_questions():
    owner = create_user(3)
    inquiry = create_inquiry(owner, 3)
    InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="UNSUPPORTED_SNAPSHOT_MULTI",
        question_text="지원하지 않는 복수 선택 질문",
        answer_type_code="MULTI_CHOICE",
        answer_payload={"question_options": ["A", "B"]},
        asked_by_type_code="RULE",
    )

    response = authenticated_client(owner).get(
        f"/api/v1/me/inquiries/{inquiry.public_id}"
    )

    assert response.status_code == 200
    assert [
        action["code"]
        for action in response.json()["data"]["allowed_actions"]
    ] == ["CANCEL_INQUIRY"]


@pytest.mark.parametrize(
    "terminal_status",
    [Inquiry.Status.CANCELLED, Inquiry.Status.RESOLVED],
)
def test_customer_snapshot_hides_all_actions_for_terminal_inquiries(
    terminal_status,
    django_assert_num_queries,
):
    owner = create_user(4)
    inquiry = create_inquiry(owner, 4)
    terminal_fields = {
        "status_code": terminal_status,
        "state_version": 3,
    }
    if terminal_status == Inquiry.Status.CANCELLED:
        terminal_fields.update(
            cancelled_at=timezone.now(),
            cancellation_reason_code=Inquiry.CancellationReason.CUSTOMER_REQUEST,
        )
    Inquiry.objects.filter(pk=inquiry.pk).update(
        **terminal_fields,
    )

    with django_assert_num_queries(2):
        response = authenticated_client(owner).get(
            f"/api/v1/me/inquiries/{inquiry.public_id}"
        )

    assert response.status_code == 200
    assert response.json()["data"]["status_code"] == terminal_status
    assert response.json()["data"]["allowed_actions"] == []


def test_customer_questions_return_only_unanswered_public_metadata(
    django_assert_num_queries,
):
    owner = create_user(10)
    inquiry = create_inquiry(owner, 10)
    choice = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="FILTER_REPLACEMENT",
        question_text="필터를 최근 교체하셨나요?",
        answer_type_code="SINGLE_CHOICE",
        answer_payload={
            "question_options": ["최근 교체함", "교체하지 않음"],
            "target_field": "filter_replacement",
        },
        asked_by_type_code="RULE",
    )
    free_text = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=2,
        question_code="OCCURRENCE_TIME",
        question_text="언제부터 증상이 시작되었나요?",
        answer_type_code="FREE_TEXT",
        asked_by_type_code="RULE",
    )
    third_question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=3,
        question_code="ANSWER_RELATION_INDEPENDENT",
        question_text="별도 답변 관계와 분리된 질문입니다.",
        answer_type_code="FREE_TEXT",
        asked_by_type_code="RULE",
    )
    FollowUpAnswer.objects.create(
        question=third_question,
        answered_by=owner,
        answer_text="이미 제출한 답변",
    )
    unsupported = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=4,
        question_code="UNSUPPORTED_MULTI",
        question_text="복수 선택은 아직 공개하지 않습니다.",
        answer_type_code="MULTI_CHOICE",
        answer_payload={"question_options": ["A", "B"]},
        asked_by_type_code="RULE",
    )
    optionless = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=5,
        question_code="OPTIONLESS_SINGLE",
        question_text="선택지가 없는 단일 선택 질문",
        answer_type_code="SINGLE_CHOICE",
        asked_by_type_code="RULE",
    )

    with django_assert_num_queries(2):
        response = authenticated_client(owner).get(
            f"/api/v1/me/inquiries/{inquiry.public_id}/questions"
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["inquiry_id"] == str(inquiry.public_id)
    assert data["state_version"] == 2
    assert data["questions"] == [
        {
            "question_id": str(choice.public_id),
            "question_type": "SINGLE_CHOICE",
            "prompt": "필터를 최근 교체하셨나요?",
            "required": True,
            "options": [
                {"value": "최근 교체함", "label": "최근 교체함"},
                {"value": "교체하지 않음", "label": "교체하지 않음"},
            ],
        },
        {
            "question_id": str(free_text.public_id),
            "question_type": "FREE_TEXT",
            "prompt": "언제부터 증상이 시작되었나요?",
            "required": True,
            "options": [],
        },
    ]
    serialized = str(data)
    for forbidden in (
        "target_field",
        "filter_replacement",
        "customer_answer",
        "question_code",
        "source_ai_run",
        str(third_question.public_id),
        str(unsupported.public_id),
        str(optionless.public_id),
        "이미 제출한 답변",
    ):
        assert forbidden not in serialized


def test_customer_reads_use_same_404_for_other_owner_missing_and_invalid_uuid():
    owner = create_user(20)
    other = create_user(21)
    other_inquiry = create_inquiry(other, 20)
    client = authenticated_client(owner)

    paths = (
        f"/api/v1/me/inquiries/{other_inquiry.public_id}",
        f"/api/v1/me/inquiries/{uuid4()}",
        "/api/v1/me/inquiries/not-a-uuid",
        f"/api/v1/me/inquiries/{other_inquiry.public_id}/questions",
        f"/api/v1/me/inquiries/{uuid4()}/questions",
        "/api/v1/me/inquiries/not-a-uuid/questions",
        f"/api/v1/me/inquiries/{other_inquiry.public_id}/guidance",
        f"/api/v1/me/inquiries/{uuid4()}/guidance",
        "/api/v1/me/inquiries/not-a-uuid/guidance",
    )
    responses = [client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [404] * len(
        paths
    )
    assert {
        response.json()["error"]["code"] for response in responses
    } == {"RESOURCE_NOT_FOUND"}
    assert {
        str(
            {
                "success": response.json()["success"],
                "data": response.json()["data"],
                "error": response.json()["error"],
            }
        )
        for response in responses
    } == {
        str(
            {
                "success": False,
                "data": None,
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "요청한 대상을 찾을 수 없습니다.",
                    "details": {},
                },
            }
        )
    }


def test_customer_read_auth_role_and_query_boundaries():
    owner = create_user(30)
    consultant = create_user(31, role=User.Role.CONSULTANT)
    technician = create_user(32, role=User.Role.TECHNICIAN)
    inquiry = create_inquiry(owner, 30)
    paths = (
        f"/api/v1/me/inquiries/{inquiry.public_id}",
        f"/api/v1/me/inquiries/{inquiry.public_id}/questions",
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance",
    )

    for path in paths:
        assert APIClient().get(path).status_code == 401
        assert authenticated_client(consultant).get(path).status_code == 403
        assert authenticated_client(technician).get(path).status_code == 403
        invalid_query = authenticated_client(owner).get(f"{path}?expand=all")
        assert invalid_query.status_code == 422
        assert invalid_query.json()["error"]["code"] == "VALIDATION_ERROR"

    owner.is_active = False
    for path in paths:
        assert authenticated_client(owner).get(path).status_code == 403


def test_customer_reads_are_side_effect_free():
    owner = create_user(40)
    inquiry = create_inquiry(owner, 40)
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
    )
    inquiry.refresh_from_db()
    InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="SIDE_EFFECT_CHECK",
        question_text="읽기 전용 확인 질문",
        asked_by_type_code="RULE",
    )
    guidance = create_ai_guidance(inquiry, 140)
    before_inquiry = Inquiry.objects.values(
        "status_code",
        "state_version",
        "updated_at",
        "assigned_user_id",
        "assigned_role_code",
    ).get(pk=inquiry.pk)
    before_qa = list(
        InquiryQA.objects.filter(inquiry=inquiry).values(
            "public_id",
            "question_text",
            "answer_payload",
        )
    )
    before_guidance = Guidance.objects.values(
        "guidance_version",
        "review_status_code",
        "summary_text",
        "requires_consultation",
        "updated_at",
    ).get(pk=guidance.pk)
    before_ai_run = AIRun.objects.values(
        "status_code",
        "schema_validation_status_code",
        "validated_output_payload",
        "updated_at",
    ).get(pk=guidance.generated_by_ai_run_id)

    client = authenticated_client(owner)
    assert client.get(
        f"/api/v1/me/inquiries/{inquiry.public_id}"
    ).status_code == 200
    assert client.get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/questions"
    ).status_code == 200
    assert client.get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/guidance"
    ).status_code == 200

    assert Inquiry.objects.values(
        "status_code",
        "state_version",
        "updated_at",
        "assigned_user_id",
        "assigned_role_code",
    ).get(pk=inquiry.pk) == before_inquiry
    assert list(
        InquiryQA.objects.filter(inquiry=inquiry).values(
            "public_id",
            "question_text",
            "answer_payload",
        )
    ) == before_qa
    assert Guidance.objects.values(
        "guidance_version",
        "review_status_code",
        "summary_text",
        "requires_consultation",
        "updated_at",
    ).get(pk=guidance.pk) == before_guidance
    assert AIRun.objects.values(
        "status_code",
        "schema_validation_status_code",
        "validated_output_payload",
        "updated_at",
    ).get(pk=guidance.generated_by_ai_run_id) == before_ai_run
