"""GUIDANCE_ONLY OpenAI Adapter와 Pipeline 안전 경계 테스트."""

import json
import logging
from pathlib import Path
import subprocess
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from ai.app.bootstrap import create_app
from ai.app.common.timeout import PipelineStageTimeoutError
from ai.app.generation.customer_guidance.guidance_generator import (
    GuidanceGenerationExecutionError,
)
from ai.app.generation.customer_guidance.models import (
    GuidanceGenerationRequest,
    GuidanceGenerationResult,
)
from ai.app.integrations.llm import (
    GuidanceLLMResponse,
    LLMConfigurationError,
    LLMOutputValidationError,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMUsage,
    OpenAIResponsesLLMClient,
)
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval import RetrievedChunk
from ai.app.schemas.common import RiskLevel, UsageGuidanceStatus


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


class MixedTasteEvidenceSearchService:
    def search(self, *args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="RAG-WPUJAC104DWH-LOW-FLOW-001",
                document_title="WPU-JAC104D 사용설명서",
                manual_model="WPUJAC104DWH",
                model_code="WPUJAC104DWH",
                product_generation="D",
                content="무관한 출수량 근거",
                similarity_score=0.99,
                verification_status="official_verified",
                allowed_use=True,
                topic_code="symptom_low_flow",
            ),
            RetrievedChunk(
                chunk_id="RAG-WPUJAC104DWH-TASTE-ODOR-001",
                document_title="WPU-JAC104D 사용설명서",
                manual_model="WPUJAC104DWH",
                model_code="WPUJAC104DWH",
                product_generation="D",
                content="물맛과 냄새 관련 공식 근거",
                similarity_score=0.91,
                verification_status="official_verified",
                allowed_use=True,
                topic_code="symptom_taste_odor",
            ),
        ]


class UnrelatedTasteEvidenceSearchService:
    def search(self, *args, **kwargs):
        return MixedTasteEvidenceSearchService().search(*args, **kwargs)[:1]


class UnexpectedSearchService:
    def search(self, *args, **kwargs):
        raise AssertionError("문진 완료 전에는 근거 검색을 호출하면 안 됩니다.")


class SequenceLLMClient:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0
        self.requests = []
        self.timeouts = []

    def generate_guidance(self, request, *, timeout_seconds):
        self.requests.append(request)
        self.timeouts.append(timeout_seconds)
        value = self.values[self.calls]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value


def llm_response(
    *,
    message="출수량이 적을 때 원수 공급과 필터 상태를 확인합니다.",
    actions=None,
):
    return GuidanceLLMResponse(
        output=GuidanceGenerationResult(
            message=message,
            next_actions=actions or ["안내된 자가조치 단계별 점검 수행"],
        ),
        model_name="gpt-4.1-mini",
        usage=LLMUsage(input_tokens=20, output_tokens=10, total_tokens=30),
        latency_ms=23.4,
    )


def run_pipeline(
    *,
    search_service,
    llm_client,
    raw_symptom="냉수 출수량이 적습니다.",
    selected_symptoms=None,
    model_code="WPUJAC104DWH",
    previous_answers=None,
):
    return PipelineRouter(
        search_service=search_service,
        llm_client=llm_client,
    ).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-guidance-only",
        state_version=1,
        raw_symptom=raw_symptom,
        model_code=model_code,
        selected_symptoms=selected_symptoms,
        previous_answers=previous_answers or [],
    )


def accepted_actions(raw_symptom="냉수 출수량이 적습니다."):
    return (
        ["안내된 자가조치 단계별 점검 수행"]
        if "미지근" in raw_symptom or "출수량" in raw_symptom
        else ["기본 필터 및 사용 환경 유지"]
    )


COMPLETE_TASTE_ANSWERS = [
    {"question_id": "followup-occurrence-time", "answer_text": "오늘부터"},
    {"question_id": "followup-target-water-type", "answer_text": "정수"},
    {"question_id": "followup-actions-taken", "answer_text": "아직 조치하지 않음"},
    {
        "question_id": "followup-taste-odor-applicability",
        "answer_text": "10일 이내 부재 후",
    },
]


def test_earthy_taste_waits_for_context_before_retrieval_or_llm():
    client = SequenceLLMClient(llm_response())

    pipeline_result = run_pipeline(
        search_service=UnexpectedSearchService(),
        llm_client=client,
        raw_symptom="물에서 흙맛이 나는 것 같아요",
    )
    result = pipeline_result.to_analysis_result()

    assert client.calls == 0
    assert pipeline_result.context.awaiting_customer_input is True
    assert pipeline_result.context.retrieval_outcome.value == "NOT_RUN"
    assert result.status.value == "SUCCEEDED"
    assert result.failure_stage is None
    assert {
        question.question_id for question in result.followup_questions
    }.issuperset({"followup-taste-odor-applicability"})
    assert "followup-occurrence-condition" not in {
        question.question_id for question in result.followup_questions
    }
    assert result.evidence_references == []
    assert result.usage_guidance.guidance_status.value == "PENDING_CONSULTATION"
    assert result.safety_assessment.risk_level == RiskLevel.CAUTION
    assert result.safety_assessment.requires_consultation is True


def test_earthy_taste_generation_receives_only_taste_or_odor_evidence():
    taste_message = "물맛과 냄새 관련 공식 근거"
    client = SequenceLLMClient(
        llm_response(
            message=taste_message,
            actions=["기본 필터 및 사용 환경 유지"],
        )
    )

    result = run_pipeline(
        search_service=MixedTasteEvidenceSearchService(),
        llm_client=client,
        raw_symptom="물에서 흙맛이 나는 것 같아요",
        previous_answers=COMPLETE_TASTE_ANSWERS,
    ).to_analysis_result()

    assert result.structured_symptom.symptom_type == "물맛/냄새 이상"
    assert result.structured_symptom.occurrence_condition == "10일 이내 부재 후"
    assert [reference.summary for reference in result.evidence_references] == [
        taste_message
    ]
    assert client.requests[0].symptom_summary == (
        "물맛/냄새 이상 | 정수 | 10일 이내 부재 후"
    )
    assert client.requests[0].evidence_summaries == [taste_message]


@pytest.mark.parametrize(
    ("answer_text", "expected_code", "expected_condition"),
    [
        ("해당 없음", "NOT_APPLICABLE", "해당 없음"),
        ("10일 이상 부재 후", "ABSENCE_OVER_10_DAYS", "10일 이상 부재 후"),
        ("장시간 미사용 후", "LONG_UNUSED", "장시간 미사용 후"),
        (
            "부적합 장소 설치 후",
            "UNSUITABLE_INSTALLATION",
            "부적합 장소 설치 후",
        ),
    ],
)
def test_earthy_taste_context_without_safe_self_guidance_routes_to_no_evidence(
    answer_text,
    expected_code,
    expected_condition,
):
    client = SequenceLLMClient(llm_response())
    previous_answers = [
        *COMPLETE_TASTE_ANSWERS[:-1],
        {
            "question_id": "followup-taste-odor-applicability",
            "answer_text": answer_text,
        },
    ]

    pipeline_result = run_pipeline(
        search_service=MixedTasteEvidenceSearchService(),
        llm_client=client,
        raw_symptom="물에서 흙맛이 나는 것 같아요",
        previous_answers=previous_answers,
    )
    result = pipeline_result.to_analysis_result()

    assert client.calls == 0
    assert pipeline_result.context.evidence_applicability.value == expected_code
    assert result.structured_symptom.occurrence_condition == expected_condition
    assert pipeline_result.context.retrieval_outcome.value == "NO_MATCH"
    assert result.status.value == "FALLBACK"
    assert result.failure_stage.value == "RETRIEVING"
    assert result.evidence_references == []
    assert result.usage_guidance.guidance_status.value == "PENDING_CONSULTATION"


def test_earthy_taste_with_only_unrelated_evidence_fails_closed_without_llm():
    client = SequenceLLMClient(llm_response())

    result = run_pipeline(
        search_service=UnrelatedTasteEvidenceSearchService(),
        llm_client=client,
        raw_symptom="물에서 흙맛이 나는 것 같아요",
        previous_answers=COMPLETE_TASTE_ANSWERS,
    ).to_analysis_result()

    assert client.calls == 0
    assert result.evidence_references == []
    assert result.usage_guidance.guidance_status.value == "PENDING_CONSULTATION"


def generation_request() -> GuidanceGenerationRequest:
    return GuidanceGenerationRequest(
        model_code="WPUJAC104DWH",
        symptom_summary="출수량 저하",
        risk_level="caution",
        guidance_status="PARTIAL_STOP",
        safety_reason="일반 점검 필요",
        restricted_functions=["냉수 출수 확인 필요"],
        allowed_next_actions=["원수 공급 상태를 확인하세요."],
        evidence_summaries=["원수 공급과 필터 상태를 확인합니다."],
    )


def test_openai_adapter_sends_guidance_only_strict_schema():
    captured = {}

    def handler(request: httpx.Request):
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={
            "status": "completed",
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
    request = generation_request()

    response = client.generate_guidance(request, timeout_seconds=1.0)

    output_schema = captured["payload"]["text"]["format"]["schema"]
    assert captured["authorization"] == "Bearer test-only-key"
    assert captured["payload"]["model"] == "gpt-4.1-mini"
    assert captured["payload"]["store"] is False
    assert captured["payload"]["temperature"] == 0.0
    assert captured["payload"]["max_output_tokens"] == 500
    assert captured["payload"]["text"]["format"]["strict"] is True
    assert set(output_schema["properties"]) == {"message", "next_actions"}
    assert output_schema["properties"]["message"]["enum"] == (
        request.evidence_summaries
    )
    assert output_schema["properties"]["next_actions"]["items"]["enum"] == (
        request.allowed_next_actions
    )
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
                "status": "completed",
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


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (408, LLMProviderTimeoutError),
        (504, LLMProviderTimeoutError),
        (429, LLMProviderConnectionError),
        (500, LLMProviderConnectionError),
    ],
)
def test_openai_adapter_classifies_provider_http_failures(
    status_code,
    expected_error,
):
    client = OpenAIResponsesLLMClient(
        api_key="test-only-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status_code, json={"error": {}})
            )
        ),
    )

    with pytest.raises(expected_error):
        client.generate_guidance(generation_request(), timeout_seconds=1.0)


def test_openai_adapter_rejects_incomplete_response_even_with_valid_output():
    client = OpenAIResponsesLLMClient(
        api_key="test-only-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "status": "incomplete",
                        "incomplete_details": {"reason": "max_output_tokens"},
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": json.dumps(
                                            {
                                                "message": "안내",
                                                "next_actions": ["상담 연결"],
                                            },
                                            ensure_ascii=False,
                                        ),
                                    }
                                ],
                            }
                        ],
                    },
                )
            )
        ),
    )

    with pytest.raises(LLMOutputValidationError):
        client.generate_guidance(generation_request(), timeout_seconds=1.0)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.openai.com/v1",
        "https://api.openai.com.evil.example/v1",
        "https://evil.example/v1",
        "https://api.openai.com/v1?redirect=evil",
        "https://token@api.openai.com/v1",
        "https://api.openai.com:8443/v1",
        "https://api.openai.com:not-a-port/v1",
    ],
)
def test_openai_adapter_rejects_untrusted_base_url(base_url):
    with pytest.raises(LLMConfigurationError):
        OpenAIResponsesLLMClient(
            api_key="test-only-key",
            base_url=base_url,
        )


def test_environment_rejects_unapproved_llm_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("AI_LLM_MODEL", "unapproved-model")

    with pytest.raises(LLMConfigurationError, match="승인된"):
        OpenAIResponsesLLMClient.from_environment()


def test_evidence_path_calls_llm_and_preserves_runtime_owned_fields():
    client = SequenceLLMClient(llm_response())
    result = run_pipeline(search_service=EvidenceSearchService(), llm_client=client)
    response = result.to_analysis_result()

    assert client.calls == 1
    assert response.usage_guidance.message == (
        "출수량이 적을 때 원수 공급과 필터 상태를 확인합니다."
    )
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
            llm_client=SequenceLLMClient(
                llm_response(actions=accepted_actions(raw_symptom))
            ),
            raw_symptom=raw_symptom,
        )
    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "llm_guidance_completed"
    assert payload["model_name"] == "gpt-4.1-mini"
    assert payload["prompt_version"] == "customer_guidance/v3"
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


def test_pipeline_stage_timeout_is_not_reclassified_as_provider_503():
    client = SequenceLLMClient(PipelineStageTimeoutError("GENERATING"))

    with pytest.raises(PipelineStageTimeoutError) as raised:
        run_pipeline(search_service=EvidenceSearchService(), llm_client=client)

    assert raised.value.stage == "GENERATING"
    assert client.calls == 1


def test_prohibited_llm_action_fails_closed():
    client = SequenceLLMClient(llm_response(
        message="정확한 원인은 점검이 필요합니다.",
        actions=["커버를 분해하세요."],
    ))
    with pytest.raises(GuidanceGenerationExecutionError) as raised:
        run_pipeline(search_service=EvidenceSearchService(), llm_client=client)

    assert client.calls == 1
    assert raised.value.retryable is False


@pytest.mark.parametrize(
    "unsafe_message",
    [
        "모든 기능을 정상적으로 계속 사용해도 됩니다.",
        "제품 뒷면을 열고 전선 연결을 확인해 주세요.",
        "공식 수질 검사 결과 세균이 없으므로 바로 마셔도 됩니다.",
        "원수 공급과 필터 상태 확인은 필요 없습니다.",
    ],
)
def test_unsafe_or_ungrounded_llm_message_fails_closed(
    unsafe_message,
):
    client = SequenceLLMClient(llm_response(message=unsafe_message))

    with pytest.raises(GuidanceGenerationExecutionError) as raised:
        run_pipeline(search_service=EvidenceSearchService(), llm_client=client)

    assert client.calls == 1
    assert raised.value.retryable is False


def test_exact_official_directive_message_is_allowed_without_rewriting():
    official_message = "원수 공급 상태를 확인해 주세요."

    class DirectiveEvidenceSearchService:
        def search(self, *args, **kwargs):
            chunk = EvidenceSearchService().search(*args, **kwargs)[0]
            return [chunk.model_copy(update={"content": official_message})]

    result = run_pipeline(
        search_service=DirectiveEvidenceSearchService(),
        llm_client=SequenceLLMClient(
            llm_response(
                message=official_message,
                actions=accepted_actions(),
            )
        ),
    ).to_analysis_result()

    assert result.usage_guidance.message == official_message


def test_rewritten_official_directive_message_fails_closed():
    class DirectiveEvidenceSearchService:
        def search(self, *args, **kwargs):
            chunk = EvidenceSearchService().search(*args, **kwargs)[0]
            return [
                chunk.model_copy(
                    update={"content": "원수 상태를 확인해 주세요."}
                )
            ]

    with pytest.raises(GuidanceGenerationExecutionError):
        run_pipeline(
            search_service=DirectiveEvidenceSearchService(),
            llm_client=SequenceLLMClient(
                llm_response(
                    message="원수 상태를 반드시 확인해 주세요.",
                    actions=accepted_actions(),
                )
            ),
        )


def test_provider_request_redacts_pii_and_excludes_raw_occurrence_condition():
    phone_number = "010-1234-5678"
    raw_symptom = (
        f"냉수 출수량이 적고 사용할 때 연락처 {phone_number}, "
        "주소 서울시 고객동 1번지로 연락해 주세요."
    )
    client = SequenceLLMClient(llm_response())

    run_pipeline(
        search_service=EvidenceSearchService(),
        llm_client=client,
        raw_symptom=raw_symptom,
        selected_symptoms=[f"출수량 저하 {phone_number}"],
        model_code="WPUJAC104DWH",
    )

    provider_request = client.requests[0]
    serialized = provider_request.model_dump_json()
    assert phone_number not in serialized
    assert "서울시 고객동" not in serialized
    assert raw_symptom not in serialized
    assert provider_request.symptom_summary.startswith("기타 증상")
    assert provider_request.model_code == "WPUJAC104DWH"


def test_unregistered_pii_shaped_model_code_stops_before_provider():
    client = SequenceLLMClient(llm_response())

    pipeline_result = run_pipeline(
        search_service=EvidenceSearchService(),
        llm_client=client,
        model_code="customer@example.com",
    )

    response = pipeline_result.to_analysis_result()
    assert client.calls == 0
    assert client.requests == []
    assert response.status.value == "FALLBACK"
    assert response.evidence_references == []


def test_provider_request_excludes_free_form_previous_answers():
    name_and_address = "홍길동이 서울특별시 강남구 테헤란로 123에서 확인했습니다."
    client = SequenceLLMClient(llm_response())

    PipelineRouter(
        search_service=EvidenceSearchService(),
        llm_client=client,
    ).run_pipeline(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-req-free-form-pii",
        state_version=1,
        raw_symptom="냉수 출수량이 적습니다.",
        model_code="WPUJAC104DWH",
        previous_answers=[
            {
                "question_id": "followup-occurrence-time",
                "answer_text": name_and_address,
            },
            {
                "question_id": "followup-actions-taken",
                "answer_text": name_and_address,
            },
            {
                "question_id": "followup-target-water-type",
                "answer_text": name_and_address,
            },
        ],
    )

    serialized = client.requests[0].model_dump_json()
    assert "홍길동" not in serialized
    assert "서울특별시" not in serialized
    assert "테헤란로" not in serialized


def test_guidance_generator_imports_in_fresh_interpreter():
    repository_root = Path(__file__).resolve().parents[3]
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from ai.app.generation.customer_guidance.guidance_generator "
                "import CustomerGuidanceGenerator"
            ),
        ],
        cwd=repository_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


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
