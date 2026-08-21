"""AI escalation -> Backend -> customer confirmation -> consultant projection bridge.

This file verifies the *same Inquiry* across the currently implemented runtime:

AI NO_EVIDENCE
    -> Backend CONSULTATION_REQUIRED
    -> customer REQUEST_CONSULTATION
    -> synthetic E2E consultant assignment
    -> Consultation WAITING
    -> consultant GET /api/v1/inquiries and detail

The second case persists a sanitized internal AI handoff before the customer
creates a Consultation, then verifies the same draft in the consultant view.
"""

from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import httpx
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation, ConsultationHandoff
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.inquiries.services.inquiry_ai_service import InquiryAIService
from apps.inquiries.services.synthetic_e2e_assignment_service import (
    DEMO_CONSULTANT_USERNAME,
    DEMO_CUSTOMER_NO,
    DEMO_CUSTOMER_USERNAME,
    SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from integrations.ai.client import AIClient
from integrations.ai.schema_validator import DEFAULT_CONTRACT_ROOT


pytestmark = pytest.mark.django_db

TARGET_MODEL_CODE = "WPUJAC104DWH"
INTERNAL_HANDOFF_TOKEN = "test-protected-ai-handoff-token"


def _create_user(*, username: str, role: str) -> User:
    return User.objects.create_user(
        username=username,
        password=None,
        full_name=f"Synthetic {username}",
        role_code=role,
        employee_no=(None if role == User.Role.CUSTOMER else username[-32:]),
        is_active=True,
        is_synthetic=True,
    )


def _create_runtime_fixture() -> tuple[User, User, Inquiry]:
    customer_user = _create_user(
        username=DEMO_CUSTOMER_USERNAME,
        role=User.Role.CUSTOMER,
    )
    consultant = _create_user(
        username=DEMO_CONSULTANT_USERNAME,
        role=User.Role.CONSULTANT,
    )
    customer = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=DEMO_CUSTOMER_NO,
        customer_name="합성 AI Handoff 고객",
        phone="010-0000-0001",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=TARGET_MODEL_CODE,
        model_name="Synthetic JAC104",
        generation_code="D",
        manufacturer="SK매직",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no="AI-HANDOFF-BRIDGE-CONTRACT-001",
        customer=customer,
        product_model=product,
        serial_no="AI-HANDOFF-BRIDGE-SERIAL-001",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="정수기 출수량이 갑자기 줄었어요.",
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=2,
        # The production preparation command currently only marks AI_GUIDANCE.
        # Setting the approved synthetic marker here lets this integration test
        # exercise the NO_EVIDENCE -> customer confirmation bridge on one Inquiry
        # without changing operational assignment behavior.
        scenario_code=SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
    )
    SymptomEntry.objects.create(
        inquiry=inquiry,
        symptom_type_code="LOW_FLOW",
        structured_payload={
            "representative_symptom_code": "LOW_FLOW",
        },
        schema_version="v1",
        is_customer_confirmed=True,
    )
    return customer_user, consultant, inquiry


def _no_evidence_payload(request_payload: dict) -> dict:
    example_path = (
        DEFAULT_CONTRACT_ROOT
        / "examples"
        / "symptom-analysis"
        / "general-guidance.json"
    )
    response = json.loads(example_path.read_text(encoding="utf-8"))["response"]

    for field in (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
    ):
        response[field] = request_payload[field]

    response.update(
        {
            "status": "FALLBACK",
            "fallback_reason_code": "NO_EVIDENCE",
            "failure_stage": "RETRIEVING",
            "evidence_references": [],
        }
    )
    response["safety_assessment"]["requires_consultation"] = True
    response["usage_guidance"].update(
        {
            "guidance_status": "PENDING_CONSULTATION",
            "message": (
                "확인 가능한 공식 근거가 부족하여 상담 연결이 필요합니다."
            ),
            "next_actions": ["상담 연결을 요청해 주세요."],
        }
    )
    return response


def _ai_client() -> tuple[AIClient, httpx.Client]:
    def handler(request: httpx.Request) -> httpx.Response:
        request_payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json=_no_evidence_payload(request_payload),
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return (
        AIClient(
            base_url="http://ai.test",
            mode="local",
            http_client=http_client,
        ),
        http_client,
    )


def _client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _handoff_payload(
    *,
    inquiry: Inquiry,
    correlation_id,
    ai_request_id,
) -> dict:
    return {
        "inquiry_id": str(inquiry.public_id),
        "correlation_id": str(correlation_id),
        "ai_request_id": str(ai_request_id),
        "model_code": TARGET_MODEL_CODE,
        "product_family": "WATER_PURIFIER",
        "customer_symptom_summary": "출수량 저하가 확인되어 상담 확인이 필요합니다.",
        "questionnaire_answers": [],
        "self_help_actions": [],
        "evidence": [],
        "safety_level": "unknown",
        "safety_requires_consultation": False,
        "safety_notes": ["공식 근거 없음"],
        "escalation_reason": "NO_EVIDENCE",
        "consultant_priority_checks": ["제품 상태와 출수 환경 확인"],
        "source_chunk_ids": [],
    }


def _run_same_inquiry_bridge(
    *,
    persist_handoff: bool = False,
) -> tuple[Inquiry, Consultation, dict]:
    customer, consultant, inquiry = _create_runtime_fixture()
    ai_client, http_client = _ai_client()
    correlation_id = uuid4()
    ai_request_id = f"ai-handoff-{uuid4().hex}"

    try:
        outcome = InquiryAIService.analyze_inquiry(
            inquiry_public_id=inquiry.public_id,
            correlation_id=correlation_id,
            ai_request_id=ai_request_id,
            client=ai_client,
        )
    finally:
        http_client.close()

    assert outcome.status == AIRun.Status.NO_EVIDENCE
    assert outcome.event_candidate == "NO_EVIDENCE"
    assert outcome.event_applied == "NO_EVIDENCE"

    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 3
    assert inquiry.usage_guidance_status == (
        Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
    )

    # State-machine contract intentionally does not create Consultation on the
    # AI event itself. The customer confirms/request consultation next.
    assert inquiry.assigned_user is None
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.NONE
    assert not Consultation.objects.filter(inquiry=inquiry).exists()

    if persist_handoff:
        handoff_response = APIClient().post(
            (
                f"/api/v1/internal/ai/inquiries/{inquiry.public_id}/"
                "consultation-handoffs"
            ),
            _handoff_payload(
                inquiry=inquiry,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
            ),
            format="json",
            HTTP_X_AI_HANDOFF_TOKEN=INTERNAL_HANDOFF_TOKEN,
            HTTP_IDEMPOTENCY_KEY=ai_request_id,
            HTTP_X_CORRELATION_ID=str(correlation_id),
        )
        assert handoff_response.status_code == 201
        assert handoff_response.data["data"]["consultation_id"] is None

    request_response = _client_for(customer).post(
        f"/api/v1/inquiries/{inquiry.public_id}/request-consultation",
        {"state_version": 3},
        format="json",
        HTTP_IDEMPOTENCY_KEY="ai-handoff-bridge-request-001",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    assert request_response.status_code == 200

    inquiry.refresh_from_db()
    consultation = Consultation.objects.get(inquiry=inquiry)
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 4
    assert inquiry.assigned_user == consultant
    assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
    assert consultation.status == Consultation.Status.WAITING

    consultant_client = _client_for(consultant)

    list_response = consultant_client.get(
        "/api/v1/inquiries",
        {"q": inquiry.inquiry_code},
    )
    assert list_response.status_code == 200
    items = list_response.data["data"]["items"]
    assert [item["inquiry_id"] for item in items] == [
        str(inquiry.public_id)
    ]

    detail_response = consultant_client.get(
        f"/api/v1/inquiries/{inquiry.public_id}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.data["data"]

    assert detail["inquiry"]["inquiry_id"] == str(inquiry.public_id)
    assert detail["inquiry"]["status"] == Inquiry.Status.CONSULTATION_REQUIRED
    assert detail["workflow"]["state_version"] == 4
    assert (
        detail["guidance_and_actions"]["usage_guidance_status"]
        == Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION
    )

    serialized = json.dumps(detail, ensure_ascii=False)
    for forbidden in (
        "system_prompt",
        "raw_output_text",
        "stacktrace",
        "traceback",
        "internal_error",
    ):
        assert forbidden not in serialized

    return inquiry, consultation, detail


def test_ai_no_evidence_customer_confirmation_reaches_consultant_projection():
    """Current implemented same-Inquiry bridge works through customer confirmation."""

    inquiry, consultation, detail = _run_same_inquiry_bridge()

    assert detail["consultation"]["consultation_id"] == str(
        consultation.public_id
    )
    assert detail["consultation"]["result_code"] == "PENDING"
    assert detail["inquiry"]["inquiry_id"] == str(inquiry.public_id)


@override_settings(AI_HANDOFF_INTERNAL_TOKEN=INTERNAL_HANDOFF_TOKEN)
def test_consultant_projection_contains_persisted_ai_handoff_draft():
    """Persist the AI handoff before Consultation and expose its safe draft."""

    inquiry, consultation, detail = _run_same_inquiry_bridge(
        persist_handoff=True
    )

    ai_draft = detail["consultation"]["summary"]["ai_draft_summary"]
    assert isinstance(ai_draft, str)
    assert ai_draft.strip()
    assert "출수량 저하" in ai_draft
    handoff = ConsultationHandoff.objects.get(inquiry=inquiry)
    assert handoff.consultation == consultation
    assert handoff.ai_draft_summary == ai_draft
    assert ConsultationHandoff.objects.filter(inquiry=inquiry).count() == 1
