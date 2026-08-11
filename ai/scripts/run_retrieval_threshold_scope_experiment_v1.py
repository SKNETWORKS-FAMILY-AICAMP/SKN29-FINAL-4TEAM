#!/usr/bin/env python3
"""Run the B2-1 Dense threshold and query scope policy comparison."""

from __future__ import annotations

import argparse
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
from ai.evaluation.query_scope_policy import ExperimentalQueryScopePolicy
from ai.scripts.run_chunking_experiment_v1 import (
    DEFAULT_CACHE,
    DEFAULT_CHUNKING_PROFILE,
    _load_or_build_embeddings,
    _percentile,
)
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


DEFAULT_RETRIEVAL_PROFILE = (
    "ai/configs/experiments/retrieval_threshold_scope_profiles.yaml"
)
DEFAULT_OUTPUT = (
    "ai/evaluation/reports/experiments/retrieval_threshold_scope_v1"
)


def _triage_failure(row: dict[str, Any]) -> str | None:
    metrics = row["metrics"]
    if row["scope_decision"]["blocked"] and not row["expected_no_evidence"]:
        return "SCOPE_FILTER_ERROR"
    if row["expected_no_evidence"]:
        return None if metrics["no_evidence_passed"] else "RETRIEVAL_ERROR"
    if metrics["hit_at_5"] == 0:
        return "RETRIEVAL_ERROR"
    if metrics["first_relevant_rank"] != 1:
        return "RERANK_ERROR"
    return None


def run_retrieval_threshold_scope_experiment(
    retrieval_profile_path: Path,
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
        raise RuntimeError("B2-1 Preflight 차단: " + ", ".join(preflight["blockers"]))

    experiment = _load_json(retrieval_profile_path)
    chunking_config = _load_json(chunking_profile_path)
    baseline = _load_json(baseline_profile_path)
    dataset_path = _resolve(baseline["dataset"]["path"])
    source_path = _resolve(baseline["corpus"]["path"])
    dataset_rows = [
        row for row in _load_jsonl(dataset_path)
        if row["split"] == experiment["dataset_split"]
    ]
    source_rows = _load_jsonl(source_path)
    chunking_by_id = {
        row["profile_id"]: row for row in chunking_config["profiles"]
    }
    selected_chunking = []
    for profile_id in experiment["provisional_chunking_profiles"]:
        profile = chunking_by_id.get(profile_id)
        if profile is None or profile.get("status") != "RUNNABLE":
            raise ValueError(f"B2-1 Chunking Profile 실행 불가: {profile_id}")
        selected_chunking.append(profile)

    provider = embedding_provider or LocalBgeM3Provider(baseline)
    if provider.dimension != baseline["embedding"]["dimension"]:
        raise ValueError("Embedding Provider Dimension 불일치")

    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    query_started = time.perf_counter()
    query_vectors = _normalize(provider.embed_queries([row["query"] for row in dataset_rows]))
    query_embedding_seconds = time.perf_counter() - query_started
    fixed_retrieval = experiment["fixed_retrieval"]
    thresholds = [float(value) for value in fixed_retrieval["score_thresholds"]]
    scope_policies = [
        ExperimentalQueryScopePolicy(definition)
        for definition in experiment["scope_policies"]
    ]
    resolved_cache = cache_directory or _resolve(DEFAULT_CACHE)
    structures: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    for chunking_profile in selected_chunking:
        chunks = build_profile_chunks(source_rows, chunking_profile)
        vectors, embedding_seconds, cache_hit, cache_key = _load_or_build_embeddings(
            [row["text"] for row in chunks],
            baseline["embedding"],
            provider,
            resolved_cache,
        )
        structures[chunking_profile["profile_id"]] = {
            **profile_statistics(source_rows, chunks),
            "document_embedding_seconds": round(embedding_seconds, 6),
            "embedding_cache_hit": cache_hit,
            "embedding_cache_key": cache_key,
        }
        candidates_by_model = {
            model: [
                index for index, chunk in enumerate(chunks)
                if chunk["exact_sales_code"] == model
            ]
            for model in {row["product_model_code"] for row in dataset_rows}
        }
        for scope_policy in scope_policies:
            for threshold in thresholds:
                for case_index, case in enumerate(dataset_rows):
                    scope_decision = scope_policy.evaluate(
                        product_model_code=case["product_model_code"],
                        query=case["query"],
                    )
                    query_clock = time.perf_counter()
                    ranked: list[dict[str, Any]] = []
                    if not scope_decision.blocked:
                        candidates = candidates_by_model.get(case["product_model_code"], [])
                        if candidates:
                            scores = vectors[candidates] @ query_vectors[case_index]
                            for local_index in np.argsort(-scores):
                                score = float(scores[local_index])
                                if score < threshold:
                                    continue
                                ranked.append({
                                    "chunk": chunks[candidates[int(local_index)]],
                                    "score": score,
                                })
                                if len(ranked) == fixed_retrieval["top_k"]:
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
                        "chunking_profile_id": chunking_profile["profile_id"],
                        "scope_policy_id": scope_policy.policy_id,
                        "score_threshold": threshold,
                        "case_id": case["case_id"],
                        "query_variant_type": case["query_variant_type"],
                        "expected_no_evidence": case["expected_no_evidence"],
                        "scope_decision": scope_decision.as_dict(),
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

    grouped: dict[tuple[str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[(
            row["chunking_profile_id"],
            row["scope_policy_id"],
            row["score_threshold"],
        )].append(row)

    comparisons: list[dict[str, Any]] = []
    failure_analysis: list[dict[str, Any]] = []
    for (chunking_id, scope_id, threshold), rows in sorted(grouped.items()):
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
            "chunking_profile_id": chunking_id,
            "scope_policy_id": scope_id,
            "score_threshold": threshold,
            "case_count": len(rows),
            "positive_case_count": len(positives),
            "negative_case_count": len(negatives),
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
            "scope_block_count": sum(row["scope_decision"]["blocked"] for row in rows),
            "positive_scope_block_count": sum(
                row["scope_decision"]["blocked"] for row in positives
            ),
            "retrieval_latency_p50_ms": _percentile(latencies, 50),
            "retrieval_latency_p95_ms": _percentile(latencies, 95),
            "structure": structures[chunking_id],
        })
        for row in rows:
            failure_type = _triage_failure(row)
            if failure_type:
                failure_analysis.append({
                    "chunking_profile_id": chunking_id,
                    "scope_policy_id": scope_id,
                    "score_threshold": threshold,
                    "case_id": row["case_id"],
                    "query_variant_type": row["query_variant_type"],
                    "failure_type": failure_type,
                    "scope_rule_id": row["scope_decision"]["rule_id"],
                    "first_relevant_rank": row["metrics"]["first_relevant_rank"],
                    "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
                })

    total_seconds = time.perf_counter() - started_clock
    manifest = {
        "experiment_id": experiment["experiment_id"],
        "experiment_version": experiment["experiment_version"],
        "run_status": "DRAFT_THRESHOLD_SCOPE_EXPERIMENT_COMPLETE",
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
            "path": retrieval_profile_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": file_sha256(retrieval_profile_path),
            "chunking_profile_path": (
                chunking_profile_path.relative_to(REPOSITORY_ROOT).as_posix()
            ),
            "provisional_chunking_profiles": [
                row["profile_id"] for row in selected_chunking
            ],
            "chunking_selection_status": experiment["chunking_selection_status"],
            "scope_policy_ids": [policy.policy_id for policy in scope_policies],
            "thresholds": thresholds,
        },
        "fixed_embedding": baseline["embedding"],
        "fixed_retrieval": fixed_retrieval,
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
            "publication_limits": experiment["publication_limits"],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_directory / "failure_analysis.json").write_text(
        json.dumps({
            "experiment_id": experiment["experiment_id"],
            "status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
            "policy": (
                "Scope 결정은 제품 코드와 질의어만 사용하며 Gold Label은 평가에만 사용"
            ),
            "items": failure_analysis,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="B2-1 Threshold·Scope Policy Experiment")
    parser.add_argument("--profiles", default=DEFAULT_RETRIEVAL_PROFILE)
    parser.add_argument("--chunking-profiles", default=DEFAULT_CHUNKING_PROFILE)
    parser.add_argument("--baseline-profile", default=DEFAULT_BASELINE_PROFILE)
    parser.add_argument("--output-directory", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-draft-gold", action="store_true")
    args = parser.parse_args()
    manifest = run_retrieval_threshold_scope_experiment(
        _resolve(args.profiles),
        _resolve(args.chunking_profiles),
        _resolve(args.baseline_profile),
        _resolve(args.output_directory),
        allow_draft_gold=args.allow_draft_gold,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
