from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.retrieval.query.query_expander import RetrievalQueryExpander
from ai.app.retrieval.runtime_profile import (
    load_runtime_retrieval_policy,
    resolve_rag_runtime_profile,
)
from ai.app.retrieval.verification.answerability_capability_gate import (
    AnswerabilityCapabilityGate,
)


SCRIPT_VERSION = "2.0"

MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"

CASE_PATH = ROOT / "data/config/rag/three_model_evaluation_cases.json"
CHILD_PATH = ROOT / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
POLICY_PATH = ROOT / "ai/configs/retrieval_policy.yaml"

PREFLIGHT_PATH = ROOT / ".runtime/e02_v2/preflight.json"
BUILD_MANIFEST_PATH = ROOT / ".runtime/e02_v2/manifest.json"
VARIANT_DIR = ROOT / ".runtime/e02_v2/variants"
OUT_DIR = ROOT / ".runtime/e02_v2/results"

VARIANTS = (
    "fixed512",
    "section_aware_512",
    "parent_child_256",
)

EXPECTED_CASES = 50
EXPECTED_POSITIVE = 43
EXPECTED_NEGATIVE = 7
EXPECTED_GROUP_COVERAGE = "43/43"
EXPECTED_CHILD_COVERAGE = "53/53"
MIN_CANDIDATES_PER_MODEL = 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except Exception as exc:
                raise RuntimeError(
                    f"{path.relative_to(ROOT)}:{line_no} JSON parse 실패: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise RuntimeError(
                    f"{path.relative_to(ROOT)}:{line_no} JSON object가 아닙니다."
                )
            rows.append(row)
    return rows


def get_git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def get_branch() -> str:
    return subprocess.check_output(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def round6(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def load_primary_cases() -> list[dict[str, Any]]:
    data = load_json(CASE_PATH)
    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict) and isinstance(data.get("cases"), list):
        cases = data["cases"]
    else:
        raise RuntimeError("E01 50 Case JSON 구조를 해석하지 못했습니다.")

    positive = sum(case.get("case_type") == "POSITIVE" for case in cases)
    negative = sum(case.get("case_type") == "NEGATIVE" for case in cases)

    if (
        len(cases) != EXPECTED_CASES
        or positive != EXPECTED_POSITIVE
        or negative != EXPECTED_NEGATIVE
    ):
        raise RuntimeError(
            "E01 evaluation contract가 변경되었습니다: "
            f"cases={len(cases)}, positive={positive}, negative={negative}"
        )

    normalized = []
    for case in cases:
        item = dict(case)
        item["query_set"] = "PRIMARY_E01_50"
        item["publication_status"] = "E01_CONTRACT_REUSE"
        normalized.append(item)
    return normalized


def load_supplemental_faq_cases(
    preflight: dict[str, Any],
) -> list[dict[str, Any]]:
    faq = preflight.get("faq") or {}
    compatible = faq.get("compatible_cases") or []

    cases: list[dict[str, Any]] = []
    for row in compatible:
        query = str(row.get("query") or "").strip()
        model = str(row.get("model") or "").strip()
        groups = [
            str(gid)
            for gid in row.get("group_ids") or []
            if gid
        ]
        case_id = str(row.get("case_id") or "").strip()

        if not query or not model or not groups or not case_id:
            raise RuntimeError(
                f"FAQ supplemental case 필수 필드 누락: {row}"
            )

        cases.append({
            "case_id": f"SUPP-{case_id}",
            "source_case_id": case_id,
            "case_type": "POSITIVE",
            "query_set": "SUPPLEMENTAL_FAQ_DRAFT",
            "publication_status": "UNREVIEWED_DRAFT_DIAGNOSTIC_ONLY",
            "query": query,
            "exact_sales_code": model,
            "expected_evidence_group_ids": groups,
            "expected_no_evidence": False,
            "forbidden_model_codes": [],
            "source_faq_ids": row.get("faq_ids") or [],
            "review_status": row.get("review_status"),
            "label_generation": row.get("label_generation"),
        })

    return cases


def resolve_runtime_contract():
    config = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    retrieval = config["retrieval_params"]
    top_k = int(retrieval["top_k"])
    threshold = float(retrieval["score_threshold"])

    if top_k != 5:
        raise RuntimeError(
            f"E02-v2는 Top-K=5 고정 계약입니다. actual={top_k}"
        )

    profile = resolve_rag_runtime_profile("three_model_integration")
    runtime_policy = load_runtime_retrieval_policy(profile)

    gate = AnswerabilityCapabilityGate(
        definition=runtime_policy.answerability_gate
    )
    expander = RetrievalQueryExpander()

    return profile, runtime_policy, gate, expander, top_k, threshold


def derive_product_generations() -> dict[str, str]:
    rows = load_jsonl(CHILD_PATH)
    by_model: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        by_model[str(row["exact_sales_code"])].add(
            str(row["product_generation"])
        )

    ambiguous = {
        model: sorted(values)
        for model, values in by_model.items()
        if len(values) != 1
    }
    if ambiguous:
        raise RuntimeError(
            f"판매코드별 product_generation이 유일하지 않습니다: {ambiguous}"
        )

    return {
        model: next(iter(values))
        for model, values in by_model.items()
    }


def validate_inputs(
    current_sha: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not PREFLIGHT_PATH.exists():
        raise RuntimeError(
            "E02-v2 preflight 결과가 없습니다. e02_v2_preflight.py를 먼저 실행하세요."
        )
    if not BUILD_MANIFEST_PATH.exists():
        raise RuntimeError(
            "E02-v2 build manifest가 없습니다. e02_v2_build_variants.py를 먼저 실행하세요."
        )

    preflight = load_json(PREFLIGHT_PATH)
    manifest = load_json(BUILD_MANIFEST_PATH)

    if preflight.get("status") != "E02_V2_PREFLIGHT_READY":
        raise RuntimeError(
            f"Preflight 상태가 READY가 아닙니다: {preflight.get('status')}"
        )

    if manifest.get("status") != "E02_V2_VARIANTS_READY":
        raise RuntimeError(
            f"Build 상태가 READY가 아닙니다: {manifest.get('status')}"
        )

    qa = {
        row["variant"]: row
        for row in manifest.get("mapping_qa", [])
    }
    for name in VARIANTS:
        row = qa.get(name)
        if not row or row.get("status") != "PASS":
            raise RuntimeError(f"{name} Mapping QA가 PASS가 아닙니다.")
        if row.get("evidence_group_coverage") != EXPECTED_GROUP_COVERAGE:
            raise RuntimeError(
                f"{name} Evidence Group coverage가 {EXPECTED_GROUP_COVERAGE}가 아닙니다."
            )
        if row.get("source_child_span_coverage") != EXPECTED_CHILD_COVERAGE:
            raise RuntimeError(
                f"{name} Child coverage가 {EXPECTED_CHILD_COVERAGE}가 아닙니다."
            )

        counts = row.get("candidate_counts_by_model") or {}
        if not counts or min(int(v) for v in counts.values()) < MIN_CANDIDATES_PER_MODEL:
            raise RuntimeError(
                f"{name} 후보 Chunk 난도 Gate가 깨졌습니다: {counts}"
            )

    # HEAD SHA 자체가 아니라 실제 입력 Hash 변화만 차단한다.
    changed_inputs = []
    for rel, expected in (manifest.get("input_hashes") or {}).items():
        path = ROOT / rel
        if not path.exists():
            changed_inputs.append({
                "path": rel,
                "reason": "MISSING",
            })
            continue
        actual = sha256_file(path)
        if actual != expected:
            changed_inputs.append({
                "path": rel,
                "expected": expected,
                "actual": actual,
            })

    if changed_inputs:
        raise RuntimeError(
            "Build 이후 E02-v2 입력 파일이 변경되었습니다. 재빌드가 필요합니다:\n"
            + json.dumps(changed_inputs, ensure_ascii=False, indent=2)
        )

    return preflight, manifest


def load_variants() -> dict[str, list[dict[str, Any]]]:
    result = {}
    for name in VARIANTS:
        path = VARIANT_DIR / f"{name}.jsonl"
        if not path.exists():
            raise RuntimeError(
                f"Variant 파일 없음: {path.relative_to(ROOT)}"
            )
        rows = load_jsonl(path)
        if not rows:
            raise RuntimeError(f"{name} Variant가 비어 있습니다.")
        result[name] = rows
    return result


def embed_documents(
    client: BgeM3EmbeddingClient,
    variants: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    matrices: dict[str, np.ndarray] = {}
    seconds: dict[str, float] = {}

    for name in VARIANTS:
        texts = [str(row["text"]) for row in variants[name]]

        started = time.perf_counter()
        vectors = client.embed_documents(texts)
        elapsed = time.perf_counter() - started

        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.shape != (len(texts), 1024):
            raise RuntimeError(
                f"{name} document embedding shape 불일치: {matrix.shape}"
            )

        matrices[name] = matrix
        seconds[name] = elapsed

    return matrices, seconds


def prepare_queries(
    cases: list[dict[str, Any]],
    expander: RetrievalQueryExpander,
    client: BgeM3EmbeddingClient,
) -> tuple[list[dict[str, Any]], np.ndarray, float]:
    prepared: list[dict[str, Any]] = []

    for case in cases:
        decision = expander.expand(
            case["query"],
            model_code=case["exact_sales_code"],
        )
        prepared.append({
            "case_id": case["case_id"],
            "expanded_query": decision.expanded_query,
            "query_expansion_applied": decision.applied,
            "query_expansion_rule_ids": list(
                decision.applied_rule_ids
            ),
        })

    started = time.perf_counter()
    vectors = client.embed_documents(
        [row["expanded_query"] for row in prepared]
    )
    elapsed = time.perf_counter() - started

    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.shape != (len(cases), 1024):
        raise RuntimeError(
            f"query embedding shape 불일치: {matrix.shape}"
        )

    return prepared, matrix, elapsed


def dcg_new_group_coverage(
    ranked_rows: list[dict[str, Any]],
    expected_groups: set[str],
    k: int,
) -> float:
    seen: set[str] = set()
    score = 0.0

    for rank, row in enumerate(ranked_rows[:k], start=1):
        row_groups = set(row.get("evidence_group_ids") or [])
        newly_covered = row_groups.intersection(expected_groups) - seen
        gain = len(newly_covered)
        if gain:
            score += gain / math.log2(rank + 1)
            seen.update(newly_covered)

    return score


def ideal_dcg(expected_group_count: int, k: int) -> float:
    if expected_group_count <= 0:
        return 0.0
    return sum(
        1.0 / math.log2(rank + 1)
        for rank in range(
            1,
            min(expected_group_count, k) + 1,
        )
    )


def score_positive_case(
    ranked_rows: list[dict[str, Any]],
    expected_groups: set[str],
) -> dict[str, Any]:
    first_rank = None

    for rank, row in enumerate(ranked_rows, start=1):
        if expected_groups.intersection(
            row.get("evidence_group_ids") or []
        ):
            first_rank = rank
            break

    covered_at: dict[int, set[str]] = {}
    for k in (1, 3, 5):
        covered_at[k] = {
            gid
            for row in ranked_rows[:k]
            for gid in row.get("evidence_group_ids") or []
            if gid in expected_groups
        }

    recall = {
        k: (
            len(covered_at[k]) / len(expected_groups)
            if expected_groups
            else 0.0
        )
        for k in (1, 3, 5)
    }
    hit = {
        k: 1.0 if covered_at[k] else 0.0
        for k in (1, 3, 5)
    }

    idcg = ideal_dcg(len(expected_groups), 5)
    ndcg = (
        dcg_new_group_coverage(
            ranked_rows,
            expected_groups,
            5,
        ) / idcg
        if idcg
        else 0.0
    )

    return {
        "hit_at_1": hit[1],
        "hit_at_3": hit[3],
        "hit_at_5": hit[5],
        "recall_at_1": recall[1],
        "recall_at_3": recall[3],
        "recall_at_5": recall[5],
        "mrr_at_5": (
            1.0 / first_rank
            if first_rank is not None and first_rank <= 5
            else 0.0
        ),
        "ndcg_at_5": ndcg,
        "first_relevant_rank": first_rank,
    }


def token_count(row: dict[str, Any]) -> int | None:
    start = row.get("token_start")
    end = row.get("token_end")
    if isinstance(start, int) and isinstance(end, int):
        return end - start
    return None


def run_variant(
    *,
    name: str,
    rows: list[dict[str, Any]],
    matrix: np.ndarray,
    cases: list[dict[str, Any]],
    query_prepared: list[dict[str, Any]],
    query_vectors: np.ndarray,
    gate: AnswerabilityCapabilityGate,
    product_generations: dict[str, str],
    top_k: int,
    threshold: float,
) -> list[dict[str, Any]]:
    indexes_by_model: dict[str, np.ndarray] = {}

    for model in sorted({
        str(row["exact_sales_code"])
        for row in rows
    }):
        indexes_by_model[model] = np.asarray(
            [
                i
                for i, row in enumerate(rows)
                if str(row["exact_sales_code"]) == model
            ],
            dtype=np.int64,
        )

    results: list[dict[str, Any]] = []

    for case_index, case in enumerate(cases):
        model = str(case["exact_sales_code"])
        generation = product_generations.get(
            model,
            "__UNSUPPORTED__",
        )

        gate_decision = gate.evaluate(
            query_text=case["query"],
            model_code=model,
            product_generation=generation,
        )

        ranked_indices: list[int] = []
        ranked_scores: list[float] = []
        ranking_ms = 0.0

        if not gate_decision.blocked:
            candidate_indices = indexes_by_model.get(model)

            if candidate_indices is not None and len(candidate_indices):
                started = time.perf_counter_ns()

                scores = (
                    matrix[candidate_indices]
                    @ query_vectors[case_index]
                )

                valid_positions = np.flatnonzero(
                    scores >= threshold
                )

                if len(valid_positions):
                    ordered_positions = valid_positions[
                        np.argsort(
                            scores[valid_positions],
                            kind="stable",
                        )[::-1]
                    ][:top_k]

                    ranked_indices = [
                        int(candidate_indices[pos])
                        for pos in ordered_positions
                    ]
                    ranked_scores = [
                        float(scores[pos])
                        for pos in ordered_positions
                    ]

                ranking_ms = (
                    time.perf_counter_ns() - started
                ) / 1_000_000.0

        ranked_rows = [
            rows[index]
            for index in ranked_indices
        ]

        expected_groups = set(
            case.get("expected_evidence_group_ids") or []
        )
        negative = bool(case.get("expected_no_evidence"))

        if negative:
            metrics = {
                "hit_at_1": None,
                "hit_at_3": None,
                "hit_at_5": None,
                "recall_at_1": None,
                "recall_at_3": None,
                "recall_at_5": None,
                "mrr_at_5": None,
                "ndcg_at_5": None,
                "first_relevant_rank": None,
            }
            no_evidence_success = len(ranked_rows) == 0
            passed = no_evidence_success
        else:
            metrics = score_positive_case(
                ranked_rows,
                expected_groups,
            )
            no_evidence_success = None
            passed = metrics["hit_at_5"] == 1.0

        forbidden_codes = set(
            case.get("forbidden_model_codes") or []
        )

        wrong_product_count = sum(
            str(row["exact_sales_code"]) != model
            for row in ranked_rows
        )
        forbidden_model_count = sum(
            str(row["exact_sales_code"]) in forbidden_codes
            for row in ranked_rows
        )
        invalid_role_count = sum(
            row.get("record_type") != "child"
            or row.get("retrieval_role") != "SEARCH_CANDIDATE"
            for row in ranked_rows
        )

        if (
            wrong_product_count
            or forbidden_model_count
            or invalid_role_count
        ):
            passed = False

        results.append({
            "variant": name,
            "query_set": case["query_set"],
            "publication_status": case["publication_status"],
            "case_id": case["case_id"],
            "source_case_id": case.get("source_case_id"),
            "case_type": case["case_type"],
            "exact_sales_code": model,
            "query": case["query"],
            "source_faq_ids": case.get("source_faq_ids") or [],
            "expected_no_evidence": negative,
            "expected_evidence_group_ids": sorted(expected_groups),
            "query_expansion_applied": query_prepared[case_index][
                "query_expansion_applied"
            ],
            "query_expansion_rule_ids": query_prepared[case_index][
                "query_expansion_rule_ids"
            ],
            "gate_blocked": gate_decision.blocked,
            "gate_execution_path": gate_decision.execution_path,
            "gate_rule_id": gate_decision.rule_id,
            "candidate_count_after_product_filter": int(
                len(indexes_by_model.get(model, []))
            ),
            "ranked_result_count": len(ranked_rows),
            "ranked_chunk_ids": [
                row["chunk_id"]
                for row in ranked_rows
            ],
            "ranked_scores": [
                round6(score)
                for score in ranked_scores
            ],
            "ranked_evidence_group_ids": [
                row.get("evidence_group_ids") or []
                for row in ranked_rows
            ],
            "ranked_group_cardinality": [
                len(row.get("evidence_group_ids") or [])
                for row in ranked_rows
            ],
            "ranked_chunk_tokens": [
                token_count(row)
                for row in ranked_rows
            ],
            "wrong_product_hit_count": wrong_product_count,
            "forbidden_model_hit_count": forbidden_model_count,
            "invalid_role_hit_count": invalid_role_count,
            "ranking_latency_ms": round6(ranking_ms),
            "no_evidence_success": no_evidence_success,
            "passed": bool(passed),
            **{
                key: round6(value)
                if isinstance(value, float)
                else value
                for key, value in metrics.items()
            },
        })

    return results


def summarize_query_set(
    *,
    variant: str,
    query_set: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    subset = [
        row
        for row in rows
        if row["variant"] == variant
        and row["query_set"] == query_set
    ]

    positives = [
        row
        for row in subset
        if row["case_type"] == "POSITIVE"
    ]
    negatives = [
        row
        for row in subset
        if row["case_type"] == "NEGATIVE"
    ]

    def mean_metric(key: str) -> float | None:
        values = [
            float(row[key])
            for row in positives
            if row.get(key) is not None
        ]
        return (
            statistics.fmean(values)
            if values
            else None
        )

    latencies = [
        float(row["ranking_latency_ms"])
        for row in subset
    ]
    all_group_cardinality = [
        value
        for row in subset
        for value in row["ranked_group_cardinality"]
    ]

    return {
        "variant": variant,
        "query_set": query_set,
        "case_count": len(subset),
        "positive_case_count": len(positives),
        "negative_case_count": len(negatives),
        "passed_count": sum(
            bool(row["passed"])
            for row in subset
        ),
        "positive_passed_count": sum(
            bool(row["passed"])
            for row in positives
        ),
        "negative_passed_count": sum(
            bool(row["passed"])
            for row in negatives
        ),
        "hit_at_1": round6(mean_metric("hit_at_1")),
        "hit_at_3": round6(mean_metric("hit_at_3")),
        "hit_at_5": round6(mean_metric("hit_at_5")),
        "recall_at_1": round6(mean_metric("recall_at_1")),
        "recall_at_3": round6(mean_metric("recall_at_3")),
        "recall_at_5": round6(mean_metric("recall_at_5")),
        "mrr_at_5": round6(mean_metric("mrr_at_5")),
        "ndcg_at_5": round6(mean_metric("ndcg_at_5")),
        "no_evidence_accuracy": (
            round6(
                sum(
                    row["no_evidence_success"] is True
                    for row in negatives
                ) / len(negatives)
            )
            if negatives
            else None
        ),
        "wrong_product_hit_count": sum(
            int(row["wrong_product_hit_count"])
            for row in subset
        ),
        "forbidden_model_hit_count": sum(
            int(row["forbidden_model_hit_count"])
            for row in subset
        ),
        "invalid_role_hit_count": sum(
            int(row["invalid_role_hit_count"])
            for row in subset
        ),
        "ranking_latency_p50_ms": round6(
            percentile(latencies, 50)
        ),
        "ranking_latency_p95_ms": round6(
            percentile(latencies, 95)
        ),
        "mean_retrieved_group_cardinality": round6(
            statistics.fmean(all_group_cardinality)
            if all_group_cardinality
            else 0.0
        ),
        "failed_case_ids": [
            row["case_id"]
            for row in subset
            if not row["passed"]
        ],
    }


def write_case_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    fields = [
        "variant",
        "query_set",
        "publication_status",
        "case_id",
        "source_case_id",
        "case_type",
        "exact_sales_code",
        "candidate_count_after_product_filter",
        "expected_no_evidence",
        "gate_blocked",
        "ranked_result_count",
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "mrr_at_5",
        "ndcg_at_5",
        "first_relevant_rank",
        "no_evidence_success",
        "wrong_product_hit_count",
        "forbidden_model_hit_count",
        "invalid_role_hit_count",
        "ranking_latency_ms",
        "passed",
    ]

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )
        writer.writeheader()

        for row in rows:
            writer.writerow({
                key: row.get(key)
                for key in fields
            })


def write_summary_csv(
    path: Path,
    summaries: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    stats = manifest["variant_statistics"]
    fields = [
        "variant",
        "query_set",
        "chunk_count",
        "candidate_counts_by_model",
        "average_chunk_tokens",
        "max_chunk_tokens",
        "case_count",
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "recall_at_1",
        "recall_at_3",
        "recall_at_5",
        "mrr_at_5",
        "ndcg_at_5",
        "no_evidence_accuracy",
        "wrong_product_hit_count",
        "ranking_latency_p50_ms",
        "ranking_latency_p95_ms",
        "mean_retrieved_group_cardinality",
        "failed_case_ids",
    ]

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
        )
        writer.writeheader()

        for summary in summaries:
            name = summary["variant"]
            structural = stats[name]

            writer.writerow({
                "variant": name,
                "query_set": summary["query_set"],
                "chunk_count": structural["chunk_count"],
                "candidate_counts_by_model": json.dumps(
                    structural["candidate_counts_by_model"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "average_chunk_tokens": structural[
                    "average_chunk_tokens"
                ],
                "max_chunk_tokens": structural[
                    "max_chunk_tokens"
                ],
                "case_count": summary["case_count"],
                "hit_at_1": summary["hit_at_1"],
                "hit_at_3": summary["hit_at_3"],
                "hit_at_5": summary["hit_at_5"],
                "recall_at_1": summary["recall_at_1"],
                "recall_at_3": summary["recall_at_3"],
                "recall_at_5": summary["recall_at_5"],
                "mrr_at_5": summary["mrr_at_5"],
                "ndcg_at_5": summary["ndcg_at_5"],
                "no_evidence_accuracy": summary[
                    "no_evidence_accuracy"
                ],
                "wrong_product_hit_count": summary[
                    "wrong_product_hit_count"
                ],
                "ranking_latency_p50_ms": summary[
                    "ranking_latency_p50_ms"
                ],
                "ranking_latency_p95_ms": summary[
                    "ranking_latency_p95_ms"
                ],
                "mean_retrieved_group_cardinality": summary[
                    "mean_retrieved_group_cardinality"
                ],
                "failed_case_ids": ",".join(
                    summary["failed_case_ids"]
                ),
            })


def build_report(
    *,
    provenance: dict[str, Any],
    primary: list[dict[str, Any]],
    supplemental: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> str:
    stats = manifest["variant_statistics"]

    lines = [
        "# E02-v2 Full-Corpus Chunking Strategy Ablation",
        "",
        f"- Run Git SHA: `{provenance['git_sha']}`",
        f"- Build Git SHA: `{provenance['build_git_sha']}`",
        f"- Result Label: `{provenance['result_label']}`",
        f"- Corpus: `3 official manuals / 144 processed pages`",
        f"- Embedding: `{MODEL_NAME}` / `{MODEL_REVISION}`",
        f"- Top-K: `{provenance['top_k']}`",
        f"- Score Threshold: `{provenance['score_threshold']}`",
        "- Product Filter: `exact_sales_code` pre-filter",
        "- Cross-model fallback: `OFF`",
        "- Ranking postprocess: `NONE`",
        "",
        "## Primary — E01 50 Case",
        "",
        "| Variant | Chunks | Candidate counts | H@1 | H@3 | H@5 | MRR@5 | nDCG@5 | No-Evidence | Mean Groups/Hit |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in primary:
        name = row["variant"]
        structural = stats[name]
        lines.append(
            "| "
            + " | ".join([
                name,
                str(structural["chunk_count"]),
                json.dumps(
                    structural["candidate_counts_by_model"],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                f"{row['hit_at_1']:.4f}",
                f"{row['hit_at_3']:.4f}",
                f"{row['hit_at_5']:.4f}",
                f"{row['mrr_at_5']:.4f}",
                f"{row['ndcg_at_5']:.4f}",
                (
                    f"{row['no_evidence_accuracy']:.4f}"
                    if row["no_evidence_accuracy"] is not None
                    else "-"
                ),
                f"{row['mean_retrieved_group_cardinality']:.3f}",
            ])
            + " |"
        )

    lines.extend([
        "",
        "## Supplemental — FAQ-origin Draft Cases",
        "",
        "> 아래 결과는 `UNREVIEWED_DRAFT` Case이므로 공식 성능 수치에 합산하지 않는다.",
        "",
        "| Variant | Cases | H@1 | H@3 | H@5 | MRR@5 | nDCG@5 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])

    for row in supplemental:
        lines.append(
            "| "
            + " | ".join([
                row["variant"],
                str(row["case_count"]),
                (
                    f"{row['hit_at_1']:.4f}"
                    if row["hit_at_1"] is not None
                    else "-"
                ),
                (
                    f"{row['hit_at_3']:.4f}"
                    if row["hit_at_3"] is not None
                    else "-"
                ),
                (
                    f"{row['hit_at_5']:.4f}"
                    if row["hit_at_5"] is not None
                    else "-"
                ),
                (
                    f"{row['mrr_at_5']:.4f}"
                    if row["mrr_at_5"] is not None
                    else "-"
                ),
                (
                    f"{row['ndcg_at_5']:.4f}"
                    if row["ndcg_at_5"] is not None
                    else "-"
                ),
            ])
            + " |"
        )

    lines.extend([
        "",
        "## Interpretation Guardrails",
        "",
        "- E02-v1의 15-page 제한 Corpus는 `SUPERSEDED`로 취급한다.",
        "- E02-v2는 144-page 전체 매뉴얼에서 생성된 134~216개의 자동 Chunk를 비교한다.",
        "- 제품 선필터 후에도 모델별 후보 Chunk가 42~76개이므로 Top-5가 전체 후보를 사실상 전부 보는 구조가 아니다.",
        "- FAQ-origin 5 Case는 사용자 표현 robustness 확인용이며 `UNREVIEWED_DRAFT`이므로 공식 TEST Metric이 아니다.",
        "- Ranking latency는 Local NumPy Exact Cosine 시간이며 E01 pgvector Runtime latency와 직접 비교하지 않는다.",
        "- Parent-Child는 Child text만 검색 점수에 사용하며 Parent context는 retrieval score에 영향을 주지 않는다.",
        "- Public Runtime activation은 변경하지 않는다.",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    current_sha = get_git_sha()
    preflight, manifest = validate_inputs(current_sha)

    primary_cases = load_primary_cases()
    supplemental_cases = load_supplemental_faq_cases(
        preflight
    )

    all_cases = primary_cases + supplemental_cases

    variants = load_variants()

    (
        profile,
        runtime_policy,
        gate,
        expander,
        top_k,
        threshold,
    ) = resolve_runtime_contract()

    product_generations = derive_product_generations()

    client = BgeM3EmbeddingClient(
        device="cpu",
        model_revision=MODEL_REVISION,
    )
    client.warmup()

    matrices, document_embedding_seconds = embed_documents(
        client,
        variants,
    )

    (
        query_prepared,
        query_vectors,
        query_embedding_seconds,
    ) = prepare_queries(
        all_cases,
        expander,
        client,
    )

    all_case_results: list[dict[str, Any]] = []

    for name in VARIANTS:
        all_case_results.extend(
            run_variant(
                name=name,
                rows=variants[name],
                matrix=matrices[name],
                cases=all_cases,
                query_prepared=query_prepared,
                query_vectors=query_vectors,
                gate=gate,
                product_generations=product_generations,
                top_k=top_k,
                threshold=threshold,
            )
        )

    primary_summaries = [
        summarize_query_set(
            variant=name,
            query_set="PRIMARY_E01_50",
            rows=all_case_results,
        )
        for name in VARIANTS
    ]

    supplemental_summaries = [
        summarize_query_set(
            variant=name,
            query_set="SUPPLEMENTAL_FAQ_DRAFT",
            rows=all_case_results,
        )
        for name in VARIANTS
    ]

    input_hashes = {
        str(CASE_PATH.relative_to(ROOT)).replace("\\", "/"): sha256_file(CASE_PATH),
        str(PREFLIGHT_PATH.relative_to(ROOT)).replace("\\", "/"): sha256_file(PREFLIGHT_PATH),
        str(BUILD_MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"): sha256_file(BUILD_MANIFEST_PATH),
    }
    for name in VARIANTS:
        path = VARIANT_DIR / f"{name}.jsonl"
        input_hashes[
            str(path.relative_to(ROOT)).replace("\\", "/")
        ] = sha256_file(path)

    provenance = {
        "experiment_id": "E02-v2",
        "script_version": SCRIPT_VERSION,
        "result_label": "DRAFT_DIAGNOSTIC",
        "branch": get_branch(),
        "git_sha": current_sha,
        "preflight_git_sha": preflight["git"]["head_sha"],
        "build_git_sha": manifest["source"]["build_git_sha"],
        "embedding_model": MODEL_NAME,
        "embedding_revision": MODEL_REVISION,
        "embedding_dimension": 1024,
        "embedding_normalized": True,
        "search_engine": "LOCAL_NUMPY_COSINE_EXACT",
        "ranking_postprocess": "NONE",
        "top_k": top_k,
        "score_threshold": threshold,
        "product_filter": "EXACT_SALES_CODE_PRE_FILTER",
        "cross_model_fallback": False,
        "runtime_policy_profile": profile.name,
        "runtime_activation_scope": profile.activation_scope,
        "query_expansion_policy": expander.policy_id,
        "answerability_policy": gate.policy_id,
        "manual_corpus_pages": 144,
        "primary_case_count": len(primary_cases),
        "supplemental_faq_case_count": len(supplemental_cases),
        "supplemental_publication_status": "UNREVIEWED_DRAFT_DIAGNOSTIC_ONLY",
        "shared_query_embedding_seconds": round6(
            query_embedding_seconds
        ),
        "document_embedding_seconds": {
            name: round6(seconds)
            for name, seconds in document_embedding_seconds.items()
        },
        "input_hashes": input_hashes,
        "build_mapping_policy": manifest.get("mapping_policy"),
        "notes": [
            "E02-v1 15-page experiment는 SUPERSEDED로 취급한다.",
            "E02-v2는 3개 매뉴얼 전체 144 page에서 자동 생성한 세 Chunking 전략을 비교한다.",
            "Primary Metric은 E01 50 Case로 계산한다.",
            "FAQ-origin 5 Case는 UNREVIEWED_DRAFT이므로 supplemental diagnostic로만 분리한다.",
            "Local ranking latency는 E01 pgvector Runtime latency와 직접 비교하지 않는다.",
            "Public runtime activation은 변경하지 않는다.",
        ],
    }

    result = {
        "status": "E02_V2_COMPLETE",
        "result_label": "DRAFT_DIAGNOSTIC",
        "provenance": provenance,
        "primary_summaries": primary_summaries,
        "supplemental_faq_summaries": supplemental_summaries,
        "structural_statistics": manifest["variant_statistics"],
        "mapping_qa": manifest["mapping_qa"],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUT_DIR / "summary.json").write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    (OUT_DIR / "provenance.json").write_text(
        json.dumps(
            provenance,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with (
        OUT_DIR / "case_results.jsonl"
    ).open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as f:
        for row in all_case_results:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    write_case_csv(
        OUT_DIR / "case_results.csv",
        all_case_results,
    )

    write_summary_csv(
        OUT_DIR / "summary.csv",
        primary_summaries + supplemental_summaries,
        manifest,
    )

    report = build_report(
        provenance=provenance,
        primary=primary_summaries,
        supplemental=supplemental_summaries,
        manifest=manifest,
    )
    (OUT_DIR / "report.md").write_text(
        report,
        encoding="utf-8",
    )

    compact = {
        "status": "E02_V2_COMPLETE",
        "result_label": "DRAFT_DIAGNOSTIC",
        "git_sha": current_sha,
        "search_engine": "LOCAL_NUMPY_COSINE_EXACT",
        "manual_corpus_pages": 144,
        "top_k": top_k,
        "score_threshold": threshold,
        "primary_results": {
            row["variant"]: {
                "hit_at_1": row["hit_at_1"],
                "hit_at_3": row["hit_at_3"],
                "hit_at_5": row["hit_at_5"],
                "mrr_at_5": row["mrr_at_5"],
                "ndcg_at_5": row["ndcg_at_5"],
                "no_evidence_accuracy": row[
                    "no_evidence_accuracy"
                ],
                "wrong_product_hits": row[
                    "wrong_product_hit_count"
                ],
                "mean_groups_per_retrieved_chunk": row[
                    "mean_retrieved_group_cardinality"
                ],
                "failed_cases": row["failed_case_ids"],
            }
            for row in primary_summaries
        },
        "supplemental_faq_results": {
            row["variant"]: {
                "case_count": row["case_count"],
                "hit_at_1": row["hit_at_1"],
                "hit_at_3": row["hit_at_3"],
                "hit_at_5": row["hit_at_5"],
                "mrr_at_5": row["mrr_at_5"],
                "ndcg_at_5": row["ndcg_at_5"],
                "failed_cases": row["failed_case_ids"],
            }
            for row in supplemental_summaries
        },
        "output_dir": str(
            OUT_DIR.relative_to(ROOT)
        ).replace("\\", "/"),
    }

    print(
        json.dumps(
            compact,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
