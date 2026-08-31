"""검색 결과가 실제로 모호할 때만 추가 질문 대상을 결정한다."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..retrieval import EvidenceApplicabilityGate
from ..schemas import FollowUpQuestion, RiskLevel
from .pipeline_context import PipelineContext


@dataclass(frozen=True, slots=True)
class EvidenceClarificationDecision:
    evidence_sufficient: bool
    target_fields: tuple[str, ...] = ()
    question_overrides: tuple[FollowUpQuestion, ...] = ()
    reason: str = "EVIDENCE_SUFFICIENT"


class EvidenceClarificationPolicy:
    """MissingField가 아닌 Evidence sufficiency를 질문 트리거로 사용한다."""

    MAX_CLARIFICATION_ROUNDS = 1
    _QUESTION_PREFIX = "followup-"
    _IMPORTANCE_ORDER = {"high": 0, "medium": 1, "low": 2}
    _CONDITION_SCENARIOS = (
        (
            "FIRST_DRAW",
            re.compile(r"첫\s*(?:잔|출수)|처음\s*(?:잔|출수|사용)"),
            "첫 잔에서만 미지근함",
        ),
        (
            "CONSECUTIVE_DRAW",
            re.compile(r"여러\s*잔|연속\s*(?:출수|사용)|두\s*번째\s*잔"),
            "여러 잔 연속 받을 때 미지근해짐",
        ),
        (
            "PERSISTENT",
            re.compile(r"사용할\s*때마다|항상|계속\s*(?:미지근|온도)"),
            "사용할 때마다 계속 미지근함",
        ),
        (
            "DISPLAY_CODE",
            re.compile(r"LCD|점검\s*문구|오류\s*코드", re.IGNORECASE),
            "LCD에 점검 문구도 표시됨",
        ),
    )

    def decide(self, ctx: PipelineContext) -> EvidenceClarificationDecision:
        if (
            ctx.safety_assessment is not None
            and ctx.safety_assessment.risk_level == RiskLevel.DANGER
        ):
            return EvidenceClarificationDecision(
                evidence_sufficient=False,
                reason="DANGER_PRIORITY",
            )

        evidence_available = bool(ctx.evidence_references)
        if not ctx.evidence_clarification_allowed:
            return EvidenceClarificationDecision(
                evidence_sufficient=evidence_available,
                reason="CLARIFICATION_BLOCKED_BY_RETRIEVAL_GUARD",
            )
        if self._clarification_rounds(ctx) >= self.MAX_CLARIFICATION_ROUNDS:
            return EvidenceClarificationDecision(
                evidence_sufficient=evidence_available,
                reason="CLARIFICATION_LIMIT_REACHED",
            )

        symptom_type = (
            ctx.structured_symptom.symptom_type
            if ctx.structured_symptom is not None
            else None
        )
        applicability_gate = EvidenceApplicabilityGate()
        if (
            symptom_type == "물맛/냄새 이상"
            and applicability_gate.classify(ctx.previous_answers) is None
        ):
            question = applicability_gate.followup_question(
                symptom_type=symptom_type,
                previous_answers=ctx.previous_answers,
            )
            return EvidenceClarificationDecision(
                evidence_sufficient=False,
                target_fields=(applicability_gate.TARGET_FIELD,),
                question_overrides=(question,) if question is not None else (),
                reason="EVIDENCE_APPLICABILITY_AMBIGUOUS",
            )

        ambiguity_question = self._scenario_ambiguity_question(ctx)
        if ambiguity_question is not None:
            return EvidenceClarificationDecision(
                evidence_sufficient=False,
                target_fields=(ambiguity_question.target_field,),
                question_overrides=(ambiguity_question,),
                reason="EVIDENCE_SCENARIOS_AMBIGUOUS",
            )

        if evidence_available:
            return EvidenceClarificationDecision(evidence_sufficient=True)

        unresolved = sorted(
            ctx.missing_fields,
            key=lambda item: self._IMPORTANCE_ORDER[item.importance],
        )
        if not unresolved:
            return EvidenceClarificationDecision(
                evidence_sufficient=False,
                reason="NO_EVIDENCE_NO_CLARIFICATION_TARGET",
            )
        return EvidenceClarificationDecision(
            evidence_sufficient=False,
            target_fields=(unresolved[0].field_name,),
            reason="NO_EVIDENCE_REQUIRES_DISAMBIGUATION",
        )

    def _scenario_ambiguity_question(
        self,
        ctx: PipelineContext,
    ) -> FollowUpQuestion | None:
        if not ctx.evidence_references or ctx.structured_symptom is None:
            return None
        if not (
            ctx.structured_symptom.symptom_type == "온도 이상"
            and ctx.structured_symptom.target_water_type == "온수"
        ):
            return None
        if ctx.structured_symptom.occurrence_condition:
            return None
        content = " ".join(item.summary for item in ctx.evidence_references)
        options = [
            option
            for _, pattern, option in self._CONDITION_SCENARIOS
            if pattern.search(content)
        ]
        if len(options) < 2:
            return None
        return FollowUpQuestion(
            question_id="followup-occurrence-condition",
            question_text=(
                "검색된 공식 근거를 구분하기 위해, 증상이 어떤 상황에 가장 가깝나요?"
            ),
            options=options[:5],
            target_field="occurrence_condition",
        )

    def _clarification_rounds(self, ctx: PipelineContext) -> int:
        return min(
            self.MAX_CLARIFICATION_ROUNDS,
            sum(
                1
                for answer in ctx.previous_answers
                if isinstance(answer, dict)
                and str(answer.get("question_id", "")).startswith(
                    self._QUESTION_PREFIX
                )
            ),
        )


__all__ = ["EvidenceClarificationDecision", "EvidenceClarificationPolicy"]
