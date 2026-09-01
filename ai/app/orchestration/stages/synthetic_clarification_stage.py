"""Choose one deterministic clarification from the isolated scenario catalog."""

from __future__ import annotations

from opentelemetry import trace

from ...retrieval.synthetic_scenarios import (
    SyntheticScenarioDatasetError,
    SyntheticScenarioRetriever,
    SyntheticScenarioSearchResult,
    get_synthetic_scenario_retriever,
)
from ...schemas import RiskLevel
from ..pipeline_context import PipelineContext


_TRACER = trace.get_tracer("waterbridge.ai.synthetic_clarification", "1.0.0")


def execute_synthetic_clarification_stage(
    ctx: PipelineContext,
    retriever: SyntheticScenarioRetriever | None = None,
) -> SyntheticScenarioSearchResult:
    """Search synthetic candidates without exposing them as official evidence."""

    with _TRACER.start_as_current_span(
        "waterbridge.evidence.synthetic_clarification"
    ) as span:
        if ctx.domain_relevance == "OFF_DOMAIN":
            result = SyntheticScenarioSearchResult(reason="OFF_DOMAIN")
        elif (
            ctx.safety_assessment is not None
            and ctx.safety_assessment.risk_level == RiskLevel.DANGER
        ):
            result = SyntheticScenarioSearchResult(reason="DANGER_PRIORITY")
        elif _clarification_rounds(ctx) >= 1:
            result = SyntheticScenarioSearchResult(
                reason="CLARIFICATION_LIMIT_REACHED"
            )
        else:
            try:
                result = (retriever or get_synthetic_scenario_retriever()).search(
                    structured_symptom=ctx.structured_symptom,
                    previous_answers=ctx.previous_answers,
                )
            except SyntheticScenarioDatasetError:
                # Synthetic data is optional classification knowledge. An invalid
                # catalog is never promoted to evidence and must not block the
                # existing official retrieval / no-evidence policy.
                result = SyntheticScenarioSearchResult(
                    reason="SYNTHETIC_DATASET_UNAVAILABLE"
                )

        ctx.synthetic_scenario_candidate_count = len(result.candidates)
        ctx.synthetic_scenario_ids = [
            candidate.scenario_id for candidate in result.candidates
        ]
        ctx.synthetic_clarification_requested = result.question is not None
        ctx.synthetic_clarification_target_field = (
            result.question.target_field if result.question is not None else None
        )
        ctx.synthetic_clarification_reason = result.reason

        span.set_attribute(
            "synthetic.scenario_candidate_count",
            ctx.synthetic_scenario_candidate_count,
        )
        span.set_attribute(
            "synthetic.clarification_requested",
            ctx.synthetic_clarification_requested,
        )
        if ctx.synthetic_clarification_target_field:
            span.set_attribute(
                "synthetic.target_field",
                ctx.synthetic_clarification_target_field,
            )
        span.set_attribute("synthetic.decision_reason", result.reason)
        if result.question is not None:
            ctx.followup_questions = [result.question]
            ctx.evidence_sufficient = False
            ctx.evidence_clarification_reason = "SYNTHETIC_SCENARIO_AMBIGUOUS"
        return result


def _clarification_rounds(ctx: PipelineContext) -> int:
    return sum(
        1
        for answer in ctx.previous_answers
        if isinstance(answer, dict)
        and str(answer.get("question_id", "")).startswith("followup-")
    )


__all__ = ["execute_synthetic_clarification_stage"]
