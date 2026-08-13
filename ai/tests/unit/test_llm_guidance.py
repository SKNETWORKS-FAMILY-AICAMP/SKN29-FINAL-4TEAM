"""GUIDANCE_ONLY OpenAI Adapter와 Pipeline 안전 경계 테스트."""

import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from ai.app.bootstrap import create_app
from ai.app.generation.customer_guidance.guidance_generator import (
    GuidanceGenerationExecutionError,
)
from ai.app.generation.customer_guidance.models import (
    GuidanceGenerationRequest,
    GuidanceGenerationResult,
)
from ai.app.integrations.llm import (
    GuidanceLLMResponse,
    LLMOutputValidationError,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMUsage,
    OpenAIResponsesLLMClient,
)
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval import RetrievedChunk
from ai.app.schemas.common import UsageGuidanceStatus


INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88b321"
CORRELATION_ID = "018f2f9b-7c30-7981-b541-1a987c88b421"


class EvidenceSearchService:
    def search(self, *args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="RAG-WPUJAC104DWH-LOW-FLOW-001",
                document_title="WPU-JAC104D 사용설명서",
                document_version="REV.00",
                page=38,
                page_refs=[38],
                manual_model="WPUJAC104DWH",
                model_code="WPUJAC104DWH",
                product_generation="D",
                content="출수량이 적을 때 원수 공급과 필터 상태를 확인합니다.",
                similarity_score=0.93,
                official_url="https://example.invalid/manual",
                verification_status="official_verified",
                allowed_use=True,
            )
        ]


class EmptySearchService:
    def search(self, *args, **kwargs):
        return []


class SequenceLLMClient:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def generate_guidance(self, request, *, timeout_seconds):
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value


def llm_response(*, message="공식 안내에 따라 출수 상태를 확인해 주세요.", actions=None):
    return GuidanceLLMResponse(
        output=GuidanceGenerationResult(
            message=message,
            next_actions=actions or ["안내된 자가조치 단계별 점검 수행"],
        ),
        model_name="gpt-4.1-mini",
        usage=LLMUsage(input_tokens=20, output_tokens=10, total_tokens=30),
        latency_ms=23.4,
    )


def run_pipeline(*, search_service, llm_client, raw_symptom="냉수 출수량이 적습니다."):
    return PipelineRouter(
        search_service=search_service,
        llm_client=llm_client,
    ).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-guidance-only",
        state_version=1,
        raw_symptom=raw_symptom,
        model_code="WPUJAC104DWH",
    )


def test_openai_adapter_sends_guidance_only_strict_schema():
    captured = {}

    def handler(request: httpx.Request):
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "gpt-4.1-mini-2025-04-14",
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({
                        "message": "출수 상태를 확인해 주세요.",
                        "next_actions": ["원수 공급 상태를 확인하세요."],
                    }, ensure_ascii=False),
                }],
            }],
            "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        })

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OpenAIResponsesLLMClient(api_key="test-only-key", http_client=http_client)
    request = GuidanceGenerationRequest(
        model_code="WPUJAC104DWH",
        symptom_summary="출수량 저하",
        risk_level="caution",
        guidance_status="PARTIAL_STOP",
        safety_reason="일반 점검 필요",
        restricted_functions=["냉수 출수 확인 필요"],
        allowed_next_actions=["원수 공급 상태를 확인하세요."],
        evidence_summaries=["원수 공급과 필터 상태를 확인합니다."],
    )

    response = client.generate_guidance(request, timeout_seconds=1.0)

    output_schema = captured["payload"]["text"]["format"]["schema"]
    assert captured["authorization"] == "Bearer test-only-key"
    assert captured["payload"]["model"] == "gpt-4.1-mini"
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert set(output_schema["properties"]) == {"message", "next_actions"}
    assert "correlation_id" not in output_schema["properties"]
    assert "safety_assessment" not in output_schema["properties"]
    assert "evidence_references" not in output_schema["properties"]
    assert response.output.message == "출수 상태를 확인해 주세요."
    assert response.usage.total_tokens == 18


def test_openai_adapter_rejects_schema_violation_without_retry():
    client = OpenAIResponsesLLMClient(
        api_key="test-only-key",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200,
            json={
                "output": [{"type": "message", "content": [{
                    "type": "output_text",
                    "text": '{"message":"안내"}',
                }]}],
            },
        ))),
    )
    request = GuidanceGenerationRequest(
        model_code="WPUJAC104DWH",
        symptom_summary="출수량 저하",
        risk_level="caution",
        guidance_status="PARTIAL_STOP",
        safety_reason="점검 필요",
        allowed_next_actions=["원수 공급 상태를 확인하세요."],
        evidence_summaries=["공식 근거"],
    )
    with pytest.raises(LLMOutputValidationError):
        client.generate_guidance(request, timeout_seconds=1.0)


def test_evidence_path_calls_llm_and_preserves_runtime_owned_fields():
    client = SequenceLLMClient(llm_response())
    result = run_pipeline(search_service=EvidenceSearchService(), llm_client=client)
    response = result.to_analysis_result()

    assert client.calls == 1
    assert response.usage_guidance.message.startswith("공식 안내")
    assert response.usage_guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP
    assert response.safety_assessment.risk_level.value == "caution"
    assert len(response.evidence_references) == 1
    assert str(response.correlation_id) == CORRELATION_ID
    assert result.context.model_metadata.tokens_used == 30


def test_llm_usage_log_records_tokens_without_customer_or_evidence_text(caplog):
    raw_symptom = "로그에 남으면 안 되는 고객 증상 원문"
    with caplog.at_level(logging.INFO, logger="watercare.ai.llm"):
        run_pipeline(
            search_service=EvidenceSearchService(),
            llm_client=SequenceLLMClient(llm_response()),
            raw_symptom=raw_symptom,
        )
    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "llm_guidance_completed"
    assert payload["model_name"] == "gpt-4.1-mini"
    assert payload["total_tokens"] == 30
    assert payload["correlation_id"] == CORRELATION_ID
    assert raw_symptom not in caplog.text
    assert "원수 공급과 필터 상태" not in caplog.text


@pytest.mark.parametrize(
    ("search_service", "raw_symptom", "expected_status"),
    [
        (EmptySearchService(), "처음 보는 표시가 나타납니다.", "PENDING_CONSULTATION"),
        (None, "전원선 주변으로 물이 새고 있습니다.", "TOTAL_STOP"),
    ],
)
def test_no_evidence_and_danger_paths_never_call_llm(
    search_service,
    raw_symptom,
    expected_status,
):
    client = SequenceLLMClient(llm_response())
    result = run_pipeline(
        search_service=search_service,
        llm_client=client,
        raw_symptom=raw_symptom,
    )
    assert client.calls == 0
    assert result.to_analysis_result().usage_guidance.guidance_status.value == expected_status


def test_transient_llm_failure_retries_once_then_succeeds():
    client = SequenceLLMClient(
        LLMProviderConnectionError("temporary"),
        llm_response(),
    )
    result = run_pipeline(search_service=EvidenceSearchService(), llm_client=client)
    generation_trace = next(
        trace for trace in result.context.processing_traces
        if trace.stage.value == "GENERATING"
    )
    assert client.calls == 2
    assert result.to_analysis_result().retry_count == 1
    assert generation_trace.retry_count == 1


def test_evidence_path_without_openai_key_fails_closed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(GuidanceGenerationExecutionError) as raised:
        run_pipeline(search_service=EvidenceSearchService(), llm_client=None)
    assert raised.value.retryable is False
    assert raised.value.timed_out is False
    assert raised.value.retry_count == 0


def test_llm_timeout_retries_once_then_raises_typed_504_candidate():
    client = SequenceLLMClient(
        LLMProviderTimeoutError("timeout-1"),
        LLMProviderTimeoutError("timeout-2"),
    )
    with pytest.raises(GuidanceGenerationExecutionError) as raised:
        run_pipeline(search_service=EvidenceSearchService(), llm_client=client)
    assert client.calls == 2
    assert raised.value.timed_out is True
    assert raised.value.retryable is True
    assert raised.value.retry_count == 1


def test_prohibited_llm_action_falls_back_to_deterministic_guidance():
    client = SequenceLLMClient(llm_response(
        message="정확한 원인은 점검이 필요합니다.",
        actions=["커버를 분해하세요."],
    ))
    result = run_pipeline(search_service=EvidenceSearchService(), llm_client=client)
    guidance = result.to_analysis_result().usage_guidance
    assert client.calls == 1
    assert "커버를 분해하세요" not in guidance.next_actions
    assert guidance.message.startswith("일부 기능에 이상")


def test_http_llm_timeout_is_504_generating(monkeypatch):
    from ai.app.generation.customer_guidance import guidance_generator
    from ai.app.interfaces.http.routes import analysis_routes

    client = SequenceLLMClient(
        LLMProviderTimeoutError("timeout-1"),
        LLMProviderTimeoutError("timeout-2"),
    )
    monkeypatch.setattr(
        analysis_routes.PipelineRouter,
        "_configured_search_service",
        staticmethod(lambda: EvidenceSearchService()),
    )
    monkeypatch.setattr(
        guidance_generator.OpenAIResponsesLLMClient,
        "from_environment",
        classmethod(lambda cls: client),
    )
    response = TestClient(create_app()).post("/api/v1/ai/analyze?mode=local", json={
        "inquiry_id": INQUIRY_ID,
        "correlation_id": CORRELATION_ID,
        "ai_request_id": "ai-req-http-llm-timeout",
        "state_version": 2,
        "raw_symptom": "냉수 출수량이 적습니다.",
        "model_code": "WPUJAC104DWH",
    })
    assert response.status_code == 504
    error = response.json()["error"]
    assert error["code"] == "AI-TIMEOUT-01"
    assert error["failure_stage"] == "GENERATING"
    assert error["retry_count"] == 1
    assert client.calls == 2
