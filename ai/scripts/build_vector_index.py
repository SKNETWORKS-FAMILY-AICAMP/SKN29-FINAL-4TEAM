"""승인 RAG 청크를 bge-m3로 임베딩해 실제 pgvector에 멱등 적재한다."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from ai.app.common.candidate_vector_index import (
    RAG_EXPANSION_PROFILE,
    RAG_EXPANSION_TABLE,
    assert_rag_expansion_candidate_target,
)
from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.indexing import (
    ChunkLoader,
    IndexManifest,
    load_rag_handoff_profile,
)


def _chunk_set_sha256(chunks) -> str:
    canonical = [
        {
            "chunk_id": chunk.chunk_id,
            "source_hash": chunk.source_hash,
            "content": chunk.content,
        }
        for chunk in sorted(chunks, key=lambda item: item.chunk_id)
    ]
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG Consumer Profile pgvector 적재")
    parser.add_argument(
        "--profile",
        default="rag",
        choices=("rag", RAG_EXPANSION_PROFILE),
        help="data/config/handoff/consumer_profiles.json의 RAG Profile",
    )
    return parser.parse_args()


def _manifest_path(repository_root: Path, profile_name: str) -> Path:
    if profile_name == RAG_EXPANSION_PROFILE:
        return repository_root / ".runtime" / "rag-expansion" / "index_manifest.json"
    return repository_root / "ai" / "configs" / "index_manifest.json"


def main() -> None:
    args = _parse_args()
    dsn = os.getenv("AI_VECTOR_DSN")
    model_revision = os.getenv("AI_EMBEDDING_REVISION")
    if not dsn:
        raise RuntimeError("실제 pgvector 적재에는 AI_VECTOR_DSN이 필요합니다.")
    if not model_revision:
        raise RuntimeError("재현 가능한 적재에는 AI_EMBEDDING_REVISION Commit SHA가 필요합니다.")

    profile = load_rag_handoff_profile(args.profile)
    chunks = ChunkLoader.from_handoff_profile(args.profile).load_verified_chunks()
    if not chunks or not all(chunk.allowed_use for chunk in chunks):
        raise RuntimeError("공식 검증·고객 안내 허용 청크만 적재할 수 있습니다.")

    table_name = os.getenv("AI_VECTOR_TABLE_NAME", "ai_rag_chunks")
    if profile.candidate_only:
        assert_rag_expansion_candidate_target(dsn, table_name)
        if any(chunk.runtime_eligible for chunk in chunks):
            raise RuntimeError("rag-expansion Candidate를 Runtime 활성 청크로 적재할 수 없습니다.")
    elif table_name == RAG_EXPANSION_TABLE:
        raise RuntimeError("공식 rag Profile은 Expansion Candidate Table에 적재할 수 없습니다.")

    embedding_client = BgeM3EmbeddingClient(model_revision=model_revision)
    chunk_set_sha256 = _chunk_set_sha256(chunks)
    index_version = "rag-expansion/1.0.0" if profile.candidate_only else "1.0.0"
    indexed_chunks = [
        chunk.model_copy(update={
            "embedding_model": embedding_client.model_name,
            "embedding_model_revision": model_revision,
            "index_version": index_version,
            "chunk_set_sha256": chunk_set_sha256,
        })
        for chunk in chunks
    ]
    vectors = embedding_client.embed_documents(chunk.content for chunk in indexed_chunks)
    store = PgVectorStore(dsn, table_name=table_name)
    upserted = store.upsert(indexed_chunks, vectors)
    chunk_ids = [chunk.chunk_id for chunk in indexed_chunks]
    stored_count = store.count(chunk_ids)
    if stored_count != len(chunks):
        raise RuntimeError(f"적재 행 수 불일치: expected={len(chunks)}, actual={stored_count}")

    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = _manifest_path(repository_root, profile.name)
    manifest = IndexManifest(
        model_name=embedding_client.model_name,
        model_revision=model_revision,
        dimension=embedding_client.dimension,
        index_type="exact_search",
        index_version=index_version,
        chunk_count=stored_count,
        chunk_set_sha256=chunk_set_sha256,
        document_hashes={
            chunk.document_id or chunk.document_title: chunk.source_hash
            for chunk in indexed_chunks
            if chunk.source_hash
        },
    )
    manifest.save_manifest(str(manifest_path))
    print(json.dumps({
        "status": (
            "PGVECTOR_CANDIDATE_INDEX_VERIFIED"
            if profile.candidate_only
            else "PGVECTOR_INDEX_VERIFIED"
        ),
        "profile": profile.name,
        "runtime_activation": "NOT_APPROVED" if profile.candidate_only else "CURRENT_BASELINE",
        "schema_ddl_executed": False,
        "upserted": upserted,
        "stored_count": stored_count,
        "dimension": embedding_client.dimension,
        "model_revision": model_revision,
        "chunk_set_sha256": manifest.chunk_set_sha256,
        "manifest_path": str(manifest_path.relative_to(repository_root)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
