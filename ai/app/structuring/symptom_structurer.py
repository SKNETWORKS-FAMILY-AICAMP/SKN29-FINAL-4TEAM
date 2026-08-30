"""고객 자연어 증상을 표준 증상 필드로 구조화."""

from __future__ import annotations

import re
import unicodedata

from opentelemetry import trace

from .llm_contracts import (
    ALLOWED_SYMPTOM_TYPES,
    ALLOWED_WATER_TYPES,
    SymptomEvidenceClaim,
    SymptomStructuringLLMClient,
    SymptomStructuringRequest,
)
from ..schemas import StructuredSymptom, TraceContext
from .symptom_normalizer import SymptomNormalizer


_STRUCTURING_TRACER = trace.get_tracer("waterbridge.ai.symptom_structuring", "1.0.0")


class SymptomStructurer:
    """원문과 기존 문진 답변을 계약의 StructuredSymptom으로 변환한다."""

    _QUESTION_FIELD_MAP = {
        "followup-occurrence-time": "occurrence_time",
        "followup-target-water-type": "target_water_type",
        "followup-occurrence-condition": "occurrence_condition",
        "followup-actions-taken": "actions_taken",
    }
    _INTENTIONAL_NON_ANSWERS = {
        "답변하지 않음",
        "답변 거절",
        "모름",
        "모르겠음",
        "확인 불가",
    }

    def __init__(
        self,
        normalizer: SymptomNormalizer | None = None,
        llm_client: SymptomStructuringLLMClient | None = None,
    ) -> None:
        self.normalizer = normalizer or SymptomNormalizer()
        self.llm_client = llm_client

    def structure(
        self,
        raw_text: str,
        selected_symptoms: list[str] | None = None,
        previous_answers: list[dict[str, str]] | None = None,
        *,
        trace_context: TraceContext | None = None,
        model_code: str = "",
        timeout_seconds: float = 4.0,
    ) -> StructuredSymptom:
        """LLM candidate를 검증하고 실패 시 기존 Rule 결과를 반환한다."""

        selected = selected_symptoms or []
        previous = previous_answers or []
        fallback = self._structure_with_rules(raw_text, selected, previous)
        prompt_version = str(
            getattr(self.llm_client, "prompt_version", "symptom_structuring/v1")
        )
        with _STRUCTURING_TRACER.start_as_current_span(
            "waterbridge.symptom_structuring.llm"
        ) as span:
            self._set_span_context(
                span,
                trace_context=trace_context,
                model_code=model_code,
                prompt_version=prompt_version,
            )
            if self.llm_client is None:
                span.set_attribute("fallback.used", True)
                span.set_attribute("validation.result", "NOT_CONFIGURED")
                self._record_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=prompt_version,
                    reason="CLIENT_NOT_CONFIGURED",
                )
                return fallback
            try:
                response = self.llm_client.structure_symptom(
                    SymptomStructuringRequest(
                        raw_symptom=raw_text,
                        selected_symptoms=tuple(selected),
                        previous_answers=tuple(previous),
                    ),
                    timeout_seconds=timeout_seconds,
                )
                span.set_attribute("llm.model", response.model_name)
                span.set_attribute("prompt.version", response.prompt_version)
                candidate = response.output
                evidence_claims = response.evidence_claims
            except Exception as exc:
                span.set_attribute("fallback.used", True)
                span.set_attribute("validation.result", "PROVIDER_FAILURE")
                self._record_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=prompt_version,
                    reason=self._fallback_reason(exc),
                )
                return fallback

        with _STRUCTURING_TRACER.start_as_current_span(
            "waterbridge.symptom_structuring.validate"
        ) as span:
            self._set_span_context(
                span,
                trace_context=trace_context,
                model_code=model_code,
                prompt_version=response.prompt_version,
            )
            span.set_attribute("llm.model", response.model_name)
            try:
                accepted, rejected_fields = self._validate_and_merge(
                    candidate,
                    fallback=fallback,
                    raw_text=raw_text,
                    selected_symptoms=selected,
                    previous_answers=previous,
                    evidence_claims=evidence_claims,
                )
            except ValueError:
                span.set_attribute("validation.result", "REJECTED")
                span.set_attribute("fallback.used", True)
                self._record_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=response.prompt_version,
                    reason="DOMAIN_VALIDATION_FAILED",
                    model_name=response.model_name,
                )
                return fallback
            if rejected_fields:
                span.set_attribute(
                    "validation.result",
                    "ACCEPTED_WITH_FIELD_FALLBACK",
                )
                span.set_attribute("fallback.used", True)
                span.set_attribute("fallback.fields", ",".join(rejected_fields))
                self._record_fallback(
                    trace_context=trace_context,
                    model_code=model_code,
                    prompt_version=response.prompt_version,
                    reason="FIELD_PROVENANCE_REJECTED",
                    model_name=response.model_name,
                    fallback_fields=rejected_fields,
                )
            else:
                span.set_attribute("validation.result", "ACCEPTED")
                span.set_attribute("fallback.used", False)

        from ..integrations.llm.token_usage import log_llm_usage

        log_llm_usage(
            event="llm_symptom_structuring_completed",
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

    def _structure_with_rules(
        self,
        raw_text: str,
        selected: list[str],
        previous_answers: list[dict[str, str]],
    ) -> StructuredSymptom:
        answer_by_field: dict[str, str] = {}
        actions = self.normalizer.extract_actions(raw_text)

        for answer in previous_answers:
            if not isinstance(answer, dict):
                continue
            question_id = answer.get("question_id", "")
            answer_text = answer.get("answer_text", "").strip()
            target_field = self._QUESTION_FIELD_MAP.get(question_id)
            if not target_field or not answer_text:
                continue
            if answer_text in self._INTENTIONAL_NON_ANSWERS:
                # 거절·확인 불가를 실제 증상 값으로 저장하지 않되 같은 질문은 반복하지 않는다.
                continue
            if target_field == "actions_taken":
                if answer_text not in actions:
                    actions.append(answer_text)
            else:
                answer_by_field[target_field] = answer_text

        return StructuredSymptom(
            symptom_type=self.normalizer.normalize_symptom_type(raw_text, selected),
            occurrence_time=(
                answer_by_field.get("occurrence_time")
                or self.normalizer.extract_occurrence_time(raw_text)
            ),
            target_water_type=(
                answer_by_field.get("target_water_type")
                or self.normalizer.normalize_water_type(raw_text)
            ),
            occurrence_condition=(
                answer_by_field.get("occurrence_condition")
                or self.normalizer.extract_occurrence_condition(raw_text)
            ),
            error_code=self.normalizer.extract_error_code(raw_text),
            accompanying_symptoms=list(dict.fromkeys(selected)),
            actions_taken=actions,
        )

    def _validate_and_merge(
        self,
        candidate: StructuredSymptom,
        *,
        fallback: StructuredSymptom,
        raw_text: str,
        selected_symptoms: list[str],
        previous_answers: list[dict[str, str]],
        evidence_claims: tuple[SymptomEvidenceClaim, ...],
    ) -> tuple[StructuredSymptom, tuple[str, ...]]:
        if candidate.symptom_type not in ALLOWED_SYMPTOM_TYPES:
            raise ValueError("지원하지 않는 symptom_type입니다.")
        if (
            candidate.target_water_type is not None
            and candidate.target_water_type not in ALLOWED_WATER_TYPES
        ):
            raise ValueError("지원하지 않는 target_water_type입니다.")
        string_values = (
            candidate.symptom_type,
            candidate.occurrence_time,
            candidate.occurrence_condition,
            candidate.error_code,
        )
        if any(
            value is not None and (not value.strip() or len(value) > 500)
            for value in string_values
        ):
            raise ValueError("비어 있거나 지나치게 긴 증상 필드입니다.")
        if any(not item.strip() or len(item) > 500 for item in candidate.accompanying_symptoms):
            raise ValueError("동반 증상 형식이 올바르지 않습니다.")
        if any(not item.strip() or len(item) > 500 for item in candidate.actions_taken):
            raise ValueError("수행 조치 형식이 올바르지 않습니다.")
        if len(candidate.accompanying_symptoms) > 20 or len(candidate.actions_taken) > 20:
            raise ValueError("증상 목록 허용 개수를 초과했습니다.")
        if candidate.error_code is not None and candidate.error_code != fallback.error_code:
            raise ValueError("고객 원문에서 확인되지 않은 error_code입니다.")

        selected_canonical = next(
            (
                normalized
                for value in selected_symptoms
                if (normalized := self.normalizer.canonical_selected_symptom(value))
                not in {None, "기타 증상"}
            ),
            None,
        )
        if selected_canonical is not None and candidate.symptom_type != selected_canonical:
            raise ValueError("선택 증상과 symptom_type이 일치하지 않습니다.")

        rejected_fields: set[str] = set()

        def accepted_scalar(field_name: str, value: str | None, fallback_value):
            if value is None:
                return fallback_value
            if self._has_valid_evidence(
                field_name=field_name,
                value=value,
                claims=evidence_claims,
                raw_text=raw_text,
                selected_symptoms=selected_symptoms,
                previous_answers=previous_answers,
            ):
                return value
            rejected_fields.add(field_name)
            return fallback_value

        symptom_type = accepted_scalar(
            "symptom_type",
            candidate.symptom_type,
            fallback.symptom_type,
        )
        occurrence_time = accepted_scalar(
            "occurrence_time",
            candidate.occurrence_time,
            fallback.occurrence_time,
        )
        target_water_type = accepted_scalar(
            "target_water_type",
            candidate.target_water_type,
            fallback.target_water_type,
        )
        occurrence_condition = accepted_scalar(
            "occurrence_condition",
            candidate.occurrence_condition,
            fallback.occurrence_condition,
        )

        accompanying_symptoms = []
        for item in candidate.accompanying_symptoms:
            if self._has_valid_evidence(
                field_name="accompanying_symptoms",
                value=item,
                claims=evidence_claims,
                raw_text=raw_text,
                selected_symptoms=selected_symptoms,
                previous_answers=previous_answers,
            ):
                accompanying_symptoms.append(item)
            else:
                rejected_fields.add("accompanying_symptoms")

        actions_taken = []
        for item in candidate.actions_taken:
            if self._has_valid_evidence(
                field_name="actions_taken",
                value=item,
                claims=evidence_claims,
                raw_text=raw_text,
                selected_symptoms=selected_symptoms,
                previous_answers=previous_answers,
            ):
                actions_taken.append(item)
            else:
                rejected_fields.add("actions_taken")

        answer_by_field: dict[str, str] = {}
        previous_actions: list[str] = []
        for answer in previous_answers:
            if not isinstance(answer, dict):
                continue
            target_field = self._QUESTION_FIELD_MAP.get(answer.get("question_id", ""))
            answer_text = str(answer.get("answer_text", "")).strip()
            if not target_field or not answer_text or answer_text in self._INTENTIONAL_NON_ANSWERS:
                continue
            if target_field == "actions_taken":
                previous_actions.append(answer_text)
            else:
                answer_by_field[target_field] = answer_text

        return (
            candidate.model_copy(
                update={
                    "symptom_type": symptom_type,
                    "occurrence_time": answer_by_field.get(
                        "occurrence_time", occurrence_time
                    ),
                    "target_water_type": answer_by_field.get(
                        "target_water_type", target_water_type
                    ),
                    "occurrence_condition": answer_by_field.get(
                        "occurrence_condition", occurrence_condition
                    ),
                    "error_code": fallback.error_code,
                    "accompanying_symptoms": list(
                        dict.fromkeys(
                            [*selected_symptoms, *accompanying_symptoms]
                        )
                    ),
                    "actions_taken": list(
                        dict.fromkeys(
                            [
                                *actions_taken,
                                *fallback.actions_taken,
                                *previous_actions,
                            ]
                        )
                    ),
                }
            ),
            tuple(sorted(rejected_fields)),
        )

    def _has_valid_evidence(
        self,
        *,
        field_name: str,
        value: str,
        claims: tuple[SymptomEvidenceClaim, ...],
        raw_text: str,
        selected_symptoms: list[str],
        previous_answers: list[dict[str, str]],
    ) -> bool:
        normalized_value = self._normalize_evidence_text(value)
        for claim in claims:
            if claim.field_name != field_name:
                continue
            if self._normalize_evidence_text(claim.value) != normalized_value:
                continue
            if not self._claim_source_matches(
                claim,
                field_name=field_name,
                raw_text=raw_text,
                selected_symptoms=selected_symptoms,
                previous_answers=previous_answers,
            ):
                continue
            if self._claim_value_matches_evidence(
                field_name,
                value,
                claim.evidence_quote,
                claim.source,
            ):
                return True
        return False

    def _claim_source_matches(
        self,
        claim: SymptomEvidenceClaim,
        *,
        field_name: str,
        raw_text: str,
        selected_symptoms: list[str],
        previous_answers: list[dict[str, str]],
    ) -> bool:
        quote = self._normalize_evidence_text(claim.evidence_quote)
        if claim.source == "RAW_SYMPTOM":
            return quote in self._normalize_evidence_text(raw_text)
        if claim.source == "SELECTED_SYMPTOM":
            if field_name not in {"symptom_type", "accompanying_symptoms"}:
                return False
            return any(
                quote in self._normalize_evidence_text(item)
                for item in selected_symptoms
            )
        if claim.source == "PREVIOUS_ANSWER":
            return any(
                self._QUESTION_FIELD_MAP.get(str(answer.get("question_id", "")))
                == field_name
                and quote
                in self._normalize_evidence_text(
                    str(answer.get("answer_text", ""))
                )
                for answer in previous_answers
                if isinstance(answer, dict)
            )
        return False

    def _claim_value_matches_evidence(
        self,
        field_name: str,
        value: str,
        evidence_quote: str,
        source: str,
    ) -> bool:
        normalized_value = self._normalize_evidence_text(value)
        normalized_quote = self._normalize_evidence_text(evidence_quote)
        if field_name == "target_water_type":
            return self.normalizer.normalize_water_type(evidence_quote) == value
        if field_name == "occurrence_time":
            extracted = self.normalizer.extract_occurrence_time(evidence_quote)
            return (
                normalized_value == normalized_quote
                or (
                    extracted is not None
                    and self._normalize_evidence_text(extracted) == normalized_value
                )
            )
        if field_name == "occurrence_condition":
            return normalized_value == normalized_quote
        if field_name == "error_code":
            return self.normalizer.extract_error_code(evidence_quote) == value
        if field_name == "actions_taken":
            return (
                normalized_value == normalized_quote
                or value in self.normalizer.extract_actions(evidence_quote)
            )
        if field_name == "accompanying_symptoms":
            if normalized_value == normalized_quote:
                return True
            if source == "SELECTED_SYMPTOM":
                return self.normalizer.canonical_selected_symptom(evidence_quote) == value
            return False
        if field_name == "symptom_type" and source == "SELECTED_SYMPTOM":
            return self.normalizer.canonical_selected_symptom(evidence_quote) == value
        return field_name == "symptom_type"

    @staticmethod
    def _normalize_evidence_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return re.sub(r"\s+", " ", normalized).strip()

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
        reason: str,
        model_name: str = "",
        fallback_fields: tuple[str, ...] = (),
    ) -> None:
        with _STRUCTURING_TRACER.start_as_current_span(
            "waterbridge.symptom_structuring.fallback"
        ) as span:
            cls._set_span_context(
                span,
                trace_context=trace_context,
                model_code=model_code,
                prompt_version=prompt_version,
            )
            span.set_attribute("fallback.used", True)
            span.set_attribute("validation.result", reason)
            if fallback_fields:
                span.set_attribute("fallback.fields", ",".join(fallback_fields))

        from ..integrations.llm.token_usage import log_llm_fallback

        log_llm_fallback(
            event="llm_symptom_structuring_fallback",
            correlation_id=(trace_context.correlation_id if trace_context else None),
            ai_request_id=(trace_context.ai_request_id if trace_context else None),
            inquiry_id=(trace_context.inquiry_id if trace_context else None),
            model_code=model_code or None,
            task="symptom_structuring",
            model_name=model_name or None,
            prompt_version=prompt_version,
            reason=reason,
            validation_result=(
                "PARTIAL_FALLBACK" if fallback_fields else "FALLBACK"
            ),
            fallback_fields=",".join(fallback_fields) or None,
        )

    @staticmethod
    def _set_span_context(
        span,
        *,
        trace_context: TraceContext | None,
        model_code: str,
        prompt_version: str,
    ) -> None:
        span.set_attribute("agent.name", "SymptomAnalysisAgent")
        span.set_attribute("prompt.version", prompt_version)
        if model_code:
            span.set_attribute("model_code", model_code)
        if trace_context is not None:
            span.set_attribute("ai.request_id", trace_context.ai_request_id)
            span.set_attribute("inquiry_id", str(trace_context.inquiry_id))
            span.set_attribute("correlation_id", str(trace_context.correlation_id))
