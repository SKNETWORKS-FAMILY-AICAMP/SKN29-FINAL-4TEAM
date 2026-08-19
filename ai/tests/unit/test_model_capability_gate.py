"""정확 판매코드·명시적 조작부 검색 전 Gate 테스트."""

from __future__ import annotations

import pytest

from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.app.retrieval.verification.model_capability_gate import ModelCapabilityGate


@pytest.mark.parametrize(
    ("model_code", "query", "rule_id"),
    [
        (
            "WPUIAC425SNW",
            "출수/출빙 버튼을 눌러 온수를 받고 싶어요.",
            "CAP-WPUIAC425SNW-DISPENSE-CONTROL-001",
        ),
        (
            "WPUIAC606SNW",
            "[물] 버튼을 눌러 온수를 받고 싶어요.",
            "CAP-WPUIAC606SNW-DISPENSE-CONTROL-001",
        ),
        (
            "WPUIAC606SNW",
            "물 출수 버튼을 눌렀는데 반응이 없어요.",
            "CAP-WPUIAC606SNW-DISPENSE-CONTROL-001",
        ),
    ],
)
def test_explicit_other_model_control_is_blocked(
    model_code: str,
    query: str,
    rule_id: str,
) -> None:
    decision = ModelCapabilityGate().evaluate(
        query_text=query,
        model_code=model_code,
    )

    assert decision.blocked is True
    assert decision.policy_id == "RAG-GATE-MODEL-CAPABILITY-001"
    assert decision.rule_id == rule_id
    assert decision.reason_code == "MODEL_CONTROL_MISMATCH"
    assert decision.execution_path == "POLICY_BLOCK_MODEL_CONTROL_MISMATCH"


@pytest.mark.parametrize(
    ("model_code", "query"),
    [
        ("WPUIAC425SNW", "[물] 버튼을 눌러 온수를 다시 받고 싶어요."),
        ("WPUIAC606SNW", "출수/출빙 버튼을 눌러 온수를 다시 받고 싶어요."),
        ("WPUIAC425SNW", "물이 출수되지 않는데 어떤 버튼을 확인하나요?"),
        ("WPUIAC606SNW", "물이 출수되지 않는데 버튼 반응이 없어요."),
    ],
)
def test_supported_or_non_explicit_control_words_remain_searchable(
    model_code: str,
    query: str,
) -> None:
    decision = ModelCapabilityGate().evaluate(
        query_text=query,
        model_code=model_code,
    )

    assert decision.blocked is False
    assert decision.execution_path == "PGVECTOR_QUERY"


def test_unregistered_exact_sales_code_is_blocked() -> None:
    decision = ModelCapabilityGate().evaluate(
        query_text="온수 잠금을 해제하는 방법은?",
        model_code="WPUIAC999ZZZ",
    )

    assert decision.blocked is True
    assert decision.rule_id == "RAG-GATE-MODEL-CAPABILITY-001"
    assert decision.reason_code == "UNREGISTERED_EXACT_SALES_CODE"
    assert decision.execution_path == "POLICY_BLOCK_UNREGISTERED_EXACT_SALES_CODE"


@pytest.mark.parametrize(
    ("model_code", "query", "expected_path"),
    [
        (
            "WPUIAC425SNW",
            "출수/출빙 버튼을 눌러 온수를 받고 싶어요.",
            "POLICY_BLOCK_MODEL_CONTROL_MISMATCH",
        ),
        (
            "WPUIAC999ZZZ",
            "온수 잠금을 해제하는 방법은?",
            "POLICY_BLOCK_UNREGISTERED_EXACT_SALES_CODE",
        ),
    ],
)
def test_model_capability_gate_blocks_before_embedding_and_pgvector(
    model_code: str,
    query: str,
    expected_path: str,
) -> None:
    class FailingEmbedding:
        dimension = 1024

        def embed_query(self, text):
            raise AssertionError("차단된 질의는 임베딩하지 않아야 합니다.")

    class FailingStore:
        def search(self, *args, **kwargs):
            raise AssertionError("차단된 질의는 pgvector를 조회하지 않아야 합니다.")

    service = VectorSearchService(FailingEmbedding(), FailingStore())
    retrieval_query = RetrievalQuery(query_text=query, model_code=model_code)

    assert service.execution_path(retrieval_query) == expected_path
    assert service.search(retrieval_query) == []
