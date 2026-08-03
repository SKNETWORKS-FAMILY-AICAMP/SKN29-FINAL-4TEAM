"""FastAPI HTTP API 라우터 단위 테스트."""

import json
import logging
import time
from threading import Event
import pytest
from fastapi.testclient import TestClient
from ai.app.bootstrap import create_app
from ai.app.interfaces.http.runtime_policy import RuntimePolicy, get_runtime_policy

INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88b301"

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
        "inquiry_id": INQUIRY_ID,
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

    assert data["inquiry_id"] == INQUIRY_ID
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
        "inquiry_id": INQUIRY_ID,
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
        "inquiry_id": INQUIRY_ID
        # raw_symptom, correlation_id 누락
    }

    response = client.post("/api/v1/ai/analyze", json=payload)
    assert response.status_code == 422
    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "AI-VALIDATION-01"
    assert data["error"]["failure_stage"] == "STRUCTURING"


def test_analyze_endpoint_rejects_non_uuid_inquiry_id_without_handler_failure(client):
    response = client.post("/api/v1/ai/analyze?mode=mock", json={
        "inquiry_id": "DEMO-INQ-001",
        "correlation_id": "corr-invalid-uuid",
        "ai_request_id": "ai-req-invalid-uuid",
        "state_version": 1,
        "raw_symptom": "물이 나오지 않습니다.",
        "model_code": "WPUJAC104DWH",
    })
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["inquiry_id"] is None
    assert body["correlation_id"] == "corr-invalid-uuid"
    assert body["error"]["code"] == "AI-VALIDATION-01"


def test_analyze_endpoint_rejects_correlation_id_mismatch(client):
    payload = {
        "inquiry_id": INQUIRY_ID,
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


def test_analyze_endpoint_timeout_contract(client, monkeypatch, caplog):
    from ai.app.interfaces.http.routes import analysis_routes

    payload = {
        "inquiry_id": INQUIRY_ID,
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

    with caplog.at_level(logging.INFO, logger="watercare.ai.analysis"):
        response = client.post("/api/v1/ai/analyze?mode=local", json=payload)
    assert response.status_code == 504
    body = response.json()
    assert body["correlation_id"] == "corr-timeout"
    assert body["ai_request_id"] == "ai-req-timeout"
    assert body["state_version"] == 4
    assert body["error"]["code"] == "AI-TIMEOUT-01"
    assert body["error"]["failure_stage"] == "CANCELLED"
    assert body["error"]["retry_count"] == 0
    payloads = [
        json.loads(record.message)
        for record in caplog.records
        if '"correlation_id": "corr-timeout"' in record.message
    ]
    assert [payload["event"] for payload in payloads] == ["analysis_started", "analysis_failed"]
    assert payloads[-1]["error_code"] == "AI-TIMEOUT-01"


def test_runtime_retry_and_timeout_policy_is_contract_value():
    policy = get_runtime_policy()
    assert policy.overall_timeout_seconds == 30.0
    assert policy.ai_internal_max_retry_count == 1
    assert policy.ai_internal_retry_enabled is False
    assert policy.backend_retry_count == 0


def test_stage_timeout_returns_stage_specific_504(client, monkeypatch):
    from ai.app.common.timeout import PipelineStageTimeoutError
    from ai.app.interfaces.http.routes import analysis_routes

    def stage_timeout(*args, **kwargs):
        raise PipelineStageTimeoutError("RETRIEVING")

    monkeypatch.setattr(analysis_routes.PipelineRouter, "run_pipeline", stage_timeout)
    response = client.post("/api/v1/ai/analyze?mode=local", json={
        "inquiry_id": INQUIRY_ID,
        "correlation_id": "corr-stage-timeout",
        "ai_request_id": "ai-req-stage-timeout",
        "state_version": 3,
        "raw_symptom": "검색 단계 지연 검증",
        "model_code": "WPUJAC104DWH",
    })

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "AI-TIMEOUT-01"
    assert response.json()["error"]["failure_stage"] == "RETRIEVING"


def test_timeout_signals_cooperative_worker_cancellation(client, monkeypatch):
    from ai.app.interfaces.http.routes import analysis_routes

    cancellation_observed = Event()

    def cooperative_pipeline(*args, cancellation_token, **kwargs):
        while not cancellation_token.is_cancelled:
            time.sleep(0.001)
        cancellation_observed.set()
        cancellation_token.raise_if_cancelled()

    monkeypatch.setattr(analysis_routes, "get_runtime_policy", lambda: RuntimePolicy(0.01, 0, 1))
    monkeypatch.setattr(analysis_routes.PipelineRouter, "run_pipeline", cooperative_pipeline)
    response = client.post("/api/v1/ai/analyze?mode=local", json={
        "inquiry_id": INQUIRY_ID,
        "correlation_id": "corr-cancel",
        "ai_request_id": "ai-req-cancel",
        "state_version": 1,
        "raw_symptom": "취소 검증",
        "model_code": "WPUJAC104DWH",
    })
    assert response.status_code == 504
    assert cancellation_observed.wait(0.2)


def test_structured_log_excludes_customer_text(client, caplog):
    raw_text = "로그에 남으면 안 되는 고객 원문"
    with caplog.at_level(logging.INFO, logger="watercare.ai.analysis"):
        response = client.post("/api/v1/ai/analyze?mode=mock", json={
            "inquiry_id": INQUIRY_ID,
            "correlation_id": "corr-log",
            "ai_request_id": "ai-req-log",
            "state_version": 1,
            "raw_symptom": raw_text,
            "model_code": "WPUJAC104DWH",
        })
    assert response.status_code == 200
    assert raw_text not in caplog.text
    payloads = [json.loads(record.message) for record in caplog.records]
    assert {payload["event"] for payload in payloads} == {"analysis_started", "analysis_completed"}
    assert all(payload["correlation_id"] == "corr-log" for payload in payloads)


def test_default_runtime_logger_emits_info():
    logger = logging.getLogger("watercare.ai.analysis")
    assert logger.isEnabledFor(logging.INFO)


def test_validation_error_emits_single_safe_failure_log(client, caplog):
    raw_text = "로그에 남으면 안 되는 검증 실패 고객 원문"
    with caplog.at_level(logging.INFO, logger="watercare.ai.analysis"):
        response = client.post("/api/v1/ai/analyze", json={
            "inquiry_id": INQUIRY_ID,
            "correlation_id": "corr-validation-log",
            "raw_symptom": raw_text,
        })
    assert response.status_code == 422
    assert raw_text not in caplog.text
    payloads = [json.loads(record.message) for record in caplog.records]
    assert [payload["event"] for payload in payloads] == ["analysis_failed"]
    assert payloads[0]["correlation_id"] == "corr-validation-log"
    assert payloads[0]["error_code"] == "AI-VALIDATION-01"


def test_header_mismatch_emits_failure_without_started_event(client, caplog):
    with caplog.at_level(logging.INFO, logger="watercare.ai.analysis"):
        response = client.post(
            "/api/v1/ai/analyze?mode=mock",
            headers={"X-Correlation-ID": "corr-header"},
            json={
                "inquiry_id": INQUIRY_ID,
                "correlation_id": "corr-body-log",
                "ai_request_id": "ai-req-log-mismatch",
                "state_version": 1,
                "raw_symptom": "출수가 안 됩니다.",
                "model_code": "WPUJAC104DWH",
            },
        )
    assert response.status_code == 400
    payloads = [json.loads(record.message) for record in caplog.records]
    assert [payload["event"] for payload in payloads] == ["analysis_failed"]
    assert payloads[0]["correlation_id"] == "corr-body-log"


def test_internal_pipeline_failure_emits_started_then_failed(client, monkeypatch, caplog):
    from ai.app.interfaces.http.routes import analysis_routes

    def failing_pipeline(*args, **kwargs):
        raise RuntimeError("고객에게 노출하거나 로그에 남기면 안 되는 내부 예외")

    monkeypatch.setattr(analysis_routes.PipelineRouter, "run_pipeline", failing_pipeline)
    with caplog.at_level(logging.INFO, logger="watercare.ai.analysis"):
        response = client.post("/api/v1/ai/analyze?mode=local", json={
            "inquiry_id": INQUIRY_ID,
            "correlation_id": "corr-internal-failure",
            "ai_request_id": "ai-req-internal-failure",
            "state_version": 1,
            "raw_symptom": "출수가 안 됩니다.",
            "model_code": "WPUJAC104DWH",
        })
    assert response.status_code == 503
    assert "내부 예외" not in caplog.text
    payloads = [
        json.loads(record.message)
        for record in caplog.records
        if '"correlation_id": "corr-internal-failure"' in record.message
    ]
    assert [payload["event"] for payload in payloads] == ["analysis_started", "analysis_failed"]
    assert payloads[-1]["error_code"] == "AI-FAILED-01"


def test_worker_limit_configuration(monkeypatch):
    from ai.app.interfaces.http.routes import analysis_routes

    monkeypatch.setenv("AI_MAX_IN_FLIGHT_WORKERS", "4")
    assert analysis_routes._worker_limit() == 4
    monkeypatch.setenv("AI_MAX_IN_FLIGHT_WORKERS", "0")
    with pytest.raises(RuntimeError, match="1~32"):
        analysis_routes._worker_limit()
