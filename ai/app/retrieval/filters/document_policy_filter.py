"""공식 문서 정책 및 미검증 FAQ 필터 모듈."""

from typing import List
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk


class DocumentPolicyFilter:
    """공식 매뉴얼 검증 상태 및 이용 안내 허용 여부 필터"""

    def __init__(self, require_official_verification: bool = True):
        self.require_official_verification = require_official_verification

    def is_valid_chunk(self, chunk: RetrievedChunk) -> bool:
        """공식 검증 여부 및 안내 허용 여부 확인"""
        # 1. 안내 허용 정책 검증
        if not chunk.allowed_use:
            return False

        # 2. 공식 검증 상태 확인
        if self.require_official_verification and chunk.verification_status != "official_verified":
            return False

        return True

    def filter_chunks(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """청크 리스트에 정책 필터 적용"""
        return [c for c in chunks if self.is_valid_chunk(c)]
