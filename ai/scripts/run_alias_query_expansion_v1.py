#!/usr/bin/env python3
"""Run the B2-4 original-query versus draft-alias dense comparison."""

from __future__ import annotations

import argparse
import json
import platform
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai.evaluation.chunking import build_profile_chunks, profile_statistics
from ai.evaluation.file_integrity import file_sha256
from ai.evaluation.query_expansion import DraftAliasQueryExpander
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
from ai.scripts.run_query_intent_domain_experiment_v1 import DEFAULT_INTENT_PROFILE
from ai.scripts.run_retrieval_threshold_scope_experiment_v1 import (
    DEFAULT_RETRIEVAL_PROFILE as DEFAULT_SCOPE_PROFILE,
)


DEFAULT_ALIAS_PROFILE = "ai/configs/experiments/alias_query_expansion_profiles.yaml"
DEFAULT_OUTPUT = "ai/evaluation/reports/experiments/alias_query_expansion_v1"


def _mean(rows: list[dict[str, Any]], metric: str) -> float | None:
    values = [
        row["metrics"][metric]
        for row in rows
        if row["metrics"][metric] is not None
    ]
    return round(sum(values) / len(values), 6) if values else None


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
        "no_evidence_accuracy": (
            round(
                sum(row["metrics"]["no_evidence_passed"] for row in negatives)
                / len(negatives),
                6,
            )
            if negatives
            else None
        ),
        "wrong_product_hit_count": sum(
            row["metrics"]["wrong_product_hit_count"] for row in rows
        ),
        "retrieval_latency_p50_ms": _percentile(latencies, 50),
        "retrieval_latency_p95_ms": _percentile(latencies, 95),
    }


def _build_preflight(
    alias_profile_path: Path,
    baseline_profile_path: Path,
    *,
    allow_draft_gold: bool,
    allow_draft_aliases: bool,
    embedding_provider_supplied: bool,
) -> dict[str, Any]:
    base = build_preflight_report(
        baseline_profile_path,
        allow_draft_gold=allow_draft_gold,
        embedding_provider_supplied=embedding_provider_supplied,
    )
    experiment = _load_json(alias_profile_path)
    baseline = _load_json(baseline_profile_path)
    dataset_rows = _load_jsonl(_resolve(baseline["dataset"]["path"]))
    selected_rows = [
        row for row in dataset_rows if row["split"] == experiment["dataset_split"]
    ]
    selected_ids = {row["case_id"] for row in selected_rows}
    target_ids = {
        case_id
        for rule in experiment["alias_policy"]["rules"]
        for case_id in rule["target_case_ids"]
    }
    expected_activation_ids = {
        case_id
        for rule in experiment["alias_policy"]["rules"]
        for case_id in rule["expected_activation_case_ids"]
    }
    checks = [
        {
            "name": "base_experiment_preflight",
            "passed": base["status"] == "READY",
            "detail": {"base_status": base["status"], "base_blockers": base["blockers"]},
        },
        {
            "name": "draft_alias_explicit_opt_in",
            "passed": (
                experiment["alias_policy"]["review_status"] == "TWO_PERSON_APPROVED"
                or allow_draft_aliases
            ),
            "detail": {
                "review_status": experiment["alias_policy"]["review_status"],
                "allow_draft_aliases": allow_draft_aliases,
            },
        },
        {
            "name": "target_cases_exist_in_selected_split",
            "passed": target_ids.issubset(selected_ids)
            and expected_activation_ids.issubset(selected_ids),
            "detail": {
                "target_case_ids": sorted(target_ids),
                "expected_activation_case_ids": sorted(expected_activation_ids),
                "missing_case_ids": sorted(
                    (target_ids | expected_activation_ids) - selected_ids
                ),
            },
        },
        {
            "name": "hard_negative_case_ids_unique",
            "passed": len({row["case_id"] for row in experiment["hard_negative_cases"]})
            == len(experiment["hard_negative_cases"]),
            "detail": {"case_count": len(experiment["hard_negative_cases"])},
        },
    ]
    blockers = [row["name"] for row in checks if not row["passed"]]
    return {
        "preflight_id": "B2-4-ALIAS-QUERY-EXPANSION-PREFLIGHT",
        "status": "READY" if not blockers else "BLOCKED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_preflight": base,
        "checks": checks,
        "blockers": blockers,
    }


def _comparison(
    baseline_rows: list[dict[str, Any]],
    expanded_rows: list[dict[str, Any]],
    target_case_ids: set[str],
    expected_activation_case_ids: set[str],
) -> dict[str, Any]:
    baseline_by_id = {row["case_id"]: row for row in baseline_rows}
    expanded_by_id = {row["case_id"]: row for row in expanded_rows}
    positive_ids = {
        row["case_id"] for row in baseline_rows if not row["expected_no_evidence"]
    }
    negative_ids = set(baseline_by_id) - positive_ids
    recovered = {
        case_id
        for case_id in positive_ids
        if baseline_by_id[case_id]["metrics"]["hit_at_5"] == 0
        and expanded_by_id[case_id]["metrics"]["hit_at_5"] == 1
    }
    regressed = {
        case_id
        for case_id in positive_ids
        if baseline_by_id[case_id]["metrics"]["hit_at_5"] == 1
        and expanded_by_id[case_id]["metrics"]["hit_at_5"] == 0
    }
    negative_regressions = {
        case_id
        for case_id in negative_ids
        if baseline_by_id[case_id]["metrics"]["no_evidence_passed"]
        and not expanded_by_id[case_id]["metrics"]["no_evidence_passed"]
    }
    alias_activated = {
        row["case_id"]
        for row in expanded_rows
        if row["expansion_decision"]["applied"]
    }
    return {
        "target_case_ids": sorted(target_case_ids),
        "expected_activation_case_ids": sorted(expected_activation_case_ids),
        "alias_activated_case_ids": sorted(alias_activated),
        "unexpected_alias_activation_case_ids": sorted(
            alias_activated - expected_activation_case_ids
        ),
        "missing_expected_alias_activation_case_ids": sorted(
            expected_activation_case_ids - alias_activated
        ),
        "recovered_positive_case_ids": sorted(recovered),
        "target_recovery_case_ids": sorted(recovered & target_case_ids),
        "positive_regression_case_ids": sorted(regressed),
        "negative_regression_case_ids": sorted(negative_regressions),
        "metric_delta": {
            metric: round(
                (_summary(expanded_rows)[metric] or 0)
                - (_summary(baseline_rows)[metric] or 0),
                6,
            )
            for metric in (
                "mean_hit_at_1",
                "mean_hit_at_3",
                "mean_hit_at_5",
                "mean_mrr",
                "mean_ndcg_at_5",
                "no_evidence_accuracy",
            )
        },
    }


def run_alias_query_expansion(
    alias_profile_path: Path,
    scope_profile_path: Path,
    intent_profile_path: Path,
    chunking_profile_path: Path,
    baseline_profile_path: Path,
    output_directory: Path,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    allow_draft_gold: bool = False,
    allow_draft_aliases: bool = False,
    cache_directory: Path | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    preflight = _build_preflight(
        alias_profile_path,
        baseline_profile_path,
        allow_draft_gold=allow_draft_gold,
        allow_draft_aliases=allow_draft_aliases,
        embedding_provider_supplied=embedding_provider is not None,
    )
    if preflight["status"] != "READY":
        raise RuntimeError("B2-4 Preflight 차단: " + ", ".join(preflight["blockers"]))

    experiment = _load_json(alias_profile_path)
    scope_config = _load_json(scope_profile_path)
    intent_config = _load_json(intent_profile_path)
    chunking_config = _load_json(chunking_profile_path)
    baseline = _load_json(baseline_profile_path)
    dataset_path = _resolve(baseline["dataset"]["path"])
    source_path = _resolve(baseline["corpus"]["path"])
    dataset_rows = [
        row
        for row in _load_jsonl(dataset_path)
        if row["split"] == experiment["dataset_split"]
    ]
    source_rows = _load_jsonl(source_path)
    controls = experiment["fixed_controls"]
    scope_definition = next(
        row
        for row in scope_config["scope_policies"]
        if row["policy_id"] == controls["scope_policy_id"]
    )
    intent_definition = next(
        row
        for row in intent_config["intent_policies"]
        if row["policy_id"] == controls["intent_policy_id"]
    )
    scope_policy = ExperimentalQueryScopePolicy(scope_definition)
    intent_policy = ExperimentalQueryIntentDomainPolicy(intent_definition)
    expander = DraftAliasQueryExpander(experiment["alias_policy"])
    chunking_profile = next(
        (
            row
            for row in chunking_config["profiles"]
            if row["profile_id"] == experiment["chunking_profile_id"]
        ),
        None,
    )
    if chunking_profile is None or chunking_profile.get("status") != "RUNNABLE":
        raise ValueError(
            f"B2-4 Chunking Profile 실행 불가: {experiment['chunking_profile_id']}"
        )

    variants = experiment["variants"]
    if len(variants) != 2 or {row["query_expansion"] for row in variants} != {
        False,
        True,
    }:
        raise ValueError("B2-4는 원문·Alias 확장 Variant 각각 1개가 필요합니다.")
    baseline_variant = next(row for row in variants if not row["query_expansion"])
    expanded_variant = next(row for row in variants if row["query_expansion"])
    target_case_ids = {
        case_id
        for rule in experiment["alias_policy"]["rules"]
        for case_id in rule["target_case_ids"]
    }
    expected_activation_case_ids = {
        case_id
        for rule in experiment["alias_policy"]["rules"]
        for case_id in rule["expected_activation_case_ids"]
    }

    decisions = {
        row["case_id"]: expander.expand(row["query"]) for row in dataset_rows
    }
    hard_negative_decisions = {
        row["case_id"]: expander.expand(row["query"])
        for row in experiment["hard_negative_cases"]
    }
    query_specs: list[tuple[str, str, str]] = []
    for row in dataset_rows:
        decision = decisions[row["case_id"]]
        query_specs.extend(
            [
                (row["case_id"], baseline_variant["variant_id"], row["query"]),
                (
                    row["case_id"],
                    expanded_variant["variant_id"],
                    decision.expanded_query,
                ),
            ]
        )
    for row in experiment["hard_negative_cases"]:
        decision = hard_negative_decisions[row["case_id"]]
        query_specs.extend(
            [
                (row["case_id"], baseline_variant["variant_id"], row["query"]),
                (
                    row["case_id"],
                    expanded_variant["variant_id"],
                    decision.expanded_query,
                ),
            ]
        )

    provider = embedding_provider or LocalBgeM3Provider(baseline)
    if provider.dimension != baseline["embedding"]["dimension"]:
        raise ValueError("Embedding Provider Dimension 불일치")
    query_started = time.perf_counter()
    query_vectors = _normalize(
        provider.embed_queries([query_text for _, _, query_text in query_specs])
    )
    query_embedding_seconds = time.perf_counter() - query_started
    query_vector_by_key = {
        (case_id, variant_id): query_vectors[index]
        for index, (case_id, variant_id, _) in enumerate(query_specs)
    }

    chunks = build_profile_chunks(source_rows, chunking_profile)
    resolved_cache = cache_directory or _resolve(DEFAULT_CACHE)
    dense_vectors, embedding_seconds, cache_hit, cache_key = _load_or_build_embeddings(
        [row["text"] for row in chunks],
        baseline["embedding"],
        provider,
        resolved_cache,
    )
    candidate_indexes = {
        model: [
            index
            for index, chunk in enumerate(chunks)
            if chunk["exact_sales_code"] == model
        ]
        for model in {
            *[row["product_model_code"] for row in dataset_rows],
            *[
                row["product_model_code"]
                for row in experiment["hard_negative_cases"]
            ],
        }
    }

    def retrieve(
        *,
        case_id: str,
        product_model_code: str,
        original_query: str,
        variant: dict[str, Any],
        decision,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], bool, float]:
        scope_decision = scope_policy.evaluate(
            product_model_code=product_model_code,
            query=original_query,
        )
        intent_decision = intent_policy.evaluate(
            product_model_code=product_model_code,
            query=original_query,
        )
        combined_blocked = scope_decision.blocked or intent_decision.blocked
        candidates = candidate_indexes.get(product_model_code, [])
        retrieval_started = time.perf_counter()
        scored: list[tuple[int, float]] = []
        if not combined_blocked and candidates:
            scores = dense_vectors[candidates] @ query_vector_by_key[
                (case_id, variant["variant_id"])
            ]
            scored = [
                (candidates[index], float(score))
                for index, score in enumerate(scores)
                if float(score) >= float(controls["score_threshold"])
            ]
            scored.sort(key=lambda item: (-item[1], chunks[item[0]]["chunk_id"]))
            scored = scored[: controls["top_k"]]
        latency_ms = (time.perf_counter() - retrieval_started) * 1000
        ranked = [{"chunk": chunks[index], "score": score} for index, score in scored]
        return (
            ranked,
            scope_decision.as_dict(),
            intent_decision.as_dict(),
            combined_blocked,
            latency_ms,
        )

    results: list[dict[str, Any]] = []
    for case in dataset_rows:
        decision = decisions[case["case_id"]]
        for variant in variants:
            ranked, scope_decision, intent_decision, blocked, latency_ms = retrieve(
                case_id=case["case_id"],
                product_model_code=case["product_model_code"],
                original_query=case["query"],
                variant=variant,
                decision=decision,
            )
            results.append(
                {
                    "variant_id": variant["variant_id"],
                    "case_id": case["case_id"],
                    "query_variant_type": case["query_variant_type"],
                    "expected_no_evidence": case["expected_no_evidence"],
                    "original_query": case["query"],
                    "retrieval_query": (
                        decision.expanded_query
                        if variant["query_expansion"]
                        else case["query"]
                    ),
                    "query_expansion_applied": bool(
                        variant["query_expansion"] and decision.applied
                    ),
                    "expansion_decision": decision.as_dict(),
                    "scope_decision": scope_decision,
                    "intent_decision": intent_decision,
                    "combined_blocked": blocked,
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
                    "metrics": _metrics(
                        ranked,
                        case["expected_evidence"],
                        case["expected_no_evidence"],
                        case["product_model_code"],
                        case["evidence_match_policy"],
                    ),
                    "retrieval_latency_ms": round(latency_ms, 6),
                }
            )

    hard_negative_results: list[dict[str, Any]] = []
    for case in experiment["hard_negative_cases"]:
        decision = hard_negative_decisions[case["case_id"]]
        for variant in variants:
            ranked, scope_decision, intent_decision, blocked, latency_ms = retrieve(
                case_id=case["case_id"],
                product_model_code=case["product_model_code"],
                original_query=case["query"],
                variant=variant,
                decision=decision,
            )
            hard_negative_results.append(
                {
                    "variant_id": variant["variant_id"],
                    "case_id": case["case_id"],
                    "original_query": case["query"],
                    "retrieval_query": (
                        decision.expanded_query
                        if variant["query_expansion"]
                        else case["query"]
                    ),
                    "expected_alias_rule_ids": case["expected_alias_rule_ids"],
                    "expansion_decision": decision.as_dict(),
                    "scope_decision": scope_decision,
                    "intent_decision": intent_decision,
                    "combined_blocked": blocked,
                    "ranked_chunk_ids": [item["chunk"]["chunk_id"] for item in ranked],
                    "retrieval_latency_ms": round(latency_ms, 6),
                }
            )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[row["variant_id"]].append(row)
    baseline_rows = grouped[baseline_variant["variant_id"]]
    expanded_rows = grouped[expanded_variant["variant_id"]]
    comparison = _comparison(
        baseline_rows,
        expanded_rows,
        target_case_ids,
        expected_activation_case_ids,
    )

    hard_by_variant: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in hard_negative_results:
        hard_by_variant[row["variant_id"]][row["case_id"]] = row
    hard_unexpected_activation = []
    hard_new_results = []
    for case in experiment["hard_negative_cases"]:
        case_id = case["case_id"]
        expanded = hard_by_variant[expanded_variant["variant_id"]][case_id]
        original = hard_by_variant[baseline_variant["variant_id"]][case_id]
        if expanded["expansion_decision"]["applied_rule_ids"] != case[
            "expected_alias_rule_ids"
        ]:
            hard_unexpected_activation.append(case_id)
        if not original["ranked_chunk_ids"] and expanded["ranked_chunk_ids"]:
            hard_new_results.append(case_id)
    hard_negative_summary = {
        "case_count": len(experiment["hard_negative_cases"]),
        "unexpected_alias_activation_case_ids": sorted(hard_unexpected_activation),
        "new_retrieval_result_case_ids": sorted(hard_new_results),
    }

    baseline_by_id = {row["case_id"]: row for row in baseline_rows}
    expanded_by_id = {row["case_id"]: row for row in expanded_rows}
    recovered_ids = set(comparison["recovered_positive_case_ids"])
    positive_regression_ids = set(comparison["positive_regression_case_ids"])
    rule_outcomes = []
    for rule in experiment["alias_policy"]["rules"]:
        rule_id = rule["rule_id"]
        target_ids = set(rule["target_case_ids"])
        expected_ids = set(rule["expected_activation_case_ids"])
        activated_ids = {
            row["case_id"]
            for row in expanded_rows
            if rule_id in row["expansion_decision"]["applied_rule_ids"]
        }
        unexpected_ids = activated_ids - expected_ids
        missing_expected_ids = expected_ids - activated_ids
        rule_hard_negative_ids = {
            row["case_id"]
            for row in hard_negative_results
            if row["variant_id"] == expanded_variant["variant_id"]
            and rule_id in row["expansion_decision"]["applied_rule_ids"]
            and rule_id not in row["expected_alias_rule_ids"]
        }
        recovered_target_ids = recovered_ids & target_ids
        ranking_improvement_ids = {
            case_id
            for case_id in activated_ids
            if not expanded_by_id[case_id]["expected_no_evidence"]
            and expanded_by_id[case_id]["metrics"]["first_relevant_rank"]
            is not None
            and (
                baseline_by_id[case_id]["metrics"]["first_relevant_rank"] is None
                or (
                    expanded_by_id[case_id]["metrics"]["first_relevant_rank"]
                    < baseline_by_id[case_id]["metrics"]["first_relevant_rank"]
                )
            )
        }
        supported = bool(recovered_target_ids) and not (
            unexpected_ids
            or missing_expected_ids
            or rule_hard_negative_ids
            or (positive_regression_ids & activated_ids)
        )
        rule_outcomes.append(
            {
                "rule_id": rule_id,
                "status": (
                    "SUPPORTED_ON_DRAFT_DEV_PENDING_REVIEW"
                    if supported
                    else "NOT_SUPPORTED_ON_CURRENT_DRAFT_DEV"
                ),
                "target_case_ids": sorted(target_ids),
                "expected_activation_case_ids": sorted(expected_ids),
                "activated_case_ids": sorted(activated_ids),
                "recovered_target_case_ids": sorted(recovered_target_ids),
                "ranking_improvement_case_ids": sorted(ranking_improvement_ids),
                "unexpected_activation_case_ids": sorted(unexpected_ids),
                "missing_expected_activation_case_ids": sorted(
                    missing_expected_ids
                ),
                "hard_negative_activation_case_ids": sorted(
                    rule_hard_negative_ids
                ),
                "positive_regression_case_ids": sorted(
                    positive_regression_ids & activated_ids
                ),
            }
        )

    gates = experiment["success_gate"]
    gate_results = {
        "minimum_target_recovery_count": len(
            comparison["target_recovery_case_ids"]
        )
        >= gates["minimum_target_recovery_count"],
        "maximum_positive_regression_count": len(
            comparison["positive_regression_case_ids"]
        )
        <= gates["maximum_positive_regression_count"],
        "maximum_negative_regression_count": len(
            comparison["negative_regression_case_ids"]
        )
        <= gates["maximum_negative_regression_count"],
        "maximum_unexpected_alias_activation_count": len(
            comparison["unexpected_alias_activation_case_ids"]
        )
        <= gates["maximum_unexpected_alias_activation_count"],
        "maximum_missing_expected_alias_activation_count": len(
            comparison["missing_expected_alias_activation_case_ids"]
        )
        <= gates["maximum_missing_expected_alias_activation_count"],
        "maximum_hard_negative_unexpected_activation_count": len(
            hard_unexpected_activation
        )
        <= gates["maximum_hard_negative_unexpected_activation_count"],
        "maximum_hard_negative_new_result_count": len(hard_new_results)
        <= gates["maximum_hard_negative_new_result_count"],
    }
    gate_passed = all(gate_results.values())
    supported_rule_count = sum(
        row["status"] == "SUPPORTED_ON_DRAFT_DEV_PENDING_REVIEW"
        for row in rule_outcomes
    )
    if gate_passed and supported_rule_count == len(rule_outcomes):
        selection_status = "DRAFT_ALIAS_CANDIDATE_SUPPORTED_PENDING_REVIEW"
    elif gate_passed and supported_rule_count:
        selection_status = "DRAFT_ALIAS_CANDIDATE_PARTIALLY_SUPPORTED_PENDING_REVIEW"
    else:
        selection_status = "DRAFT_ALIAS_CANDIDATE_NOT_SUPPORTED"

    failures = [
        {
            "case_id": row["case_id"],
            "failure_type": "POSITIVE_RETRIEVAL_MISS",
            "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
        }
        for row in expanded_rows
        if not row["expected_no_evidence"] and row["metrics"]["hit_at_5"] == 0
    ]
    failures.extend(
        {
            "case_id": case_id,
            "failure_type": "ALIAS_POSITIVE_REGRESSION",
            "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
        }
        for case_id in comparison["positive_regression_case_ids"]
    )
    failures.extend(
        {
            "case_id": case_id,
            "failure_type": "ALIAS_HARD_NEGATIVE_UNEXPECTED_ACTIVATION",
            "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
        }
        for case_id in hard_unexpected_activation
    )
    failures.extend(
        {
            "rule_id": row["rule_id"],
            "failure_type": "ALIAS_RULE_NO_TARGET_RECOVERY",
            "target_case_ids": row["target_case_ids"],
            "review_status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
        }
        for row in rule_outcomes
        if not row["recovered_target_case_ids"]
    )

    manifest = {
        "experiment_id": experiment["experiment_id"],
        "experiment_version": experiment["experiment_version"],
        "run_status": "DRAFT_ALIAS_QUERY_EXPANSION_COMPARISON_COMPLETE",
        "selection_status": selection_status,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "metrics_publishable_as_official": False,
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
            "alias_profile_path": alias_profile_path.relative_to(
                REPOSITORY_ROOT
            ).as_posix(),
            "alias_profile_sha256": file_sha256(alias_profile_path),
            "scope_profile_sha256": file_sha256(scope_profile_path),
            "intent_profile_sha256": file_sha256(intent_profile_path),
            "chunking_profile_id": chunking_profile["profile_id"],
            "variants": variants,
            "fixed_controls": controls,
        },
        "fixed_embedding": baseline["embedding"],
        "structure": {
            **profile_statistics(source_rows, chunks),
            "document_embedding_seconds": round(embedding_seconds, 6),
            "embedding_cache_hit": cache_hit,
            "embedding_cache_key": cache_key,
        },
        "performance": {
            "query_embedding_seconds": round(query_embedding_seconds, 6),
            "total_seconds": round(time.perf_counter() - started_clock, 6),
            "case_result_count": len(results),
            "hard_negative_result_count": len(hard_negative_results),
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
    payloads = {
        "preflight.json": preflight,
        "manifest.json": manifest,
        "summary.json": {
            "experiment_id": experiment["experiment_id"],
            "run_status": manifest["run_status"],
            "selection_status": selection_status,
            "metrics_publishable_as_official": False,
            "variant_summaries": [
                {
                    "variant_id": variant_id,
                    **_summary(rows),
                }
                for variant_id, rows in sorted(grouped.items())
            ],
            "comparison": comparison,
            "rule_outcomes": rule_outcomes,
            "hard_negative_summary": hard_negative_summary,
            "success_gate": {
                "requirements": gates,
                "results": gate_results,
                "passed": gate_passed,
            },
            "publication_limits": experiment["publication_limits"],
        },
        "failure_analysis.json": {
            "experiment_id": experiment["experiment_id"],
            "status": "AUTOMATED_TRIAGE_REVIEW_REQUIRED",
            "items": failures,
        },
    }
    for name, payload in payloads.items():
        (output_directory / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (output_directory / "case_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
        encoding="utf-8",
    )
    (output_directory / "hard_negative_results.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n"
            for row in hard_negative_results
        ),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="B2-4 Draft Alias Query Expansion Experiment"
    )
    parser.add_argument("--profiles", default=DEFAULT_ALIAS_PROFILE)
    parser.add_argument("--scope-profiles", default=DEFAULT_SCOPE_PROFILE)
    parser.add_argument("--intent-profiles", default=DEFAULT_INTENT_PROFILE)
    parser.add_argument("--chunking-profiles", default=DEFAULT_CHUNKING_PROFILE)
    parser.add_argument("--baseline-profile", default=DEFAULT_BASELINE_PROFILE)
    parser.add_argument("--output-directory", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-draft-gold", action="store_true")
    parser.add_argument("--allow-draft-aliases", action="store_true")
    args = parser.parse_args()
    manifest = run_alias_query_expansion(
        _resolve(args.profiles),
        _resolve(args.scope_profiles),
        _resolve(args.intent_profiles),
        _resolve(args.chunking_profiles),
        _resolve(args.baseline_profile),
        _resolve(args.output_directory),
        allow_draft_gold=args.allow_draft_gold,
        allow_draft_aliases=args.allow_draft_aliases,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
