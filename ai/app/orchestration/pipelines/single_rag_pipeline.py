"""최소 LangGraph 기반 단일 RAG 오케스트레이터."""

from langgraph.graph import END, START, StateGraph

from ..pipeline_context import PipelineContext
from ..pipeline_result import PipelineResult
from ...common.timeout import CancellationToken, get_stage_timeout_policy
from ...integrations.llm import GuidanceLLMClient
from ...retrieval import RetrievalConfigurationError
from ...schemas import AiStage
from ..stages import (
    execute_generation_stage,
    execute_missing_fields_stage,
    execute_retrieval_stage,
    execute_safety_check_stage,
    execute_structuring_stage,
    execute_validation_stage,
)


class SingleRAGPipeline:
    """위험·근거 검색 경로를 분리한 최소 LangGraph."""

    def __init__(
        self,
        search_service=None,
        *,
        retrieval_configuration_error: RetrievalConfigurationError | None = None,
        llm_client: GuidanceLLMClient | None = None,
    ) -> None:
        self.search_service = search_service
        self.retrieval_configuration_error = retrieval_configuration_error
        self.llm_client = llm_client
        self.cancellation_token = CancellationToken()
        self.timeout_policy = get_stage_timeout_policy()
        graph = StateGraph(dict)
        graph.add_node("structuring", self._structuring)
        graph.add_node("safety", self._safety)
        graph.add_node("missing_fields", self._missing_fields)
        graph.add_node("retrieval", self._retrieval)
        graph.add_node("generation", self._generation)
        graph.add_node("validation", self._validation)
        graph.add_edge(START, "structuring")
        graph.add_edge("structuring", "safety")
        graph.add_conditional_edges(
            "safety",
            self._route_after_safety,
            {"danger": "generation", "questionnaire": "missing_fields"},
        )
        graph.add_edge("missing_fields", "retrieval")
        graph.add_edge("retrieval", "generation")
        graph.add_edge("generation", "validation")
        graph.add_edge("validation", END)
        self.graph = graph.compile()

    def _structuring(self, state):
        self._run_stage(AiStage.STRUCTURING, execute_structuring_stage, state["ctx"])
        return state

    def _safety(self, state):
        self._run_stage(AiStage.SAFETY_CHECK, execute_safety_check_stage, state["ctx"])
        return state

    @staticmethod
    def _route_after_safety(state):
        return "danger" if state["ctx"].safety_assessment.risk_level.value == "danger" else "questionnaire"

    def _missing_fields(self, state):
        self._run_stage(AiStage.CHECKING_MISSING_FIELDS, execute_missing_fields_stage, state["ctx"])
        return state

    def _retrieval(self, state):
        with self.cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(AiStage.RETRIEVING.value),
            AiStage.RETRIEVING.value,
        ):
            if self.retrieval_configuration_error is not None:
                raise self.retrieval_configuration_error
            execute_retrieval_stage(
                state["ctx"],
                self.search_service,
                cancellation_token=self.cancellation_token,
            )
        return state

    def _generation(self, state):
        timeout_seconds = self.timeout_policy.for_stage(AiStage.GENERATING.value)
        with self.cancellation_token.deadline_scope(
            timeout_seconds,
            AiStage.GENERATING.value,
        ):
            execute_generation_stage(
                state["ctx"],
                self.llm_client,
                self.cancellation_token,
                attempt_timeout_seconds=min(7.0, timeout_seconds / 2.0),
            )
        return state

    def _validation(self, state):
        self._run_stage(AiStage.VALIDATING, execute_validation_stage, state["ctx"])
        return state

    def _run_stage(self, stage: AiStage, callback, ctx) -> None:
        with self.cancellation_token.deadline_scope(
            self.timeout_policy.for_stage(stage.value),
            stage.value,
        ):
            callback(ctx)

    def run(
        self,
        ctx: PipelineContext,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> PipelineResult:
        """LangGraph를 실행하고 공개 응답 변환용 결과를 반환한다."""
        self.cancellation_token = cancellation_token or CancellationToken()
        self.cancellation_token.raise_if_cancelled()
        state = self.graph.invoke({"ctx": ctx})
        return PipelineResult(success=True, context=state["ctx"])
