"""FastAPI HTTP API 라우터 단위 테스트."""

import pytest
from fastapi.testclient import TestClient
from ai.app.bootstrap import create_app

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
        "raw_symptom": "냉수가 미지근하고 졸졸 나옵니다.",
        "model_code": "WPUJAC104DWH",
        "selected_symptoms": ["출수량 저하"],
        "previous_answers": []
    }

    response = client.post("/api/v1/ai/analyze?mode=mock", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["trace_context"]["inquiry_id"] == "DEMO-INQ-002"
    assert data["safety_assessment"]["risk_level"] == "caution"
    assert data["usage_guidance"]["guidance_status"] == "PARTIAL_STOP"


def test_analyze_endpoint_local_mode_leak(client):
    """POST /api/v1/ai/analyze?mode=local 누수 감지 테스트"""
    payload = {
        "inquiry_id": "DEMO-INQ-003",
        "correlation_id": "corr-test-leak",
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
    assert data["error"]["code"] == "INVALID_INPUT_FORMAT"
