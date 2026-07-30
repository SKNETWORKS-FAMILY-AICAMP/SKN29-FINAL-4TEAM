"""승인 RAG 청크를 bge-m3로 임베딩해 실제 pgvector에 멱등 적재한다."""

import hashlib
import json
import os
from pathlib import Path

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.indexing.index_manifest import IndexManifest


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


def main() -> None:
    dsn = os.getenv("AI_VECTOR_DSN")
    model_revision = os.getenv("AI_EMBEDDING_REVISION")
    if not dsn:
        raise RuntimeError("실제 pgvector 적재에는 AI_VECTOR_DSN이 필요합니다.")
    if not model_revision:
        raise RuntimeError("재현 가능한 적재에는 AI_EMBEDDING_REVISION Commit SHA가 필요합니다.")

    chunks = ChunkLoader().load_verified_chunks()
    if not chunks or not all(chunk.allowed_use for chunk in chunks):
        raise RuntimeError("공식 검증·고객 안내 허용 청크만 적재할 수 있습니다.")

    embedding_client = BgeM3EmbeddingClient(model_revision=model_revision)
    vectors = embedding_client.embed_documents(chunk.content for chunk in chunks)
    store = PgVectorStore(dsn)
    store.initialize_schema()
    upserted = store.upsert(chunks, vectors)
    stored_count = store.count()
    if stored_count != len(chunks):
        raise RuntimeError(f"적재 행 수 불일치: expected={len(chunks)}, actual={stored_count}")

    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = repository_root / "ai" / "configs" / "index_manifest.json"
    manifest = IndexManifest(
        model_name=embedding_client.model_name,
        model_revision=model_revision,
        dimension=embedding_client.dimension,
        index_type="exact_search",
        index_version="1.0.0",
        chunk_count=stored_count,
        chunk_set_sha256=_chunk_set_sha256(chunks),
        document_hashes={
            chunk.document_id or chunk.document_title: chunk.source_hash
            for chunk in chunks
            if chunk.source_hash
        },
    )
    manifest.save_manifest(str(manifest_path))
    print(json.dumps({
        "status": "PGVECTOR_INDEX_VERIFIED",
        "upserted": upserted,
        "stored_count": stored_count,
        "dimension": embedding_client.dimension,
        "model_revision": model_revision,
        "chunk_set_sha256": manifest.chunk_set_sha256,
        "manifest_path": str(manifest_path.relative_to(repository_root)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
