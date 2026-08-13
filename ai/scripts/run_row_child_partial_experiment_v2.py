#!/usr/bin/env python3
"""Run the D04 row-child partial-scope diagnostic without changing runtime RAG."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ai.evaluation.file_integrity import file_sha256
from ai.evaluation.row_child_partial import (
    build_partial_replacement_corpus,
    expand_parent_context,
)
from ai.scripts.run_chunking_experiment_v1 import (
    DEFAULT_CACHE,
    _load_or_build_embeddings,
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


DEFAULT_EXPERIMENT = "ai/configs/experiments/row_child_partial_v2.yaml"
DEFAULT_OUTPUT = "ai/evaluation/reports/experiments/row_child_partial_v2"


def _mean(rows: list[dict[str, Any]], metric: str) -> float | None:
    values = [row["metrics"][metric] for row in rows if row["metrics"][metric] is not None]
    return round(sum(values) / len(values), 6) if values else None


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(rows),
        "mean_hit_at_1": _mean(rows, "hit_at_1"),
        "mean_hit_at_3": _mean(rows, "hit_at_3"),
        "mean_hit_at_5": _mean(rows, "hit_at_5"),
        "mean_mrr": _mean(rows, "mrr"),
        "mean_ndcg_at_5": _mean(rows, "ndcg_at_5"),
    }


def _build_preflight(
    experiment_path: Path,
    baseline_path: Path,
    *,
    allow_draft_gold: bool,
    embedding_provider_supplied: bool,
) -> dict[str, Any]:
    base = build_preflight_report(
        baseline_path,
        allow_draft_gold=allow_draft_gold,
        embedding_provider_supplied=embedding_provider_supplied,
    )
    experiment = _load_json(experiment_path)
    baseline = _load_json(baseline_path)
    paths = {name: _resolve(path) for name, path in experiment["inputs"].items()}
    children = _load_jsonl(paths["children"])
    parents = _load_jsonl(paths["parents"])
    manifest = _load_json(paths["data_manifest"])
    qa = _load_json(paths["data_qa"])
    dataset = _load_jsonl(_resolve(baseline["dataset"]["path"]))
    selected_ids = set(experiment["impact_case_ids"] + experiment["normal_control_case_ids"])
    available_ids = {row["case_id"] for row in dataset if row["split"] == experiment["dataset_split"]}
    parent_ids = {row["parent_id"] for row in parents}
    checks = [
        {"name": "base_preflight", "passed": base["status"] == "READY", "detail": base["blockers"]},
        {"name": "partial_scope_status", "passed": experiment["status"] == "PARTIAL_SCOPE_DIAGNOSTIC", "detail": experiment["status"]},
        {"name": "selected_case_ids", "passed": selected_ids.issubset(available_ids) and len(selected_ids) == 16, "detail": {"selected": len(selected_ids), "missing": sorted(selected_ids - available_ids)}},
        {"name": "data_qa", "passed": qa.get("qa_status") == "PASS", "detail": qa.get("qa_status")},
        {"name": "child_hash", "passed": file_sha256(paths["children"]) == manifest["output_files"]["child"]["sha256"], "detail": file_sha256(paths["children"])},
        {"name": "parent_hash", "passed": file_sha256(paths["parents"]) == manifest["output_files"]["parent"]["sha256"], "detail": file_sha256(paths["parents"])},
        {"name": "qa_hash", "passed": file_sha256(paths["data_qa"]) == manifest["output_files"]["qa"]["sha256"], "detail": file_sha256(paths["data_qa"])},
        {"name": "record_counts", "passed": len(children) == 15 and len(parents) == 5, "detail": {"children": len(children), "parents": len(parents)}},
        {"name": "child_single_evidence", "passed": all(isinstance(row.get("evidence_group_id"), str) and row["evidence_group_id"] for row in children), "detail": "one scalar evidence_group_id per Child"},
        {"name": "child_parent_links", "passed": all(row.get("parent_id") in parent_ids for row in children), "detail": "all Child parent_id values resolve"},
    ]
    blockers = [row["name"] for row in checks if not row["passed"]]
    return {
        "preflight_id": "D04-ROW-CHILD-PARTIAL-V2-PREFLIGHT",
        "status": "READY" if not blockers else "BLOCKED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_preflight": base,
        "checks": checks,
        "blockers": blockers,
    }


def run_row_child_partial_experiment(
    experiment_path: Path,
    baseline_path: Path,
    output_directory: Path,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    allow_draft_gold: bool = False,
    cache_directory: Path | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    preflight = _build_preflight(
        experiment_path,
        baseline_path,
        allow_draft_gold=allow_draft_gold,
        embedding_provider_supplied=embedding_provider is not None,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if preflight["status"] != "READY":
        raise RuntimeError("D04 부분 진단 Preflight 차단: " + ", ".join(preflight["blockers"]))

    experiment = _load_json(experiment_path)
    baseline = _load_json(baseline_path)
    dataset_path = _resolve(baseline["dataset"]["path"])
    source_path = _resolve(baseline["corpus"]["path"])
    child_path = _resolve(experiment["inputs"]["children"])
    parent_path = _resolve(experiment["inputs"]["parents"])
    selected_ids = experiment["impact_case_ids"] + experiment["normal_control_case_ids"]
    selected_set = set(selected_ids)
    dataset_rows = [
        row for row in _load_jsonl(dataset_path)
        if row["split"] == experiment["dataset_split"] and row["case_id"] in selected_set
    ]
    dataset_rows.sort(key=lambda row: selected_ids.index(row["case_id"]))
    source_rows = _load_jsonl(source_path)
    child_rows = _load_jsonl(child_path)
    parent_rows = _load_jsonl(parent_path)
    parent_by_id = {row["parent_id"]: row for row in parent_rows}
    partial, removed_count = build_partial_replacement_corpus(
        source_rows,
        child_rows,
        document_id=experiment["candidate_corpus"]["document_id"],
        replaced_page_refs=set(experiment["candidate_corpus"]["replaced_page_refs"]),
    )

    provider = embedding_provider or LocalBgeM3Provider(baseline)
    if provider.dimension != baseline["embedding"]["dimension"]:
        raise ValueError("Embedding Provider Dimension 불일치")
    query_started = time.perf_counter()
    query_vectors = _normalize(provider.embed_queries([row["query"] for row in dataset_rows]))
    query_embedding_seconds = time.perf_counter() - query_started
    resolved_cache = cache_directory or _resolve(DEFAULT_CACHE)
    baseline_vectors, baseline_embedding_seconds, baseline_cache_hit, baseline_cache_key = _load_or_build_embeddings(
        [row["text"] for row in source_rows], baseline["embedding"], provider, resolved_cache
    )
    partial_vectors, partial_embedding_seconds, partial_cache_hit, partial_cache_key = _load_or_build_embeddings(
        [row["text"] for row in partial], baseline["embedding"], provider, resolved_cache
    )
    controls = experiment["fixed_retrieval"]

    def retrieve(chunks: list[dict[str, Any]], vectors: np.ndarray, query_vector: np.ndarray, model: str) -> tuple[list[dict[str, Any]], float]:
        candidates = [index for index, chunk in enumerate(chunks) if chunk["exact_sales_code"] == model]
        clock = time.perf_counter()
        scores = vectors[candidates] @ query_vector if candidates else np.asarray([])
        scored = [
            (candidates[index], float(score))
            for index, score in enumerate(scores)
            if float(score) >= controls["score_threshold"]
        ]
        scored.sort(key=lambda item: (-item[1], chunks[item[0]]["chunk_id"]))
        ranked = [{"chunk": chunks[index], "score": score} for index, score in scored[: controls["top_k"]]]
        return ranked, (time.perf_counter() - clock) * 1000

    results: list[dict[str, Any]] = []
    v2_rank_parity = True
    for case_index, case in enumerate(dataset_rows):
        baseline_ranked, baseline_latency = retrieve(
            source_rows, baseline_vectors, query_vectors[case_index], case["product_model_code"]
        )
        partial_ranked, partial_latency = retrieve(
            partial, partial_vectors, query_vectors[case_index], case["product_model_code"]
        )
        base_metrics = _metrics(
            baseline_ranked, case["expected_evidence"], case["expected_no_evidence"],
            case["product_model_code"], case["evidence_match_policy"],
        )
        partial_metrics = _metrics(
            partial_ranked, case["expected_evidence"], case["expected_no_evidence"],
            case["product_model_code"], case["evidence_match_policy"],
        )
        parent_context = expand_parent_context(partial_ranked, parent_by_id, child_rows)

        def ranked_output(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "rank": rank,
                    "chunk_id": item["chunk"]["chunk_id"],
                    "page_refs": item["chunk"]["page_refs"],
                    "score": round(item["score"], 8),
                    "evidence_unit_ids": item["chunk"].get("evidence_unit_ids", []),
                    "parent_id": item["chunk"].get("parent_id"),
                    "source_variant_id": item["chunk"].get("source_variant_id"),
                }
                for rank, item in enumerate(ranked, 1)
            ]

        common = {
            "case_id": case["case_id"],
            "case_role": "IMPACT" if case["case_id"] in experiment["impact_case_ids"] else "NORMAL_CONTROL",
            "query_variant_type": case["query_variant_type"],
            "evidence_match_policy": case["evidence_match_policy"],
            "expected_evidence": case["expected_evidence"],
        }
        results.append({**common, "variant_id": "CURRENT_PAGE_V1", "ranked_results": ranked_output(baseline_ranked), "metrics": base_metrics, "retrieval_latency_ms": round(baseline_latency, 6), "context": {"mode": "CHUNK_ONLY"}})
        child_ranked_output = ranked_output(partial_ranked)
        results.append({**common, "variant_id": "CHILD_ONLY_V2", "ranked_results": child_ranked_output, "metrics": partial_metrics, "retrieval_latency_ms": round(partial_latency, 6), "context": {"mode": "CHILD_ONLY", "context_whitespace_tokens": sum(len(item["chunk"]["text"].split()) for item in partial_ranked)}})
        results.append({**common, "variant_id": "CHILD_PARENT_CONTEXT_V2", "ranked_results": child_ranked_output, "metrics": partial_metrics, "retrieval_latency_ms": round(partial_latency, 6), "context": {"mode": "DEDUPLICATED_PARENT", **parent_context}})
        v2_rank_parity = v2_rank_parity and results[-1]["ranked_results"] == results[-2]["ranked_results"]

    by_variant = {
        variant["variant_id"]: [row for row in results if row["variant_id"] == variant["variant_id"]]
        for variant in experiment["variants"]
    }
    baseline_by_case = {row["case_id"]: row for row in by_variant["CURRENT_PAGE_V1"]}
    child_by_case = {row["case_id"]: row for row in by_variant["CHILD_ONLY_V2"]}
    recovered = sorted(
        case_id for case_id in selected_ids
        if baseline_by_case[case_id]["metrics"]["hit_at_5"] == 0
        and child_by_case[case_id]["metrics"]["hit_at_5"] == 1
    )
    regressed = sorted(
        case_id for case_id in selected_ids
        if baseline_by_case[case_id]["metrics"]["hit_at_5"] == 1
        and child_by_case[case_id]["metrics"]["hit_at_5"] == 0
    )
    control_regressions = sorted(set(regressed).intersection(experiment["normal_control_case_ids"]))
    ranking_improvements = sorted(
        case_id for case_id in selected_ids
        if child_by_case[case_id]["metrics"]["first_relevant_rank"] is not None
        and (
            baseline_by_case[case_id]["metrics"]["first_relevant_rank"] is None
            or child_by_case[case_id]["metrics"]["first_relevant_rank"]
            < baseline_by_case[case_id]["metrics"]["first_relevant_rank"]
        )
    )
    ranking_regressions = sorted(
        case_id for case_id in selected_ids
        if baseline_by_case[case_id]["metrics"]["first_relevant_rank"] is not None
        and (
            child_by_case[case_id]["metrics"]["first_relevant_rank"] is None
            or child_by_case[case_id]["metrics"]["first_relevant_rank"]
            > baseline_by_case[case_id]["metrics"]["first_relevant_rank"]
        )
    )
    control_ranking_regressions = sorted(
        set(ranking_regressions).intersection(experiment["normal_control_case_ids"])
    )
    parent_rows_result = by_variant["CHILD_PARENT_CONTEXT_V2"]
    child_rows_result = by_variant["CHILD_ONLY_V2"]
    context_review_required = [
        row["case_id"] for row in parent_rows_result
        if row["context"]["human_context_review_status"] == "REVIEW_REQUIRED"
    ]
    automatic_gate_passed = (
        v2_rank_parity
        and not control_regressions
        and not control_ranking_regressions
        and all(row["context"]["deduplicated_parent_reference_count"] >= 0 for row in parent_rows_result)
    )
    child_context_tokens = [row["context"]["context_whitespace_tokens"] for row in child_rows_result]
    parent_context_tokens = [row["context"]["context_whitespace_tokens"] for row in parent_rows_result]
    incremental_context_tokens = [
        parent - child
        for child, parent in zip(child_context_tokens, parent_context_tokens, strict=True)
    ]
    summary = {
        "experiment_id": experiment["experiment_id"],
        "run_status": "PARTIAL_SCOPE_DIAGNOSTIC_COMPLETE",
        "metrics_publishable_as_official": False,
        "production_adoption": "NOT_APPROVED",
        "variant_summaries": {key: _summary(value) for key, value in by_variant.items()},
        "comparison": {
            "recovered_case_ids": recovered,
            "hit_at_5_regression_case_ids": regressed,
            "normal_control_regression_case_ids": control_regressions,
            "ranking_improvement_case_ids": ranking_improvements,
            "ranking_regression_case_ids": ranking_regressions,
            "normal_control_ranking_regression_case_ids": control_ranking_regressions,
            "v2_child_rankings_identical": v2_rank_parity,
        },
        "focus_cases": {
            case_id: {
                "baseline_first_relevant_rank": baseline_by_case[case_id]["metrics"]["first_relevant_rank"],
                "v2_first_relevant_rank": child_by_case[case_id]["metrics"]["first_relevant_rank"],
                "baseline_hit_at_5": baseline_by_case[case_id]["metrics"]["hit_at_5"],
                "v2_hit_at_5": child_by_case[case_id]["metrics"]["hit_at_5"],
            }
            for case_id in experiment["required_focus_case_ids"]
        },
        "parent_context": {
            "review_required_case_ids": context_review_required,
            "mean_context_whitespace_tokens": round(sum(row["context"]["context_whitespace_tokens"] for row in parent_rows_result) / len(parent_rows_result), 3),
            "maximum_context_whitespace_tokens": max(row["context"]["context_whitespace_tokens"] for row in parent_rows_result),
            "mean_child_only_whitespace_tokens": round(sum(child_context_tokens) / len(child_context_tokens), 3),
            "mean_incremental_expansion_tokens": round(sum(incremental_context_tokens) / len(incremental_context_tokens), 3),
            "maximum_incremental_expansion_tokens": max(incremental_context_tokens),
            "mean_parent_to_child_token_ratio": round(
                sum(parent / child if child else 0.0 for child, parent in zip(child_context_tokens, parent_context_tokens, strict=True))
                / len(child_context_tokens),
                3,
            ),
            "expansion_latency_p50_ms": round(float(np.percentile([row["context"]["expansion_latency_ms"] for row in parent_rows_result], 50)), 6),
            "expansion_latency_p95_ms": round(float(np.percentile([row["context"]["expansion_latency_ms"] for row in parent_rows_result], 95)), 6),
            "case_ids_with_additional_evidence_groups": [row["case_id"] for row in parent_rows_result if row["context"]["additional_context_evidence_group_ids"]],
            "case_ids_with_excluded_micro_particle_context": [row["case_id"] for row in parent_rows_result if row["context"]["contains_excluded_micro_particle_row"]],
        },
        "gate": {
            "automatic_checks_passed": automatic_gate_passed,
            "final_decision": "PENDING_HUMAN_CONTEXT_REVIEW",
        },
        "publication_limits": experiment["publication_limits"],
    }
    manifest = {
        "experiment_id": experiment["experiment_id"],
        "experiment_version": experiment["experiment_version"],
        "run_status": summary["run_status"],
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "metrics_publishable_as_official": False,
        "production_adoption": "NOT_APPROVED",
        "inputs": {
            "experiment": {"path": experiment_path.relative_to(REPOSITORY_ROOT).as_posix(), "sha256": file_sha256(experiment_path)},
            "baseline": {"path": baseline_path.relative_to(REPOSITORY_ROOT).as_posix(), "sha256": file_sha256(baseline_path)},
            "gold": {"path": baseline["dataset"]["path"], "sha256": file_sha256(dataset_path)},
            "source_corpus": {"path": baseline["corpus"]["path"], "sha256": file_sha256(source_path), "record_count": len(source_rows)},
            "children": {"path": experiment["inputs"]["children"], "sha256": file_sha256(child_path), "record_count": len(child_rows)},
            "parents": {"path": experiment["inputs"]["parents"], "sha256": file_sha256(parent_path), "record_count": len(parent_rows)},
        },
        "candidate_corpus": {"mode": "PARTIAL_PAGE_REPLACEMENT", "removed_page_chunks": removed_count, "added_child_chunks": len(child_rows), "record_count": len(partial)},
        "selected_cases": {"impact": experiment["impact_case_ids"], "normal_control": experiment["normal_control_case_ids"], "total": len(dataset_rows)},
        "embedding": baseline["embedding"],
        "retrieval": controls,
        "performance": {
            "query_embedding_seconds": round(query_embedding_seconds, 6),
            "baseline_document_embedding_seconds": round(baseline_embedding_seconds, 6),
            "partial_document_embedding_seconds": round(partial_embedding_seconds, 6),
            "baseline_embedding_cache_hit": baseline_cache_hit,
            "partial_embedding_cache_hit": partial_cache_hit,
            "baseline_embedding_cache_key": baseline_cache_key,
            "partial_embedding_cache_key": partial_cache_key,
            "case_result_count": len(results),
            "total_seconds": round(time.perf_counter() - started_clock, 6),
        },
        "runtime": {"python": platform.python_version(), "os": f"{platform.system()} {platform.release()}"},
        "git": _git_facts(),
        "publication_limits": experiment["publication_limits"],
    }
    (output_directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_directory / "case_results.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="D04 row-child partial diagnostic")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--baseline-profile", default=DEFAULT_BASELINE_PROFILE)
    parser.add_argument("--output-directory", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-draft-gold", action="store_true")
    args = parser.parse_args()
    manifest = run_row_child_partial_experiment(
        _resolve(args.experiment),
        _resolve(args.baseline_profile),
        _resolve(args.output_directory),
        allow_draft_gold=args.allow_draft_gold,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
