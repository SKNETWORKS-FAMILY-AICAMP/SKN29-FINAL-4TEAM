"""LLM 자연어 구조화·질문 표현의 검증 및 결정적 fallback 테스트."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from uuid import UUID

import httpx
import pytest

import ai.app.structuring.followup_question_generator as followup_module
import ai.app.structuring.symptom_structurer as structurer_module
import ai.app.orchestration.pipeline_router as router_module
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
    MissingFieldChecker,
    SymptomStructurer,
)
from ai.app.structuring.llm_contracts import (
    FollowUpWording,
    FollowUpWordingLLMResponse,
    FollowUpWordingResult,
    FollowUpWordingRequest,
    MissingFieldContext,
    SymptomEvidenceClaim,
    SymptomStructuringResult,
    SymptomStructuringLLMResponse,
    SymptomStructuringRequest,
)


class EmptySearchService:
    def search(self, *args, **kwargs):
        return []


class FakeSymptomClient:
    prompt_version = "symptom_structuring/v1"

    def __init__(
        self,
        output: StructuredSymptom | None = None,
        error=None,
        evidence_claims: list[SymptomEvidenceClaim] | None = None,
    ) -> None:
        self.output = output or StructuredSymptom(symptom_type="기타 증상")
        self.error = error
        self.evidence_claims = tuple(evidence_claims or [])
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
            evidence_claims=self.evidence_claims,
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
            default_questions = {
                "occurrence_time": "증상은 언제부터 시작됐나요?",
                "target_water_type": "어떤 출수에서 증상이 발생하나요?",
                "occurrence_condition": "증상은 어떤 조건에서 발생하나요?",
                "actions_taken": "이미 확인하거나 조치해 본 내용이 있나요?",
            }
            wordings = [
                FollowUpWording(
                    target_field=field,
                    question_text=default_questions[field],
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


def _evidence_claim(
    field_name: str,
    value: str,
    evidence_quote: str,
    source: str = "RAW_SYMPTOM",
) -> SymptomEvidenceClaim:
    return SymptomEvidenceClaim(
        field_name=field_name,
        value=value,
        source=source,
        evidence_quote=evidence_quote,
    )


def test_llm_structures_complex_customer_language() -> None:
    condition = "온수 버튼을 누르고 10초쯤 지나면"
    raw_text = f"{condition} 안쪽에서 진동하며 덜덜거려요. 어제부터입니다."
    candidate = _noise_symptom(occurrence_condition=condition)
    client = FakeSymptomClient(
        candidate,
        evidence_claims=[
            _evidence_claim("symptom_type", "소음 이상", "NOISE", "SELECTED_SYMPTOM"),
            _evidence_claim("occurrence_time", "어제부터", "어제부터"),
            _evidence_claim("target_water_type", "온수", "온수"),
            _evidence_claim("occurrence_condition", condition, condition),
            _evidence_claim("accompanying_symptoms", "진동", "진동"),
        ],
    )
    result = SymptomStructurer(llm_client=client).structure(
        raw_text,
        ["NOISE"],
        trace_context=_trace_context(),
        model_code="WPU-JAC104",
    )

    assert result == candidate.model_copy(
        update={"accompanying_symptoms": ["NOISE", "진동"]}
    )
    assert client.requests[0].selected_symptoms == ("NOISE",)


def test_hallucinated_fields_without_provenance_are_removed_and_questioned() -> None:
    candidate = StructuredSymptom(
        symptom_type="물맛/냄새 이상",
        occurrence_time="어제부터",
        target_water_type="정수",
        occurrence_condition="출수할 때",
        accompanying_symptoms=["이상한 냄새"],
        actions_taken=["필터 확인"],
    )
    result = SymptomStructurer(
        llm_client=FakeSymptomClient(candidate)
    ).structure("물이 이상해요.")

    assert result.symptom_type == "기타 증상"
    assert result.occurrence_time is None
    assert result.target_water_type is None
    assert result.occurrence_condition is None
    assert result.accompanying_symptoms == []
    assert result.actions_taken == []
    assert {
        item.field_name for item in MissingFieldChecker().check(result)
    } == {
        "occurrence_time",
        "target_water_type",
        "occurrence_condition",
        "actions_taken",
    }


def test_only_fields_with_valid_provenance_survive_partial_fallback() -> None:
    candidate = StructuredSymptom(
        symptom_type="소음 이상",
        occurrence_time="어제부터",
        target_water_type="정수",
        occurrence_condition="출수 버튼을 누를 때",
        actions_taken=["필터 확인"],
    )
    result = SymptomStructurer(
        llm_client=FakeSymptomClient(
            candidate,
            evidence_claims=[
                _evidence_claim("symptom_type", "소음 이상", "소음"),
                _evidence_claim("occurrence_time", "어제부터", "어제부터"),
                _evidence_claim("target_water_type", "정수", "정수"),
                _evidence_claim(
                    "occurrence_condition",
                    "출수 버튼을 누를 때",
                    "없는 문장",
                ),
                _evidence_claim("actions_taken", "필터 확인", "없는 조치"),
            ],
        )
    ).structure("정수에서 소음이 어제부터 납니다.")

    assert result.symptom_type == "소음 이상"
    assert result.occurrence_time == "어제부터"
    assert result.target_water_type == "정수"
    assert result.occurrence_condition is None
    assert result.actions_taken == []


def test_previous_answer_evidence_must_match_question_target_field() -> None:
    candidate = StructuredSymptom(
        symptom_type="기타 증상",
        occurrence_time="오늘 아침부터",
    )
    result = SymptomStructurer(
        llm_client=FakeSymptomClient(
            candidate,
            evidence_claims=[
                _evidence_claim(
                    "occurrence_time",
                    "오늘 아침부터",
                    "오늘 아침부터",
                    "PREVIOUS_ANSWER",
                )
            ],
        )
    ).structure(
        "상태가 이상합니다.",
        previous_answers=[
            {
                "question_id": "followup-actions-taken",
                "answer_text": "오늘 아침부터",
            }
        ],
    )

    assert result.occurrence_time is None
    assert result.actions_taken == []


def test_water_type_claim_must_match_evidence_meaning() -> None:
    result = SymptomStructurer(
        llm_client=FakeSymptomClient(
            StructuredSymptom(
                symptom_type="기타 증상",
                target_water_type="냉수",
            ),
            evidence_claims=[
                _evidence_claim("target_water_type", "냉수", "정수"),
            ],
        )
    ).structure("정수에서 문제가 납니다.")

    assert result.target_water_type == "정수"


def test_list_fields_keep_only_items_with_item_level_evidence() -> None:
    result = SymptomStructurer(
        llm_client=FakeSymptomClient(
            StructuredSymptom(
                symptom_type="소음 이상",
                accompanying_symptoms=["진동", "누수"],
                actions_taken=["필터를 확인", "밸브를 확인"],
            ),
            evidence_claims=[
                _evidence_claim("symptom_type", "소음 이상", "소음"),
                _evidence_claim("accompanying_symptoms", "진동", "진동"),
                _evidence_claim("actions_taken", "필터를 확인", "필터를 확인"),
            ],
        )
    ).structure("필터를 확인했고 진동과 소음이 있어요.")

    assert result.accompanying_symptoms == ["진동"]
    assert result.actions_taken == ["필터를 확인"]


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


def test_followup_request_contains_full_runtime_context() -> None:
    client = FakeFollowUpClient()
    missing = MissingField(
        field_name="occurrence_condition",
        reason="소음이 발생하는 동작이나 조건을 확인해야 합니다.",
        importance="high",
    )

    FollowUpQuestionGenerator(llm_client=client).generate(
        [missing],
        symptom=StructuredSymptom(symptom_type="소음 이상"),
        raw_symptom="출수 후에 웅웅거리는 소리가 납니다.",
        selected_symptoms=["NOISE"],
        previous_answers=[
            {
                "question_id": "followup-occurrence-time",
                "answer_text": "어제부터",
            }
        ],
    )

    request = client.requests[0]
    assert request.raw_symptom == "출수 후에 웅웅거리는 소리가 납니다."
    assert request.selected_symptoms == ("NOISE",)
    assert request.previous_answers == (
        {
            "question_id": "followup-occurrence-time",
            "answer_text": "어제부터",
        },
    )
    assert request.missing_field_contexts == (
        MissingFieldContext(
            target_field="occurrence_condition",
            reason=missing.reason,
            importance="high",
        ),
    )


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
    provider_result = SymptomStructuringResult(
        structured_symptom=_noise_symptom(),
        evidence_claims=[
            _evidence_claim("symptom_type", "소음 이상", "소음"),
            _evidence_claim("target_water_type", "온수", "온수"),
        ],
    )

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
                                "text": provider_result.model_dump_json(),
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
    assert schema["$defs"]["StructuredSymptom"]["properties"]["symptom_type"][
        "enum"
    ]
    assert schema["$defs"]["SymptomEvidenceClaim"]["properties"]["source"][
        "enum"
    ] == ["RAW_SYMPTOM", "SELECTED_SYMPTOM", "PREVIOUS_ANSWER"]
    assert "010-1234-5678" not in user_prompt
    assert "user@example.com" not in user_prompt
    assert response.output.symptom_type == "소음 이상"
    assert response.evidence_claims == tuple(provider_result.evidence_claims)


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


def test_openai_symptom_adapter_requires_evidence_claim_contract() -> None:
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
                                    {
                                        "type": "output_text",
                                        "text": _noise_symptom().model_dump_json(),
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
        client.structure_symptom(
            SymptomStructuringRequest(raw_symptom="온수에서 소음이 있습니다"),
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
            raw_symptom=(
                "010-1234-5678 user@example.com으로 연락했고 "
                "아침에만 온수 소음이 납니다."
            ),
            selected_symptoms=("NOISE",),
            previous_answers=(
                {
                    "question_id": "followup-occurrence-condition",
                    "answer_text": "https://private.example 에서 확인 후 어제부터",
                },
            ),
            missing_field_contexts=(
                MissingFieldContext(
                    target_field="occurrence_time",
                    reason="소음 시작 시점 확인",
                    importance="high",
                ),
            ),
        ),
        timeout_seconds=1.0,
    )

    schema = captured["payload"]["text"]["format"]["schema"]
    target_schema = schema["$defs"]["FollowUpWording"]["properties"]["target_field"]
    user_prompt = captured["payload"]["input"][1]["content"]
    assert target_schema["enum"] == ["occurrence_time"]
    assert response.output.questions[0].target_field == "occurrence_time"
    assert "010-1234-5678" not in user_prompt
    assert "user@example.com" not in user_prompt
    assert "https://private.example" not in user_prompt
    assert user_prompt.count("[REDACTED]") == 3
    assert "아침에만 온수 소음이 납니다" in user_prompt
    assert "어제부터" in user_prompt
    assert "NOISE" in user_prompt
    assert "소음 시작 시점 확인" in user_prompt
    assert '"importance": "high"' in user_prompt


def test_followup_provider_payload_preserves_raw_context_difference() -> None:
    captured_prompts = []

    def handler(request: httpx.Request):
        payload = json.loads(request.content)
        captured_prompts.append(payload["input"][1]["content"])
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
                                                "target_field": "occurrence_condition",
                                                "question_text": "온수 증상은 어떤 조건에서 발생하나요?",
                                                "options": [
                                                    "첫 출수에서만 발생",
                                                    "아침 첫 사용 때 주로 발생",
                                                ],
                                                "allow_free_text": True,
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
    common = {
        "structured_symptom": StructuredSymptom(
            symptom_type="온도 이상",
            target_water_type="온수",
        ),
        "target_fields": ("occurrence_condition",),
        "missing_field_contexts": (
            MissingFieldContext(
                target_field="occurrence_condition",
                reason="온도 이상이 지속되는 조건을 확인해야 합니다.",
                importance="medium",
            ),
        ),
    }

    for raw_symptom in (
        "온수가 첫 잔만 미지근하고 두 번째부터 뜨거워요",
        "아침에만 온수가 미지근해요",
    ):
        client.generate_followup_wording(
            FollowUpWordingRequest(raw_symptom=raw_symptom, **common),
            timeout_seconds=1.0,
        )

    assert captured_prompts[0] != captured_prompts[1]
    assert "첫 잔만 미지근" in captured_prompts[0]
    assert "아침에만" in captured_prompts[1]


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
        selected_symptoms=["NOISE"],
        previous_answers=[
            {
                "question_id": "followup-occurrence-time",
                "answer_text": "답변하지 않음",
            }
        ],
    )

    assert len(symptom_client.requests) == 1
    assert len(followup_client.requests) == 1
    assert result.context.followup_questions
    followup_request = followup_client.requests[0]
    assert followup_request.raw_symptom == "상태가 이상합니다"
    assert followup_request.selected_symptoms == ("NOISE",)
    assert followup_request.previous_answers[0]["answer_text"] == "답변하지 않음"
    assert followup_request.missing_field_contexts


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
        llm_client=FakeSymptomClient(
            StructuredSymptom(
                symptom_type="소음 이상",
                target_water_type="온수",
            ),
            evidence_claims=[
                _evidence_claim(
                    "symptom_type",
                    "소음 이상",
                    "NOISE",
                    "SELECTED_SYMPTOM",
                ),
                _evidence_claim("target_water_type", "온수", "온수"),
            ],
        )
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
    caplog,
) -> None:
    structuring_tracer = FakeTracer()
    followup_tracer = FakeTracer()
    monkeypatch.setattr(structurer_module, "_STRUCTURING_TRACER", structuring_tracer)
    monkeypatch.setattr(followup_module, "_FOLLOWUP_TRACER", followup_tracer)
    private_text = "010-9876-5432 secret@example.com 냉수 문제"
    trace_context = _trace_context()

    with caplog.at_level("WARNING", logger="watercare.ai.llm"):
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
            [
                MissingField(
                    field_name="occurrence_time",
                    reason="필요",
                    importance="high",
                )
            ],
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
        assert forbidden not in caplog.text
    assert "llm_symptom_structuring_fallback" in caplog.text
    assert "llm_followup_wording_fallback" in caplog.text
    assert "PROVIDER_TIMEOUT" in caplog.text
    assert "PROVIDER_CONNECTION_ERROR" in caplog.text


def test_missing_provider_configuration_logs_once_per_task(monkeypatch, caplog) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    router_module._LLM_CONFIGURATION_LOGGED.clear()

    with caplog.at_level("WARNING", logger="watercare.ai.llm"):
        PipelineRouter(search_service=None)
        PipelineRouter(search_service=None)

    records = [
        json.loads(record.message)
        for record in caplog.records
        if "llm_client_configuration_fallback" in record.message
    ]
    assert records == [
        {
            "event": "llm_client_configuration_fallback",
            "reason": "OPENAI_API_KEY_MISSING",
            "task": "symptom_structuring",
            "validation_result": "FALLBACK",
        },
        {
            "event": "llm_client_configuration_fallback",
            "reason": "OPENAI_API_KEY_MISSING",
            "task": "followup_question",
            "validation_result": "FALLBACK",
        },
    ]
