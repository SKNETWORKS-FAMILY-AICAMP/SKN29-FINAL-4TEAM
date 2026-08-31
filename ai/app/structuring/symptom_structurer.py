"""고객 자연어 증상을 표준 증상 필드로 구조화."""

from __future__ import annotations

import re
import unicodedata

from opentelemetry import trace

from .llm_contracts import (
    ALLOWED_SYMPTOM_TYPES,
    ALLOWED_WATER_TYPES,
    SymptomEvidenceClaim,
    SafetySignals,
    SymptomStructuringLLMClient,
    SymptomStructuringRequest,
)
from ..schemas import StructuredSymptom, TraceContext
from .symptom_normalizer import SymptomNormalizer


_STRUCTURING_TRACER = trace.get_tracer("waterbridge.ai.symptom_structuring", "1.0.0")

_SAFETY_SIGNAL_PATTERNS = {
    "electrical_component_damage": re.compile(
        r"(?:전선|전원선|전원\s*코드|케이블|플러그).{0,12}(?:피복|벗겨|손상|찢어|끊어|파손)"
        r"|(?:피복|손상|찢어|끊어|파손).{0,12}(?:전선|전원선|전원\s*코드|케이블|플러그)"
    ),
    "exposed_wire": re.compile(
        r"(?:구리선|도체).{0,8}(?:노출|보이|드러)"
        r"|(?:전선|전원선|전원\s*코드|케이블).{0,12}(?:피복.{0,6}벗겨|노출|속이\s*보)"
    ),
    "water_near_electrical_part": re.compile(
        r"(?:(?:전선|전원|전기|콘센트|플러그).{0,16}(?:물|누수|젖|고임)"
        r"|(?:물|누수|젖|고임).{0,16}(?:전선|전원|전기|콘센트|플러그))"
    ),
    "smoke_or_burn": re.compile(r"연기|화재|불이\s*남|탄\s*냄새|그을"),
    "shock_or_spark": re.compile(r"감전|스파크|불꽃"),
}
_PRIVATE_ANSWER_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
    re.compile(r"https?://\S+", flags=re.IGNORECASE),
)
_UNSAFE_ANSWER_PATTERN = re.compile(
    r"(?:직접\s*)?(?:분해|수리|배선\s*작업|전기\s*작업|전선을?\s*(?:자르|연결|교체))"
)
_SYMPTOM_EVIDENCE_PATTERNS = {
    "제품 누수": re.compile(
        r"누수|(?:물|냉수|온수|정수|찬물).{0,14}(?:새|흐르|고[여이]|떨어)"
    ),
    "전기 이상": re.compile(
        r"스파크|감전|연기|탄\s*냄새|타는\s*냄새|전원선|전선|콘센트|플러그"
    ),
    "온도 이상": re.compile(
        r"미지근|안\s*차갑|차갑지\s*않|뜨겁지\s*않|온도.{0,8}(?:이상|낮|높)"
    ),
    "출수량 저하": re.compile(
        r"잘\s*안\s*나|안\s*나오|나오지\s*않|약하게\s*나|"
        r"(?:물|출수|수압|양).{0,10}(?:약하|적|줄|낮)|졸졸|쫄쫄"
    ),
    "물맛/냄새 이상": re.compile(
        r"(?:맛|냄새).{0,10}(?:이상|나|역|비리)|흙\s*맛|흙\s*냄새"
    ),
    "소음 이상": re.compile(r"소음|진동|웅웅|덜컹|소리가.{0,8}(?:나|커|이상)"),
    "필터/관리 문의": re.compile(r"필터|교체\s*주기|관리\s*주기"),
}


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
        self.last_safety_signals = SafetySignals()

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
        self.last_safety_signals = SafetySignals()
        pending_safety_signals = SafetySignals()
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
                pending_safety_signals = response.safety_signals
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

            self.last_safety_signals = self._validated_safety_signals(
                pending_safety_signals,
                raw_text=raw_text,
                previous_answers=previous,
            )

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
        validated_selected = self._validated_selected_symptoms(selected)

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
            validated_answer = self._validated_previous_answer(
                target_field,
                answer_text,
            )
            if validated_answer is None:
                continue
            if target_field == "actions_taken":
                if validated_answer not in actions:
                    actions.append(validated_answer)
            else:
                answer_by_field[target_field] = validated_answer

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
            accompanying_symptoms=validated_selected,
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

        rejected_fields: set[str] = set()
        validated_selected = self._validated_selected_symptoms(selected_symptoms)

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
            validated_answer = self._validated_previous_answer(
                target_field,
                answer_text,
            )
            if validated_answer is None:
                continue
            if target_field == "actions_taken":
                previous_actions.append(validated_answer)
            else:
                answer_by_field[target_field] = validated_answer

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
                            [*validated_selected, *accompanying_symptoms]
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
        raw_rule_symptom = (
            self.normalizer.normalize_symptom_type(raw_text, [])
            if field_name == "symptom_type"
            else None
        )
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
            if (
                field_name == "symptom_type"
                and claim.source == "RAW_SYMPTOM"
                and raw_rule_symptom not in {None, "기타 증상", value}
            ):
                # 보수적 Rule이 원문에서 다른 명시 신호를 확인한 경우에는
                # LLM 후보를 fail-closed 처리한다. selected hint 충돌은 여기서
                # 비교하지 않는다.
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
                if self.normalizer.canonical_selected_symptom(item) is not None
            )
        if claim.source == "PREVIOUS_ANSWER":
            return any(
                self._QUESTION_FIELD_MAP.get(str(answer.get("question_id", "")))
                == field_name
                and self._validated_previous_answer(
                    field_name,
                    str(answer.get("answer_text", "")),
                )
                is not None
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
        if field_name == "symptom_type" and source == "RAW_SYMPTOM":
            return self._symptom_type_matches_evidence(value, evidence_quote)
        return False

    def _symptom_type_matches_evidence(
        self,
        value: str,
        evidence_quote: str,
    ) -> bool:
        """Canonical label이 없어도 고객 표현의 의미가 field와 맞는지 확인한다."""

        if not self._has_substantive_symptom_evidence(evidence_quote):
            return False
        rule_value = self.normalizer.normalize_symptom_type(evidence_quote, [])
        if rule_value != "기타 증상":
            return rule_value == value
        if value == "기타 증상":
            return True
        pattern = _SYMPTOM_EVIDENCE_PATTERNS.get(value)
        return pattern is not None and pattern.search(evidence_quote) is not None

    def _validated_previous_answer(
        self,
        field_name: str,
        answer_text: str,
    ) -> str | None:
        """질문 식별자와 field 의미에 맞는 안전한 답변만 반영한다."""

        value = answer_text.strip()
        if (
            not value
            or len(value) > 200
            or "\n" in value
            or any(pattern.search(value) for pattern in _PRIVATE_ANSWER_PATTERNS)
            or _UNSAFE_ANSWER_PATTERN.search(value)
        ):
            return None
        if field_name == "occurrence_time":
            extracted = self.normalizer.extract_occurrence_time(value)
            if extracted is not None or re.search(
                r"오늘|어제|그제|방금|최근|처음|설치.{0,4}(?:직후|후)|"
                r"\d+\s*(?:분|시간|일|주|개월|달|년)\s*(?:전|째|이상|부터)?",
                value,
            ):
                return value
            return None
        if field_name == "target_water_type":
            normalized = self.normalizer.normalize_water_type(value)
            return normalized if normalized in ALLOWED_WATER_TYPES else None
        if field_name == "occurrence_condition":
            return value if re.search(
                r"항상|간헐|가끔|계속|출수|버튼|사용|대기|연속|특정|"
                r"처음|잠시|반복|\b때\b|중(?:에|에도)?|후(?:에|에도)?|전(?:에|부터)?|부터",
                value,
            ) else None
        if field_name == "actions_taken":
            return value if re.search(
                r"없|안\s*함|하지\s*않|아직\s*(?:조치|확인|시도)|"
                r"전원.{0,8}(?:재부팅|껐|켰|확인)|재부팅|"
                r"원수\s*밸브.{0,8}확인|필터.{0,8}(?:확인|청소|교체)|"
                r"(?:출수|온도|소음|제품\s*상태).{0,8}(?:확인|살펴)|"
                r"(?:고객센터|상담).{0,8}문의|점검\s*신청",
                value,
            ) else None
        return None

    def _validated_safety_signals(
        self,
        signals: SafetySignals,
        *,
        raw_text: str,
        previous_answers: list[dict[str, str]],
    ) -> SafetySignals:
        """실제 고객 source에 존재하고 의미가 일치하는 true signal만 유지한다."""

        updates = {
            "electrical_component_damage": False,
            "exposed_wire": False,
            "water_near_electrical_part": False,
            "smoke_or_burn": False,
            "shock_or_spark": False,
        }
        accepted_evidence = []
        for evidence in signals.evidence:
            signal_name = evidence.signal_name
            if not getattr(signals, signal_name):
                continue
            if not self._safety_evidence_source_matches(
                evidence.source,
                evidence.evidence_quote,
                raw_text=raw_text,
                previous_answers=previous_answers,
            ):
                continue
            pattern = _SAFETY_SIGNAL_PATTERNS[signal_name]
            if pattern.search(self._normalize_evidence_text(evidence.evidence_quote)) is None:
                continue
            updates[signal_name] = True
            accepted_evidence.append(evidence)
        return SafetySignals(**updates, evidence=accepted_evidence)

    def _safety_evidence_source_matches(
        self,
        source: str,
        evidence_quote: str,
        *,
        raw_text: str,
        previous_answers: list[dict[str, str]],
    ) -> bool:
        quote = self._normalize_evidence_text(evidence_quote)
        if source == "RAW_SYMPTOM":
            return quote in self._normalize_evidence_text(raw_text)
        if source != "PREVIOUS_ANSWER":
            return False
        return any(
            (target_field := self._QUESTION_FIELD_MAP.get(
                str(answer.get("question_id", ""))
            ))
            and self._validated_previous_answer(
                target_field,
                str(answer.get("answer_text", "")),
            )
            is not None
            and quote in self._normalize_evidence_text(str(answer.get("answer_text", "")))
            for answer in previous_answers
            if isinstance(answer, dict)
        )

    def _validated_selected_symptoms(self, values: list[str]) -> list[str]:
        return list(
            dict.fromkeys(
                value
                for value in values
                if self.normalizer.canonical_selected_symptom(value) is not None
            )
        )

    def _has_substantive_symptom_evidence(self, evidence_quote: str) -> bool:
        """출수명·시점만 인용한 symptom_type 자기주장을 거절한다."""

        normalized = self._normalize_evidence_text(evidence_quote)
        stripped = re.sub(
            r"(?:정수기|냉수|온수|정수|전체|물|오늘|어제|그제|최근|부터|자꾸|계속)",
            " ",
            normalized,
        )
        informative = re.sub(r"[^0-9a-z가-힣]+", "", stripped)
        return len(informative) >= 2

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
