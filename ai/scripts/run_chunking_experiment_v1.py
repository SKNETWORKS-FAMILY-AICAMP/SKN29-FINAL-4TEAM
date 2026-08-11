#!/usr/bin/env python3
"""Run the Phase B B1 chunking comparison with fixed retrieval settings."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ai.evaluation.chunking import build_profile_chunks, profile_statistics
from ai.evaluation.file_integrity import file_sha256
from ai.scripts.run_full_corpus_baseline_v1 import (
    DEFAULT_PROFILE as DEFAULT_BASELINE_PROFILE,
    EmbeddingProvider,
    LocalBgeM3Provider,
    REPOSITORY_ROOT,
    _git_facts,
    _load_json,
    _load_jsonl,
    _metrics,
    _normalize,
    _resolve,
    build_preflight_report,
)


DEFAULT_CHUNKING_PROFILE = "ai/configs/experiments/chunking_profiles.yaml"
DEFAULT_OUTPUT = "ai/evaluation/reports/experiments/chunking_comparison_v1"
DEFAULT_CACHE = "tmp/ai_chunking_experiment_cache"


def _percentile(values: list[float], percentile: int) -> float:
    return round(float(np.percentile(np.asarray(values), percentile)), 6) if values else 0.0


def _embedding_cache_key(
    texts: list[str],
    embedding_contract: dict[str, Any],
    provider: EmbeddingProvider,
) -> str:
    payload = json.dumps({
        "texts": texts,
        "embedding": embedding_contract,
        "provider_class": provider.__class__.__name__,
        "dimension": provider.dimension,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def _load_or_build_embeddings(
    texts: list[str],
    embedding_contract: dict[str, Any],
    provider: EmbeddingProvider,
    cache_directory: Path,
) -> tuple[np.ndarray, float, bool, str]:
    cache_key = _embedding_cache_key(texts, embedding_contract, provider)
    cache_directory.mkdir(parents=True, exist_ok=True)
    cache_path = cache_directory / f"{cache_key}.npz"
    if cache_path.is_file():
        with np.load(cache_path, allow_pickle=False) as payload:
            vectors = np.asarray(payload["vectors"], dtype=np.float32)
            embedding_seconds = float(payload["embedding_seconds"][0])
        if vectors.shape == (len(texts), provider.dimension):
            return vectors, embedding_seconds, True, cache_key
    started = time.perf_counter()
    vectors = _normalize(provider.embed_documents(texts))
    embedding_seconds = time.perf_counter() - started
    np.savez_compressed(
        cache_path,
        vectors=vectors,
        embedding_seconds=np.asarray([embedding_seconds], dtype=np.float64),
    )
    return vectors, embedding_seconds, False, cache_key


def _triage_failure(row: dict[str, Any]) -> str | None:
    """Classify B1 failures conservatively; final diagnosis remains review-gated."""

    metrics = row["metrics"]
    if row["expected_no_evidence"]:
        if metrics["no_evidence_passed"]:
            return None
        if row["query_variant_type"] == "CROSS_PRODUCT":
            return "SCOPE_FILTER_ERROR"
        return "RETRIEVAL_ERROR"
    if metrics["hit_at_5"] == 0:
        return "RETRIEVAL_ERROR"
    if metrics["first_relevant_rank"] != 1:
        return "RERANK_ERROR"
    return None


def run_chunking_experiment(
    chunking_profile_path: Path,
    baseline_profile_path: Path,
    output_directory: Path,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    allow_draft_gold: bool = False,
    cache_directory: Path | None = None,
) -> dict[str, Any]:
    preflight = build_preflight_report(
        baseline_profile_path,
        allow_draft_gold=allow_draft_gold,
        embedding_provider_supplied=embedding_provider is not None,
    )
    if preflight["status"] != "READY":
        raise RuntimeError("B1 Preflight 차단: " + ", ".join(preflight["blockers"]))

    baseline = _load_json(baseline_profile_path)
    experiment = _load_json(chunking_profile_path)
    source_path = _resolve(baseline["corpus"]["path"])
    dataset_path = _resolve(baseline["dataset"]["path"])
    source_rows = _load_jsonl(source_path)
    dataset_rows = [
        row for row in _load_jsonl(dataset_path)
        if row["split"] == experiment["dataset_split"]
    ]
    provider = embedding_provider or LocalBgeM3Provider(baseline)
    if provider.dimension != baseline["embedding"]["dimension"]:
        raise ValueError("Embedding Provider Dimension 불일치")

    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    query_started = time.perf_counter()
    query_vectors = _normalize(provider.embed_queries([row["query"] for row in dataset_rows]))
    query_embedding_seconds = time.perf_counter() - query_started
    retrieval = experiment["fixed_retrieval_profile"]
    runnable = [row for row in experiment["profiles"] if row["status"] == "RUNNABLE"]
    blocked = [row for row in experiment["profiles"] if row["status"] != "RUNNABLE"]
    results: list[dict[str, Any]] = []
    structures: dict[str, dict[str, Any]] = {}
    resolved_cache = cache_directory or _resolve(DEFAULT_CACHE)

    for profile in runnable:
        chunks = build_profile_chunks(source_rows, profile)
        vectors, index_seconds, cache_hit, cache_key = _load_or_build_embeddings(
            [row["text"] for row in chunks],
            baseline["embedding"],
            provider,
            resolved_cache,
        )
        structures[profile["profile_id"]] = {
            **profile_statistics(source_rows, chunks),
            "document_embedding_seconds": round(index_seconds, 6),
            "embedding_cache_hit": cache_hit,
            "embedding_cache_key": cache_key,
        }
        for filter_mode in retrieval["filter_modes"]:
            for case_index, case in enumerate(dataset_rows):
                candidates = list(range(len(chunks)))
                if filter_mode == "EXACT_PRODUCT_FILTER":
                    candidates = [
                        index for index in candidates
                        if chunks[index]["exact_sales_code"] == case["product_model_code"]
                    ]
                query_clock = time.perf_counter()
                ranked: list[dict[str, Any]] = []
                if candidates:
                    scores = vectors[candidates] @ query_vectors[case_index]
                    for local_index in np.argsort(-scores):
                        score = float(scores[local_index])
                        if score < retrieval["score_threshold"]:
                            continue
                        ranked.append({
                            "chunk": chunks[candidates[int(local_index)]],
                            "score": score,
                        })
                        if len(ranked) == retrieval["top_k"]:
                            break
                latency_ms = (time.perf_counter() - query_clock) * 1000
                metrics = _metrics(
                    ranked,
                    case["expected_evidence"],
                    case["expected_no_evidence"],
                    case["product_model_code"],
                    case["evidence_match_policy"],
                )
                results.append({
                    "profile_id": profile["profile_id"],
                    "filter_mode": filter_mode,
                    "case_id": case["case_id"],
                    "query_variant_type": case["query_variant_type"],
                    "expected_no_evidence": case["expected_no_evidence"],
                    "ranked_results": [
                        {
                            "rank": rank,
                            "chunk_id": item["chunk"]["chunk_id"],
                            "document_id": item["chunk"]["document_id"],
                            "page_refs": item["chunk"]["page_refs"],
                            "exact_sales_code": item["chunk"]["exact_sales_code"],
                            "score": round(item["score"], 8),
                            "parent_id": item["chunk"].get("parent_id"),
                        }
                        for rank, item in enumerate(ranked, 1)
                    ],
                    "metrics": metrics,
                    "retrieval_latency_ms": round(latency_ms, 6),
                })

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[(row["profile_id"], row["filter_mode"])].append(row)
    comparisons = []
    failure_analysis: list[dict[str, Any]] = []
    for (profile_id, filter_mode), rows in sorted(grouped.items()):
        positives = [row for row in rows if not row["expected_no_evidence"]]
        negatives = [row for row in rows if row["expected_no_evidence"]]

        def mean(metric: str) -> float | None:
            values = [
                row["metrics"][metric]
                for row in positives
                if row["metrics"][metric] is not None
            ]
            return round(sum(values) / len(values), 6) if values else None

        latencies = [row["retrieval_latency_ms"] for row in rows]
        comparisons.append({
            "profile_id": profile_id,
            "filter_mode": filter_mode,
            "case_count": len(rows),
            "positive_case_count": len(positives),
            "mean_hit_at_1": mean("hit_at_1"),
            "mean_hit_at_3": mean("hit_at_3"),
            "mean_hit_at_5": mean("hit_at_5"),
            "mean_mrr": mean("mrr"),
            "mean_ndcg_at_5": mean("ndcg_at_5"),
            "wrong_product_hit_count": sum(
                row["metrics"]["wrong_product_hit_count"] for row in rows
            ),
            "no_evidence_accuracy": round(
                sum(row["metrics"]["no_evidence_passed"] for row in negatives)
                / len(negatives),
                6,
            ) if negatives else None,
            "retrieval_latency_p50_ms": _percentile(latencies, 50),
            "retrieval_latency_p95_ms": _percentile(latencies, 95),
            "structure": structures[profile_id],
        })
        for row in rows:
            failure_type = _triage_failure(row)
            if failure_type:
                failure_analysis.append({
                    "profile_id": profile_id,
                    "filter_mode": filter_mode,
                    "case_id": row["case_id"],
                    "query_variant_type": row["query_variant_type"],
                    "failure_type": failure_type,
                    "first_relevant_rank": row["metrics"]["first_relevant_rank"],
                    "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
                })

    total_seconds = time.perf_counter() - started_clock
    manifest = {
        "experiment_id": experiment["experiment_id"],
        "experiment_version": experiment["experiment_version"],
        "run_status": "DRAFT_CHUNKING_EXPERIMENT_COMPLETE",
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "metrics_publishable_as_official": False,
        "selection_status": "PENDING_GOLD_REVIEW_AND_PM_GATE",
        "dataset": {
            "path": baseline["dataset"]["path"],
            "sha256": file_sha256(dataset_path),
            "split": experiment["dataset_split"],
            "selected_cases": len(dataset_rows),
        },
        "source_corpus": {
            "path": baseline["corpus"]["path"],
            "sha256": file_sha256(source_path),
            "source_chunks": len(source_rows),
        },
        "profiles": {
            "path": chunking_profile_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": file_sha256(chunking_profile_path),
            "runnable": [row["profile_id"] for row in runnable],
            "blocked": blocked,
        },
        "fixed_embedding": baseline["embedding"],
        "fixed_retrieval": retrieval,
        "performance": {
            "query_embedding_seconds": round(query_embedding_seconds, 6),
            "total_seconds": round(total_seconds, 6),
            "case_result_count": len(results),
        },
        "runtime": {
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "provider_class": provider.__class__.__name__,
        },
        "git": _git_facts(),
        "publication_limits": experiment["publication_limits"],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_directory / "case_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
        encoding="utf-8",
    )
    (output_directory / "summary.json").write_text(
        json.dumps({
            "experiment_id": experiment["experiment_id"],
            "run_status": manifest["run_status"],
            "metrics_publishable_as_official": False,
            "selection_status": manifest["selection_status"],
            "comparisons": comparisons,
            "blocked_profiles": blocked,
            "publication_limits": experiment["publication_limits"],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_directory / "failure_analysis.json").write_text(
        json.dumps({
            "experiment_id": experiment["experiment_id"],
            "status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
            "policy": (
                "실패 Case를 데이터 추가 전에 분류하며 CHUNKING_ERROR와 KNOWLEDGE_GAP은 "
                "원문·근거 수동 검토 없이 자동 확정하지 않음"
            ),
            "items": failure_analysis,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="B1 Chunking Experiment v1")
    parser.add_argument("--profiles", default=DEFAULT_CHUNKING_PROFILE)
    parser.add_argument("--baseline-profile", default=DEFAULT_BASELINE_PROFILE)
    parser.add_argument("--output-directory", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-draft-gold", action="store_true")
    args = parser.parse_args()
    manifest = run_chunking_experiment(
        _resolve(args.profiles),
        _resolve(args.baseline_profile),
        _resolve(args.output_directory),
        allow_draft_gold=args.allow_draft_gold,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
