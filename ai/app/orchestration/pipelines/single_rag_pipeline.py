"""최소 LangGraph 기반 단일 RAG 오케스트레이터."""

from langgraph.graph import END, START, StateGraph

from ..pipeline_context import PipelineContext
from ..pipeline_result import PipelineResult
from ..stages import (
    execute_generation_stage,
    execute_retrieval_stage,
    execute_safety_check_stage,
    execute_structuring_stage,
    execute_validation_stage,
)


class SingleRAGPipeline:
    """위험·근거 검색 경로를 분리한 최소 LangGraph."""

    def __init__(self, search_service=None) -> None:
        self.search_service = search_service
        graph = StateGraph(dict)
        graph.add_node("structuring", self._structuring)
        graph.add_node("safety", self._safety)
        graph.add_node("retrieval", self._retrieval)
        graph.add_node("generation", self._generation)
        graph.add_node("validation", self._validation)
        graph.add_edge(START, "structuring")
        graph.add_edge("structuring", "safety")
        graph.add_conditional_edges(
            "safety",
            self._route_after_safety,
            {"danger": "generation", "retrieve": "retrieval"},
        )
        graph.add_edge("retrieval", "generation")
        graph.add_edge("generation", "validation")
        graph.add_edge("validation", END)
        self.graph = graph.compile()

    @staticmethod
    def _structuring(state):
        execute_structuring_stage(state["ctx"])
        return state

    @staticmethod
    def _safety(state):
        execute_safety_check_stage(state["ctx"])
        return state

    @staticmethod
    def _route_after_safety(state):
        return "danger" if state["ctx"].safety_assessment.risk_level.value == "danger" else "retrieve"

    def _retrieval(self, state):
        execute_retrieval_stage(state["ctx"], self.search_service)
        return state

    @staticmethod
    def _generation(state):
        execute_generation_stage(state["ctx"])
        return state

    @staticmethod
    def _validation(state):
        execute_validation_stage(state["ctx"])
        return state

    def run(self, ctx: PipelineContext) -> PipelineResult:
        """LangGraph를 실행하고 공개 응답 변환용 결과를 반환한다."""
        state = self.graph.invoke({"ctx": ctx})
        return PipelineResult(success=True, context=state["ctx"])
