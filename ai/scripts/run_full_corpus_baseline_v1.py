#!/usr/bin/env python3
"""A3-1 Full Manual Corpus BGE-M3 Dense Cosine Baseline Runner."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ai.evaluation.file_integrity import file_sha256
from ai.evaluation.evidence_scoring_v2 import score_gold_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = "ai/configs/experiments/full_corpus_baseline_v1.yaml"
REQUIRED_RUNTIME_MODULES = ["sentence_transformers", "torch", "transformers"]


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_queries(self, texts: list[str]) -> np.ndarray: ...


class LocalBgeM3Provider:
    """로컬 Hugging Face Snapshot만 사용하는 BGE-M3 Provider."""

    def __init__(self, profile: dict[str, Any]) -> None:
        embedding = profile["embedding"]
        self.dimension = embedding["dimension"]
        self.revision = embedding["revision"]
        self.device = embedding["device"]
        self.snapshot = (
            Path.home()
            / ".cache/huggingface/hub/models--BAAI--bge-m3/snapshots"
            / self.revision
        )
        if not self.snapshot.is_dir():
            raise FileNotFoundError(f"BGE-M3 Snapshot이 없습니다: {self.snapshot}")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            str(self.snapshot),
            device=self.device,
            local_files_only=True,
        )

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding Dimension 불일치: expected={self.dimension}, actual={matrix.shape}"
            )
        return matrix

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)


def _resolve(path_value: str) -> Path:
    path = (REPOSITORY_ROOT / path_value).resolve()
    path.relative_to(REPOSITORY_ROOT.resolve())
    return path


def _sha256(path: Path) -> str:
    return file_sha256(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"빈 JSONL 행: {path}:{line_number}")
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"JSONL 행이 객체가 아님: {path}:{line_number}")
        rows.append(row)
    return rows


def _git(*args: str) -> str | None:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={REPOSITORY_ROOT.as_posix()}", *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _git_facts() -> dict[str, Any]:
    status = _git("status", "--porcelain")
    return {
        "commit_sha": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "working_tree_clean": status == "" if status is not None else None,
        "changed_path_count": len(status.splitlines()) if status else 0,
    }


def build_preflight_report(
    profile_path: Path,
    *,
    allow_draft_gold: bool,
    embedding_provider_supplied: bool = False,
) -> dict[str, Any]:
    profile = _load_json(profile_path)
    dataset_path = _resolve(profile["dataset"]["path"])
    dataset_manifest_path = _resolve(profile["dataset"]["manifest_path"])
    corpus_path = _resolve(profile["corpus"]["path"])
    corpus_manifest_path = _resolve(profile["corpus"]["manifest_path"])
    dataset_manifest = _load_json(dataset_manifest_path)
    corpus_manifest = _load_json(corpus_manifest_path)
    dataset_rows = _load_jsonl(dataset_path)
    corpus_rows = _load_jsonl(corpus_path)

    checks: list[dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: Any, blocking: bool = True) -> None:
        checks.append({
            "name": name,
            "passed": passed,
            "blocking": blocking,
            "detail": detail,
        })

    add_check(
        "dataset_hash",
        dataset_manifest["dataset"]["sha256"] == _sha256(dataset_path),
        {"records": len(dataset_rows), "sha256": _sha256(dataset_path)},
    )
    add_check(
        "corpus_hash",
        corpus_manifest["dataset"]["sha256"] == _sha256(corpus_path),
        {"records": len(corpus_rows), "sha256": _sha256(corpus_path)},
    )
    add_check(
        "corpus_count",
        len(corpus_rows) == 96,
        dict(Counter(row["corpus_scope"] for row in corpus_rows)),
    )
    pending_gold = sum(
        row.get("review_status") != "TWO_PERSON_APPROVED" for row in dataset_rows
    )
    add_check(
        "gold_two_person_review",
        pending_gold == 0 or allow_draft_gold,
        {
            "pending_records": pending_gold,
            "allow_draft_gold": allow_draft_gold,
            "official_metrics_allowed": pending_gold == 0,
        },
    )

    missing_modules = [] if embedding_provider_supplied else [
        module
        for module in REQUIRED_RUNTIME_MODULES
        if importlib.util.find_spec(module) is None
    ]
    add_check(
        "embedding_runtime_dependencies",
        not missing_modules,
        {"missing_modules": missing_modules},
    )
    revision = profile["embedding"]["revision"]
    snapshot = (
        Path.home()
        / ".cache/huggingface/hub/models--BAAI--bge-m3/snapshots"
        / revision
    )
    snapshot_required = not embedding_provider_supplied
    snapshot_available = snapshot.is_dir()
    add_check(
        "embedding_model_snapshot",
        snapshot_available or not snapshot_required,
        {
            "model": profile["embedding"]["model"],
            "revision": revision,
            "required": snapshot_required,
            "available": snapshot_available,
        },
    )

    blockers = [check["name"] for check in checks if check["blocking"] and not check["passed"]]
    return {
        "preflight_id": "A3-1-FULL-CORPUS-BASELINE-PREFLIGHT",
        "status": "READY" if not blockers else "BLOCKED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "path": profile_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(profile_path),
        },
        "checks": checks,
        "blockers": blockers,
        "decision": {
            "draft_baseline_execution": "READY" if not blockers else "BLOCKED",
            "official_phase_b_baseline": (
                "READY" if pending_gold == 0 and not blockers else "BLOCKED"
            ),
            "dependency_install_performed": False,
            "docker_used": False,
        },
    }


def _normalize(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("0 Vector는 Cosine Search에 사용할 수 없습니다.")
    return matrix / norms


def _metrics(
    ranked: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    expected_no_evidence: bool,
    product_model_code: str,
    evidence_match_policy: str,
) -> dict[str, Any]:
    scored = score_gold_case(
        {
            "product_model_code": product_model_code,
            "expected_evidence": expected,
            "expected_no_evidence": expected_no_evidence,
            "evidence_match_policy": evidence_match_policy,
            "expected_execution_path": "LOCAL_DENSE_QUERY",
        },
        ranked,
        actual_execution_path="LOCAL_DENSE_QUERY",
        vector_query_count=1,
        evaluation_top_k=5,
    )
    # v1 Report의 역사적 Shape는 보존하고 계산만 공통 Scorer에 위임한다.
    historical_keys = (
        "evidence_match_policy",
        "required_evidence_unit_ids",
        "covered_evidence_unit_ids",
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "mrr",
        "ndcg_at_5",
        "first_matched_rank",
        "evidence_completion_rank",
        "first_relevant_rank",
        "wrong_product_hit_count",
        "no_evidence_retrieval_empty",
        "no_evidence_passed",
        "answerability_gate_passed",
    )
    return {key: scored[key] for key in historical_keys}


def run_baseline(
    profile_path: Path,
    output_directory: Path,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    allow_draft_gold: bool = False,
) -> dict[str, Any]:
    preflight = build_preflight_report(
        profile_path,
        allow_draft_gold=allow_draft_gold,
        embedding_provider_supplied=embedding_provider is not None,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if preflight["status"] != "READY":
        raise RuntimeError("A3-1 Preflight 차단: " + ", ".join(preflight["blockers"]))

    profile = _load_json(profile_path)
    dataset_path = _resolve(profile["dataset"]["path"])
    corpus_path = _resolve(profile["corpus"]["path"])
    dataset_rows = [
        row for row in _load_jsonl(dataset_path)
        if row["split"] == profile["dataset"]["split"]
    ]
    corpus_rows = _load_jsonl(corpus_path)
    provider = embedding_provider or LocalBgeM3Provider(profile)
    if provider.dimension != profile["embedding"]["dimension"]:
        raise ValueError(
            "Embedding Provider Dimension 불일치: "
            f"expected={profile['embedding']['dimension']}, actual={provider.dimension}"
        )
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    document_started = time.perf_counter()
    document_vectors = _normalize(provider.embed_documents([row["text"] for row in corpus_rows]))
    document_embedding_seconds = time.perf_counter() - document_started
    query_started = time.perf_counter()
    query_vectors = _normalize(provider.embed_queries([row["query"] for row in dataset_rows]))
    query_embedding_seconds = time.perf_counter() - query_started
    if document_vectors.shape[0] != len(corpus_rows) or query_vectors.shape[0] != len(dataset_rows):
        raise ValueError("Embedding 행 수가 입력 수와 다릅니다.")

    retrieval_started = time.perf_counter()
    results: list[dict[str, Any]] = []
    top_k = profile["retrieval"]["top_k"]
    threshold = profile["retrieval"]["score_threshold"]
    for variant_name, scopes in profile["corpus"]["variants"].items():
        variant_indices = [
            index for index, chunk in enumerate(corpus_rows)
            if chunk["corpus_scope"] in scopes
        ]
        for filter_mode in profile["retrieval"]["filter_modes"]:
            for case_index, case in enumerate(dataset_rows):
                candidate_indices = variant_indices
                if filter_mode == "EXACT_PRODUCT_FILTER":
                    candidate_indices = [
                        index for index in candidate_indices
                        if corpus_rows[index]["exact_sales_code"] == case["product_model_code"]
                    ]
                scored = []
                if candidate_indices:
                    scores = document_vectors[candidate_indices] @ query_vectors[case_index]
                    order = np.argsort(-scores)
                    for local_index in order:
                        score = float(scores[local_index])
                        if score < threshold:
                            continue
                        chunk_index = candidate_indices[int(local_index)]
                        scored.append({"chunk": corpus_rows[chunk_index], "score": score})
                        if len(scored) == top_k:
                            break
                case_metrics = _metrics(
                    scored,
                    case["expected_evidence"],
                    case["expected_no_evidence"],
                    case["product_model_code"],
                    case["evidence_match_policy"],
                )
                results.append({
                    "case_id": case["case_id"],
                    "split": case["split"],
                    "query_variant_type": case["query_variant_type"],
                    "query": case["query"],
                    "product_model_code": case["product_model_code"],
                    "corpus_variant": variant_name,
                    "filter_mode": filter_mode,
                    "expected_evidence": case["expected_evidence"],
                    "evidence_match_policy": case["evidence_match_policy"],
                    "expected_no_evidence": case["expected_no_evidence"],
                    "ranked_results": [
                        {
                            "rank": rank,
                            "chunk_id": item["chunk"]["chunk_id"],
                            "document_id": item["chunk"]["document_id"],
                            "page_refs": item["chunk"]["page_refs"],
                            "exact_sales_code": item["chunk"]["exact_sales_code"],
                            "score": round(item["score"], 8),
                        }
                        for rank, item in enumerate(scored, 1)
                    ],
                    "metrics": case_metrics,
                })
    retrieval_seconds = time.perf_counter() - retrieval_started

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        groups[(row["corpus_variant"], row["filter_mode"])].append(row)
    group_summaries = []
    for (variant, filter_mode), rows in sorted(groups.items()):
        positive = [row for row in rows if not row["expected_no_evidence"]]
        negative = [row for row in rows if row["expected_no_evidence"]]
        def mean(key: str) -> float | None:
            values = [
                row["metrics"][key]
                for row in positive
                if row["metrics"][key] is not None
            ]
            return round(sum(values) / len(values), 6) if values else None

        no_evidence_empty_result_rate = (
            round(
                sum(row["metrics"]["no_evidence_retrieval_empty"] for row in negative)
                / len(negative),
                6,
            )
            if negative
            else None
        )
        group_summaries.append({
            "corpus_variant": variant,
            "filter_mode": filter_mode,
            "case_count": len(rows),
            "positive_case_count": len(positive),
            "no_evidence_case_count": len(negative),
            "mean_hit_at_1": mean("hit_at_1"),
            "mean_hit_at_3": mean("hit_at_3"),
            "mean_hit_at_5": mean("hit_at_5"),
            "mean_mrr": mean("mrr"),
            "mean_ndcg_at_5": mean("ndcg_at_5"),
            "ndcg_at_5_evaluated_case_count": sum(
                row["metrics"]["ndcg_at_5"] is not None for row in positive
            ),
            "ndcg_at_5_excluded_all_case_count": sum(
                row["evidence_match_policy"] == "ALL" for row in positive
            ),
            "wrong_product_hit_count": sum(
                row["metrics"]["wrong_product_hit_count"] for row in rows
            ),
            "no_evidence_empty_result_rate": no_evidence_empty_result_rate,
            "no_evidence_accuracy": no_evidence_empty_result_rate,
            "no_evidence_metric_status": "RETRIEVAL_DIAGNOSTIC_D03_GATE_PENDING",
        })

    total_seconds = time.perf_counter() - started_clock
    completed_at = datetime.now(timezone.utc)
    metrics_publishable = all(
        row["review_status"] == "TWO_PERSON_APPROVED" for row in dataset_rows
    )
    retrieval_summary = {
        "profile_id": profile["profile_id"],
        "run_status": "DRAFT_BASELINE_COMPLETE",
        "metrics_publishable_as_official": metrics_publishable,
        "evaluation_contract": {
            "version": "d01_evidence_policy_v1",
            "all_hit_and_mrr": "ALL_UNIQUE_EVIDENCE_UNIT_IDS_REQUIRED",
            "all_ndcg_at_5": "EXCLUDED_PENDING_DEFINITION",
            "none_metric": "RETRIEVAL_EMPTY_RESULT_DIAGNOSTIC_D03_GATE_PENDING",
        },
        "groups": group_summaries,
        "publication_limits": profile["publication_limits"],
    }
    performance_summary = {
        "profile_id": profile["profile_id"],
        "device": profile["embedding"]["device"],
        "document_embedding_seconds": round(document_embedding_seconds, 6),
        "query_embedding_seconds": round(query_embedding_seconds, 6),
        "retrieval_seconds": round(retrieval_seconds, 6),
        "total_seconds": round(total_seconds, 6),
        "document_count": len(corpus_rows),
        "query_count": len(dataset_rows),
        "case_result_count": len(results),
    }
    manifest = {
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "run_status": "DRAFT_BASELINE_COMPLETE",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "execution_seconds": round(total_seconds, 6),
        "metrics_publishable_as_official": metrics_publishable,
        "dataset": {
            "path": profile["dataset"]["path"],
            "sha256": _sha256(dataset_path),
            "split": profile["dataset"]["split"],
            "selected_cases": len(dataset_rows),
        },
        "corpus": {
            "path": profile["corpus"]["path"],
            "sha256": _sha256(corpus_path),
            "chunks": len(corpus_rows),
            "variants": profile["corpus"]["variants"],
        },
        "chunking": profile["chunking"],
        "embedding": profile["embedding"],
        "retrieval": profile["retrieval"],
        "runtime": {
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
            "provider_class": provider.__class__.__name__,
        },
        "git": _git_facts(),
        "publication_limits": profile["publication_limits"],
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_directory / "case_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
        encoding="utf-8",
    )
    (output_directory / "retrieval_summary.json").write_text(
        json.dumps(retrieval_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_directory / "performance_summary.json").write_text(
        json.dumps(performance_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="A3-1 Full Corpus BGE-M3 Baseline")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--output-directory")
    parser.add_argument("--allow-draft-gold", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    profile_path = _resolve(args.profile)
    profile = _load_json(profile_path)
    output_directory = (
        _resolve(args.output_directory)
        if args.output_directory
        else _resolve(profile["output_directory"])
    )
    preflight = build_preflight_report(
        profile_path,
        allow_draft_gold=args.allow_draft_gold,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.preflight_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return
    manifest = run_baseline(
        profile_path,
        output_directory,
        allow_draft_gold=args.allow_draft_gold,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
