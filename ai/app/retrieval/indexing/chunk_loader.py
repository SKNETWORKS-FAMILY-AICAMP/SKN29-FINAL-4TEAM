"""전처리 데이터 청크 로더 모듈."""

import json
from pathlib import Path
from typing import List, Literal, Optional

from ..models.retrieved_chunk import RetrievedChunk
from .handoff_profile import load_rag_handoff_profile


class ChunkLoader:
    """data/processed/ 청크 데이터 파일 읽기 로더"""

    def __init__(
        self,
        data_file: Optional[str | Path] = None,
        *,
        data_layout: Literal["legacy", "rag-expansion"] = "legacy",
        dataset_profile: str = "rag",
    ):
        repository_root = Path(__file__).resolve().parents[4]
        self.data_file = Path(data_file) if data_file else (
            repository_root / "data" / "processed" / "structured" / "rag" / "mvp" / "rag_verified_sample.jsonl"
        )
        self.data_layout = data_layout
        self.dataset_profile = dataset_profile

    @classmethod
    def from_handoff_profile(
        cls,
        profile_name: str,
        *,
        repository_root: Path | None = None,
    ) -> "ChunkLoader":
        """Consumer Profile이 지정한 적재 후보만 선택한다."""

        profile = load_rag_handoff_profile(
            profile_name,
            repository_root=repository_root,
        )
        layout = "rag-expansion" if profile.candidate_only else "legacy"
        return cls(
            profile.ingest_path,
            data_layout=layout,
            dataset_profile=profile.name,
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
                if self.data_layout == "rag-expansion":
                    chunks.append(self._expansion_chunk(raw, line_number=line_number))
                else:
                    chunks.append(self._legacy_chunk(raw, line_number=line_number))
        return chunks

    def _legacy_chunk(self, raw: dict, *, line_number: int) -> RetrievedChunk:
        required = {
            "chunk_id", "document_id", "exact_sales_code", "product_generation",
            "version", "page_start", "chunk_text", "source_file_sha256",
            "verification_status", "scope_role",
        }
        missing = required.difference(raw)
        if missing:
            raise ValueError(f"RAG JSONL {line_number}행 필수 필드 누락: {sorted(missing)}")
        allowed_use = (
            raw["scope_role"] == "mvp"
            and raw["verification_status"] == "TEXT_AND_VISUAL_VERIFIED"
        )
        return RetrievedChunk(
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
            verification_status=(
                "official_verified" if allowed_use else raw["verification_status"]
            ),
            allowed_use=allowed_use,
            source_hash=raw["source_file_sha256"],
            safe_actions=raw.get("safe_actions", []),
            topic_code=raw.get("topic_code"),
            record_type="CHILD",
            retrieval_role="SEARCH_CANDIDATE",
            dataset_profile=self.dataset_profile,
            runtime_eligible=True,
        )

    def _expansion_chunk(self, raw: dict, *, line_number: int) -> RetrievedChunk:
        required = {
            "child_id", "record_type", "retrieval_role", "child_text",
            "exact_sales_code", "product_model", "product_generation", "document_id",
            "version", "parent_id", "page_refs", "section_title", "evidence_group_id",
            "source_variant_id", "source_file_sha256", "verification_status",
            "allowed_use", "safe_actions",
        }
        missing = required.difference(raw)
        if missing:
            raise ValueError(
                f"RAG Expansion JSONL {line_number}행 필수 필드 누락: {sorted(missing)}"
            )
        if raw["record_type"] != "child" or raw["retrieval_role"] != "SEARCH_CANDIDATE":
            raise ValueError(f"RAG Expansion JSONL {line_number}행은 검색 Child가 아닙니다.")
        if raw["verification_status"] != "TEXT_AND_VISUAL_VERIFIED":
            raise ValueError(f"RAG Expansion JSONL {line_number}행은 공식 검증되지 않았습니다.")
        if raw["allowed_use"] != "RAG_HANDOFF_ONLY":
            raise ValueError(f"RAG Expansion JSONL {line_number}행의 허용 범위가 잘못됐습니다.")
        page_refs = raw["page_refs"]
        if not page_refs:
            raise ValueError(f"RAG Expansion JSONL {line_number}행에 Page 참조가 없습니다.")

        return RetrievedChunk(
            chunk_id=raw["child_id"],
            document_id=raw["document_id"],
            document_title=raw["section_title"],
            document_version=raw["version"],
            page=page_refs[0],
            page_refs=page_refs,
            manual_model=raw["product_model"],
            model_code=raw["exact_sales_code"],
            product_generation=raw["product_generation"],
            content=raw["child_text"],
            similarity_score=0.0,
            official_url=None,
            verification_status="official_verified",
            allowed_use=True,
            source_hash=raw["source_file_sha256"],
            safe_actions=raw["safe_actions"],
            evidence_group_id=raw["evidence_group_id"],
            source_variant_id=raw["source_variant_id"],
            parent_id=raw["parent_id"],
            record_type="CHILD",
            retrieval_role=raw["retrieval_role"],
            dataset_profile=self.dataset_profile,
            runtime_eligible=False,
        )

    def load_sample_chunks(self) -> List[RetrievedChunk]:
        """이전 호출자 호환용 별칭. 하드코딩 샘플을 반환하지 않는다."""
        return self.load_verified_chunks()
