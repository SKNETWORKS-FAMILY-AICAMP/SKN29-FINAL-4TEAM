"""Source ID 선택 결과를 추출형 상담 브리프로 조립."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from ...generation.consultation_summary.context_models import (
    ConsultationContextSynthesisCandidate,
    ContextSource,
    ContextSourceGroup,
    ContextSourceKind,
    CounselorContextBrief,
    EvidenceBriefFinding,
    SourcedBriefStatement,
)


class ContextBriefValidationError(ValueError):
    """합성 결과가 출처·범주·완전성 계약을 충족하지 못했다."""


class CounselorContextBriefValidator:
    """LLM에는 Source의 선택·순서·그룹만 허용하고 문장은 입력에서 추출한다."""

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

    def validate_and_build(
        self,
        *,
        candidate: ConsultationContextSynthesisCandidate,
        sources_by_id: dict[str, ContextSource],
        evidence_chunk_ids_by_source_id: dict[str, str],
        provider_source_ids: frozenset[str],
    ) -> CounselorContextBrief:
        if not sources_by_id:
            raise ContextBriefValidationError("합성 결과를 검증할 Source가 없습니다.")

        if not provider_source_ids.issubset(sources_by_id):
            raise ContextBriefValidationError(
                "Provider Source Registry가 내부 Source Registry와 일치하지 않습니다."
            )
        provider_sources_by_id = {
            source_id: sources_by_id[source_id]
            for source_id in provider_source_ids
        }
        category_ids = {
            kind: {
                source_id
                for source_id, source in provider_sources_by_id.items()
                if source.kind == kind
            }
            for kind in ContextSourceKind
        }
        reported_ids = (
            category_ids[ContextSourceKind.CUSTOMER_REPORTED]
            | category_ids[ContextSourceKind.QUESTIONNAIRE]
        )
        self._require_exact_coverage(
            "customer_reported_fact_ids",
            candidate.customer_reported_fact_ids,
            reported_ids,
        )
        self._require_exact_coverage(
            "attempted_action_ids",
            candidate.attempted_action_ids,
            category_ids[ContextSourceKind.ATTEMPTED_ACTION],
        )
        self._require_exact_coverage(
            "unresolved_question_ids",
            candidate.unresolved_question_ids,
            category_ids[ContextSourceKind.UNRESOLVED],
        )
        self._require_exact_coverage(
            "safety_constraint_ids",
            candidate.safety_constraint_ids,
            category_ids[ContextSourceKind.SAFETY],
        )
        self._require_exact_coverage(
            "consultant_priority_check_ids",
            candidate.consultant_priority_check_ids,
            category_ids[ContextSourceKind.PRIORITY],
        )

        self._validate_group_ids(
            candidate.issue_summary_source_ids,
            sources_by_id=provider_sources_by_id,
            allowed_kinds={
                ContextSourceKind.CUSTOMER_REPORTED,
                ContextSourceKind.QUESTIONNAIRE,
                ContextSourceKind.UNRESOLVED,
                ContextSourceKind.ESCALATION,
            },
        )
        evidence_ids: list[str] = []
        for group in candidate.evidence_finding_source_groups:
            self._validate_group(
                group,
                sources_by_id=provider_sources_by_id,
                allowed_kinds={ContextSourceKind.EVIDENCE},
            )
            evidence_ids.extend(group.source_ids)
        self._require_exact_coverage(
            "evidence_finding_source_groups",
            evidence_ids,
            category_ids[ContextSourceKind.EVIDENCE],
        )
        for group in candidate.uncertainty_source_groups:
            self._validate_group(
                group,
                sources_by_id=provider_sources_by_id,
                allowed_kinds={
                    ContextSourceKind.CUSTOMER_REPORTED,
                    ContextSourceKind.QUESTIONNAIRE,
                    ContextSourceKind.ATTEMPTED_ACTION,
                    ContextSourceKind.UNRESOLVED,
                    ContextSourceKind.ESCALATION,
                },
            )

        uncertainty_notes = [
            self._materialize_group(group.source_ids, sources_by_id)
            for group in candidate.uncertainty_source_groups
        ]
        uncertainty_notes.extend(
            self._deterministic_uncertainty_notes(sources_by_id)
        )
        internal_evidence_ids = {
            source_id
            for source_id, source in sources_by_id.items()
            if source.kind == ContextSourceKind.EVIDENCE
        }
        if not internal_evidence_ids:
            escalation_id = next(
                source_id
                for source_id, source in sources_by_id.items()
                if source.kind == ContextSourceKind.ESCALATION
            )
            uncertainty_notes.append(
                SourcedBriefStatement(
                    text="승인된 공식 근거가 없어 상담사 확인이 필요합니다.",
                    source_ids=[escalation_id],
                )
            )

        evidence_findings = [
            EvidenceBriefFinding(
                text=self._join_source_texts(group.source_ids, sources_by_id),
                source_ids=group.source_ids,
                source_chunk_ids=[
                    evidence_chunk_ids_by_source_id[source_id]
                    for source_id in group.source_ids
                ],
            )
            for group in candidate.evidence_finding_source_groups
        ]
        selected_evidence_ids = {
            source_id
            for finding in evidence_findings
            for source_id in finding.source_ids
        }
        evidence_findings.extend(
            EvidenceBriefFinding(
                text=source.text,
                source_ids=[source_id],
                source_chunk_ids=[evidence_chunk_ids_by_source_id[source_id]],
            )
            for source_id, source in sources_by_id.items()
            if source.kind == ContextSourceKind.EVIDENCE
            and source_id not in selected_evidence_ids
        )

        return CounselorContextBrief(
            safety_constraints=self._resolve_exact(
                self._merge_with_internal_ids(
                    candidate.safety_constraint_ids,
                    {ContextSourceKind.SAFETY},
                    sources_by_id,
                ),
                sources_by_id,
            ),
            issue_summary=self._materialize_group(
                candidate.issue_summary_source_ids,
                sources_by_id,
            ),
            customer_reported_facts=self._resolve_exact(
                self._merge_with_internal_ids(
                    candidate.customer_reported_fact_ids,
                    {
                        ContextSourceKind.CUSTOMER_REPORTED,
                        ContextSourceKind.QUESTIONNAIRE,
                    },
                    sources_by_id,
                ),
                sources_by_id,
            ),
            attempted_actions_and_outcomes=self._resolve_exact(
                self._merge_with_internal_ids(
                    candidate.attempted_action_ids,
                    {ContextSourceKind.ATTEMPTED_ACTION},
                    sources_by_id,
                ),
                sources_by_id,
            ),
            unresolved_questions=self._resolve_exact(
                self._merge_with_internal_ids(
                    candidate.unresolved_question_ids,
                    {ContextSourceKind.UNRESOLVED},
                    sources_by_id,
                ),
                sources_by_id,
            ),
            evidence_based_findings=evidence_findings,
            consultant_priority_checks=self._resolve_exact(
                self._merge_with_internal_ids(
                    candidate.consultant_priority_check_ids,
                    {ContextSourceKind.PRIORITY},
                    sources_by_id,
                ),
                sources_by_id,
            ),
            uncertainty_notes=self._stable_unique_statements(uncertainty_notes),
        )

    @staticmethod
    def _validate_group(
        group: ContextSourceGroup,
        *,
        sources_by_id: dict[str, ContextSource],
        allowed_kinds: set[ContextSourceKind],
    ) -> None:
        CounselorContextBriefValidator._validate_group_ids(
            group.source_ids,
            sources_by_id=sources_by_id,
            allowed_kinds=allowed_kinds,
        )

    @staticmethod
    def _validate_group_ids(
        source_ids: Iterable[str],
        *,
        sources_by_id: dict[str, ContextSource],
        allowed_kinds: set[ContextSourceKind],
    ) -> None:
        selected = list(source_ids)
        if len(selected) != len(set(selected)):
            raise ContextBriefValidationError("Source Group에 중복 ID가 있습니다.")
        unknown_ids = set(selected).difference(sources_by_id)
        if unknown_ids:
            raise ContextBriefValidationError(
                "합성 결과가 알 수 없는 Source를 인용했습니다."
            )
        if any(
            sources_by_id[source_id].kind not in allowed_kinds
            for source_id in selected
        ):
            raise ContextBriefValidationError(
                "합성 결과가 허용되지 않은 종류의 Source를 그룹화했습니다."
            )

    @staticmethod
    def _require_exact_coverage(
        field_name: str,
        selected_ids: Iterable[str],
        expected_ids: set[str],
    ) -> None:
        selected = list(selected_ids)
        if len(selected) != len(set(selected)):
            raise ContextBriefValidationError(
                f"{field_name}에 중복 Source가 포함되었습니다."
            )
        if set(selected) != expected_ids:
            raise ContextBriefValidationError(
                f"{field_name}가 입력 Source를 누락하거나 추가했습니다."
            )

    @staticmethod
    def _resolve_exact(
        source_ids: Iterable[str],
        sources_by_id: dict[str, ContextSource],
    ) -> list[SourcedBriefStatement]:
        return [
            SourcedBriefStatement(
                text=sources_by_id[source_id].text,
                source_ids=[source_id],
            )
            for source_id in source_ids
        ]

    @staticmethod
    def _merge_with_internal_ids(
        selected_ids: Iterable[str],
        kinds: set[ContextSourceKind],
        sources_by_id: dict[str, ContextSource],
    ) -> list[str]:
        merged = list(selected_ids)
        selected = set(merged)
        merged.extend(
            source_id
            for source_id, source in sources_by_id.items()
            if source.kind in kinds and source_id not in selected
        )
        return merged

    @staticmethod
    def _materialize_group(
        source_ids: Iterable[str],
        sources_by_id: dict[str, ContextSource],
    ) -> SourcedBriefStatement:
        selected = list(source_ids)
        return SourcedBriefStatement(
            text=CounselorContextBriefValidator._join_source_texts(
                selected,
                sources_by_id,
            ),
            source_ids=selected,
        )

    @staticmethod
    def _join_source_texts(
        source_ids: Iterable[str],
        sources_by_id: dict[str, ContextSource],
    ) -> str:
        selected = list(source_ids)
        separator = " / "
        available = 2000 - len(separator) * max(0, len(selected) - 1)
        per_source = max(1, available // max(1, len(selected)))
        return separator.join(
            sources_by_id[source_id].text[:per_source]
            for source_id in selected
        )[:2000]

    def _deterministic_uncertainty_notes(
        self,
        sources_by_id: dict[str, ContextSource],
    ) -> list[SourcedBriefStatement]:
        notes: list[SourcedBriefStatement] = []
        reported_by_label: dict[str, list[ContextSource]] = defaultdict(list)
        for source in sources_by_id.values():
            if source.kind in {
                ContextSourceKind.CUSTOMER_REPORTED,
                ContextSourceKind.QUESTIONNAIRE,
            }:
                reported_by_label[source.label].append(source)
            if (
                source.kind == ContextSourceKind.ATTEMPTED_ACTION
                and not any(
                    marker in source.text
                    for marker in self._ACTION_OUTCOME_MARKERS
                )
            ):
                notes.append(
                    SourcedBriefStatement(
                        text=f"조치 결과 미확인: {source.text}"[:2000],
                        source_ids=[source.source_id],
                    )
                )
        for sources in reported_by_label.values():
            distinct_texts = {source.text for source in sources}
            if len(distinct_texts) > 1:
                for start in range(0, len(sources), 20):
                    grouped_sources = sources[start : start + 20]
                    notes.append(
                        SourcedBriefStatement(
                            text=(
                                "상충 정보: "
                                + self._join_source_texts(
                                    [source.source_id for source in grouped_sources],
                                    sources_by_id,
                                )
                            )[:2000],
                            source_ids=[
                                source.source_id for source in grouped_sources
                            ],
                        )
                    )
        return notes

    @staticmethod
    def _stable_unique_statements(
        statements: Iterable[SourcedBriefStatement],
    ) -> list[SourcedBriefStatement]:
        unique: list[SourcedBriefStatement] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for statement in statements:
            key = (statement.text, tuple(statement.source_ids))
            if key not in seen:
                seen.add(key)
                unique.append(statement)
        return unique
