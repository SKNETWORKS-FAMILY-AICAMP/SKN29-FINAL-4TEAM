#!/usr/bin/env python3
"""Run the B2-3 BM25 versus Dense retrieval comparison."""

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
from ai.evaluation.lexical_retrieval import BM25Index, BM25Parameters
from ai.evaluation.query_intent_domain_policy import ExperimentalQueryIntentDomainPolicy
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
from ai.scripts.run_query_intent_domain_experiment_v1 import (
    DEFAULT_INTENT_PROFILE,
)
from ai.scripts.run_retrieval_threshold_scope_experiment_v1 import (
    DEFAULT_RETRIEVAL_PROFILE as DEFAULT_SCOPE_PROFILE,
)


DEFAULT_METHOD_PROFILE = "ai/configs/experiments/retrieval_method_profiles.yaml"
DEFAULT_OUTPUT = "ai/evaluation/reports/experiments/retrieval_method_comparison_v1"


def _mean(rows: list[dict[str, Any]], metric: str) -> float | None:
    return (
        round(sum(row["metrics"][metric] for row in rows) / len(rows), 6)
        if rows else None
    )


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if not row["expected_no_evidence"]]
    negatives = [row for row in rows if row["expected_no_evidence"]]
    latencies = [row["retrieval_latency_ms"] for row in rows]
    return {
        "case_count": len(rows),
        "positive_case_count": len(positives),
        "negative_case_count": len(negatives),
        "mean_hit_at_1": _mean(positives, "hit_at_1"),
        "mean_hit_at_3": _mean(positives, "hit_at_3"),
        "mean_hit_at_5": _mean(positives, "hit_at_5"),
        "mean_mrr": _mean(positives, "mrr"),
        "mean_ndcg_at_5": _mean(positives, "ndcg_at_5"),
        "wrong_product_hit_count": sum(
            row["metrics"]["wrong_product_hit_count"] for row in rows
        ),
        "no_evidence_accuracy": (
            round(sum(row["metrics"]["no_evidence_passed"] for row in negatives) / len(negatives), 6)
            if negatives else None
        ),
        "policy_block_count": sum(row["combined_blocked"] for row in rows),
        "positive_policy_block_count": sum(
            row["combined_blocked"] for row in positives
        ),
        "retrieval_latency_p50_ms": _percentile(latencies, 50),
        "retrieval_latency_p95_ms": _percentile(latencies, 95),
    }


def _variant_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["query_variant_type"]].append(row)
    return [
        {
            "query_variant_type": variant,
            **_summary(group),
        }
        for variant, group in sorted(grouped.items())
    ]


def _complementarity(
    dense_rows: list[dict[str, Any]],
    bm25_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    dense_by_id = {row["case_id"]: row for row in dense_rows}
    bm25_by_id = {row["case_id"]: row for row in bm25_rows}
    positive_ids = sorted(
        row["case_id"] for row in dense_rows if not row["expected_no_evidence"]
    )
    dense_hits = {
        case_id for case_id in positive_ids
        if dense_by_id[case_id]["metrics"]["hit_at_5"] == 1
    }
    bm25_hits = {
        case_id for case_id in positive_ids
        if bm25_by_id[case_id]["metrics"]["hit_at_5"] == 1
    }
    candidate_jaccards: list[float] = []
    for case_id in sorted(dense_by_id):
        dense_ids = {row["chunk_id"] for row in dense_by_id[case_id]["ranked_results"]}
        bm25_ids = {row["chunk_id"] for row in bm25_by_id[case_id]["ranked_results"]}
        union = dense_ids | bm25_ids
        if union:
            candidate_jaccards.append(len(dense_ids & bm25_ids) / len(union))
    return {
        "positive_case_count": len(positive_ids),
        "dense_hit_at_5_case_count": len(dense_hits),
        "bm25_hit_at_5_case_count": len(bm25_hits),
        "both_hit_case_count": len(dense_hits & bm25_hits),
        "dense_only_hit_case_ids": sorted(dense_hits - bm25_hits),
        "bm25_only_recovery_case_ids": sorted(bm25_hits - dense_hits),
        "both_miss_case_ids": sorted(set(positive_ids) - (dense_hits | bm25_hits)),
        "oracle_union_hit_at_5": round(len(dense_hits | bm25_hits) / len(positive_ids), 6),
        "candidate_overlap_case_count": len(candidate_jaccards),
        "mean_top5_candidate_jaccard": (
            round(sum(candidate_jaccards) / len(candidate_jaccards), 6)
            if candidate_jaccards else None
        ),
    }


def run_retrieval_method_comparison(
    method_profile_path: Path,
    scope_profile_path: Path,
    intent_profile_path: Path,
    chunking_profile_path: Path,
    baseline_profile_path: Path,
    output_directory: Path,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    allow_draft_gold: bool = False,
    cache_directory: Path | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    preflight = build_preflight_report(
        baseline_profile_path,
        allow_draft_gold=allow_draft_gold,
        embedding_provider_supplied=embedding_provider is not None,
    )
    if preflight["status"] != "READY":
        raise RuntimeError("B2-3 Preflight 차단: " + ", ".join(preflight["blockers"]))

    experiment = _load_json(method_profile_path)
    scope_config = _load_json(scope_profile_path)
    intent_config = _load_json(intent_profile_path)
    chunking_config = _load_json(chunking_profile_path)
    baseline = _load_json(baseline_profile_path)
    dataset_path = _resolve(baseline["dataset"]["path"])
    source_path = _resolve(baseline["corpus"]["path"])
    dataset_rows = [
        row for row in _load_jsonl(dataset_path)
        if row["split"] == experiment["dataset_split"]
    ]
    source_rows = _load_jsonl(source_path)
    controls = experiment["fixed_controls"]
    scope_definition = next(
        row for row in scope_config["scope_policies"]
        if row["policy_id"] == controls["scope_policy_id"]
    )
    intent_definition = next(
        row for row in intent_config["intent_policies"]
        if row["policy_id"] == controls["intent_policy_id"]
    )
    scope_policy = ExperimentalQueryScopePolicy(scope_definition)
    intent_policy = ExperimentalQueryIntentDomainPolicy(intent_definition)
    chunking_by_id = {row["profile_id"]: row for row in chunking_config["profiles"]}
    selected_chunking = []
    for profile_id in experiment["provisional_chunking_profiles"]:
        profile = chunking_by_id.get(profile_id)
        if profile is None or profile.get("status") != "RUNNABLE":
            raise ValueError(f"B2-3 Chunking Profile 실행 불가: {profile_id}")
        selected_chunking.append(profile)
    methods = {row["method_id"]: row for row in experiment["retrieval_methods"]}
    dense_method = next(row for row in methods.values() if row["method"] == "dense_cosine_exact")
    bm25_method = next(row for row in methods.values() if row["method"] == "bm25")

    provider = embedding_provider or LocalBgeM3Provider(baseline)
    if provider.dimension != baseline["embedding"]["dimension"]:
        raise ValueError("Embedding Provider Dimension 불일치")
    query_started = time.perf_counter()
    query_vectors = _normalize(provider.embed_queries([row["query"] for row in dataset_rows]))
    query_embedding_seconds = time.perf_counter() - query_started
    resolved_cache = cache_directory or _resolve(DEFAULT_CACHE)
    results: list[dict[str, Any]] = []
    structures: dict[str, dict[str, Any]] = {}

    for chunking_profile in selected_chunking:
        chunks = build_profile_chunks(source_rows, chunking_profile)
        dense_vectors, embedding_seconds, cache_hit, cache_key = _load_or_build_embeddings(
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
        candidate_indexes = {
            model: [
                index for index, chunk in enumerate(chunks)
                if chunk["exact_sales_code"] == model
            ]
            for model in {row["product_model_code"] for row in dataset_rows}
        }
        bm25_indexes = {
            model: BM25Index(
                [chunks[index]["text"] for index in indexes],
                parameters=BM25Parameters(k1=float(bm25_method["k1"]), b=float(bm25_method["b"])),
            )
            for model, indexes in candidate_indexes.items()
            if indexes
        }
        for case_index, case in enumerate(dataset_rows):
            scope_decision = scope_policy.evaluate(
                product_model_code=case["product_model_code"], query=case["query"]
            )
            intent_decision = intent_policy.evaluate(
                product_model_code=case["product_model_code"], query=case["query"]
            )
            combined_blocked = scope_decision.blocked or intent_decision.blocked
            candidates = candidate_indexes.get(case["product_model_code"], [])
            for method in (dense_method, bm25_method):
                retrieval_started = time.perf_counter()
                scored: list[tuple[int, float]] = []
                if not combined_blocked and candidates:
                    if method["method"] == "dense_cosine_exact":
                        scores = dense_vectors[candidates] @ query_vectors[case_index]
                        scored = [
                            (candidates[index], float(score))
                            for index, score in enumerate(scores)
                            if float(score) >= float(method["score_threshold"])
                        ]
                    else:
                        scores = bm25_indexes[case["product_model_code"]].scores(case["query"])
                        scored = [
                            (candidates[index], float(score))
                            for index, score in enumerate(scores)
                            if float(score) > float(method["minimum_score_exclusive"])
                        ]
                    scored.sort(key=lambda item: (-item[1], chunks[item[0]]["chunk_id"]))
                    scored = scored[: controls["top_k"]]
                latency_ms = (time.perf_counter() - retrieval_started) * 1000
                ranked = [{"chunk": chunks[index], "score": score} for index, score in scored]
                metrics = _metrics(
                    ranked,
                    case["expected_evidence"],
                    case["expected_no_evidence"],
                    case["product_model_code"],
                )
                results.append({
                    "chunking_profile_id": chunking_profile["profile_id"],
                    "method_id": method["method_id"],
                    "case_id": case["case_id"],
                    "query_variant_type": case["query_variant_type"],
                    "expected_no_evidence": case["expected_no_evidence"],
                    "scope_decision": scope_decision.as_dict(),
                    "intent_decision": intent_decision.as_dict(),
                    "combined_blocked": combined_blocked,
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
        grouped[(row["chunking_profile_id"], row["method_id"])].append(row)
    comparisons = [
        {
            "chunking_profile_id": chunking_id,
            "method_id": method_id,
            **_summary(rows),
            "query_variant_breakdown": _variant_breakdown(rows),
            "structure": structures[chunking_id],
        }
        for (chunking_id, method_id), rows in sorted(grouped.items())
    ]
    complementarity = []
    for chunking_profile in selected_chunking:
        profile_id = chunking_profile["profile_id"]
        complementarity.append({
            "chunking_profile_id": profile_id,
            **_complementarity(
                grouped[(profile_id, dense_method["method_id"])],
                grouped[(profile_id, bm25_method["method_id"])],
            ),
        })

    failures = []
    for row in results:
        failure_type = None
        if row["combined_blocked"] and not row["expected_no_evidence"]:
            failure_type = "QUERY_POLICY_FALSE_BLOCK"
        elif row["expected_no_evidence"] and not row["metrics"]["no_evidence_passed"]:
            failure_type = "RETRIEVAL_ERROR"
        elif not row["expected_no_evidence"] and row["metrics"]["hit_at_5"] == 0:
            failure_type = "RETRIEVAL_ERROR"
        elif not row["expected_no_evidence"] and row["metrics"]["first_relevant_rank"] != 1:
            failure_type = "RERANK_ERROR"
        if failure_type:
            failures.append({
                "chunking_profile_id": row["chunking_profile_id"],
                "method_id": row["method_id"],
                "case_id": row["case_id"],
                "query_variant_type": row["query_variant_type"],
                "failure_type": failure_type,
                "first_relevant_rank": row["metrics"]["first_relevant_rank"],
                "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
            })

    manifest = {
        "experiment_id": experiment["experiment_id"],
        "experiment_version": experiment["experiment_version"],
        "run_status": "DRAFT_RETRIEVAL_METHOD_COMPARISON_COMPLETE",
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
            "method_profile_path": method_profile_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "method_profile_sha256": file_sha256(method_profile_path),
            "scope_profile_sha256": file_sha256(scope_profile_path),
            "intent_profile_sha256": file_sha256(intent_profile_path),
            "chunking_profile_ids": [row["profile_id"] for row in selected_chunking],
            "retrieval_method_ids": list(methods),
            "fixed_controls": controls,
        },
        "fixed_embedding": baseline["embedding"],
        "performance": {
            "query_embedding_seconds": round(query_embedding_seconds, 6),
            "total_seconds": round(time.perf_counter() - started_clock, 6),
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
    for name, payload in (
        ("preflight.json", preflight),
        ("manifest.json", manifest),
        ("summary.json", {
            "experiment_id": experiment["experiment_id"],
            "run_status": manifest["run_status"],
            "metrics_publishable_as_official": False,
            "selection_status": manifest["selection_status"],
            "comparisons": comparisons,
            "complementarity": complementarity,
            "publication_limits": experiment["publication_limits"],
        }),
        ("failure_analysis.json", {
            "experiment_id": experiment["experiment_id"],
            "status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
            "items": failures,
        }),
    ):
        (output_directory / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (output_directory / "case_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="B2-3 BM25 vs Dense Experiment")
    parser.add_argument("--profiles", default=DEFAULT_METHOD_PROFILE)
    parser.add_argument("--scope-profiles", default=DEFAULT_SCOPE_PROFILE)
    parser.add_argument("--intent-profiles", default=DEFAULT_INTENT_PROFILE)
    parser.add_argument("--chunking-profiles", default=DEFAULT_CHUNKING_PROFILE)
    parser.add_argument("--baseline-profile", default=DEFAULT_BASELINE_PROFILE)
    parser.add_argument("--output-directory", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-draft-gold", action="store_true")
    args = parser.parse_args()
    manifest = run_retrieval_method_comparison(
        _resolve(args.profiles),
        _resolve(args.scope_profiles),
        _resolve(args.intent_profiles),
        _resolve(args.chunking_profiles),
        _resolve(args.baseline_profile),
        _resolve(args.output_directory),
        allow_draft_gold=args.allow_draft_gold,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
