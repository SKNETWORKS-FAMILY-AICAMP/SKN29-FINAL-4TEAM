"""RAG 검색 지표 계산 모듈."""

from typing import List


def calculate_recall_at_k(retrieved_chunk_ids: List[str], expected_chunk_ids: List[str], k: int = 5) -> float:
    """Recall@K 지표 계산 (상위 K개 중 정답 청크 포함 비율)"""
    if not expected_chunk_ids:
        return 1.0

    top_k_retrieved = set(retrieved_chunk_ids[:k])
    expected_set = set(expected_chunk_ids)

    hits = len(top_k_retrieved.intersection(expected_set))
    return hits / len(expected_set)


def calculate_mrr(retrieved_chunk_ids: List[str], expected_chunk_ids: List[str]) -> float:
    """MRR (Mean Reciprocal Rank) 계산 (최초 정답 청크 순위의 역수)"""
    if not expected_chunk_ids:
        return 1.0

    expected_set = set(expected_chunk_ids)
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in expected_set:
            return 1.0 / rank

    return 0.0
