from pydantic import BaseModel, Field

from ....orchestration.harness.product_registry import (
    resolve_product_generation,
)
from ....retrieval import (
    EvidenceApplicabilityGate,
    EvidenceTopicFilter,
    RetrievalQuery,
)
from ....retrieval.search.vector_search import VectorSearchService
from ....schemas import EvidenceReference


class SearchOfficialEvidencePreviousAnswer(BaseModel):
    """MCP 공식 근거 검색에서 사용하는 이전 문진 답변."""

    question_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="이전 문진 질문 식별자",
    )

    answer_text: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="고객이 입력하거나 선택한 이전 문진 답변",
    )


class SearchOfficialEvidenceInput(BaseModel):
    """MCP 공식 근거 검색 Tool 입력 계약."""

    customer_query: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="고객이 입력한 원문 질문 또는 증상",
    )

    model_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="구독 정보에서 확인한 정확한 판매 모델 코드",
    )

    symptom_type: str | None = Field(
        default=None,
        description="구조화된 증상 유형",
    )

    previous_answers: list[SearchOfficialEvidencePreviousAnswer] = Field(
        default_factory=list,
        max_length=50,
        description="이전 문진 답변 목록",
    )


class SearchOfficialEvidenceOutput(BaseModel):
    """MCP 공식 근거 검색 Tool 출력 계약."""

    # 최종적으로 사용할 수 있는 공식 근거
    evidence_references: list[EvidenceReference] = Field(
        default_factory=list
    )

    # 실제 pgvector 검색 경로가 실행됐는지
    vector_search_executed: bool = False

    # VectorSearchService 검색 결과가 존재했는지
    search_result_found: bool = False

    # Topic / Applicability Filter까지 통과한 최종 Evidence가 존재하는지
    evidence_found: bool = False

    # 정책에 의해 검색이 차단됐는지
    policy_blocked: bool = False

    # PGVECTOR_QUERY 또는 POLICY_BLOCK_* 실행 경로
    policy_execution_path: str | None = None

    # 적용된 정책 Rule ID
    applied_rule_id: str | None = None

    # 정책 차단 이유
    block_reason: str | None = None


class SearchOfficialEvidenceAdapter:
    """기존 Retriever를 MCP Tool 계약으로 변환하는 Adapter."""

    def __init__(
        self,
        search_service: VectorSearchService,
    ) -> None:
        # VectorSearchService를 외부에서 주입한다.
        # MCP에서 PgVectorStore를 직접 생성하거나 호출하지 않는다.
        self.search_service = search_service

    def execute(
        self,
        request: SearchOfficialEvidenceInput,
    ) -> SearchOfficialEvidenceOutput:
        """MCP 공식 근거 검색 요청 하나를 처리한다."""

        # 1. 정확 판매코드에 해당하는 제품 세대를
        #    현재 Product Registry SSOT에서 조회한다.
        product_generation = resolve_product_generation(
            request.model_code
        )

        # 2. MCP Input -> 기존 Retriever의 RetrievalQuery 변환
        query = RetrievalQuery(
            query_text=request.customer_query,
            model_code=request.model_code,
            product_generation=product_generation,
            top_k=5,
            require_official_verified=True,
        )

        # 3. 검색 전 정책 판정 정보를 확보한다.
        #
        # Model Capability Gate
        # Answerability Capability Gate
        # 등의 Rule ID / reason을 MCP 결과에 반환하기 위함이다.
        decision = self.search_service.evaluate_pre_search_gate(
            query
        )

        # 4. FAQ 미검증 출처 정책까지 포함하여
        #    실제 검색 실행 경로를 확인한다.
        # 이미 Policy Gate에서 차단된 경우에는
        # 같은 Gate를 다시 평가하지 않고 해당 실행 경로를 그대로 사용한다.
        if decision.blocked:
            execution_path = decision.execution_path
        else:
            # Gate는 통과했지만 FAQ 미검증 출처 정책 등
            # 추가 실행 경로 확인이 필요한 경우에만 조회한다.
            execution_path = self.search_service.execution_path(
                query
            )

        # 5. 실제 검색은 반드시 기존 VectorSearchService.search() 사용
        #
        # VectorSearchService 내부에서:
        #   Policy Gate
        #   -> FAQ 검증
        #   -> Embedding
        #   -> PgVectorStore
        #
        # 순서로 처리한다.
        #
        # 정책 차단 요청의 경우 search() 내부에서
        # pgvector 이전에 빈 결과로 종료된다.
        chunks = self.search_service.search(query)

        # 6. 검색 전 정책에서 차단된 경우
        if execution_path != "PGVECTOR_QUERY":
            if decision.blocked:
                applied_rule_id = decision.rule_id
                block_reason = decision.reason
            else:
                # 현재 FaqUsageValidator는 bool만 반환하므로
                # 공식 Rule ID는 임의로 만들지 않는다.
                applied_rule_id = None

                block_reason = (
                    "미검증·비공식 출처만 사용하라는 요청으로 검색이 차단됨"
                    if execution_path
                    == "POLICY_BLOCK_UNVERIFIED_SOURCE"
                    else None
                )

            return SearchOfficialEvidenceOutput(
                evidence_references=[],
                vector_search_executed=False,
                search_result_found=False,
                evidence_found=False,
                policy_blocked=True,
                policy_execution_path=execution_path,
                applied_rule_id=applied_rule_id,
                block_reason=block_reason,
            )

        # 여기까지 왔다면 실제 pgvector 검색 경로를 실행한 것이다.
        search_result_found = bool(chunks)

        # 7. 구조화된 증상 기준 Evidence Topic Filter
        chunks = EvidenceTopicFilter().filter_chunks(
            chunks,
            symptom_type=request.symptom_type,
        )

        # 8. MCP PreviousAnswer 모델을
        #    기존 Applicability Gate 입력 형식으로 변환
        previous_answers = [
            answer.model_dump()
            for answer in request.previous_answers
        ]

        # 9. 이전 문진 답변을 이용한 Evidence 적용성 판정
        applicability_gate = EvidenceApplicabilityGate()

        applicability = (
            applicability_gate.classify_for_symptom(
                symptom_type=request.symptom_type,
                previous_answers=previous_answers,
            )
        )

        # 10. 현재 고객 상황에 적용할 수 없는 Evidence 제거
        chunks = applicability_gate.filter_chunks(
            chunks,
            symptom_type=request.symptom_type,
            applicability=applicability,
        )

        # 11. 내부 RetrievedChunk를
        #     MCP가 외부에 반환할 EvidenceReference로 변환
        evidence_references = [
            EvidenceReference(
                document_title=chunk.document_title,
                document_version=chunk.document_version,
                page=chunk.page,
                page_refs=chunk.page_refs,
                chunk_id=chunk.chunk_id,
                official_url=chunk.official_url,
                summary=chunk.content,
                similarity_score=chunk.similarity_score,
                verification_status=chunk.verification_status,
            )
            for chunk in chunks
        ]

        # 12. 최종 MCP Tool 결과
        return SearchOfficialEvidenceOutput(
            evidence_references=evidence_references,
            vector_search_executed=True,
            search_result_found=search_result_found,
            evidence_found=bool(evidence_references),
            policy_blocked=False,
            policy_execution_path="PGVECTOR_QUERY",
            applied_rule_id=None,
            block_reason=None,
        )
