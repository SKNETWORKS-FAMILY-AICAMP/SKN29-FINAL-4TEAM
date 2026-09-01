"""Public HTTP v4 boundary after selective natural-language integration."""

import logging

import pytest
from fastapi.testclient import TestClient

from ai.app.bootstrap import create_app
from ai.app.interfaces.http.routes import analysis_routes
from ai.app.orchestration.pipeline_router import PipelineRouter


REQUEST = {
    "inquiry_id": "018f2f9b-7c30-7981-b541-1a987c88b811",
    "correlation_id": "018f2f9b-7c30-7981-b541-1a987c88b812",
    "ai_request_id": "selective-http-safety", "state_version": 7,
    "raw_symptom": "전선 피복이 벗겨졌어요. 연락처 010-1234-5678입니다.",
    "model_code": "WPUJAC104DWH",
}


class ForbiddenDependencies:
    def __init__(self):
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Search must not run")

    def structure_symptom(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Provider must not run")

    generate_followup_wording = structure_symptom
    generate_guidance = structure_symptom


def client(monkeypatch, runtime):
    monkeypatch.delenv("AI_VECTOR_DSN", raising=False)
    monkeypatch.delenv("AI_RAG_RUNTIME_PROFILE", raising=False)
    monkeypatch.setenv("AI_PIPELINE_RUNTIME", runtime)
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "direct")
    monkeypatch.setenv("AI_BACKEND_HANDOFF_ENABLED", "false")
    dependency = ForbiddenDependencies()
    router = PipelineRouter(
        search_service=dependency, symptom_llm_client=dependency,
        followup_llm_client=dependency, llm_client=dependency, mcp_context_service=None,
    )
    monkeypatch.setattr(analysis_routes, "PipelineRouter", lambda: router)
    return TestClient(create_app()), dependency


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
@pytest.mark.parametrize("model", ["WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"])
def test_http_electrical_danger_has_no_external_calls_and_retains_trace(monkeypatch, caplog, runtime, model):
    http, dependency = client(monkeypatch, runtime)
    with caplog.at_level(logging.INFO):
        response = http.post("/api/v1/ai/analyze?mode=local", json={**REQUEST, "model_code": model})
    assert response.status_code == 200
    data = response.json()
    for name in ("inquiry_id", "correlation_id", "ai_request_id", "state_version"):
        assert data[name] == REQUEST[name]
    assert response.headers["X-Correlation-ID"] == REQUEST["correlation_id"]
    assert data["safety_assessment"]["risk_level"] == "danger"
    assert data["safety_assessment"]["requires_consultation"] is True
    assert data["safety_assessment"]["matched_safety_rule_ids"]
    assert data["usage_guidance"]["guidance_status"] == "TOTAL_STOP"
    assert data["evidence_references"] == [] and dependency.calls == 0
    assert data["fallback_reason_code"] == (None if model == "WPUJAC104DWH" else "RUNTIME_PRODUCT_NOT_APPROVED")
    assert "010-1234-5678" not in response.text + caplog.text
    assert "safety_signals" not in response.text and "evidence_quote" not in response.text
