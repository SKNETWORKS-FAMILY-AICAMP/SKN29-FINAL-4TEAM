"""A4 Experiment Playground v0의 단일 Query Dense Retrieval Runtime."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from ...evaluation.evidence_scoring_v2 import score_gold_case
from ai.scripts.run_full_corpus_baseline_v1 import (
    EmbeddingProvider,
    LocalBgeM3Provider,
    REPOSITORY_ROOT,
    _load_json,
    _load_jsonl,
    _normalize,
    _sha256,
)


DEFAULT_PROFILE = "ai/configs/experiments/full_corpus_baseline_v1.yaml"
DEFAULT_INDEX = "ai/evaluation/indexes/playground_bge_m3_page_v1.npz"
DEFAULT_INDEX_MANIFEST = "ai/evaluation/indexes/playground_bge_m3_page_v1_manifest.json"


class PlaygroundIndexError(RuntimeError):
    """Playground 검색 Index가 없거나 현재 Corpus/Profile과 일치하지 않음."""


def _resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    path = path.resolve()
    path.relative_to(REPOSITORY_ROOT.resolve())
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_playground_index(
    profile_path: str | Path = DEFAULT_PROFILE,
    index_path: str | Path = DEFAULT_INDEX,
    manifest_path: str | Path = DEFAULT_INDEX_MANIFEST,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    """Full Corpus 문서 Embedding을 재사용 가능한 Playground Index로 저장한다."""

    resolved_profile = _resolve(profile_path)
    resolved_index = _resolve(index_path)
    resolved_manifest = _resolve(manifest_path)
    profile = _load_json(resolved_profile)
    corpus_path = _resolve(profile["corpus"]["path"])
    corpus_rows = _load_jsonl(corpus_path)
    provider = embedding_provider or LocalBgeM3Provider(profile)
    if provider.dimension != profile["embedding"]["dimension"]:
        raise ValueError(
            "Embedding Dimension 불일치: "
            f"expected={profile['embedding']['dimension']}, actual={provider.dimension}"
        )

    started = time.perf_counter()
    vectors = _normalize(provider.embed_documents([row["text"] for row in corpus_rows]))
    if vectors.shape != (len(corpus_rows), profile["embedding"]["dimension"]):
        raise ValueError(
            "Playground Index Shape 불일치: "
            f"expected={(len(corpus_rows), profile['embedding']['dimension'])}, "
            f"actual={vectors.shape}"
        )

    resolved_index.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        resolved_index,
        vectors=vectors.astype(np.float32),
        corpus_sha256=np.asarray([_sha256(corpus_path)]),
        profile_sha256=np.asarray([_sha256(resolved_profile)]),
        embedding_revision=np.asarray([profile["embedding"]["revision"]]),
    )
    manifest = {
        "index_id": "playground_bge_m3_page_v1",
        "status": "READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "path": resolved_profile.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(resolved_profile),
        },
        "corpus": {
            "path": corpus_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(corpus_path),
            "chunks": len(corpus_rows),
        },
        "embedding": profile["embedding"],
        "index": {
            "path": resolved_index.relative_to(REPOSITORY_ROOT).as_posix(),
            "shape": list(vectors.shape),
            "dtype": str(vectors.dtype),
        },
        "build_seconds": round(time.perf_counter() - started, 6),
        "official_metrics_allowed": False,
    }
    _write_json(resolved_manifest, manifest)
    return manifest


class ExperimentPlaygroundEngine:
    """고정된 A3-1 Profile에서 한 번에 한 Query를 검색하는 v0 Engine."""

    def __init__(
        self,
        profile_path: str | Path = DEFAULT_PROFILE,
        index_path: str | Path = DEFAULT_INDEX,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        document_vectors: np.ndarray | None = None,
    ) -> None:
        self.profile_path = _resolve(profile_path)
        self.index_path = _resolve(index_path)
        self.profile = _load_json(self.profile_path)
        self.corpus_path = _resolve(self.profile["corpus"]["path"])
        self.dataset_path = _resolve(self.profile["dataset"]["path"])
        self.corpus_rows = _load_jsonl(self.corpus_path)
        self.gold_rows = _load_jsonl(self.dataset_path)
        self._provider = embedding_provider
        self._provider_lock = Lock()
        self.document_vectors = (
            _normalize(document_vectors)
            if document_vectors is not None
            else self._load_index()
        )
        expected_shape = (
            len(self.corpus_rows),
            self.profile["embedding"]["dimension"],
        )
        if self.document_vectors.shape != expected_shape:
            raise PlaygroundIndexError(
                f"Index Shape 불일치: expected={expected_shape}, "
                f"actual={self.document_vectors.shape}"
            )

    def _load_index(self) -> np.ndarray:
        if not self.index_path.is_file():
            raise PlaygroundIndexError(
                "Playground Index가 없습니다. "
                "python -B -m ai.scripts.build_experiment_playground_index_v1 를 먼저 실행하세요."
            )
        with np.load(self.index_path, allow_pickle=False) as stored:
            checks = {
                "corpus_sha256": _sha256(self.corpus_path),
                "profile_sha256": _sha256(self.profile_path),
                "embedding_revision": self.profile["embedding"]["revision"],
            }
            for key, expected in checks.items():
                actual = str(stored[key][0])
                if actual != expected:
                    raise PlaygroundIndexError(
                        f"Playground Index {key} 불일치: expected={expected}, actual={actual}"
                    )
            return np.asarray(stored["vectors"], dtype=np.float32)

    def _get_provider(self) -> EmbeddingProvider:
        if self._provider is None:
            with self._provider_lock:
                if self._provider is None:
                    self._provider = LocalBgeM3Provider(self.profile)
        return self._provider

    def options(self) -> dict[str, Any]:
        return {
            "status": "DRAFT_PLAYGROUND_READY",
            "products": sorted({row["exact_sales_code"] for row in self.corpus_rows}),
            "corpus_variants": list(self.profile["corpus"]["variants"]),
            "chunking_profiles": [self.profile["chunking"]["profile"]],
            "embedding_profiles": ["bge_m3"],
            "retrieval_profiles": ["dense_cosine_exact_v1"],
            "top_k": {"default": self.profile["retrieval"]["top_k"], "min": 1, "max": 10},
            "generation": {
                "status": "NOT_IMPLEMENTED_V0",
                "profile": "current_default_profile",
            },
            "official_metrics_allowed": False,
        }

    def search(
        self,
        *,
        product_model_code: str,
        query: str,
        corpus_variant: str = "JAC104_IAC425_COMBINED",
        chunking_profile: str = "current_source_page_v1",
        embedding_profile: str = "bge_m3",
        retrieval_profile: str = "dense_cosine_exact_v1",
        top_k: int = 5,
        product_filter: bool = True,
    ) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise ValueError("Query는 비어 있을 수 없습니다.")
        if not 1 <= top_k <= 10:
            raise ValueError("Top-K는 1~10 범위여야 합니다.")
        variants = self.profile["corpus"]["variants"]
        if corpus_variant not in variants:
            raise ValueError(f"지원하지 않는 Corpus Variant: {corpus_variant}")
        if chunking_profile != self.profile["chunking"]["profile"]:
            raise ValueError(f"지원하지 않는 Chunking Profile: {chunking_profile}")
        if embedding_profile != "bge_m3":
            raise ValueError(f"지원하지 않는 Embedding Profile: {embedding_profile}")
        if retrieval_profile != self.profile["retrieval"]["profile"]:
            raise ValueError(f"지원하지 않는 Retrieval Profile: {retrieval_profile}")

        total_started = time.perf_counter()
        embedding_started = time.perf_counter()
        provider = self._get_provider()
        query_vector = _normalize(provider.embed_queries([query]))[0]
        embedding_ms = (time.perf_counter() - embedding_started) * 1000

        retrieval_started = time.perf_counter()
        scopes = variants[corpus_variant]
        candidate_indices = [
            index
            for index, row in enumerate(self.corpus_rows)
            if row["corpus_scope"] in scopes
            and (not product_filter or row["exact_sales_code"] == product_model_code)
        ]
        threshold = float(self.profile["retrieval"]["score_threshold"])
        ranked: list[dict[str, Any]] = []
        ranked_for_scoring: list[dict[str, Any]] = []
        if candidate_indices:
            scores = self.document_vectors[candidate_indices] @ query_vector
            for local_index in np.argsort(-scores):
                score = float(scores[local_index])
                if score < threshold:
                    continue
                chunk = self.corpus_rows[candidate_indices[int(local_index)]]
                ranked_for_scoring.append({"chunk": chunk, "score": score})
                ranked.append({
                    "rank": len(ranked) + 1,
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "page_refs": chunk["page_refs"],
                    "section_title": chunk["section_title"],
                    "exact_sales_code": chunk["exact_sales_code"],
                    "score": round(score, 8),
                    "text_preview": chunk["text"][:500],
                })
                if len(ranked) == top_k:
                    break
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

        matched_gold = next(
            (
                row for row in self.gold_rows
                if row["query"] == query
                and row["product_model_code"] == product_model_code
            ),
            None,
        )
        expected = matched_gold["expected_evidence"] if matched_gold else []
        retrieval_pass = None
        gold_scoring: dict[str, Any] | None = None
        exposed_gold_scoring: dict[str, Any] | None = None
        scoring_status = "NOT_SCORED"
        if matched_gold is not None:
            gold_scoring = score_gold_case(
                {**matched_gold, "expected_execution_path": "LOCAL_DENSE_QUERY"},
                ranked_for_scoring,
                actual_execution_path="LOCAL_DENSE_QUERY",
                vector_query_count=1,
                evaluation_top_k=5,
            )
            scoring_status = (
                "DRAFT_SCORED"
                if top_k == 5 and product_filter
                else "NOT_COMPARABLE"
            )
            retrieval_pass = (
                gold_scoring["passed"]
                if scoring_status == "DRAFT_SCORED"
                else None
            )
            exposed_gold_scoring = dict(gold_scoring)
            if scoring_status == "NOT_COMPARABLE":
                for pass_field in (
                    "passed",
                    "semantic_passed",
                    "execution_contract_passed",
                    "no_evidence_passed",
                    "no_evidence_success",
                    "policy_block_success",
                    "answerability_gate_passed",
                ):
                    if pass_field in exposed_gold_scoring:
                        exposed_gold_scoring[pass_field] = None

        wrong_product_hits = sum(
            result["exact_sales_code"] != product_model_code for result in ranked
        )
        return {
            "status": "DRAFT_RETRIEVAL_COMPLETE",
            "request": {
                "product_model_code": product_model_code,
                "query": query,
                "corpus_variant": corpus_variant,
                "chunking_profile": chunking_profile,
                "embedding_profile": embedding_profile,
                "retrieval_profile": retrieval_profile,
                "top_k": top_k,
                "product_filter": product_filter,
            },
            "retrieval": {
                "results": ranked,
                "result_count": len(ranked),
                "score_threshold": threshold,
                "wrong_product_hit_count": wrong_product_hits,
            },
            "gold": {
                "matched": matched_gold is not None,
                "case_id": matched_gold["case_id"] if matched_gold else None,
                "review_status": matched_gold["review_status"] if matched_gold else None,
                "expected_evidence": expected,
                "retrieval_pass": retrieval_pass,
                "scoring_status": scoring_status,
                "scoring_contract_version": (
                    gold_scoring["scoring_contract_version"]
                    if gold_scoring is not None
                    else None
                ),
                "metrics": exposed_gold_scoring,
            },
            "generation": {
                "status": "NOT_IMPLEMENTED_V0",
                "message": "A4 v0는 Retrieval 단일 Query 실행만 지원합니다.",
            },
            "validation": {
                "schema": "PASS",
                "grounding": "NOT_EXECUTED",
                "safety": "NOT_EXECUTED",
            },
            "latency_ms": {
                "query_embedding": round(embedding_ms, 2),
                "retrieval": round(retrieval_ms, 2),
                "total": round((time.perf_counter() - total_started) * 1000, 2),
            },
            "official_metrics_allowed": False,
        }
