"""누락 정보 확인을 위한 추가 질문 생성."""

from __future__ import annotations

import re

from opentelemetry import trace

from .llm_contracts import (
    FollowUpWording,
    FollowUpWordingLLMClient,
    FollowUpWordingRequest,
)
from ..schemas import FollowUpQuestion, MissingField, StructuredSymptom, TraceContext


_FOLLOWUP_TRACER = trace.get_tracer("waterbridge.ai.followup", "1.0.0")
_PRIVATE_QUESTION_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
    re.compile(r"https?://\S+", flags=re.IGNORECASE),
)


class FollowUpQuestionGenerator:
    """질문 대상은 결정적으로 유지하고 표현만 LLM 후보를 허용한다."""

    _QUESTIONS = {
        "occurrence_time": ("증상은 언제부터 시작됐나요?", ["오늘", "어제", "2~3일 전", "일주일 이상 전"]),
        "target_water_type": ("어떤 출수에서 증상이 발생하나요?", ["냉수", "온수", "정수", "전체"]),
        "occurrence_condition": (
            "증상은 언제 또는 어떤 조건에서 발생하나요?",
            ["항상", "간헐적으로", "출수 버튼을 누를 때", "특정 기능 사용 중"],
        ),
        "actions_taken": (
            "이미 확인하거나 조치해 본 내용이 있나요?",
            ["없음", "전원 재부팅", "원수 밸브 확인", "필터 확인"],
        ),
    }

    def __init__(self, llm_client: FollowUpWordingLLMClient | None = None) -> None:
        self.llm_client = llm_client

    def generate(
        self,
        missing_fields: list[MissingField],
        *,
        symptom: StructuredSymptom | None = None,
        trace_context: TraceContext | None = None,
        model_code: str = "",
        timeout_seconds: float = 4.0,
    ) -> list[FollowUpQuestion]:
        fallback = self._fixed_questions(missing_fields)
        if not fallback:
            return []
        target_fields = tuple(question.target_field for question in fallback)
        prompt_version = str(
            getattr(self.llm_client, "prompt_version", "followup_question/v1")
        )
        with _FOLLOWUP_TRACER.start_as_current_span(
            "waterbridge.followup.generate"
        ) as span:
            self._set_span_context(
                span,
                trace_context=trace_context,
                model_code=model_code,
                prompt_version=prompt_version,
                target_fields=target_fields,
            )
            if self.llm_client is None or symptom is None:
                reason = (
                    "CLIENT_NOT_CONFIGURED"
                    if self.llm_client is None
                    else "STRUCTURED_CONTEXT_MISSING"
                )
                span.set_attribute("fallback.used", True)
                span.set_attribute("validation.result", reason)
                self._record_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=prompt_version,
                    target_fields=target_fields,
                    reason=reason,
                )
                return fallback
            try:
                response = self.llm_client.generate_followup_wording(
                    FollowUpWordingRequest(
                        structured_symptom=symptom,
                        target_fields=target_fields,
                    ),
                    timeout_seconds=timeout_seconds,
                )
                span.set_attribute("llm.model", response.model_name)
                span.set_attribute("prompt.version", response.prompt_version)
            except Exception as exc:
                span.set_attribute("fallback.used", True)
                span.set_attribute("validation.result", "PROVIDER_FAILURE")
                self._record_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=prompt_version,
                    target_fields=target_fields,
                    reason=self._fallback_reason(exc),
                )
                return fallback

        with _FOLLOWUP_TRACER.start_as_current_span(
            "waterbridge.followup.validate"
        ) as span:
            self._set_span_context(
                span,
                trace_context=trace_context,
                model_code=model_code,
                prompt_version=response.prompt_version,
                target_fields=target_fields,
            )
            span.set_attribute("llm.model", response.model_name)
            try:
                accepted = self._apply_wording(
                    fallback,
                    response.output.questions,
                )
            except ValueError:
                span.set_attribute("validation.result", "REJECTED")
                span.set_attribute("fallback.used", True)
                self._record_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=response.prompt_version,
                    target_fields=target_fields,
                    reason="DOMAIN_VALIDATION_FAILED",
                )
                return fallback
            span.set_attribute("validation.result", "ACCEPTED")
            span.set_attribute("fallback.used", False)

        from ..integrations.llm.token_usage import log_llm_usage

        log_llm_usage(
            event="llm_followup_wording_completed",
            correlation_id=(trace_context.correlation_id if trace_context else None),
            ai_request_id=(trace_context.ai_request_id if trace_context else None),
            model_name=response.model_name,
            prompt_version=response.prompt_version,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            latency_ms=response.latency_ms,
            retry_count=0,
        )
        return accepted

    def _fixed_questions(
        self,
        missing_fields: list[MissingField],
    ) -> list[FollowUpQuestion]:
        questions: list[FollowUpQuestion] = []
        for missing in missing_fields:
            definition = self._QUESTIONS.get(missing.field_name)
            if definition is None:
                continue
            question_text, options = definition
            questions.append(
                FollowUpQuestion(
                    question_id=f"followup-{missing.field_name.replace('_', '-')}",
                    question_text=question_text,
                    options=options,
                    target_field=missing.field_name,
                )
            )
        return questions

    @staticmethod
    def _apply_wording(
        fallback: list[FollowUpQuestion],
        wordings: list[FollowUpWording],
    ) -> list[FollowUpQuestion]:
        expected_fields = [question.target_field for question in fallback]
        actual_fields = [wording.target_field for wording in wordings]
        if len(actual_fields) != len(set(actual_fields)):
            raise ValueError("Follow-up target_field가 중복되었습니다.")
        if set(actual_fields) != set(expected_fields):
            raise ValueError("Follow-up target_field 계약이 변경되었습니다.")
        wording_by_field = {item.target_field: item.question_text for item in wordings}
        result: list[FollowUpQuestion] = []
        for fixed in fallback:
            question_text = wording_by_field[fixed.target_field].strip()
            if (
                len(question_text) > 200
                or "\n" in question_text
                or not question_text.endswith(("?", "？"))
                or any(pattern.search(question_text) for pattern in _PRIVATE_QUESTION_PATTERNS)
            ):
                raise ValueError("Follow-up 질문 문구 형식이 올바르지 않습니다.")
            result.append(
                fixed.model_copy(update={"question_text": question_text})
            )
        return result

    @staticmethod
    def _fallback_reason(exc: Exception) -> str:
        if isinstance(exc, TimeoutError):
            return "PROVIDER_TIMEOUT"
        if isinstance(exc, ConnectionError):
            return "PROVIDER_CONNECTION_ERROR"
        if isinstance(exc, ValueError):
            return "OUTPUT_VALIDATION_FAILED"
        return "PROVIDER_FAILURE"

    @classmethod
    def _record_fallback(
        cls,
        *,
        trace_context: TraceContext | None,
        model_code: str,
        prompt_version: str,
        target_fields: tuple[str, ...],
        reason: str,
    ) -> None:
        with _FOLLOWUP_TRACER.start_as_current_span(
            "waterbridge.followup.fallback"
        ) as span:
            cls._set_span_context(
                span,
                trace_context=trace_context,
                model_code=model_code,
                prompt_version=prompt_version,
                target_fields=target_fields,
            )
            span.set_attribute("fallback.used", True)
            span.set_attribute("validation.result", reason)

    @staticmethod
    def _set_span_context(
        span,
        *,
        trace_context: TraceContext | None,
        model_code: str,
        prompt_version: str,
        target_fields: tuple[str, ...],
    ) -> None:
        span.set_attribute("agent.name", "SymptomAnalysisAgent")
        span.set_attribute("prompt.version", prompt_version)
        span.set_attribute("target_field", ",".join(target_fields))
        if model_code:
            span.set_attribute("model_code", model_code)
        if trace_context is not None:
            span.set_attribute("ai.request_id", trace_context.ai_request_id)
            span.set_attribute("inquiry_id", str(trace_context.inquiry_id))
            span.set_attribute("correlation_id", str(trace_context.correlation_id))
