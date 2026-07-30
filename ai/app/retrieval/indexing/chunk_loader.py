"""전처리 데이터 청크 로더 모듈."""

import json
from pathlib import Path
from typing import List, Optional

from ..models.retrieved_chunk import RetrievedChunk


class ChunkLoader:
    """data/processed/ 청크 데이터 파일 읽기 로더"""

    def __init__(self, data_file: Optional[str | Path] = None):
        repository_root = Path(__file__).resolve().parents[4]
        self.data_file = Path(data_file) if data_file else (
            repository_root / "data" / "processed" / "structured" / "rag" / "mvp" / "rag_verified_sample.jsonl"
        )

    def load_verified_chunks(self) -> List[RetrievedChunk]:
        """공통 검증 JSONL을 읽어 검색 DTO로 변환한다."""
        if not self.data_file.is_file():
            raise FileNotFoundError(f"검증 RAG 데이터가 없습니다: {self.data_file}")

        chunks: List[RetrievedChunk] = []
        with self.data_file.open("r", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                raw = json.loads(line)
                required = {
                    "chunk_id", "document_id", "exact_sales_code", "product_generation",
                    "version", "page_start", "chunk_text", "source_file_sha256",
                    "verification_status", "scope_role",
                }
                missing = required.difference(raw)
                if missing:
                    raise ValueError(f"RAG JSONL {line_number}행 필수 필드 누락: {sorted(missing)}")
                allowed_use = raw["scope_role"] == "mvp" and raw["verification_status"] == "TEXT_AND_VISUAL_VERIFIED"
                chunks.append(RetrievedChunk(
                    chunk_id=raw["chunk_id"],
                    document_id=raw["document_id"],
                    document_title=raw.get("section_title") or raw["document_id"],
                    document_version=raw["version"],
                    page=raw["page_start"],
                    page_refs=raw.get("page_refs", [raw["page_start"]]),
                    manual_model=raw.get("model_family") or raw["exact_sales_code"],
                    model_code=raw["exact_sales_code"],
                    product_generation=raw["product_generation"],
                    content=raw["chunk_text"],
                    similarity_score=0.0,
                    official_url=raw.get("source_url"),
                    verification_status="official_verified" if allowed_use else raw["verification_status"],
                    allowed_use=allowed_use,
                    source_hash=raw["source_file_sha256"],
                    safe_actions=raw.get("safe_actions", []),
                ))
        return chunks

    def load_sample_chunks(self) -> List[RetrievedChunk]:
        """이전 호출자 호환용 별칭. 하드코딩 샘플을 반환하지 않는다."""
        return self.load_verified_chunks()
