#!/usr/bin/env python3
"""Full Corpus v3와 Gold v2의 로컬 BGE-M3 Dense 검색 진단 실행기.

이 실행기는 실제 로컬 임베딩과 NumPy Cosine ranking을 수행하지만 pgvector를
호출하지 않는다. 따라서 검색 Case의 관측 경로는 항상
``LOCAL_DENSE_QUERY``이며, Gold의 기대 경로 ``PGVECTOR_QUERY``를 가장하지
않는다. Evidence Group의 의미 Hit와 실행 경로 계약은 별도 필드로 보고한다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ai.evaluation.evidence_scoring_v2 import score_gold_case
from ai.evaluation.file_integrity import file_sha256
from ai.scripts.validate_gold_corpus_compatibility_v2 import (
    build_compatibility_report,
)
from ai.scripts.validate_gold_evaluation_v2 import build_qa_report


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = "ai/configs/experiments/full_corpus_baseline_v2.yaml"
LOCAL_DENSE_QUERY = "LOCAL_DENSE_QUERY"
LOCAL_POLICY_SIMULATION = "LOCAL_POLICY_SIMULATION"
PGVECTOR_QUERY = "PGVECTOR_QUERY"
POLICY_BLOCK_PATHS = frozenset(
    {
        "POLICY_BLOCK_PRODUCT_MISMATCH",
        "POLICY_BLOCK_UNSUPPORTED_MODEL",
        "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
        "POLICY_BLOCK_UNVERIFIED_SOURCE",
    }
)
REQUIRED_RUNTIME_MODULES = ("sentence_transformers", "torch", "transformers")


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_queries(self, texts: list[str]) -> np.ndarray: ...


class LocalBgeM3Provider:
    """고정된 로컬 Hugging Face Snapshot만 사용하는 BGE-M3 Provider."""

    def __init__(self, profile: dict[str, Any]) -> None:
        embedding = profile["embedding"]
        self.dimension = int(embedding["dimension"])
        self.revision = str(embedding["revision"])
        self.device = str(embedding["device"])
        self.snapshot = _embedding_snapshot(self.revision)
        if not self.snapshot.is_dir():
            raise FileNotFoundError("고정 BGE-M3 Snapshot이 없습니다.")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            str(self.snapshot),
            device=self.device,
            local_files_only=True,
        )

    def _encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] != self.dimension:
            raise ValueError("Embedding Dimension이 Profile과 다릅니다.")
        return matrix

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode(texts)


def _resolve(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    path = path.resolve()
    path.relative_to(REPOSITORY_ROOT.resolve())
    return path


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            raise ValueError(f"빈 JSONL 행: {_relative(path)}:{line_number}")
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"JSONL 행이 Object가 아님: {_relative(path)}:{line_number}")
        rows.append(row)
    return rows


def _embedding_snapshot(revision: str) -> Path:
    return (
        Path.home()
        / ".cache/huggingface/hub/models--BAAI--bge-m3/snapshots"
        / revision
    )


def _normalise(matrix: np.ndarray, *, dimension: int) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[1] != dimension:
        raise ValueError(
            f"Embedding Matrix Shape 불일치: expected=(*,{dimension}), actual={matrix.shape}"
        )
    if not len(matrix):
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("0 Vector는 Cosine Search에 사용할 수 없습니다.")
    return matrix / norms


def _git(*args: str) -> str | None:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={REPOSITORY_ROOT.as_posix()}", *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_facts() -> dict[str, Any]:
    status = _git("status", "--porcelain")
    return {
        "commit_sha": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "working_tree_clean": status == "" if status is not None else None,
        "changed_path_count": len(status.splitlines()) if status else 0,
    }


def _select_registry_path(profile: dict[str, Any]) -> tuple[Path, str]:
    registry = profile["evidence_groups"]
    preferred = _resolve(registry["preferred_path"])
    if preferred.is_file():
        return preferred, "EVALUATION_REGISTRY"
    fallback = _resolve(registry["fallback_path"])
    return fallback, "DATA_HANDOFF_REGISTRY"


def _manifest_record_count(dataset_section: dict[str, Any]) -> int | None:
    value = dataset_section.get("records", dataset_section.get("record_count"))
    return value if isinstance(value, int) else None


def _select_eligible_corpus_rows(
    profile: dict[str, Any],
    corpus_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Profile의 선택적 Record Type 제한을 검증하고 Embedding 대상을 고른다.

    ``allowed_record_types``가 없으면 기존과 동일하게 Source Corpus 전체를
    사용한다. 명시된 경우 빈 목록, 중복, 문자열이 아닌 값, Source Corpus에
    존재하지 않는 Type을 모두 차단해 오타나 잘못된 Ablation이 조용히 실행되지
    않게 한다.
    """

    raw_allowed = profile.get("retrieval", {}).get("allowed_record_types")
    observed_record_types = {
        row.get("record_type")
        for row in corpus_rows
        if isinstance(row.get("record_type"), str)
    }
    issues: list[str] = []
    configured = raw_allowed is not None
    if raw_allowed is None:
        allowed_record_types = set(observed_record_types)
    elif not isinstance(raw_allowed, list) or not raw_allowed:
        allowed_record_types = set()
        issues.append("allowed_record_types는 비어 있지 않은 JSON Array여야 합니다.")
    else:
        string_values = [value for value in raw_allowed if isinstance(value, str)]
        if len(string_values) != len(raw_allowed):
            issues.append("allowed_record_types의 모든 값은 문자열이어야 합니다.")
        if len(set(string_values)) != len(string_values):
            issues.append("allowed_record_types에 중복 값이 있습니다.")
        unknown = sorted(set(string_values) - observed_record_types)
        if unknown:
            issues.append(
                "Source Corpus에 없는 record_type이 지정됐습니다: "
                + ", ".join(unknown)
            )
        allowed_record_types = set(string_values)

    eligible_rows = [
        row for row in corpus_rows if row.get("record_type") in allowed_record_types
    ]
    if not eligible_rows:
        issues.append("Embedding 가능한 Corpus 후보가 0건입니다.")

    source_type_counts = dict(
        sorted(Counter(str(row.get("record_type")) for row in corpus_rows).items())
    )
    eligible_type_counts = dict(
        sorted(Counter(str(row.get("record_type")) for row in eligible_rows).items())
    )
    return eligible_rows, {
        "configured": configured,
        "mode": "EXPLICIT_ALLOWLIST" if configured else "ALL_RECORD_TYPES_DEFAULT",
        "allowed_record_types": sorted(allowed_record_types),
        "observed_record_types": sorted(observed_record_types),
        "source_corpus_record_count": len(corpus_rows),
        "eligible_candidate_count": len(eligible_rows),
        "planned_embedded_candidate_count": len(eligible_rows),
        "source_record_type_counts": source_type_counts,
        "eligible_record_type_counts": eligible_type_counts,
        "issues": issues,
    }


def build_preflight_report(
    profile_path: Path,
    *,
    allow_review_pending: bool,
    embedding_provider_supplied: bool = False,
) -> dict[str, Any]:
    """Gold 자체 계약과 Gold–Corpus 계보를 검색 전에 fail-closed 검사한다."""

    profile = _load_json(profile_path)
    dataset_path = _resolve(profile["dataset"]["path"])
    dataset_manifest_path = _resolve(profile["dataset"]["manifest_path"])
    gold_schema_path = _resolve(profile["dataset"]["schema_path"])
    registry_path, registry_source = _select_registry_path(profile)
    fallback_registry_path = _resolve(profile["evidence_groups"]["fallback_path"])
    registry_manifest_path = (
        _resolve(profile["evidence_groups"]["preferred_manifest_path"])
        if registry_source == "EVALUATION_REGISTRY"
        else None
    )
    children_path = _resolve(profile["children"]["path"])
    corpus_path = _resolve(profile["corpus"]["path"])
    handoff_manifest_path = _resolve(profile["corpus"]["handoff_manifest_path"])

    paths = {
        "dataset": dataset_path,
        "dataset_manifest": dataset_manifest_path,
        "gold_schema": gold_schema_path,
        "evidence_groups": registry_path,
        "children": children_path,
        "corpus": corpus_path,
        "handoff_manifest": handoff_manifest_path,
    }
    if registry_manifest_path is not None:
        paths["evidence_group_registry_manifest"] = registry_manifest_path
        paths["evidence_group_source_registry"] = fallback_registry_path
    checks: list[dict[str, Any]] = []

    def add_check(
        name: str,
        passed: bool,
        detail: Any,
        *,
        blocking: bool = True,
    ) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "blocking": blocking,
                "detail": detail,
            }
        )

    for name, path in paths.items():
        add_check(f"{name}_exists", path.is_file(), {"path": _relative(path)})

    if any(not path.is_file() for path in paths.values()):
        blockers = [
            check["name"]
            for check in checks
            if check["blocking"] and not check["passed"]
        ]
        return {
            "preflight_id": "FULL-CORPUS-V3-LOCAL-DENSE-PREFLIGHT",
            "status": "BLOCKED",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile": {"path": _relative(profile_path)},
            "registry": {
                "path": _relative(registry_path),
                "source": registry_source,
            },
            "checks": checks,
            "blockers": blockers,
            "official": False,
            "official_metrics_allowed": False,
        }

    dataset_manifest = _load_json(dataset_manifest_path)
    handoff_manifest = _load_json(handoff_manifest_path)
    registry_manifest = (
        _load_json(registry_manifest_path)
        if registry_manifest_path is not None
        else None
    )
    dataset_rows = _load_jsonl(dataset_path)
    corpus_rows = _load_jsonl(corpus_path)
    group_rows = _load_jsonl(registry_path)
    child_rows = _load_jsonl(children_path)
    eligible_corpus_rows, retrieval_scope = _select_eligible_corpus_rows(
        profile, corpus_rows
    )

    dataset_section = dataset_manifest.get("dataset", {})
    add_check(
        "dataset_manifest_hash",
        dataset_section.get("sha256") == file_sha256(dataset_path),
        {
            "records": len(dataset_rows),
            "manifest_records": _manifest_record_count(dataset_section),
        },
    )
    manifest_records = _manifest_record_count(dataset_section)
    add_check(
        "dataset_manifest_count",
        manifest_records == len(dataset_rows),
        {"records": len(dataset_rows), "manifest_records": manifest_records},
    )

    output_contract = handoff_manifest.get("outputs", {})
    expected_corpus = output_contract.get("corpus", {})
    expected_children = output_contract.get("children", {})
    add_check(
        "corpus_handoff_hash",
        expected_corpus.get("sha256") == file_sha256(corpus_path),
        {
            "records": len(corpus_rows),
            "expected_records": expected_corpus.get("record_count"),
        },
    )
    add_check(
        "corpus_handoff_count",
        expected_corpus.get("record_count") == len(corpus_rows),
        {
            "records": len(corpus_rows),
            "expected_records": expected_corpus.get("record_count"),
        },
    )
    add_check(
        "children_handoff_hash",
        expected_children.get("sha256") == file_sha256(children_path),
        {
            "records": len(child_rows),
            "expected_records": expected_children.get("record_count"),
        },
    )
    add_check(
        "children_handoff_count",
        expected_children.get("record_count") == len(child_rows),
        {
            "records": len(child_rows),
            "expected_records": expected_children.get("record_count"),
        },
    )
    expected_groups = (
        registry_manifest.get("output", {})
        if registry_manifest is not None
        else output_contract.get("evidence_groups", {})
    )
    expected_group_count = expected_groups.get(
        "group_count", expected_groups.get("record_count")
    )
    add_check(
        "evidence_group_registry_integrity",
        expected_groups.get("path") == _relative(registry_path)
        and expected_groups.get("sha256") == file_sha256(registry_path)
        and expected_group_count == len(group_rows),
        {
            "records": len(group_rows),
            "expected_records": expected_group_count,
            "source": registry_source,
            "manifest": (
                _relative(registry_manifest_path)
                if registry_manifest_path is not None
                else _relative(handoff_manifest_path)
            ),
        },
    )
    preferred_sources = (
        registry_manifest.get("source_files", {})
        if registry_manifest is not None
        else {}
    )
    preferred_source_targets = {
        "evidence_groups": fallback_registry_path,
        "children": children_path,
        "corpus": corpus_path,
    }
    preferred_source_hashes_match = registry_manifest is None or all(
        isinstance(preferred_sources.get(name), dict)
        and preferred_sources[name].get("path") == _relative(path)
        and preferred_sources[name].get("sha256") == file_sha256(path)
        for name, path in preferred_source_targets.items()
    )
    add_check(
        "evidence_group_registry_source_integrity",
        preferred_source_hashes_match,
        {
            "applicable": registry_manifest is not None,
            "source_file_count": len(preferred_sources),
        },
    )
    add_check(
        "corpus_search_candidate_contract",
        all(row.get("retrieval_role") == "SEARCH_CANDIDATE" for row in corpus_rows),
        {
            "records": len(corpus_rows),
            "record_types": dict(
                sorted(Counter(str(row.get("record_type")) for row in corpus_rows).items())
            ),
        },
    )
    add_check(
        "retrieval_allowed_record_types",
        not retrieval_scope["issues"],
        retrieval_scope,
    )

    gold_qa = build_qa_report(dataset_path, gold_schema_path)
    gold_contract_valid = gold_qa["status"] != "FAIL"
    add_check(
        "gold_v2_contract",
        gold_contract_valid,
        {
            "status": gold_qa["status"],
            **gold_qa["summary"],
        },
    )
    pending_active = int(gold_qa["summary"]["review_pending_active_records"])
    add_check(
        "gold_human_review_gate",
        pending_active == 0 or allow_review_pending,
        {
            "review_pending_active_records": pending_active,
            "allow_review_pending": allow_review_pending,
            "official_metrics_allowed": pending_active == 0,
        },
    )

    compatibility = build_compatibility_report(
        dataset_path,
        registry_path,
        children_path,
        corpus_path,
    )
    add_check(
        "gold_corpus_compatibility",
        compatibility["status"] == "PASS",
        {
            "status": compatibility["status"],
            "counts": compatibility["counts"],
            "error_code_counts": compatibility["error_code_counts"],
        },
    )

    selected_splits = set(profile["dataset"]["splits"])
    active_rows = [
        row
        for row in dataset_rows
        if row.get("evaluation_status") == "ACTIVE" and row.get("split") in selected_splits
    ]
    add_check(
        "active_case_selection",
        bool(active_rows),
        {
            "dataset_records": len(dataset_rows),
            "active_records": len(active_rows),
            "excluded_or_rejected_records": len(dataset_rows) - len(active_rows),
            "splits": sorted(selected_splits),
        },
    )

    missing_modules = (
        []
        if embedding_provider_supplied
        else [
            module
            for module in REQUIRED_RUNTIME_MODULES
            if importlib.util.find_spec(module) is None
        ]
    )
    add_check(
        "embedding_runtime_dependencies",
        not missing_modules,
        {"missing_modules": missing_modules},
    )
    revision = str(profile["embedding"]["revision"])
    snapshot_required = not embedding_provider_supplied
    snapshot_available = _embedding_snapshot(revision).is_dir()
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

    blockers = [
        check["name"]
        for check in checks
        if check["blocking"] and not check["passed"]
    ]
    has_policy_cases = any(
        row["expected_execution_path"] in POLICY_BLOCK_PATHS for row in active_rows
    )
    return {
        "preflight_id": "FULL-CORPUS-V3-LOCAL-DENSE-PREFLIGHT",
        "status": "READY" if not blockers else "BLOCKED",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "path": _relative(profile_path),
            "sha256": file_sha256(profile_path),
        },
        "registry": {
            "path": _relative(registry_path),
            "source": registry_source,
            "sha256": file_sha256(registry_path),
        },
        "checks": checks,
        "blockers": blockers,
        "counts": {
            "dataset_records": len(dataset_rows),
            "active_records": len(active_rows),
            "corpus_search_candidates": len(corpus_rows),
            "corpus_source_records": len(corpus_rows),
            "corpus_eligible_candidates": len(eligible_corpus_rows),
            "corpus_planned_embedded_candidates": len(eligible_corpus_rows),
            "evidence_groups": len(group_rows),
            "children": len(child_rows),
        },
        "retrieval_scope": retrieval_scope,
        "official": False,
        "official_metrics_allowed": False,
        "official_metrics_blockers": [
            "LOCAL_DENSE_QUERY_IS_NOT_PGVECTOR_QUERY",
            *(["POLICY_BLOCK_RUNTIME_NOT_EXECUTED"] if has_policy_cases else []),
            *([] if pending_active == 0 else ["HUMAN_REVIEW_PENDING"]),
        ],
    }


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row["metrics"][key] for row in rows if row["metrics"].get(key) is not None]
    return round(sum(float(value) for value in values) / len(values), 6) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _semantic_quality_passed(
    case: dict[str, Any],
    scoring: dict[str, Any],
    ranked_count: int,
) -> bool:
    expected_path = case["expected_execution_path"]
    if expected_path in POLICY_BLOCK_PATHS:
        return bool(scoring["policy_block_success"])
    if case["expected_retrieval_outcome"] == "NO_EVIDENCE":
        return ranked_count == 0
    return bool(scoring["semantic_passed"]) and scoring["invalid_top_k_hit_count"] == 0


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [
        row for row in results if row["expected_retrieval_outcome"] == "EVIDENCE"
    ]
    corpus_absence = [
        row
        for row in results
        if row["expected_retrieval_outcome"] == "NO_EVIDENCE"
        and row["expected_execution_path"] == PGVECTOR_QUERY
    ]
    policy_blocks = [
        row for row in results if row["expected_execution_path"] in POLICY_BLOCK_PATHS
    ]
    supporting = [row for row in evidence if row["supporting_evidence_group_ids"]]
    fully_covered_supporting = sum(
        set(row["supporting_evidence_group_ids"]).issubset(
            set(row["metrics"]["covered_supporting_group_ids"])
        )
        for row in supporting
    )
    metric_count_keys = (
        "wrong_product_hit_count",
        "non_child_hit_count",
        "non_search_candidate_hit_count",
        "disallowed_use_hit_count",
        "unverified_hit_count",
        "forbidden_document_hit_count",
        "forbidden_model_hit_count",
        "invalid_top_k_hit_count",
    )
    return {
        "case_count": len(results),
        "evidence_case_count": len(evidence),
        "corpus_absence_case_count": len(corpus_absence),
        "policy_block_case_count": len(policy_blocks),
        "semantic_group_passed_count": sum(
            row["metrics"]["semantic_passed"] is True for row in evidence
        ),
        "semantic_quality_passed_count": sum(
            row["semantic_quality_passed"] for row in results
        ),
        "execution_contract_passed_count": sum(
            row["metrics"]["execution_contract_passed"] is True for row in results
        ),
        "scorer_passed_count": sum(row["metrics"]["passed"] is True for row in results),
        "mean_hit_at_1": _mean(evidence, "hit_at_1"),
        "mean_hit_at_3": _mean(evidence, "hit_at_3"),
        "mean_hit_at_5": _mean(evidence, "hit_at_5"),
        "mean_recall_at_1": _mean(evidence, "recall_at_1"),
        "mean_recall_at_3": _mean(evidence, "recall_at_3"),
        "mean_recall_at_5": _mean(evidence, "recall_at_5"),
        "mean_mrr": _mean(evidence, "mrr"),
        "corpus_absence_empty_count": sum(
            row["ranked_result_count"] == 0 for row in corpus_absence
        ),
        "corpus_absence_empty_rate": _rate(
            sum(row["ranked_result_count"] == 0 for row in corpus_absence),
            len(corpus_absence),
        ),
        "policy_block_passed_count": sum(
            row["metrics"]["policy_block_success"] is True for row in policy_blocks
        ),
        "supporting_case_count": len(supporting),
        "fully_covered_supporting_case_count": fully_covered_supporting,
        "supporting_coverage_rate": _rate(fully_covered_supporting, len(supporting)),
        "vector_query_count": sum(row["vector_query_count"] for row in results),
        "actual_execution_path_counts": dict(
            sorted(Counter(row["actual_execution_path"] for row in results).items())
        ),
        **{
            key: sum(int(row["metrics"][key]) for row in results)
            for key in metric_count_keys
        },
    }


def run_baseline(
    profile_path: Path,
    output_directory: Path,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    allow_review_pending: bool = False,
) -> dict[str, Any]:
    """실제 Local Dense ranking을 수행하고 의미·실행계약 Metric을 분리 저장한다."""

    preflight = build_preflight_report(
        profile_path,
        allow_review_pending=allow_review_pending,
        embedding_provider_supplied=embedding_provider is not None,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if preflight["status"] != "READY":
        raise RuntimeError("Full Corpus v3 Preflight 차단: " + ", ".join(preflight["blockers"]))

    profile = _load_json(profile_path)
    dataset_path = _resolve(profile["dataset"]["path"])
    registry_path, registry_source = _select_registry_path(profile)
    corpus_path = _resolve(profile["corpus"]["path"])
    selected_splits = set(profile["dataset"]["splits"])
    dataset_rows = [
        row
        for row in _load_jsonl(dataset_path)
        if row["evaluation_status"] == "ACTIVE" and row["split"] in selected_splits
    ]
    evidence_groups = _load_jsonl(registry_path)
    source_corpus_rows = _load_jsonl(corpus_path)
    corpus_rows, retrieval_scope = _select_eligible_corpus_rows(
        profile, source_corpus_rows
    )
    if retrieval_scope["issues"]:
        raise RuntimeError(
            "Preflight 이후 Retrieval Scope가 유효하지 않습니다: "
            + "; ".join(retrieval_scope["issues"])
        )

    provider = embedding_provider or LocalBgeM3Provider(profile)
    dimension = int(profile["embedding"]["dimension"])
    if provider.dimension != dimension:
        raise ValueError(
            f"Embedding Provider Dimension 불일치: expected={dimension}, actual={provider.dimension}"
        )

    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    document_started = time.perf_counter()
    document_vectors = _normalise(
        np.asarray(provider.embed_documents([row["text"] for row in corpus_rows])),
        dimension=dimension,
    )
    document_embedding_seconds = time.perf_counter() - document_started
    if len(document_vectors) != len(corpus_rows):
        raise ValueError("문서 Embedding 행 수가 Corpus와 다릅니다.")

    query_cases = [
        row for row in dataset_rows if row["expected_execution_path"] == PGVECTOR_QUERY
    ]
    query_started = time.perf_counter()
    query_vectors = _normalise(
        np.asarray(provider.embed_queries([row["query"] for row in query_cases])),
        dimension=dimension,
    )
    query_embedding_seconds = time.perf_counter() - query_started
    if len(query_vectors) != len(query_cases):
        raise ValueError("질의 Embedding 행 수가 검색 대상 Case와 다릅니다.")
    query_vector_by_case = {
        case["case_id"]: query_vectors[index]
        for index, case in enumerate(query_cases)
    }

    top_k = int(profile["retrieval"]["top_k"])
    threshold = float(profile["retrieval"]["score_threshold"])
    results: list[dict[str, Any]] = []
    retrieval_started = time.perf_counter()
    for case in dataset_rows:
        case_started = time.perf_counter()
        expected_path = case["expected_execution_path"]
        if expected_path in POLICY_BLOCK_PATHS:
            ranked: list[dict[str, Any]] = []
            # 이 Runner는 Runtime Policy Evaluator를 호출하지 않는다. Gold의 기대
            # 경로를 관측값으로 복사하면 self-fulfilling PASS가 되므로 명시적인
            # 진단 전용 경로로 남기고 실행 계약을 실패 상태로 보존한다.
            actual_path = LOCAL_POLICY_SIMULATION
            vector_query_count = 0
            policy_execution_source = None
            policy_block_status = "NOT_RUN_RUNTIME_POLICY"
        else:
            candidate_indices = [
                index
                for index, row in enumerate(corpus_rows)
                if row["exact_sales_code"] == case["product_model_code"]
            ]
            ranked = []
            if candidate_indices:
                scores = document_vectors[candidate_indices] @ query_vector_by_case[case["case_id"]]
                for local_index in np.argsort(-scores):
                    score = float(scores[int(local_index)])
                    if score < threshold:
                        continue
                    corpus_index = candidate_indices[int(local_index)]
                    ranked.append({"chunk": corpus_rows[corpus_index], "score": score})
                    if len(ranked) == top_k:
                        break
            actual_path = LOCAL_DENSE_QUERY
            vector_query_count = 1
            policy_execution_source = None
            policy_block_status = None

        scoring = score_gold_case(
            case,
            ranked,
            actual_execution_path=actual_path,
            vector_query_count=vector_query_count,
            evidence_groups=evidence_groups,
            evaluation_top_k=top_k,
        )
        case_latency_ms = round((time.perf_counter() - case_started) * 1000.0, 3)
        results.append(
            {
                "case_id": case["case_id"],
                "split": case["split"],
                "query_variant_type": case["query_variant_type"],
                "product_model_code": case["product_model_code"],
                "expected_retrieval_outcome": case["expected_retrieval_outcome"],
                "expected_execution_path": expected_path,
                "actual_execution_path": actual_path,
                "vector_query_count": vector_query_count,
                "policy_execution_source": policy_execution_source,
                "policy_block_status": policy_block_status,
                "required_evidence_group_ids": case["required_evidence_group_ids"],
                "supporting_evidence_group_ids": case["supporting_evidence_group_ids"],
                "ranked_result_count": len(ranked),
                "ranked_results": [
                    {
                        "rank": rank,
                        "chunk_id": item["chunk"]["chunk_id"],
                        "source_record_id": item["chunk"]["source_record_id"],
                        "record_type": item["chunk"]["record_type"],
                        "document_id": item["chunk"]["document_id"],
                        "page_refs": item["chunk"]["page_refs"],
                        "exact_sales_code": item["chunk"]["exact_sales_code"],
                        "score": round(item["score"], 8),
                    }
                    for rank, item in enumerate(ranked, start=1)
                ],
                "semantic_quality_passed": _semantic_quality_passed(
                    case, scoring, len(ranked)
                ),
                "metrics": scoring,
                "retrieval_latency_ms": case_latency_ms,
            }
        )
    retrieval_seconds = time.perf_counter() - retrieval_started

    summary = _build_summary(results)
    total_seconds = time.perf_counter() - started_clock
    completed_at = datetime.now(timezone.utc)
    run_status = "LOCAL_DENSE_DIAGNOSTIC_COMPLETE"
    retrieval_summary = {
        "profile_id": profile["profile_id"],
        "run_status": run_status,
        "official": False,
        "official_metrics_allowed": False,
        "execution_contract_status": "NOT_COMPARABLE_FOR_PGVECTOR_QUERY_CASES",
        "scoring_contract": "evidence_group_policy_v2",
        "summary": summary,
        "semantic_metrics": {
            key: summary[key]
            for key in (
                "evidence_case_count",
                "corpus_absence_case_count",
                "semantic_group_passed_count",
                "semantic_quality_passed_count",
                "mean_hit_at_1",
                "mean_hit_at_3",
                "mean_hit_at_5",
                "mean_recall_at_1",
                "mean_recall_at_3",
                "mean_recall_at_5",
                "mean_mrr",
                "corpus_absence_empty_count",
                "corpus_absence_empty_rate",
                "supporting_case_count",
                "fully_covered_supporting_case_count",
                "supporting_coverage_rate",
                "wrong_product_hit_count",
                "non_child_hit_count",
                "non_search_candidate_hit_count",
                "disallowed_use_hit_count",
                "unverified_hit_count",
                "forbidden_document_hit_count",
                "forbidden_model_hit_count",
                "invalid_top_k_hit_count",
            )
        },
        "execution_contract": {
            "status": "NOT_COMPARABLE_FOR_PGVECTOR_QUERY_CASES",
            "passed_count": summary["execution_contract_passed_count"],
            "scorer_passed_count": summary["scorer_passed_count"],
            "vector_query_count": summary["vector_query_count"],
            "actual_execution_path_counts": summary["actual_execution_path_counts"],
            "policy_block_case_count": summary["policy_block_case_count"],
            "policy_block_passed_count": summary["policy_block_passed_count"],
            "policy_block_runtime_status": (
                "NOT_RUN_RUNTIME_POLICY"
                if summary["policy_block_case_count"]
                else "NOT_APPLICABLE"
            ),
        },
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
        "source_corpus_record_count": len(source_corpus_rows),
        "eligible_candidate_count": len(corpus_rows),
        "embedded_candidate_count": len(document_vectors),
        "embedded_query_count": len(query_cases),
        "active_case_count": len(dataset_rows),
        "policy_block_case_count": summary["policy_block_case_count"],
        "case_result_count": len(results),
    }
    manifest = {
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "run_status": run_status,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "execution_seconds": round(total_seconds, 6),
        "official": False,
        "official_metrics_allowed": False,
        "official_metrics_blockers": preflight["official_metrics_blockers"],
        "dataset": {
            "path": profile["dataset"]["path"],
            "sha256": file_sha256(dataset_path),
            "records": preflight["counts"]["dataset_records"],
            "active_records": len(dataset_rows),
            "splits": sorted(selected_splits),
        },
        "evidence_groups": {
            "path": _relative(registry_path),
            "source": registry_source,
            "sha256": file_sha256(registry_path),
            "records": len(evidence_groups),
        },
        "corpus": {
            "path": profile["corpus"]["path"],
            "sha256": file_sha256(corpus_path),
            "search_candidates": len(source_corpus_rows),
            "source_records": len(source_corpus_rows),
            "source_search_candidates": len(source_corpus_rows),
            "eligible_search_candidates": len(corpus_rows),
            "embedded_candidates": len(document_vectors),
            "allowed_record_types": retrieval_scope["allowed_record_types"],
            "record_type_counts": dict(
                sorted(
                    Counter(row["record_type"] for row in source_corpus_rows).items()
                )
            ),
            "eligible_record_type_counts": dict(
                sorted(Counter(row["record_type"] for row in corpus_rows).items())
            ),
        },
        "embedding": profile["embedding"],
        "retrieval": {
            **profile["retrieval"],
            "vector_query_actual_execution_path": LOCAL_DENSE_QUERY,
            "policy_block_execution": "NOT_RUN_RUNTIME_POLICY",
        },
        "runtime": {
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
            "provider_class": provider.__class__.__name__,
        },
        "git": _git_facts(),
        "publication_limits": profile["publication_limits"],
    }

    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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
    parser = argparse.ArgumentParser(description="Full Corpus v3 Local Dense Diagnostic")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--output-directory")
    parser.add_argument("--allow-review-pending", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    profile_path = _resolve(args.profile)
    profile = _load_json(profile_path)
    output_directory = (
        _resolve(args.output_directory)
        if args.output_directory
        else _resolve(profile["output_directory"])
    )
    if args.preflight_only:
        preflight = build_preflight_report(
            profile_path,
            allow_review_pending=args.allow_review_pending,
        )
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / "preflight.json").write_text(
            json.dumps(preflight, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return

    manifest = run_baseline(
        profile_path,
        output_directory,
        allow_review_pending=args.allow_review_pending,
    )
    print(
        json.dumps(
            {
                "run_status": manifest["run_status"],
                "official_metrics_allowed": manifest["official_metrics_allowed"],
                "active_cases": manifest["dataset"]["active_records"],
                "corpus_search_candidates": manifest["corpus"]["search_candidates"],
                "eligible_search_candidates": manifest["corpus"][
                    "eligible_search_candidates"
                ],
                "embedded_candidates": manifest["corpus"]["embedded_candidates"],
                "output_directory": _relative(output_directory),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
