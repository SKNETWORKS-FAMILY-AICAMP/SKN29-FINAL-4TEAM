"""인덱스 버전·문서 해시·차원 메타데이터 Manifest 관리 모듈."""

from datetime import datetime, timezone
import json
import os
from typing import Dict, Optional
from pydantic import BaseModel, Field


class IndexManifest(BaseModel):
    """BAAI/bge-m3 pgvector 인덱스 Manifest 데이터 모델"""
    model_name: str = Field("BAAI/bge-m3", description="사용된 임베딩 모델명")
    dimension: int = Field(1024, description="임베딩 출력 차원 (원본 1024차원)")
    index_type: str = Field("exact_search", description="검색 인덱스 유형 (Cosine Exact Search)")
    chunk_count: int = Field(0, description="적재된 총 청크 수")
    document_hashes: Dict[str, str] = Field(default_factory=dict, description="문서 파일별 해시값")
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="인덱싱 완료 시각")

    def save_manifest(self, filepath: str) -> None:
        """Manifest 파일 저장"""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load_manifest(cls, filepath: str) -> Optional["IndexManifest"]:
        """Manifest 파일 로딩"""
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return cls(**data)
