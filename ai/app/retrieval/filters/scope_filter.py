"""답변용 Child와 문맥·보존 레코드를 검색 단계에서 분리한다."""

from __future__ import annotations

from ..models.retrieved_chunk import RetrievedChunk


class SearchCandidateFilter:
    """직접 답변 후보인 Child만 허용한다.

    Public MVP 1.0.0의 기존 7개 레코드는 ``record_type``과
    ``retrieval_role`` 도입 전 적재됐으므로 두 필드가 모두 없는 경우에만
    Legacy 호환을 허용한다. 둘 중 하나라도 명시된 신규 데이터는
    ``CHILD + SEARCH_CANDIDATE``를 모두 충족해야 한다.
    """

    @staticmethod
    def is_valid_chunk(chunk: RetrievedChunk) -> bool:
        record_type = (
            chunk.record_type.strip().casefold()
            if isinstance(chunk.record_type, str)
            else None
        )
        retrieval_role = (
            chunk.retrieval_role.strip().upper()
            if isinstance(chunk.retrieval_role, str)
            else None
        )
        if record_type is None and retrieval_role is None:
            return True
        return record_type == "child" and retrieval_role == "SEARCH_CANDIDATE"


__all__ = ["SearchCandidateFilter"]
