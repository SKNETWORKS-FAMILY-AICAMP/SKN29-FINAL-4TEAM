"""Supervisor와 세 역할이 협업하는 후보 Multi-Agent Runtime."""

from __future__ import annotations

from ...common.timeout import CancellationToken
from ...integrations.llm import GuidanceLLMClient
from ...retrieval import RetrievalConfigurationError, RetrievalOutcome
from ...schemas import RiskLevel
from ..agents import (
    AgentRole,
    CareDecisionAgent,
    EvidenceAnalysisAgent,
    HandoffReason,
    MultiAgentSharedState,
    SymptomAnalysisAgent,
)
from ..pipeline_context import PipelineContext
from ..pipeline_result import PipelineResult


class MultiAgentPipeline:
    """조건부 Routing·Feedback·Hop 제한을 적용하는 3-Agent Supervisor."""

    def __init__(
        self,
        search_service=None,
        *,
        retrieval_configuration_error: RetrievalConfigurationError | None = None,
        llm_client: GuidanceLLMClient | None = None,
        max_hops: int = 8,
    ) -> None:
        self.search_service = search_service
        self.retrieval_configuration_error = retrieval_configuration_error
        self.llm_client = llm_client
        self.max_hops = max_hops

    def run(
        self,
        ctx: PipelineContext,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> PipelineResult:
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        shared = MultiAgentSharedState(context=ctx, max_hops=self.max_hops)
        symptom_agent = SymptomAnalysisAgent(token)
        evidence_agent = EvidenceAnalysisAgent(
            self.search_service,
            token,
            retrieval_configuration_error=self.retrieval_configuration_error,
        )
        care_agent = CareDecisionAgent(token, self.llm_client)

        shared.handoff(AgentRole.SYMPTOM_ANALYSIS, HandoffReason.START_ANALYSIS)
        symptom_output = symptom_agent.run(ctx)

        if symptom_output.safety_assessment.risk_level == RiskLevel.DANGER:
            shared.handoff(AgentRole.CARE_DECISION, HandoffReason.DANGER_PRIORITY)
            care_agent.run(ctx)
        else:
            shared.handoff(AgentRole.EVIDENCE_ANALYSIS, HandoffReason.RETRIEVAL_REQUIRED)
            evidence_output = evidence_agent.run(ctx)
            if evidence_output.request_more_information:
                if shared.feedback_handoff_count >= 1:
                    raise RuntimeError("한 실행의 Evidence Feedback은 1회를 초과할 수 없습니다.")
                shared.feedback_handoff_count += 1
                shared.handoff(
                    AgentRole.SYMPTOM_ANALYSIS,
                    HandoffReason.MORE_INFORMATION_REQUIRED,
                )
                symptom_agent.review_evidence_feedback(ctx)
                shared.awaiting_customer_input = True
                shared.handoff(
                    AgentRole.CARE_DECISION,
                    HandoffReason.CUSTOMER_INPUT_PENDING,
                )
                care_agent.run(ctx, awaiting_customer_input=True)
            else:
                reason = (
                    HandoffReason.EVIDENCE_READY
                    if evidence_output.retrieval_outcome == RetrievalOutcome.AVAILABLE
                    else HandoffReason.NO_EVIDENCE
                )
                shared.handoff(AgentRole.CARE_DECISION, reason)
                care_agent.run(ctx)

        shared.handoff(AgentRole.SUPERVISOR, HandoffReason.CARE_DECISION_READY)
        return PipelineResult(
            success=True,
            context=ctx,
            runtime_name="multi_agent",
            multi_agent_metadata=shared.metadata(),
        )
