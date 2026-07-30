"""FastAPI HTTP API 라우터 단위 테스트."""

import time
import pytest
from fastapi.testclient import TestClient
from ai.app.bootstrap import create_app
from ai.app.interfaces.http.runtime_policy import RuntimePolicy, get_runtime_policy

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_check_endpoint(client):
    """GET /health 및 GET /api/v1/ai/health 테스트"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ai-service"
    assert data["config_loaded"] is True

    response_v1 = client.get("/api/v1/ai/health")
    assert response_v1.status_code == 200


def test_analyze_endpoint_mock_mode(client):
    """POST /api/v1/ai/analyze?mode=mock 테스트"""
    payload = {
        "inquiry_id": "DEMO-INQ-002",
        "correlation_id": "corr-test-999",
        "ai_request_id": "ai-req-test-999",
        "state_version": 3,
        "raw_symptom": "냉수가 미지근하고 졸졸 나옵니다.",
        "model_code": "WPUJAC104DWH",
        "selected_symptoms": ["출수량 저하"],
        "previous_answers": []
    }

    response = client.post("/api/v1/ai/analyze?mode=mock", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["inquiry_id"] == "DEMO-INQ-002"
    assert data["correlation_id"] == "corr-test-999"
    assert data["ai_request_id"] == "ai-req-test-999"
    assert data["state_version"] == 3
    assert response.headers["X-Correlation-ID"] == "corr-test-999"
    assert "model_metadata" not in data
    assert "processing_traces" not in data
    assert data["safety_assessment"]["risk_level"] == "caution"
    assert data["usage_guidance"]["guidance_status"] == "PARTIAL_STOP"


def test_analyze_endpoint_local_mode_leak(client):
    """POST /api/v1/ai/analyze?mode=local 누수 감지 테스트"""
    payload = {
        "inquiry_id": "DEMO-INQ-003",
        "correlation_id": "corr-test-leak",
        "ai_request_id": "ai-req-test-leak",
        "state_version": 1,
        "raw_symptom": "정수기 하부에서 누수가 생기고 전원선 근처에 물이 샙니다.",
        "model_code": "WPUJAC104DWH",
        "selected_symptoms": ["누수"],
        "previous_answers": []
    }

    response = client.post("/api/v1/ai/analyze?mode=local", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["safety_assessment"]["risk_level"] == "danger"
    assert data["usage_guidance"]["guidance_status"] == "TOTAL_STOP"
    assert data["safety_assessment"]["requires_consultation"] is True


def test_analyze_endpoint_validation_error(client):
    """필수 필드 누락 시 422 오류 처리 테스트"""
    payload = {
        "inquiry_id": "DEMO-INQ-999"
        # raw_symptom, correlation_id 누락
    }

    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 422
    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "AI-VALIDATION-01"
    assert data["error"]["failure_stage"] == "STRUCTURING"


def test_analyze_endpoint_rejects_correlation_id_mismatch(client):
    payload = {
        "inquiry_id": "DEMO-INQ-CORR",
        "correlation_id": "corr-body",
        "ai_request_id": "ai-req-corr",
        "state_version": 1,
        "raw_symptom": "냉수가 미지근합니다.",
        "model_code": "WPUJAC104DWH",
    }
    response = client.post(
        "/api/v1/ai/analyze?mode=mock",
        json=payload,
        headers={"X-Correlation-ID": "corr-header"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AI-VALIDATION-01"
    assert response.headers["X-Correlation-ID"] == "corr-body"


def test_analyze_endpoint_timeout_contract(client, monkeypatch):
    from ai.app.interfaces.http.routes import analysis_routes

    payload = {
        "inquiry_id": "DEMO-INQ-TIMEOUT",
        "correlation_id": "corr-timeout",
        "ai_request_id": "ai-req-timeout",
        "state_version": 4,
        "raw_symptom": "알 수 없는 표시가 반복됩니다.",
        "model_code": "WPUJAC104DWH",
    }

    def slow_pipeline(*args, **kwargs):
        time.sleep(0.05)

    monkeypatch.setattr(analysis_routes, "get_runtime_policy", lambda: RuntimePolicy(0.01, 0, 1))
    monkeypatch.setattr(analysis_routes.PipelineRouter, "run_pipeline", slow_pipeline)

    response = client.post("/api/v1/ai/analyze?mode=local", json=payload)
    assert response.status_code == 504
    body = response.json()
    assert body["correlation_id"] == "corr-timeout"
    assert body["ai_request_id"] == "ai-req-timeout"
    assert body["state_version"] == 4
    assert body["error"]["code"] == "AI-TIMEOUT-01"
    assert body["error"]["failure_stage"] == "CANCELLED"
    assert body["error"]["retry_count"] == 0


def test_runtime_retry_and_timeout_policy_is_contract_value():
    policy = get_runtime_policy()
    assert policy.overall_timeout_seconds == 30.0
    assert policy.ai_internal_max_retry_count == 1
    assert policy.backend_retry_count == 0
