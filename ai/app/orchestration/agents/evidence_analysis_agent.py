"""공식 근거 검색·충분성 판정 역할."""

from __future__ import annotations

from ...common.timeout import CancellationToken, get_stage_timeout_policy
from ...retrieval import RetrievalConfigurationError
from ...schemas import AiStage
from ...structuring.llm_contracts import FollowUpWordingLLMClient
from ..pipeline_context import PipelineContext
from ..stages import (
    execute_evidence_clarification_stage,
    execute_retrieval_stage,
)
from .contracts import EvidenceAgentOutput


class EvidenceAnalysisAgent:
    """검색 결과만 소유하며 고객 안내나 Safety 결정을 변경하지 않는다."""

    allowed_tools = (
        "BgeM3EmbeddingClient",
        "PgVectorStore",
        "IndexManifest",
        "EvidenceClarificationPolicy",
        "FollowUpQuestionGenerator",
    )

    def __init__(
        self,
        search_service,
        cancellation_token: CancellationToken,
        *,
        retrieval_configuration_error: RetrievalConfigurationError | None = None,
        followup_llm_client: FollowUpWordingLLMClient | None = None,
    ) -> None:
        self.search_service = search_service
        self.cancellation_token = cancellation_token
        self.retrieval_configuration_error = retrieval_configuration_error
        self.followup_llm_client = followup_llm_client
        self.timeout_policy = get_stage_timeout_policy()

    def run(self, ctx: PipelineContext) -> EvidenceAgentOutput:
        with self.cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(AiStage.RETRIEVING.value),
            AiStage.RETRIEVING.value,
        ):
            if self.retrieval_configuration_error is not None:
                raise self.retrieval_configuration_error
            execute_retrieval_stage(
                ctx,
                self.search_service,
                cancellation_token=self.cancellation_token,
            )
            if getattr(self.search_service, "rejected_chunk_ids", []):
                ctx.evidence_clarification_allowed = False

        with self.cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(AiStage.CHECKING_MISSING_FIELDS.value),
            AiStage.CHECKING_MISSING_FIELDS.value,
        ):
            decision = execute_evidence_clarification_stage(
                ctx,
                self.followup_llm_client,
                timeout_seconds=self.timeout_policy.for_provider(
                    "FOLLOWUP_WORDING"
                ),
            )
        return EvidenceAgentOutput(
            retrieval_outcome=ctx.retrieval_outcome,
            evidence_references=list(ctx.evidence_references),
            evidence_sufficient=decision.evidence_sufficient,
            request_more_information=bool(ctx.followup_questions),
        )
