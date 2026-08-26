"""구조화된 Runtime 사실을 비식별 Provider 입력과 결정론적 브리프로 변환."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Iterable, Literal

from .context_models import (
    ConsultationContextSynthesisRequest,
    ContextSource,
    ContextSourceKind,
    CounselorContextBrief,
    EvidenceBriefFinding,
    SourcedBriefStatement,
)

if TYPE_CHECKING:
    from ...orchestration.agents.context_synthesis_contracts import (
        ConsultationContextSynthesisInput,
    )


@dataclass(frozen=True, slots=True)
class PreparedContextSynthesis:
    """Provider 호출 전 완성되는 비식별 입력과 안전한 Fallback."""

    request: ConsultationContextSynthesisRequest | None
    sources_by_id: dict[str, ContextSource]
    evidence_chunk_ids_by_source_id: dict[str, str]
    deterministic_brief: CounselorContextBrief
    provider_source_ids: frozenset[str]
    provider_bypass_reason: Literal[
        "DANGER",
        "INPUT_TOO_LARGE",
        "INPUT_NOT_ELIGIBLE",
        "RUNTIME_PRODUCT_NOT_APPROVED",
        "SAFETY_NOT_VERIFIED",
    ] | None


class ContextTextSanitizer:
    """Provider와 상담 브리프에 식별자·내부 실행정보가 남지 않게 한다."""

    _SENSITIVE_LABEL = re.compile(
        r"(?:name|customer|address|phone|email|resident|성명|이름|주소|전화|연락처|메일|주민)",
        flags=re.IGNORECASE,
    )
    _PATTERNS = (
        (
            re.compile(
                r"(?:postgres(?:ql)?|mysql|redis|mongodb(?:\+srv)?|amqp)://\S+",
                flags=re.IGNORECASE,
            ),
            "[REDACTED_DSN]",
        ),
        (
            re.compile(
                r"\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+",
                flags=re.IGNORECASE,
            ),
            "[REDACTED_SECRET]",
        ),
        (
            re.compile(
                r"\b(?:Bearer\s+\S+|AWS_SECRET_ACCESS_KEY\s*(?:[:=]|\s)\s*\S+)",
                flags=re.IGNORECASE,
            ),
            "[REDACTED_SECRET]",
        ),
        (
            re.compile(
                r"\b(?:confidential|private)[-_ ](?:customer|user|member)?"
                r"[-_ ]?(?:name|data|record)\b",
                flags=re.IGNORECASE,
            ),
            "[REDACTED_SENSITIVE]",
        ),
        (
            re.compile(
                r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|"
                r"AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b"
            ),
            "[REDACTED_SECRET]",
        ),
        (
            re.compile(
                r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"
            ),
            "[REDACTED_PHONE]",
        ),
        (
            re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            "[REDACTED_EMAIL]",
        ),
        (
            re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
            "[REDACTED_ID]",
        ),
        (
            re.compile(r"https?://\S+", flags=re.IGNORECASE),
            "[REDACTED_URL]",
        ),
        (
            re.compile(r"(?<!\d)\d{8,}(?!\d)"),
            "[REDACTED_NUMBER]",
        ),
        (
            re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b"),
            "[REDACTED_NETWORK]",
        ),
        (
            re.compile(
                r"(?:서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|"
                r"대전광역시|울산광역시|세종특별자치시|제주특별자치도|"
                r"[가-힣]{2,}도)\s+[가-힣0-9-]+(?:시|군|구)\s+"
                r"[가-힣0-9-]+(?:로|길|동|읍|면)(?:\s+\d+(?:-\d+)?)?"
            ),
            "[REDACTED_ADDRESS]",
        ),
        (
            re.compile(
                r"\b(?:AI_VECTOR_DSN|OPENAI_API_KEY|correlation_id|ai_request_id|"
                r"similarity_score|system_prompt|prompt_version|embedding_vector)\b",
                flags=re.IGNORECASE,
            ),
            "[REDACTED_INTERNAL]",
        ),
    )

    @classmethod
    def sanitize(
        cls,
        value: str,
        *,
        label: str | None = None,
        max_length: int = 2000,
        redact_ambiguous_standalone_name: bool = False,
    ) -> str:
        if label and cls._SENSITIVE_LABEL.search(label):
            return "[REDACTED_SENSITIVE]"
        sanitized = str(value)
        for pattern, replacement in cls._PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        if redact_ambiguous_standalone_name and label not in {
            "symptom_type",
            "target_water_type",
            "error_code",
            "selected_symptom",
            "accompanying_symptom",
        }:
            sanitized = re.sub(
                r"(?<=:\s)(?:김|이|박|최|정|강|조|윤|장|임|한|오|서|신|권|"
                r"황|안|송|류|홍|전|고|문|양|손|배|백|허|유|남|심|노|하|곽|"
                r"성|차|주|우|구|민|진|엄|채|원)[가-힣]{1,3}(?![가-힣])",
                "[REDACTED_NAME]",
                sanitized,
            )
            sanitized = re.sub(
                r"(?<=:\s)[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\s*$",
                "[REDACTED_NAME]",
                sanitized,
            )
        sanitized = re.sub(
            r"(?<![가-힣])[가-힣]{2,4}(?:이|가)?\s+"
            r"(?=\[REDACTED_(?:ADDRESS|PHONE|EMAIL|SECRET|SENSITIVE)\])",
            "[REDACTED_NAME] ",
            sanitized,
        )
        sanitized = re.sub(
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}"
            r"(?=\s+(?:customer|user|member|client))",
            "[REDACTED_NAME]",
            sanitized,
        )
        sanitized = re.sub(
            r"(?<![가-힣])(?:김|이|박|최|정|강|조|윤|장|임|한|오|서|신|권|"
            r"황|안|송|류|홍|전|고|문|양|손|배|백|허|유|남|심|노|하|곽|"
            r"성|차|주|우|구|민|진|엄|채|원)[가-힣]{2}"
            r"(?=\s+(?:고객|회원|사용자|님|씨))",
            "[REDACTED_NAME]",
            sanitized,
        )
        if redact_ambiguous_standalone_name and label not in {
            "symptom_type",
            "target_water_type",
            "error_code",
            "selected_symptom",
            "accompanying_symptom",
        }:
            is_ambiguous_customer_name = re.fullmatch(
                r"(?:김|이|박|최|정|강|조|윤|장|임|한|오|서|신|권|황|안|송|"
                r"류|홍|전|고|문|양|손|배|백|허|유|남|심|노|하|곽|성|차|주|"
                r"우|구|민|진|엄|채|원)[가-힣]{1,3}",
                sanitized,
            ) or re.fullmatch(
                r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}",
                sanitized,
            )
            if is_ambiguous_customer_name:
                sanitized = "[REDACTED_NAME]"
        sanitized = " ".join(sanitized.split()).strip()
        return (sanitized or "[REDACTED_EMPTY]")[:max_length]


class ConsultationContextSynthesizer:
    """LLM에 넘길 최소 Source Registry와 결정론적 상담 브리프를 만든다."""

    MAX_PROVIDER_SOURCES = 120
    MAX_PROVIDER_SOURCE_CHARACTERS = 40_000
    _PROVIDER_CUSTOMER_LABELS = frozenset(
        {
            "symptom_type",
            "target_water_type",
            "error_code",
            "selected_symptom",
            "accompanying_symptom",
        }
    )
    _PROVIDER_SYMPTOM_TYPES = frozenset(
        {
            "제품 누수",
            "전기 이상",
            "온도 이상",
            "출수량 저하",
            "물맛/냄새 이상",
            "소음 이상",
            "필터/관리 문의",
            "기타 증상",
        }
    )
    _PROVIDER_WATER_TYPES = frozenset({"냉수", "온수", "정수", "전체"})
    _PROVIDER_SAFETY_LABELS = frozenset(
        {"안전 판정", "상담 필요 판정", "적용 안전 규칙"}
    )
    _ACTION_OUTCOME_MARKERS = (
        "변화",
        "개선",
        "해결",
        "동일",
        "없음",
        "악화",
        "지속",
        "실패",
        "성공",
        "효과",
        "결과",
    )

    def prepare(
        self,
        synthesis_input: ConsultationContextSynthesisInput,
    ) -> PreparedContextSynthesis:
        sources: list[ContextSource] = []
        evidence_chunk_ids: dict[str, str] = {}

        def add_sources(
            *,
            prefix: str,
            kind: ContextSourceKind,
            items: Iterable[tuple[str, str]],
        ) -> None:
            seen: set[tuple[str, str]] = set()
            for label, raw_text in items:
                text = ContextTextSanitizer.sanitize(
                    raw_text,
                    label=label,
                    redact_ambiguous_standalone_name=kind
                    in {
                        ContextSourceKind.CUSTOMER_REPORTED,
                        ContextSourceKind.QUESTIONNAIRE,
                        ContextSourceKind.ATTEMPTED_ACTION,
                    },
                )
                key = (label, text)
                if key in seen:
                    continue
                seen.add(key)
                source_id = f"{prefix}-{len([s for s in sources if s.source_id.startswith(prefix + '-')]) + 1:03d}"
                sources.append(
                    ContextSource(
                        source_id=source_id,
                        kind=kind,
                        label=ContextTextSanitizer.sanitize(
                            label,
                            max_length=100,
                        ),
                        text=text,
                    )
                )

        add_sources(
            prefix="symptom",
            kind=ContextSourceKind.CUSTOMER_REPORTED,
            items=(
                (fact.field_name, f"{fact.field_name}: {fact.value}")
                for fact in synthesis_input.symptom_facts
            ),
        )
        add_sources(
            prefix="answer",
            kind=ContextSourceKind.QUESTIONNAIRE,
            items=(
                (answer.field_name, f"{answer.field_name}: {answer.answer}")
                for answer in synthesis_input.questionnaire_answers
            ),
        )
        add_sources(
            prefix="attempted",
            kind=ContextSourceKind.ATTEMPTED_ACTION,
            items=(("고객이 이미 수행한 조치", value) for value in synthesis_input.attempted_actions),
        )

        for index, evidence in enumerate(synthesis_input.evidence, start=1):
            source_id = f"evidence-{index:03d}"
            sources.append(
                ContextSource(
                    source_id=source_id,
                    kind=ContextSourceKind.EVIDENCE,
                    label=f"승인 근거 {index}",
                    text=ContextTextSanitizer.sanitize(evidence.summary),
                )
            )
            evidence_chunk_ids[source_id] = evidence.chunk_id

        safety_items: list[tuple[str, str]] = [
            ("안전 판정", f"위험도: {synthesis_input.safety_level}"),
            (
                "상담 필요 판정",
                "상담 필요" if synthesis_input.safety_requires_consultation else "상담 필요 판정 없음",
            ),
        ]
        safety_items.extend(
            ("적용 안전 규칙", rule_id)
            for rule_id in synthesis_input.matched_safety_rule_ids
        )
        safety_items.extend(("안전 참고", value) for value in synthesis_input.safety_notes)
        safety_items.extend(
            ("사용 제한", value) for value in synthesis_input.safety_constraints
        )
        add_sources(
            prefix="safety",
            kind=ContextSourceKind.SAFETY,
            items=safety_items,
        )
        add_sources(
            prefix="unresolved",
            kind=ContextSourceKind.UNRESOLVED,
            items=(("미확인 질문", value) for value in synthesis_input.unresolved_questions),
        )
        add_sources(
            prefix="priority",
            kind=ContextSourceKind.PRIORITY,
            items=(("상담사 우선 확인", value) for value in synthesis_input.consultant_priority_checks),
        )
        add_sources(
            prefix="escalation",
            kind=ContextSourceKind.ESCALATION,
            items=(("상담 이관 사유", synthesis_input.escalation_reason),),
        )

        sources_by_id = {source.source_id: source for source in sources}
        provider_sources = [
            source for source in sources if self._is_provider_eligible(source)
        ]
        provider_source_ids = frozenset(
            source.source_id for source in provider_sources
        )
        deterministic_brief = self._deterministic_brief(
            sources,
            evidence_chunk_ids,
        )
        request = None
        provider_bypass_reason: Literal[
            "DANGER",
            "INPUT_TOO_LARGE",
            "INPUT_NOT_ELIGIBLE",
            "RUNTIME_PRODUCT_NOT_APPROVED",
            "SAFETY_NOT_VERIFIED",
        ] | None = None
        if synthesis_input.safety_level == "danger":
            provider_bypass_reason = "DANGER"
        elif not synthesis_input.runtime_product_approved:
            provider_bypass_reason = "RUNTIME_PRODUCT_NOT_APPROVED"
        elif synthesis_input.safety_level == "unknown":
            provider_bypass_reason = "SAFETY_NOT_VERIFIED"
        elif (
            len(sources) > self.MAX_PROVIDER_SOURCES
            or sum(len(source.text) for source in sources)
            > self.MAX_PROVIDER_SOURCE_CHARACTERS
        ):
            provider_bypass_reason = "INPUT_TOO_LARGE"
        elif not any(
            source.kind == ContextSourceKind.CUSTOMER_REPORTED
            for source in provider_sources
        ):
            provider_bypass_reason = "INPUT_NOT_ELIGIBLE"
        else:
            request = ConsultationContextSynthesisRequest(
                model_code=self._safe_model_code(synthesis_input.model_code),
                product_family=ContextTextSanitizer.sanitize(
                    synthesis_input.product_family,
                    max_length=100,
                ),
                safety_level=synthesis_input.safety_level,
                sources=provider_sources,
            )
        return PreparedContextSynthesis(
            request=request,
            sources_by_id=sources_by_id,
            evidence_chunk_ids_by_source_id=evidence_chunk_ids,
            deterministic_brief=deterministic_brief,
            provider_source_ids=provider_source_ids,
            provider_bypass_reason=provider_bypass_reason,
        )

    @classmethod
    def _is_provider_eligible(cls, source: ContextSource) -> bool:
        if source.kind == ContextSourceKind.CUSTOMER_REPORTED:
            if source.label not in cls._PROVIDER_CUSTOMER_LABELS:
                return False
            value = source.text.split(":", maxsplit=1)[-1].strip()
            if source.label in {"symptom_type", "selected_symptom", "accompanying_symptom"}:
                return value in cls._PROVIDER_SYMPTOM_TYPES
            if source.label == "target_water_type":
                return value in cls._PROVIDER_WATER_TYPES
            if source.label == "error_code":
                return re.fullmatch(r"[A-Z0-9-]{1,30}", value) is not None
            return False
        if source.kind == ContextSourceKind.EVIDENCE:
            return False
        if source.kind == ContextSourceKind.SAFETY:
            return source.label in cls._PROVIDER_SAFETY_LABELS
        return False

    @staticmethod
    def _safe_model_code(value: str) -> str:
        sanitized = ContextTextSanitizer.sanitize(value, max_length=100)
        if re.fullmatch(r"[A-Z0-9-]{1,100}", sanitized) is None:
            return "UNKNOWN_MODEL"
        return sanitized

    @staticmethod
    def _deterministic_brief(
        sources: list[ContextSource],
        evidence_chunk_ids: dict[str, str],
    ) -> CounselorContextBrief:
        by_kind: dict[ContextSourceKind, list[ContextSource]] = {
            kind: [] for kind in ContextSourceKind
        }
        for source in sources:
            by_kind[source.kind].append(source)

        issue_sources = (
            by_kind[ContextSourceKind.CUSTOMER_REPORTED]
            + by_kind[ContextSourceKind.QUESTIONNAIRE]
        )[:3]
        if not issue_sources:
            issue_sources = by_kind[ContextSourceKind.ESCALATION][:1]
        issue_summary = SourcedBriefStatement(
            text=ConsultationContextSynthesizer._bounded_source_join(
                issue_sources
            ),
            source_ids=[source.source_id for source in issue_sources],
        )

        def exact_statements(kinds: set[ContextSourceKind]) -> list[SourcedBriefStatement]:
            return [
                SourcedBriefStatement(
                    text=source.text,
                    source_ids=[source.source_id],
                )
                for source in sources
                if source.kind in kinds
            ]

        evidence_findings = [
            EvidenceBriefFinding(
                text=source.text,
                source_ids=[source.source_id],
                source_chunk_ids=[evidence_chunk_ids[source.source_id]],
            )
            for source in by_kind[ContextSourceKind.EVIDENCE]
        ]
        uncertainty_notes: list[SourcedBriefStatement] = []
        for source in by_kind[ContextSourceKind.ATTEMPTED_ACTION]:
            if not any(
                marker in source.text
                for marker in ConsultationContextSynthesizer._ACTION_OUTCOME_MARKERS
            ):
                uncertainty_notes.append(
                    SourcedBriefStatement(
                        text=f"조치 결과 미확인: {source.text}"[:2000],
                        source_ids=[source.source_id],
                    )
                )
        reported_by_label: dict[str, list[ContextSource]] = {}
        for source in (
            by_kind[ContextSourceKind.CUSTOMER_REPORTED]
            + by_kind[ContextSourceKind.QUESTIONNAIRE]
        ):
            reported_by_label.setdefault(source.label, []).append(source)
        for reported_sources in reported_by_label.values():
            if len({source.text for source in reported_sources}) > 1:
                for start in range(0, len(reported_sources), 20):
                    grouped_sources = reported_sources[start : start + 20]
                    uncertainty_notes.append(
                        SourcedBriefStatement(
                            text=(
                                "상충 정보: "
                                + " / ".join(
                                    source.text for source in grouped_sources
                                )
                            )[:2000],
                            source_ids=[
                                source.source_id for source in grouped_sources
                            ],
                        )
                    )
        if not evidence_findings:
            escalation = by_kind[ContextSourceKind.ESCALATION][0]
            uncertainty_notes.append(
                SourcedBriefStatement(
                    text="승인된 공식 근거가 없어 상담사 확인이 필요합니다.",
                    source_ids=[escalation.source_id],
                )
            )

        return CounselorContextBrief(
            safety_constraints=exact_statements({ContextSourceKind.SAFETY}),
            issue_summary=issue_summary,
            customer_reported_facts=exact_statements(
                {
                    ContextSourceKind.CUSTOMER_REPORTED,
                    ContextSourceKind.QUESTIONNAIRE,
                }
            ),
            attempted_actions_and_outcomes=exact_statements(
                {ContextSourceKind.ATTEMPTED_ACTION}
            ),
            unresolved_questions=exact_statements({ContextSourceKind.UNRESOLVED}),
            evidence_based_findings=evidence_findings,
            consultant_priority_checks=exact_statements({ContextSourceKind.PRIORITY}),
            uncertainty_notes=uncertainty_notes,
        )

    @staticmethod
    def _bounded_source_join(sources: list[ContextSource]) -> str:
        separator = " / "
        available = 2000 - len(separator) * max(0, len(sources) - 1)
        per_source = max(1, available // max(1, len(sources)))
        return separator.join(
            source.text[:per_source] for source in sources
        )[:2000]
