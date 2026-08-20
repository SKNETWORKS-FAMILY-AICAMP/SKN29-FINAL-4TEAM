from mcp.server import MCPServer

from .tools.search_official_evidence import (
    SearchOfficialEvidenceAdapter,
    SearchOfficialEvidenceInput,
    SearchOfficialEvidenceOutput,
)
from ...orchestration.pipeline_router import PipelineRouter
from ...retrieval import RetrievalConfigurationError
from ...retrieval.search.vector_search import VectorSearchService


class _UnconfiguredEmbeddingProvider:
    """
    Vector Store 환경이 없는 경우 사용하는 MCP용 Fail-closed Provider.

    정책 Gate에서 차단되는 요청은 실제 Embedding까지 도달하지 않는다.
    검색이 허용된 요청이 Embedding 단계까지 오면 설정 오류를 명시적으로 발생시킨다.
    """

    dimension = 1024

    def embed_query(self, text: str) -> list[float]:
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 공식 근거 검색을 실행할 수 없습니다."
        )

    def embed_documents(
        self,
        texts,
    ) -> list[list[float]]:
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 공식 근거 검색을 실행할 수 없습니다."
        )


class _UnconfiguredVectorStore:
    """
    실제 Vector Store가 구성되지 않은 환경에서 DB 접근을 차단한다.
    """

    def search(
        self,
        vector,
        *,
        model_code: str,
        product_generation: str,
        top_k: int,
    ):
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 공식 근거 검색을 실행할 수 없습니다."
        )


def _resolve_search_service() -> VectorSearchService:
    """
    실제 Runtime 검색 서비스가 구성되어 있으면 재사용하고,
    없으면 Policy Gate만 실행 가능한 Fail-closed Service를 만든다.
    """

    search_service = PipelineRouter._configured_search_service()

    if search_service is not None:
        return search_service

    return VectorSearchService(
        _UnconfiguredEmbeddingProvider(),
        _UnconfiguredVectorStore(),
    )


mcp = MCPServer("WaterBridge MCP")


@mcp.tool()
def health_check() -> dict[str, str]:
    """Check whether the WaterBridge MCP server is running."""

    return {
        "status": "ok",
        "service": "waterbridge-mcp",
    }


@mcp.tool()
def search_official_evidence(
    customer_query: str,
    model_code: str,
    symptom_type: str | None = None,
    previous_answers: list[dict[str, str]] | None = None,
) -> SearchOfficialEvidenceOutput:
    """
    Search policy-approved official WaterBridge evidence
    for a customer inquiry.
    """

    search_service = _resolve_search_service()

    adapter = SearchOfficialEvidenceAdapter(
        search_service
    )

    request = SearchOfficialEvidenceInput(
        customer_query=customer_query,
        model_code=model_code,
        symptom_type=symptom_type,
        previous_answers=previous_answers or [],
    )

    return adapter.execute(request)


if __name__ == "__main__":
    mcp.run()
