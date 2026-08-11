#!/usr/bin/env python3
"""Run the B2-2 Query Intent·Domain Policy comparison."""

from __future__ import annotations

import argparse
import json
import platform
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator

from ai.evaluation.chunking import build_profile_chunks, profile_statistics
from ai.evaluation.file_integrity import file_sha256
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
from ai.scripts.run_retrieval_threshold_scope_experiment_v1 import (
    DEFAULT_RETRIEVAL_PROFILE as DEFAULT_SCOPE_PROFILE,
)


DEFAULT_INTENT_PROFILE = "ai/configs/experiments/query_intent_domain_profiles.yaml"
DEFAULT_OUTPUT = "ai/evaluation/reports/experiments/query_intent_domain_v1"


def _mean(rows: list[dict[str, Any]], metric: str) -> float | None:
    return (
        round(sum(row["metrics"][metric] for row in rows) / len(rows), 6)
        if rows else None
    )


def _retrieval_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if not row["expected_no_evidence"]]
    negatives = [row for row in rows if row["expected_no_evidence"]]
    latencies = [row["retrieval_latency_ms"] for row in rows]
    return {
        "case_count": len(rows),
        "positive_case_count": len(positives),
        "negative_case_count": len(negatives),
        "mean_hit_at_1": _mean(positives, "hit_at_1"),
        "mean_hit_at_5": _mean(positives, "hit_at_5"),
        "mean_mrr": _mean(positives, "mrr"),
        "mean_ndcg_at_5": _mean(positives, "ndcg_at_5"),
        "no_evidence_accuracy": (
            round(sum(row["metrics"]["no_evidence_passed"] for row in negatives) / len(negatives), 6)
            if negatives else None
        ),
        "scope_block_count": sum(row["scope_decision"]["blocked"] for row in rows),
        "intent_block_count": sum(row["intent_decision"]["blocked"] for row in rows),
        "positive_block_count": sum(
            row["combined_blocked"] for row in positives
        ),
        "wrong_product_hit_count": sum(
            row["metrics"]["wrong_product_hit_count"] for row in rows
        ),
        "retrieval_latency_p50_ms": _percentile(latencies, 50),
        "retrieval_latency_p95_ms": _percentile(latencies, 95),
    }


def _policy_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected_blocks = [row for row in rows if row["expected_decision"] == "BLOCK"]
    expected_allows = [row for row in rows if row["expected_decision"] == "ALLOW"]
    predicted_blocks = [row for row in rows if row["intent_decision"]["blocked"]]
    true_blocks = [
        row for row in expected_blocks if row["intent_decision"]["blocked"]
    ]
    true_allows = [
        row for row in expected_allows if not row["intent_decision"]["blocked"]
    ]
    correct = true_blocks + true_allows
    rule_matches = [
        row for row in expected_blocks
        if row["intent_decision"]["rule_id"] == row["expected_rule_id"]
    ]
    return {
        "case_count": len(rows),
        "decision_accuracy": round(len(correct) / len(rows), 6),
        "block_precision": (
            round(len(true_blocks) / len(predicted_blocks), 6)
            if predicted_blocks else None
        ),
        "block_recall": round(len(true_blocks) / len(expected_blocks), 6),
        "allow_accuracy": round(len(true_allows) / len(expected_allows), 6),
        "exact_rule_match_rate": round(len(rule_matches) / len(expected_blocks), 6),
        "false_block_case_ids": [
            row["case_id"] for row in expected_allows
            if row["intent_decision"]["blocked"]
        ],
        "missed_block_case_ids": [
            row["case_id"] for row in expected_blocks
            if not row["intent_decision"]["blocked"]
        ],
        "rule_counts": dict(sorted(Counter(
            row["intent_decision"]["rule_id"] for row in predicted_blocks
        ).items())),
    }


def run_query_intent_domain_experiment(
    intent_profile_path: Path,
    scope_profile_path: Path,
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
        raise RuntimeError("B2-2 Preflight 차단: " + ", ".join(preflight["blockers"]))

    experiment = _load_json(intent_profile_path)
    scope_config = _load_json(scope_profile_path)
    chunking_config = _load_json(chunking_profile_path)
    baseline = _load_json(baseline_profile_path)
    dataset_path = _resolve(experiment["dataset"]["path"])
    schema_path = _resolve(experiment["dataset"]["schema_path"])
    gold_path = _resolve(baseline["dataset"]["path"])
    source_path = _resolve(baseline["corpus"]["path"])
    supplemental_rows = _load_jsonl(dataset_path)
    validator = Draft202012Validator(_load_json(schema_path))
    for row in supplemental_rows:
        validator.validate(row)
    gold_rows = [
        row for row in _load_jsonl(gold_path)
        if row["split"] == baseline["dataset"]["split"]
    ]
    source_rows = _load_jsonl(source_path)

    fixed = experiment["fixed_retrieval"]
    chunking_profile = next(
        (
            row for row in chunking_config["profiles"]
            if row["profile_id"] == fixed["chunking_profile_id"]
        ),
        None,
    )
    if chunking_profile is None or chunking_profile.get("status") != "RUNNABLE":
        raise ValueError("B2-2 고정 Chunking Profile을 실행할 수 없습니다.")
    scope_definition = next(
        (
            row for row in scope_config["scope_policies"]
            if row["policy_id"] == fixed["scope_policy_id"]
        ),
        None,
    )
    if scope_definition is None:
        raise ValueError("B2-2 고정 Scope Policy를 찾을 수 없습니다.")
    scope_policy = ExperimentalQueryScopePolicy(scope_definition)
    intent_policies = [
        ExperimentalQueryIntentDomainPolicy(row)
        for row in experiment["intent_policies"]
    ]

    provider = embedding_provider or LocalBgeM3Provider(baseline)
    if provider.dimension != baseline["embedding"]["dimension"]:
        raise ValueError("Embedding Provider Dimension 불일치")
    chunks = build_profile_chunks(source_rows, chunking_profile)
    resolved_cache = cache_directory or _resolve(DEFAULT_CACHE)
    vectors, document_embedding_seconds, cache_hit, cache_key = _load_or_build_embeddings(
        [row["text"] for row in chunks],
        baseline["embedding"],
        provider,
        resolved_cache,
    )
    cases = [
        {**row, "dataset_kind": "SUPPLEMENTAL_DEV"}
        for row in supplemental_rows
    ] + [
        {**row, "dataset_kind": "GOLD_DEV"}
        for row in gold_rows
    ]
    query_clock = time.perf_counter()
    query_vectors = _normalize(provider.embed_queries([row["query"] for row in cases]))
    query_embedding_seconds = time.perf_counter() - query_clock
    candidates_by_model = {
        model: [
            index for index, chunk in enumerate(chunks)
            if chunk["exact_sales_code"] == model
        ]
        for model in {row["product_model_code"] for row in cases}
    }

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    threshold = float(fixed["score_threshold"])
    for intent_policy in intent_policies:
        for case_index, case in enumerate(cases):
            scope_decision = scope_policy.evaluate(
                product_model_code=case["product_model_code"],
                query=case["query"],
            )
            intent_decision = intent_policy.evaluate(
                product_model_code=case["product_model_code"],
                query=case["query"],
            )
            combined_blocked = scope_decision.blocked or intent_decision.blocked
            retrieval_clock = time.perf_counter()
            ranked: list[dict[str, Any]] = []
            if not combined_blocked:
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
                        if len(ranked) == fixed["top_k"]:
                            break
            latency_ms = (time.perf_counter() - retrieval_clock) * 1000
            expected_no_evidence = (
                case["expected_decision"] == "BLOCK"
                if case["dataset_kind"] == "SUPPLEMENTAL_DEV"
                else case["expected_no_evidence"]
            )
            metrics = _metrics(
                ranked,
                case["expected_evidence"],
                expected_no_evidence,
                case["product_model_code"],
            )
            result = {
                "dataset_kind": case["dataset_kind"],
                "intent_policy_id": intent_policy.policy_id,
                "case_id": case["case_id"],
                "query_variant_type": case.get("query_variant_type"),
                "expected_decision": case.get("expected_decision"),
                "expected_rule_id": case.get("expected_rule_id"),
                "expected_no_evidence": expected_no_evidence,
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
            }
            results.append(result)

            failure_type = None
            if case["dataset_kind"] == "SUPPLEMENTAL_DEV":
                predicted = "BLOCK" if intent_decision.blocked else "ALLOW"
                if predicted != case["expected_decision"]:
                    failure_type = "QUERY_INTENT_POLICY_ERROR"
                elif not expected_no_evidence and metrics["hit_at_5"] == 0:
                    failure_type = "RETRIEVAL_ERROR"
            elif combined_blocked and not expected_no_evidence:
                failure_type = "QUERY_POLICY_FALSE_BLOCK"
            elif expected_no_evidence and not metrics["no_evidence_passed"]:
                failure_type = "RETRIEVAL_ERROR"
            elif not expected_no_evidence and metrics["hit_at_5"] == 0:
                failure_type = "RETRIEVAL_ERROR"
            elif not expected_no_evidence and metrics["first_relevant_rank"] != 1:
                failure_type = "RERANK_ERROR"
            if failure_type:
                failures.append({
                    "dataset_kind": case["dataset_kind"],
                    "intent_policy_id": intent_policy.policy_id,
                    "case_id": case["case_id"],
                    "failure_type": failure_type,
                    "scope_rule_id": scope_decision.rule_id,
                    "intent_rule_id": intent_decision.rule_id,
                    "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
                })

    comparisons: list[dict[str, Any]] = []
    for intent_policy in intent_policies:
        policy_rows = [
            row for row in results
            if row["intent_policy_id"] == intent_policy.policy_id
        ]
        supplemental = [
            row for row in policy_rows if row["dataset_kind"] == "SUPPLEMENTAL_DEV"
        ]
        gold = [row for row in policy_rows if row["dataset_kind"] == "GOLD_DEV"]
        comparisons.append({
            "intent_policy_id": intent_policy.policy_id,
            "supplemental_policy": _policy_summary(supplemental),
            "supplemental_retrieval": _retrieval_summary(supplemental),
            "gold_dev_retrieval": _retrieval_summary(gold),
        })

    total_seconds = time.perf_counter() - started_clock
    manifest = {
        "experiment_id": experiment["experiment_id"],
        "experiment_version": experiment["experiment_version"],
        "run_status": "DRAFT_QUERY_INTENT_DOMAIN_EXPERIMENT_COMPLETE",
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "metrics_publishable_as_official": False,
        "selection_status": "PENDING_HUMAN_REVIEW_AND_PM_GATE",
        "datasets": {
            "supplemental": {
                "path": experiment["dataset"]["path"],
                "sha256": file_sha256(dataset_path),
                "schema_sha256": file_sha256(schema_path),
                "selected_cases": len(supplemental_rows),
            },
            "gold_dev": {
                "path": baseline["dataset"]["path"],
                "sha256": file_sha256(gold_path),
                "selected_cases": len(gold_rows),
            },
        },
        "source_corpus": {
            "path": baseline["corpus"]["path"],
            "sha256": file_sha256(source_path),
            "source_chunks": len(source_rows),
        },
        "profiles": {
            "intent_profile_path": intent_profile_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "intent_profile_sha256": file_sha256(intent_profile_path),
            "scope_profile_path": scope_profile_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "scope_profile_sha256": file_sha256(scope_profile_path),
            "intent_policy_ids": [policy.policy_id for policy in intent_policies],
            "fixed_retrieval": fixed,
            "chunk_structure": profile_statistics(source_rows, chunks),
        },
        "fixed_embedding": baseline["embedding"],
        "performance": {
            "document_embedding_seconds": round(document_embedding_seconds, 6),
            "document_embedding_cache_hit": cache_hit,
            "document_embedding_cache_key": cache_key,
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
            "policy": "Query·제품 코드만 정책 입력으로 사용하며 기대 Label은 평가에만 사용",
            "items": failures,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="B2-2 Query Intent·Domain Policy Experiment")
    parser.add_argument("--profiles", default=DEFAULT_INTENT_PROFILE)
    parser.add_argument("--scope-profiles", default=DEFAULT_SCOPE_PROFILE)
    parser.add_argument("--chunking-profiles", default=DEFAULT_CHUNKING_PROFILE)
    parser.add_argument("--baseline-profile", default=DEFAULT_BASELINE_PROFILE)
    parser.add_argument("--output-directory", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-draft-gold", action="store_true")
    args = parser.parse_args()
    manifest = run_query_intent_domain_experiment(
        _resolve(args.profiles),
        _resolve(args.scope_profiles),
        _resolve(args.chunking_profiles),
        _resolve(args.baseline_profile),
        _resolve(args.output_directory),
        allow_draft_gold=args.allow_draft_gold,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
