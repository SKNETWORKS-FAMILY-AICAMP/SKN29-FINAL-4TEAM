"""누락 정보 확인을 위한 추가 질문 생성."""

from __future__ import annotations

import re
from dataclasses import dataclass

from opentelemetry import trace

from .llm_contracts import (
    FollowUpWording,
    FollowUpWordingLLMClient,
    FollowUpWordingRequest,
    MissingFieldContext,
)
from ..schemas import FollowUpQuestion, MissingField, StructuredSymptom, TraceContext


_FOLLOWUP_TRACER = trace.get_tracer("waterbridge.ai.followup", "1.0.0")
_PRIVATE_QUESTION_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
    re.compile(r"https?://\S+", flags=re.IGNORECASE),
)
_UNSAFE_OPTION_PATTERN = re.compile(
    r"(?:직접\s*)?(?:분해|수리|배선\s*작업|전기\s*작업|전선을?\s*(?:자르|연결|교체))"
)
_DIAGNOSIS_OPTION_PATTERN = re.compile(
    r"(?:원인|고장|불량|누전).{0,8}(?:확정|분명|때문|입니다|이다)"
)
_DYNAMIC_OPTION_MARKERS = {
    "occurrence_time": re.compile(
        r"오늘|어제|그제|방금|최근|처음|직후|\d+\s*(?:분|시간|일|주|개월|달|년)"
    ),
    "occurrence_condition": re.compile(
        r"항상|간헐|가끔|계속|출수|버튼|사용|대기|연속|특정|처음|잠시|반복|때|중|후|전|부터"
    ),
    "actions_taken": re.compile(
        r"없|안\s*함|하지\s*않|아직|확인|재부팅|껐|켰|청소|교체|문의|점검|살펴|시도|해\s*봄|해봤"
    ),
}

_QUESTION_INTENT_MARKERS = {
    "occurrence_time": ("언제", "시작", "부터", "시점", "기간"),
    "target_water_type": ("어떤 출수", "어느 출수", "냉수", "온수", "정수", "전체 출수"),
    "occurrence_condition": (
        "어떤 조건",
        "특정 조건",
        "항상",
        "간헐",
        "반복",
        "경우",
        "상황",
        "양상",
        "패턴",
        "첫 잔",
        "다음 잔",
        "버튼을 누를 때",
    ),
    "actions_taken": ("조치", "확인", "해보", "해 보", "시도", "취하", "무엇을 했"),
}


@dataclass(frozen=True, slots=True)
class FollowUpValidationResult:
    questions: list[FollowUpQuestion]
    fallback_fields: tuple[str, ...]
    rejection_reasons: dict[str, str]


class _FollowUpFieldValidationError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


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
        raw_symptom: str = "",
        selected_symptoms: list[str] | None = None,
        previous_answers: list[dict[str, str]] | None = None,
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
                        raw_symptom=raw_symptom,
                        selected_symptoms=tuple(selected_symptoms or ()),
                        previous_answers=tuple(
                            {
                                "question_id": str(answer.get("question_id", "")),
                                "answer_text": str(answer.get("answer_text", "")),
                            }
                            for answer in (previous_answers or ())
                            if isinstance(answer, dict)
                        ),
                        missing_field_contexts=tuple(
                            MissingFieldContext(
                                target_field=missing.field_name,
                                reason=missing.reason,
                                importance=missing.importance,
                            )
                            for missing in missing_fields
                            if missing.field_name in target_fields
                        ),
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
            validation = self._validate_wordings(
                fallback,
                response.output.questions,
                symptom=symptom,
            )
            accepted = validation.questions
            for field_name in validation.fallback_fields:
                self._record_field_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=response.prompt_version,
                    target_field=field_name,
                    validation_reason=validation.rejection_reasons[field_name],
                    model_name=response.model_name,
                )
            if validation.fallback_fields:
                all_fields_rejected = len(validation.fallback_fields) == len(fallback)
                span.set_attribute(
                    "validation.result",
                    "REJECTED" if all_fields_rejected else "ACCEPTED_WITH_FIELD_FALLBACK",
                )
                span.set_attribute("fallback.used", True)
                span.set_attribute(
                    "fallback.fields",
                    ",".join(validation.fallback_fields),
                )
                if all_fields_rejected:
                    self._record_fallback(
                        trace_context=trace_context,
                        model_code=model_code,
                        prompt_version=response.prompt_version,
                        target_fields=target_fields,
                        reason="DOMAIN_VALIDATION_FAILED",
                        model_name=response.model_name,
                    )
            else:
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
        *,
        symptom: StructuredSymptom | None = None,
    ) -> list[FollowUpQuestion]:
        return FollowUpQuestionGenerator._validate_wordings(
            fallback,
            wordings,
            symptom=symptom,
        ).questions

    @staticmethod
    def _validate_wordings(
        fallback: list[FollowUpQuestion],
        wordings: list[FollowUpWording],
        *,
        symptom: StructuredSymptom | None = None,
    ) -> FollowUpValidationResult:
        wordings_by_field: dict[str, list[FollowUpWording]] = {}
        for wording in wordings:
            wordings_by_field.setdefault(wording.target_field, []).append(wording)
        result: list[FollowUpQuestion] = []
        fallback_fields: list[str] = []
        rejection_reasons: dict[str, str] = {}
        for fixed in fallback:
            candidates = wordings_by_field.get(fixed.target_field, [])
            if len(candidates) != 1:
                fallback_fields.append(fixed.target_field)
                rejection_reasons[fixed.target_field] = "TARGET_FIELD_MISMATCH"
                result.append(fixed)
                continue
            try:
                result.append(
                    FollowUpQuestionGenerator._validate_one_wording(
                        fixed,
                        candidates[0],
                        symptom=symptom,
                    )
                )
            except _FollowUpFieldValidationError as exc:
                fallback_fields.append(fixed.target_field)
                rejection_reasons[fixed.target_field] = exc.reason
                result.append(fixed)
        return FollowUpValidationResult(
            questions=result,
            fallback_fields=tuple(fallback_fields),
            rejection_reasons=rejection_reasons,
        )

    @staticmethod
    def _validate_one_wording(
        fixed: FollowUpQuestion,
        wording: FollowUpWording,
        *,
        symptom: StructuredSymptom | None,
    ) -> FollowUpQuestion:
        question_text = wording.question_text.strip()
        if wording.allow_free_text and fixed.target_field not in {
            "occurrence_time",
            "occurrence_condition",
            "actions_taken",
        }:
            raise _FollowUpFieldValidationError(
                "FREE_TEXT_NOT_ALLOWED",
                "Closed-domain 질문은 자유 입력을 허용할 수 없습니다.",
            )
        if any(pattern.search(question_text) for pattern in _PRIVATE_QUESTION_PATTERNS):
            raise _FollowUpFieldValidationError(
                "PII_DETECTED",
                "Follow-up 질문에 개인정보 형식이 포함되었습니다.",
            )
        if (
            len(question_text) > 200
            or "\n" in question_text
            or not question_text.endswith(("?", "？"))
        ):
            raise _FollowUpFieldValidationError(
                "QUESTION_FORMAT_INVALID",
                "Follow-up 질문 문구 형식이 올바르지 않습니다.",
            )
        if not FollowUpQuestionGenerator._question_matches_target_field(
            fixed.target_field,
            question_text,
        ):
            raise _FollowUpFieldValidationError(
                "QUESTION_INTENT_MISMATCH",
                "Follow-up 질문 의미가 target_field와 일치하지 않습니다.",
            )
        options = FollowUpQuestionGenerator._validated_options(
            target_field=fixed.target_field,
            options=wording.options,
            fallback_options=fixed.options,
            symptom=symptom,
        )
        return fixed.model_copy(
            update={
                "question_text": question_text,
                "options": options,
            }
        )

    @staticmethod
    def _validated_options(
        *,
        target_field: str,
        options: list[str],
        fallback_options: list[str],
        symptom: StructuredSymptom | None,
    ) -> list[str]:
        # 이전 내부 client와의 호환을 위해 options 미제공은 고정 선택지를 쓴다.
        if not options:
            return fallback_options
        normalized = [" ".join(option.split()) for option in options]
        if not 2 <= len(normalized) <= 5:
            raise _FollowUpFieldValidationError(
                "OPTION_FORMAT_INVALID",
                "Follow-up 선택지는 2~5개여야 합니다.",
            )
        if any(not option or len(option) > 80 or "\n" in option for option in normalized):
            raise _FollowUpFieldValidationError(
                "OPTION_FORMAT_INVALID",
                "Follow-up 선택지 길이 또는 형식이 올바르지 않습니다.",
            )
        if len({option.casefold() for option in normalized}) != len(normalized):
            raise _FollowUpFieldValidationError(
                "OPTION_DUPLICATE",
                "Follow-up 선택지가 중복되었습니다.",
            )
        if any(
            any(pattern.search(option) for pattern in _PRIVATE_QUESTION_PATTERNS)
            for option in normalized
        ):
            raise _FollowUpFieldValidationError(
                "PII_DETECTED",
                "Follow-up 선택지에 개인정보 형식이 포함되었습니다.",
            )
        if any(_UNSAFE_OPTION_PATTERN.search(option) for option in normalized):
            raise _FollowUpFieldValidationError(
                "UNSAFE_OPTION",
                "Follow-up 선택지에 직접 수리 또는 전기 작업이 포함되었습니다.",
            )
        if any(_DIAGNOSIS_OPTION_PATTERN.search(option) for option in normalized):
            raise _FollowUpFieldValidationError(
                "DIAGNOSIS_OPTION",
                "Follow-up 선택지에 확정 진단이 포함되었습니다.",
            )
        if any(option.endswith(("?", "？")) for option in normalized):
            raise _FollowUpFieldValidationError(
                "OPTION_FORMAT_INVALID",
                "Follow-up 선택지는 질문 문장일 수 없습니다.",
            )

        if target_field == "target_water_type":
            if normalized != ["냉수", "온수", "정수", "전체"]:
                raise _FollowUpFieldValidationError(
                    "CANONICAL_OPTION_MISMATCH",
                    "Closed-domain 선택지가 변경되었습니다.",
                )
            return normalized

        if target_field not in _DYNAMIC_OPTION_MARKERS:
            raise _FollowUpFieldValidationError(
                "OPTION_INTENT_MISMATCH",
                "지원하지 않는 Follow-up target_field입니다.",
            )
        if not FollowUpQuestionGenerator._options_match_target_field(
            target_field,
            normalized,
        ):
            raise _FollowUpFieldValidationError(
                "OPTION_INTENT_MISMATCH",
                "Follow-up 선택지가 target_field 의미와 맞지 않습니다.",
            )
        if not FollowUpQuestionGenerator._options_match_symptom(normalized, symptom):
            raise _FollowUpFieldValidationError(
                "OPTION_CONTEXT_MISMATCH",
                "Follow-up 선택지가 현재 증상 맥락과 맞지 않습니다.",
            )
        return normalized

    @staticmethod
    def _options_match_target_field(
        target_field: str,
        options: list[str],
    ) -> bool:
        joined = " ".join(options)
        water_options = {"냉수", "온수", "정수", "전체"}
        if set(options).issubset(water_options):
            return False
        time_marker = _DYNAMIC_OPTION_MARKERS["occurrence_time"]
        condition_marker = _DYNAMIC_OPTION_MARKERS["occurrence_condition"]
        action_marker = _DYNAMIC_OPTION_MARKERS["actions_taken"]
        if target_field == "occurrence_time":
            return not (
                condition_marker.search(joined)
                and time_marker.search(joined) is None
            )
        if target_field == "occurrence_condition":
            return not (
                all(time_marker.search(option) for option in options)
                and condition_marker.search(joined) is None
            )
        if target_field == "actions_taken":
            return not (
                action_marker.search(joined) is None
                and condition_marker.search(joined) is not None
            )
        return False

    @staticmethod
    def _options_match_symptom(
        options: list[str],
        symptom: StructuredSymptom | None,
    ) -> bool:
        if symptom is None:
            return True
        joined = " ".join(options)
        if symptom.target_water_type == "온수" and "냉수" in joined and "온수" not in joined:
            return False
        if symptom.target_water_type == "냉수" and "온수" in joined and "냉수" not in joined:
            return False
        incompatible_markers = {
            "소음 이상": ("미지근", "차갑", "온도"),
            "온도 이상": ("웅웅", "소음", "소리가"),
        }
        return not any(
            marker in joined
            for marker in incompatible_markers.get(symptom.symptom_type, ())
        )

    @staticmethod
    def _question_matches_target_field(
        target_field: str,
        question_text: str,
    ) -> bool:
        markers = _QUESTION_INTENT_MARKERS.get(target_field)
        if markers is None:
            return False
        compact = " ".join(question_text.split())
        if re.search(r"\b(?:occurrence_time|target_water_type|occurrence_condition|actions_taken)\b", compact):
            return False
        if not any(token in compact for token in markers):
            return False
        if target_field == "occurrence_condition":
            time_only = any(token in compact for token in ("언제", "부터", "시작"))
            condition_intent = any(token in compact for token in markers)
            if time_only and not condition_intent:
                return False
        return True

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
        model_name: str = "",
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

        from ..integrations.llm.token_usage import log_llm_fallback

        log_llm_fallback(
            event="llm_followup_wording_fallback",
            correlation_id=(trace_context.correlation_id if trace_context else None),
            ai_request_id=(trace_context.ai_request_id if trace_context else None),
            inquiry_id=(trace_context.inquiry_id if trace_context else None),
            model_code=model_code or None,
            task="followup_question",
            model_name=model_name or None,
            prompt_version=prompt_version,
            reason=reason,
            validation_result="FALLBACK",
            target_field=",".join(target_fields),
        )

    @classmethod
    def _record_field_fallback(
        cls,
        *,
        trace_context: TraceContext | None,
        model_code: str,
        prompt_version: str,
        target_field: str,
        validation_reason: str,
        model_name: str,
    ) -> None:
        with _FOLLOWUP_TRACER.start_as_current_span(
            "waterbridge.followup.field_fallback"
        ) as span:
            cls._set_span_context(
                span,
                trace_context=trace_context,
                model_code=model_code,
                prompt_version=prompt_version,
                target_fields=(target_field,),
            )
            span.set_attribute("fallback.used", True)
            span.set_attribute("validation.result", validation_reason)

        from ..integrations.llm.token_usage import log_llm_fallback

        log_llm_fallback(
            event="llm_followup_wording_field_fallback",
            correlation_id=(trace_context.correlation_id if trace_context else None),
            ai_request_id=(trace_context.ai_request_id if trace_context else None),
            inquiry_id=(trace_context.inquiry_id if trace_context else None),
            model_code=model_code or None,
            task="followup_question",
            model_name=model_name,
            prompt_version=prompt_version,
            reason=validation_reason,
            validation_reason=validation_reason,
            validation_result="FIELD_FALLBACK",
            target_field=target_field,
        )

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
