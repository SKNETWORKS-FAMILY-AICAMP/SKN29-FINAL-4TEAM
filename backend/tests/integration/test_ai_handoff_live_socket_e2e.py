"""Live socket E2E: Django -> FastAPI -> Django Handoff -> Consultant view.

Gate scope:
- real Django live_server + test DB,
- real Backend AIClient HTTP request,
- real FastAPI /api/v1/ai/analyze route,
- real Harness/Handoff creation,
- real FastAPI BackgroundTask callback,
- real Django internal Handoff API and persistence,
- real customer REQUEST_CONSULTATION,
- real consultant detail projection.

RAG/LLM providers are intentionally deterministic in the dedicated AI test
server so this bridge test does not duplicate provider/RAG gates.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import pytest
from django.core.management import call_command
from django.db import close_old_connections

from apps.accounts.models import User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation, ConsultationHandoff
from apps.inquiries.models import Inquiry
from apps.inquiries.services.synthetic_e2e_assignment_service import (
    DEMO_CONSULTANT_USERNAME,
    DEMO_CUSTOMER_USERNAME,
    SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db(transaction=True)

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVER_SCRIPT = (
    REPO_ROOT / "ai" / "scripts" / "run_handoff_bridge_e2e_server.py"
)
TOKEN = "live-socket-ai-handoff-secret"
TARGET_MODEL = "WPUJAC104DWH"


def _ai_python() -> Path:
    explicit = os.getenv("WATERBRIDGE_AI_PYTHON", "").strip()
    if explicit:
        return Path(explicit)

    windows = REPO_ROOT / "ai" / ".venv" / "Scripts" / "python.exe"
    if windows.exists():
        return windows

    posix = REPO_ROOT / "ai" / ".venv" / "bin" / "python"
    return posix


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, str], dict]:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = Request(
        f"{base_url}{path}",
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as exc:
        status = exc.code
        response_headers = dict(exc.headers.items())
        raw = exc.read()
    else:
        with response:
            status = response.status
            response_headers = dict(response.headers.items())
            raw = response.read()

    body = json.loads(raw.decode("utf-8")) if raw else {}
    return status, response_headers, body


def _wait_http_ready(base_url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 15.0
    last_error = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            raise AssertionError(
                "AI E2E server exited early.\n"
                f"stdout={stdout}\nstderr={stderr}"
            )
        try:
            status, _headers, _payload = _request_json(
                base_url,
                "/health",
                timeout=1.0,
            )
            if status == 200:
                return
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise AssertionError(f"AI E2E server not ready: {last_error!r}")


@contextmanager
def _running_ai_server(*, backend_url: str):
    if os.getenv("RUN_AI_BACKEND_SOCKET_E2E", "") != "1":
        pytest.skip(
            "Set RUN_AI_BACKEND_SOCKET_E2E=1 for the cross-venv live socket gate."
        )

    python_exe = _ai_python()
    if not python_exe.exists():
        pytest.skip(
            f"AI interpreter not found: {python_exe}. "
            "Set WATERBRIDGE_AI_PYTHON explicitly."
        )
    if not AI_SERVER_SCRIPT.exists():
        raise AssertionError(f"missing AI E2E server script: {AI_SERVER_SCRIPT}")

    port = _free_port()
    ai_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["AI_HANDOFF_BACKEND_ENABLED"] = "true"
    env["AI_BACKEND_BASE_URL"] = backend_url
    env["AI_HANDOFF_INTERNAL_TOKEN"] = TOKEN
    env["AI_HANDOFF_TIMEOUT_SECONDS"] = "2.0"
    env["AI_OTEL_ENABLED"] = "false"
    env.pop("AI_VECTOR_DSN", None)

    process = subprocess.Popen(
        [
            str(python_exe),
            str(AI_SERVER_SCRIPT),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        _wait_http_ready(ai_url, process)
        yield ai_url
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _login(base_url: str, code: str) -> str:
    correlation = str(uuid4())
    status, headers, payload = _request_json(
        base_url,
        "/api/v1/auth/demo-login",
        method="POST",
        payload={"demo_user_code": code},
        headers={"X-Correlation-ID": correlation},
    )
    assert status == 200, payload
    assert headers["X-Correlation-ID"] == correlation
    return payload["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wait_for_handoff(inquiry: Inquiry) -> ConsultationHandoff:
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        close_old_connections()
        handoff = (
            ConsultationHandoff.objects.filter(inquiry=inquiry)
            .order_by("-created_at")
            .first()
        )
        if handoff is not None:
            return handoff
        time.sleep(0.1)
    raise AssertionError("AI BackgroundTask did not persist ConsultationHandoff")


def _wait_for_no_evidence_state(inquiry: Inquiry) -> Inquiry:
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        close_old_connections()
        inquiry.refresh_from_db()
        if (
            inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
            and inquiry.state_version == 3
        ):
            return inquiry
        time.sleep(0.1)
    raise AssertionError(
        "Backend did not apply NO_EVIDENCE -> CONSULTATION_REQUIRED"
    )


def test_live_fastapi_callback_persists_and_reaches_consultant_projection(
    live_server,
    settings,
):
    settings.DEMO_LOGIN_ENABLED = True
    settings.DEMO_LOGIN_CODES = frozenset(
        {DEMO_CUSTOMER_USERNAME, DEMO_CONSULTANT_USERNAME}
    )
    settings.AI_HANDOFF_INTERNAL_TOKEN = TOKEN
    settings.AI_SERVICE_MODE = "local"

    call_command("seed_demo_accounts", verbosity=0)
    customer = User.objects.get(username=DEMO_CUSTOMER_USERNAME)
    consultant = User.objects.get(username=DEMO_CONSULTANT_USERNAME)

    product = ProductModel.objects.create(
        model_code=TARGET_MODEL,
        model_name="Live socket Handoff purifier",
        generation_code="D",
        manufacturer="SK magic",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"LIVE-HANDOFF-{uuid4().hex[:12]}",
        customer=customer.customer_profile,
        product_model=product,
        serial_no=f"LIVE-HANDOFF-SERIAL-{uuid4().hex[:12]}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )

    with _running_ai_server(backend_url=live_server.url) as ai_url:
        settings.AI_SERVICE_BASE_URL = ai_url

        customer_token = _login(live_server.url, DEMO_CUSTOMER_USERNAME)
        consultant_token = _login(
            live_server.url,
            DEMO_CONSULTANT_USERNAME,
        )

        create_correlation = str(uuid4())
        create_status, _headers, create_payload = _request_json(
            live_server.url,
            "/api/v1/inquiries",
            method="POST",
            payload={
                "subscription_id": str(subscription.public_id),
                "channel_code": "MOBILE",
                "raw_text": "정수기 출수량이 갑자기 줄었습니다.",
                "representative_symptom_code": "LOW_FLOW",
            },
            headers={
                **_bearer(customer_token),
                "Idempotency-Key": f"live-handoff-create-{uuid4().hex}",
                "X-Correlation-ID": create_correlation,
            },
        )
        assert create_status == 201, create_payload
        inquiry = Inquiry.objects.get(
            public_id=create_payload["data"]["inquiry_id"]
        )
        inquiry.scenario_code = SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE
        inquiry.save(update_fields=["scenario_code", "updated_at"])

        submit_correlation = str(uuid4())
        submit_status, submit_headers, submit_payload = _request_json(
            live_server.url,
            f"/api/v1/inquiries/{inquiry.public_id}/submit",
            method="POST",
            payload={"state_version": 1},
            headers={
                **_bearer(customer_token),
                "Idempotency-Key": f"live-handoff-submit-{uuid4().hex}",
                "X-Correlation-ID": submit_correlation,
            },
            timeout=20.0,
        )
        assert submit_status == 200, submit_payload
        assert submit_headers["X-Correlation-ID"] == submit_correlation

        inquiry = _wait_for_no_evidence_state(inquiry)
        handoff = _wait_for_handoff(inquiry)

        ai_run = AIRun.objects.get(inquiry=inquiry)
        assert ai_run.status_code == AIRun.Status.NO_EVIDENCE
        assert str(ai_run.correlation_id) == submit_correlation
        assert handoff.ai_run == ai_run
        assert handoff.consultation is None
        assert handoff.ai_request_id == ai_run.idempotency_key
        assert handoff.correlation_id == ai_run.correlation_id
        assert handoff.model_code_snapshot == TARGET_MODEL
        assert handoff.data_classification == "synthetic"
        assert ConsultationHandoff.objects.filter(inquiry=inquiry).count() == 1

        sanitized = json.dumps(
            handoff.sanitized_payload,
            ensure_ascii=False,
        )
        for forbidden in (
            "system_prompt",
            "raw_output_text",
            "stacktrace",
            "traceback",
            "internal_error",
            "010-",
            "@",
        ):
            assert forbidden not in sanitized

        request_correlation = str(uuid4())
        request_status, _headers, request_payload = _request_json(
            live_server.url,
            f"/api/v1/inquiries/{inquiry.public_id}/request-consultation",
            method="POST",
            payload={"state_version": 3},
            headers={
                **_bearer(customer_token),
                "Idempotency-Key": (
                    f"live-handoff-consult-{uuid4().hex}"
                ),
                "X-Correlation-ID": request_correlation,
            },
        )
        assert request_status == 200, request_payload

        inquiry.refresh_from_db()
        handoff.refresh_from_db()
        consultation = Consultation.objects.get(inquiry=inquiry)
        assert inquiry.state_version == 4
        assert inquiry.assigned_user == consultant
        assert inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
        assert handoff.consultation == consultation
        assert consultation.ai_draft_summary == handoff.ai_draft_summary
        assert consultation.ai_draft_summary.strip()

        detail_correlation = str(uuid4())
        detail_status, detail_headers, detail_payload = _request_json(
            live_server.url,
            f"/api/v1/inquiries/{inquiry.public_id}",
            headers={
                **_bearer(consultant_token),
                "X-Correlation-ID": detail_correlation,
            },
        )
        assert detail_status == 200, detail_payload
        assert detail_headers["X-Correlation-ID"] == detail_correlation

        detail = detail_payload["data"]
        assert detail["inquiry"]["inquiry_id"] == str(inquiry.public_id)
        assert (
            detail["consultation"]["summary"]["ai_draft_summary"]
            == handoff.ai_draft_summary
        )

        rendered_detail = json.dumps(detail, ensure_ascii=False)
        for forbidden in (
            "system_prompt",
            "raw_output_text",
            "stacktrace",
            "traceback",
            "internal_error",
        ):
            assert forbidden not in rendered_detail

        # The public AI response must not serialize the internal handoff.
        assert "reliability_runtime" not in json.dumps(
            submit_payload,
            ensure_ascii=False,
        )
