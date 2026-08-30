"""LLM 자연어 구조화·질문 표현의 검증 및 결정적 fallback 테스트."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from uuid import UUID

import httpx
import pytest

import ai.app.structuring.followup_question_generator as followup_module
import ai.app.structuring.symptom_structurer as structurer_module
from ai.app.integrations.llm import (
    LLMOutputValidationError,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMUsage,
)
from ai.app.integrations.llm.natural_language_client import (
    OpenAIResponsesFollowUpWordingClient,
    OpenAIResponsesSymptomStructuringClient,
)
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.schemas import MissingField, StructuredSymptom, TraceContext
from ai.app.structuring import (
    DuplicateQuestionGuard,
    FollowUpQuestionGenerator,
    SymptomStructurer,
)
from ai.app.structuring.llm_contracts import (
    FollowUpWording,
    FollowUpWordingLLMResponse,
    FollowUpWordingResult,
    FollowUpWordingRequest,
    SymptomStructuringLLMResponse,
    SymptomStructuringRequest,
)


class EmptySearchService:
    def search(self, *args, **kwargs):
        return []


class FakeSymptomClient:
    prompt_version = "symptom_structuring/v1"

    def __init__(self, output: StructuredSymptom | None = None, error=None) -> None:
        self.output = output or StructuredSymptom(symptom_type="기타 증상")
        self.error = error
        self.requests: list[SymptomStructuringRequest] = []

    def structure_symptom(self, request, *, timeout_seconds):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SymptomStructuringLLMResponse(
            output=self.output,
            model_name="fake-symptom-model",
            prompt_version=self.prompt_version,
            usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            latency_ms=12.5,
        )


class FakeFollowUpClient:
    prompt_version = "followup_question/v1"

    def __init__(self, wordings=None, error=None) -> None:
        self.wordings = wordings
        self.error = error
        self.requests: list[FollowUpWordingRequest] = []

    def generate_followup_wording(self, request, *, timeout_seconds):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        wordings = self.wordings
        if wordings is None:
            wordings = [
                FollowUpWording(
                    target_field=field,
                    question_text=f"현재 증상과 관련해 {field} 정보는 어떻게 되나요?",
                )
                for field in request.target_fields
            ]
        return FollowUpWordingLLMResponse(
            output=FollowUpWordingResult(questions=wordings),
            model_name="fake-followup-model",
            prompt_version=self.prompt_version,
            usage=LLMUsage(input_tokens=8, output_tokens=4, total_tokens=12),
            latency_ms=9.5,
        )


class FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, object] = {}

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class FakeSpanContext(AbstractContextManager):
    def __init__(self, span: FakeSpan) -> None:
        self.span = span

    def __enter__(self) -> FakeSpan:
        return self.span

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeTracer:
    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []

    def start_as_current_span(self, name: str) -> FakeSpanContext:
        span = FakeSpan(name)
        self.spans.append(span)
        return FakeSpanContext(span)


def _trace_context() -> TraceContext:
    return TraceContext(
        inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b701"),
        correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b702"),
        ai_request_id="ai-req-natural-language-001",
        state_version=1,
    )


def _noise_symptom(**updates) -> StructuredSymptom:
    values = {
        "symptom_type": "소음 이상",
        "occurrence_time": "어제부터",
        "target_water_type": "온수",
        "occurrence_condition": "온수 버튼을 누르고 10초 후",
        "error_code": None,
        "accompanying_symptoms": ["진동"],
        "actions_taken": [],
    }
    values.update(updates)
    return StructuredSymptom(**values)


def test_llm_structures_complex_customer_language() -> None:
    client = FakeSymptomClient(_noise_symptom())
    result = SymptomStructurer(llm_client=client).structure(
        "온수 버튼을 누르고 10초쯤 지나면 안쪽에서 덜덜거려요. 어제부터입니다.",
        ["NOISE"],
        trace_context=_trace_context(),
        model_code="WPU-JAC104",
    )

    assert result == _noise_symptom(accompanying_symptoms=["NOISE", "진동"])
    assert client.requests[0].selected_symptoms == ("NOISE",)


def test_llm_result_merges_confirmed_answer_error_code_and_actions() -> None:
    client = FakeSymptomClient(
        StructuredSymptom(
            symptom_type="기타 증상",
            occurrence_condition="정수 버튼을 누를 때",
            accompanying_symptoms=["표시 오류"],
            actions_taken=[],
        )
    )
    result = SymptomStructurer(llm_client=client).structure(
        "정수 버튼을 누르면 E-12가 표시되어 전원을 껐다 켰습니다",
        ["DISPLAY_ERROR"],
        previous_answers=[
            {
                "question_id": "followup-occurrence-time",
                "answer_text": "오늘 아침부터",
            },
            {
                "question_id": "followup-actions-taken",
                "answer_text": "전원 재부팅",
            },
        ],
    )

    assert result.occurrence_time == "오늘 아침부터"
    assert result.error_code == "E-12"
    assert result.actions_taken == ["전원 재부팅"]


@pytest.mark.parametrize(
    "error",
    [
        LLMProviderTimeoutError("timeout"),
        LLMProviderConnectionError("provider"),
        LLMOutputValidationError("invalid json"),
    ],
)
def test_symptom_provider_failures_use_rule_fallback(error: Exception) -> None:
    result = SymptomStructurer(
        llm_client=FakeSymptomClient(error=error)
    ).structure("어제부터 냉수 출수양이 줄고 물이 쫄쫄 나와요")

    assert result.symptom_type == "출수량 저하"
    assert result.occurrence_time == "어제부터"
    assert result.target_water_type == "냉수"


@pytest.mark.parametrize(
    "candidate",
    [
        StructuredSymptom(symptom_type="지원하지 않는 증상"),
        StructuredSymptom(symptom_type=""),
        StructuredSymptom(symptom_type="기타 증상", error_code="E-999"),
    ],
)
def test_invalid_symptom_domain_output_uses_rule_fallback(candidate) -> None:
    result = SymptomStructurer(
        llm_client=FakeSymptomClient(candidate)
    ).structure("어제부터 냉수가 미지근합니다")

    assert result.symptom_type == "온도 이상"
    assert result.error_code is None


def test_context_aware_followup_preserves_deterministic_contract() -> None:
    fixed = FollowUpQuestionGenerator().generate(
        [MissingField(field_name="occurrence_time", reason="필요", importance="high")]
    )[0]
    client = FakeFollowUpClient(
        [
            FollowUpWording(
                target_field="occurrence_time",
                question_text="온수 사용 중 발생하는 소음은 언제부터 시작됐나요?",
            )
        ]
    )
    generated = FollowUpQuestionGenerator(llm_client=client).generate(
        [MissingField(field_name="occurrence_time", reason="필요", importance="high")],
        symptom=_noise_symptom(occurrence_time=None),
    )[0]

    assert generated.question_text == "온수 사용 중 발생하는 소음은 언제부터 시작됐나요?"
    assert generated.question_id == fixed.question_id
    assert generated.target_field == fixed.target_field
    assert generated.options == fixed.options


@pytest.mark.parametrize(
    "wordings",
    [
        [FollowUpWording(target_field="actions_taken", question_text="무엇을 했나요?")],
        [FollowUpWording(target_field="occurrence_time", question_text="언제부터인가요")],
        [
            FollowUpWording(target_field="occurrence_time", question_text="언제부터인가요?"),
            FollowUpWording(target_field="occurrence_time", question_text="다시 알려주세요?"),
        ],
    ],
)
def test_invalid_followup_output_uses_fixed_template(wordings) -> None:
    generated = FollowUpQuestionGenerator(
        llm_client=FakeFollowUpClient(wordings)
    ).generate(
        [MissingField(field_name="occurrence_time", reason="필요", importance="high")],
        symptom=_noise_symptom(occurrence_time=None),
    )

    assert generated[0].question_text == "증상은 언제부터 시작됐나요?"


def test_followup_provider_failure_uses_fixed_template() -> None:
    generated = FollowUpQuestionGenerator(
        llm_client=FakeFollowUpClient(
            error=LLMProviderTimeoutError("timeout")
        )
    ).generate(
        [MissingField(field_name="target_water_type", reason="필요", importance="medium")],
        symptom=_noise_symptom(target_water_type=None),
    )

    assert generated[0].question_text == "어떤 출수에서 증상이 발생하나요?"


def test_duplicate_guard_still_owns_duplicate_decision_after_llm_wording() -> None:
    questions = FollowUpQuestionGenerator(
        llm_client=FakeFollowUpClient()
    ).generate(
        [MissingField(field_name="occurrence_time", reason="필요", importance="high")],
        symptom=_noise_symptom(occurrence_time=None),
    )
    filtered = DuplicateQuestionGuard().filter(
        questions,
        [{"question_id": "followup-occurrence-time", "answer_text": "답변하지 않음"}],
    )

    assert filtered == []


def test_openai_symptom_adapter_uses_strict_schema_and_redacts_private_text() -> None:
    captured = {}

    def handler(request: httpx.Request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": "gpt-4o-mini-test",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": _noise_symptom().model_dump_json(),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            },
        )

    client = OpenAIResponsesSymptomStructuringClient(
        api_key="test-only-key",
        prompt_version="symptom_structuring/v1",
        model_name="gpt-4o-mini",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = client.structure_symptom(
        SymptomStructuringRequest(
            raw_symptom="010-1234-5678 user@example.com 온수에서 소음이 납니다",
        ),
        timeout_seconds=1.0,
    )

    payload = captured["payload"]
    schema = payload["text"]["format"]["schema"]
    user_prompt = payload["input"][1]["content"]
    assert payload["text"]["format"]["strict"] is True
    assert schema["properties"]["symptom_type"]["enum"]
    assert "010-1234-5678" not in user_prompt
    assert "user@example.com" not in user_prompt
    assert response.output.symptom_type == "소음 이상"


def test_openai_symptom_adapter_rejects_invalid_output_json() -> None:
    client = OpenAIResponsesSymptomStructuringClient(
        api_key="test-only-key",
        prompt_version="symptom_structuring/v1",
        model_name="gpt-4o-mini",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "status": "completed",
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {"type": "output_text", "text": "{invalid"}
                                ],
                            }
                        ],
                    },
                )
            )
        ),
    )

    with pytest.raises(LLMOutputValidationError):
        client.structure_symptom(
            SymptomStructuringRequest(raw_symptom="증상이 있습니다"),
            timeout_seconds=1.0,
        )


def test_openai_followup_schema_constrains_target_fields() -> None:
    captured = {}

    def handler(request: httpx.Request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "questions": [
                                            {
                                                "target_field": "occurrence_time",
                                                "question_text": "온수 소음은 언제부터 시작됐나요?",
                                            }
                                        ]
                                    },
                                    ensure_ascii=False,
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    client = OpenAIResponsesFollowUpWordingClient(
        api_key="test-only-key",
        prompt_version="followup_question/v1",
        model_name="gpt-4o-mini",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = client.generate_followup_wording(
        FollowUpWordingRequest(
            structured_symptom=_noise_symptom(occurrence_time=None),
            target_fields=("occurrence_time",),
        ),
        timeout_seconds=1.0,
    )

    schema = captured["payload"]["text"]["format"]["schema"]
    target_schema = schema["$defs"]["FollowUpWording"]["properties"]["target_field"]
    assert target_schema["enum"] == ["occurrence_time"]
    assert response.output.questions[0].target_field == "occurrence_time"


def test_task_clients_follow_active_prompt_and_model_profiles(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")

    symptom_client = OpenAIResponsesSymptomStructuringClient.from_environment()
    followup_client = OpenAIResponsesFollowUpWordingClient.from_environment()

    assert symptom_client.model_name == "gpt-4o-mini"
    assert symptom_client.prompt_version == "symptom_structuring/v1"
    assert followup_client.model_name == "gpt-4o-mini"
    assert followup_client.prompt_version == "followup_question/v1"


def test_pipeline_router_injects_both_natural_language_clients() -> None:
    symptom_client = FakeSymptomClient(StructuredSymptom(symptom_type="기타 증상"))
    followup_client = FakeFollowUpClient()
    result = PipelineRouter(
        search_service=EmptySearchService(),
        symptom_llm_client=symptom_client,
        followup_llm_client=followup_client,
    ).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b711",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b712",
        ai_request_id="ai-req-natural-pipeline",
        state_version=1,
        raw_symptom="상태가 이상합니다",
    )

    assert len(symptom_client.requests) == 1
    assert len(followup_client.requests) == 1
    assert result.context.followup_questions


def test_structuring_and_followup_spans_contain_metadata_not_customer_text(
    monkeypatch,
) -> None:
    structuring_tracer = FakeTracer()
    followup_tracer = FakeTracer()
    monkeypatch.setattr(structurer_module, "_STRUCTURING_TRACER", structuring_tracer)
    monkeypatch.setattr(followup_module, "_FOLLOWUP_TRACER", followup_tracer)
    private_text = "010-1234-5678 private@example.com 온수 소음"
    trace_context = _trace_context()

    symptom = SymptomStructurer(
        llm_client=FakeSymptomClient(_noise_symptom())
    ).structure(
        private_text,
        ["NOISE"],
        trace_context=trace_context,
        model_code="WPU-JAC104",
    )
    FollowUpQuestionGenerator(llm_client=FakeFollowUpClient()).generate(
        [MissingField(field_name="actions_taken", reason="필요", importance="low")],
        symptom=symptom,
        trace_context=trace_context,
        model_code="WPU-JAC104",
    )

    assert [span.name for span in structuring_tracer.spans] == [
        "waterbridge.symptom_structuring.llm",
        "waterbridge.symptom_structuring.validate",
    ]
    assert [span.name for span in followup_tracer.spans] == [
        "waterbridge.followup.generate",
        "waterbridge.followup.validate",
    ]
    serialized = repr(
        [
            span.attributes
            for span in [*structuring_tracer.spans, *followup_tracer.spans]
        ]
    )
    assert private_text not in serialized
    assert "010-1234-5678" not in serialized
    assert "private@example.com" not in serialized
    assert "ai-req-natural-language-001" in serialized


def test_provider_failure_emits_fallback_spans_without_exception_or_payload(
    monkeypatch,
) -> None:
    structuring_tracer = FakeTracer()
    followup_tracer = FakeTracer()
    monkeypatch.setattr(structurer_module, "_STRUCTURING_TRACER", structuring_tracer)
    monkeypatch.setattr(followup_module, "_FOLLOWUP_TRACER", followup_tracer)
    private_text = "010-9876-5432 secret@example.com 냉수 문제"
    trace_context = _trace_context()

    symptom = SymptomStructurer(
        llm_client=FakeSymptomClient(
            error=LLMProviderTimeoutError("private provider detail")
        )
    ).structure(
        private_text,
        trace_context=trace_context,
        model_code="WPU-JAC104",
    )
    FollowUpQuestionGenerator(
        llm_client=FakeFollowUpClient(
            error=LLMProviderConnectionError("private connection detail")
        )
    ).generate(
        [MissingField(field_name="occurrence_time", reason="필요", importance="high")],
        symptom=symptom,
        trace_context=trace_context,
        model_code="WPU-JAC104",
    )

    assert [span.name for span in structuring_tracer.spans] == [
        "waterbridge.symptom_structuring.llm",
        "waterbridge.symptom_structuring.fallback",
    ]
    assert [span.name for span in followup_tracer.spans] == [
        "waterbridge.followup.generate",
        "waterbridge.followup.fallback",
    ]
    fallback_spans = [structuring_tracer.spans[-1], followup_tracer.spans[-1]]
    assert all(span.attributes["fallback.used"] is True for span in fallback_spans)
    serialized = repr([span.attributes for span in fallback_spans])
    for forbidden in (
        private_text,
        "010-9876-5432",
        "secret@example.com",
        "private provider detail",
        "private connection detail",
    ):
        assert forbidden not in serialized
