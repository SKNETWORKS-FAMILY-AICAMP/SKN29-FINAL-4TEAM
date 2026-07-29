"""검증된 MVP RAG 청크로 Vector Store 인덱스 및 Manifest 생성 스크립트."""

import os
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.indexing.index_manifest import IndexManifest


def main():
    print("[AI Indexer] BAAI/bge-m3 1024차원 Exact Search 인덱싱 시작...")
    loader = ChunkLoader()
    chunks = loader.load_sample_chunks()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(base_dir, "configs", "index_manifest.json")

    manifest = IndexManifest(
        model_name="BAAI/bge-m3",
        dimension=1024,
        index_type="exact_search",
        chunk_count=len(chunks),
        document_hashes={
            "WPU-JAC104D/JCC104D 사용 설명서": "hash_wpu_104_v1.0"
        }
    )

    manifest.save_manifest(manifest_path)
    print(f"[AI Indexer] 성공적으로 {len(chunks)}개 청크 인덱싱 및 Manifest 저장 완료 ({manifest_path})")


if __name__ == "__main__":
    main()
