"""S02: BM25·Embedding의 정렬된 청크 ID를 RRF로 결합한다.

RRF = Reciprocal Rank Fusion. 검색기별 원점수는 의도적으로 사용하지 않는다.
데이터 정답(Gold)은 이 모듈에서 참조하지 않는다.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence


def fuse_rrf(
    ranked_lists: Mapping[str, Sequence[str]],
    *,
    rank_constant: int = 60,
    limit: int = 3,
) -> list[dict]:
    """검색기별 Top-N 순위를 결합한 문서 목록을 반환한다.

    각 문서 d의 점수: Σ_searcher 1 / (rank_constant + rank_searcher(d))
    rank는 1부터 시작하며, 검색되지 않은 문서는 해당 검색기의 기여도가 0이다.
    점수가 완전히 같으면 chunk_id 오름차순으로 정렬해 재현성을 유지한다.
    """
    if not isinstance(rank_constant, int) or isinstance(rank_constant, bool) or rank_constant < 1:
        raise ValueError("rank_constant는 1 이상의 정수여야 합니다")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit은 1 이상의 정수여야 합니다")
    if not ranked_lists:
        raise ValueError("최소 1개 검색기 순위가 필요합니다")

    scores: dict[str, float] = defaultdict(float)
    ranks: dict[str, dict[str, int]] = defaultdict(dict)

    for method, ids in ranked_lists.items():
        if not isinstance(method, str) or not method.strip():
            raise ValueError("검색기 이름이 유효하지 않습니다")
        if isinstance(ids, (str, bytes)):
            raise ValueError("각 검색 결과는 정렬된 청크 ID 목록이어야 합니다")
        seen: set[str] = set()
        for rank, chunk_id in enumerate(ids, start=1):
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise ValueError("청크 ID는 비어 있지 않은 문자열이어야 합니다")
            if chunk_id in seen:
                raise ValueError(f"{method} 검색 결과에 중복 청크가 있습니다: {chunk_id}")
            seen.add(chunk_id)
            scores[chunk_id] += 1.0 / (rank_constant + rank)
            ranks[chunk_id][method] = rank

    ordered_ids = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    return [
        {"chunk_id": chunk_id, "rrf_score": scores[chunk_id], "source_ranks": ranks[chunk_id]}
        for chunk_id in ordered_ids[:limit]
    ]
