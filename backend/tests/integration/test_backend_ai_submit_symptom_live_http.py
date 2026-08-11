"""Actual-socket Django -> FastAPI Mock integration for SUBMIT_SYMPTOM.

The test is opt-in because it requires a separately running AI Uvicorn
process.  It proves the public customer route, transaction on-commit hook,
real HTTP adapter, validated persistence, and replay boundary together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.audit.models import AIRun
from apps.inquiries.models import Guidance, Inquiry, SymptomAssessment
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("BACKEND_AI_LIVE_HTTP_TEST") != "1",
        reason=(
            "Set BACKEND_AI_LIVE_HTTP_TEST=1 and run the AI Uvicorn Mock "
            "server before executing this actual-socket integration test."
        ),
    ),
]

CUSTOMER_CODE = "DEMO-CUSTOMER-001"
DEFAULT_AI_BASE_URL = "http://127.0.0.1:8001"


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    payload: dict | None
    body: str


def request_http(
    base_url: str,
    path_value: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
) -> HttpResult:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = Request(
        f"{base_url}{path_value}",
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        response = urlopen(request, timeout=35)
    except HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items())
        raw_response = exc.read()
    else:
        with response:
            status = response.status
            response_headers = dict(response.headers.items())
            raw_response = response.read()

    body = raw_response.decode("utf-8")
    parsed = json.loads(body) if body else None
    return HttpResult(status, response_headers, parsed, body)


def success_data(result: HttpResult, expected_status: int) -> dict:
    assert result.status == expected_status, result.body
    assert result.payload is not None
    assert result.payload["success"] is True
    correlation_id = result.headers["X-Correlation-ID"]
    UUID(correlation_id)
    assert result.payload["metadata"]["correlation_id"] == correlation_id
    return result.payload["data"]


def login(base_url: str) -> str:
    result = request_http(
        base_url,
        "/api/v1/auth/demo-login",
        method="POST",
        payload={"demo_user_code": CUSTOMER_CODE},
        headers={"X-Correlation-ID": str(uuid4())},
    )
    return success_data(result, 200)["access_token"]


def test_submit_symptom_calls_real_ai_mock_once_and_persists_result(
    live_server,
    settings,
):
    """Submit once over HTTP, persist AI result, and suppress replay calls."""

    ai_base_url = os.getenv("BACKEND_AI_TEST_BASE_URL", DEFAULT_AI_BASE_URL)
    health = request_http(ai_base_url, "/health")
    assert health.status == 200, health.body

    settings.DEMO_LOGIN_ENABLED = True
    settings.DEMO_LOGIN_CODES = frozenset({CUSTOMER_CODE})
    settings.AI_SERVICE_BASE_URL = ai_base_url
    settings.AI_SERVICE_MODE = "mock"
    settings.AI_SERVICE_TIMEOUT_SECONDS = 30.0

    call_command("seed_demo_accounts", verbosity=0)
    customer = User.objects.get(username=CUSTOMER_CODE)
    product = ProductModel.objects.create(
        model_code="WPUJAC104DWH",
        model_name="Backend AI live HTTP purifier",
        generation_code="D",
        manufacturer="SK magic",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no="BACKEND-AI-LIVE-HTTP-001",
        customer=customer.customer_profile,
        product_model=product,
        serial_no="BACKEND-AI-LIVE-SERIAL-001",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    access_token = login(live_server.url)
    authorization = {"Authorization": f"Bearer {access_token}"}

    created = request_http(
        live_server.url,
        "/api/v1/inquiries",
        method="POST",
        payload={
            "subscription_id": str(subscription.public_id),
            "channel_code": "WEB",
            "raw_text": "냉수 버튼을 누르면 물이 평소보다 조금만 나옵니다.",
            "representative_symptom_code": "LOW_FLOW",
        },
        headers={
            **authorization,
            "Idempotency-Key": "backend-ai-live-create-001",
            "X-Correlation-ID": str(uuid4()),
        },
    )
    inquiry_id = success_data(created, 201)["inquiry_id"]

    submit_correlation_id = str(uuid4())
    submit_headers = {
        **authorization,
        "Idempotency-Key": "backend-ai-live-submit-001",
        "X-Correlation-ID": submit_correlation_id,
    }
    submitted = request_http(
        live_server.url,
        f"/api/v1/inquiries/{inquiry_id}/submit",
        method="POST",
        payload={"state_version": 1},
        headers=submit_headers,
    )
    submitted_data = success_data(submitted, 200)
    assert submitted.headers["X-Correlation-ID"] == submit_correlation_id
    assert submitted_data["state"] == "QUESTIONNAIRE_IN_PROGRESS"
    assert submitted_data["state_version"] == 2
    assert submitted_data["idempotent_replay"] is False

    inquiry = Inquiry.objects.get(public_id=inquiry_id)
    run = AIRun.objects.get(inquiry=inquiry)
    history = TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="SUBMIT_SYMPTOM",
    )
    idempotency = IdempotencyRecord.objects.get(
        actor=customer,
        operation_id="submitSymptom",
    )
    assert run.status_code == AIRun.Status.SUCCEEDED
    assert run.schema_validation_status_code == (
        AIRun.SchemaValidationStatus.PASSED
    )
    assert run.request_schema_version == "3.0.0"
    assert run.response_schema_version == "3.0.0"
    assert str(run.correlation_id) == submit_correlation_id
    assert run.inquiry_id == history.inquiry_id == inquiry.id
    assert run.correlation_id == history.correlation_id
    assert run.idempotency_key == str(idempotency.public_id)
    assert run.input_payload["inquiry_id"] == inquiry_id
    assert run.input_payload["state_version"] == 2
    assert run.input_payload["correlation_id"] == submit_correlation_id
    assert run.input_payload["ai_request_id"] == run.idempotency_key
    assert run.validated_output_payload["correlation_id"] == (
        submit_correlation_id
    )
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert Guidance.objects.filter(inquiry=inquiry).count() == 1

    inquiry.refresh_from_db()
    assert inquiry.status_code == "QUESTIONNAIRE_IN_PROGRESS"
    assert inquiry.state_version == 2
    assert inquiry.risk_level_code == "caution"
    assert inquiry.usage_guidance_status == "PARTIAL_STOP"

    replay = request_http(
        live_server.url,
        f"/api/v1/inquiries/{inquiry_id}/submit",
        method="POST",
        payload={"state_version": 1},
        headers=submit_headers,
    )
    replay_data = success_data(replay, 200)
    assert replay_data["idempotent_replay"] is True
    assert AIRun.objects.filter(inquiry=inquiry).count() == 1
    assert SymptomAssessment.objects.filter(inquiry=inquiry).count() == 1
    assert Guidance.objects.filter(inquiry=inquiry).count() == 1
