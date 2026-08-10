"""기존 7청크 RAG 결과를 회귀·Smoke 전용 산출물로 고정한다.

저장소에 남아 있는 pgvector 검증 보고서를 회귀 확인용 Snapshot으로 변환한다.
실제 pgvector 재실행은 전체 Corpus Baseline 또는 팀 DB 검증 단계에서 수행한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = "ai/configs/experiments/legacy_7chunk_smoke_v1.yaml"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def _resolve(relative_path: str) -> Path:
    path = (REPOSITORY_ROOT / relative_path).resolve()
    path.relative_to(REPOSITORY_ROOT.resolve())
    return path


def _canonical_chunk_set_sha256(path: Path) -> tuple[str, int]:
    chunks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                chunks.append({
                    "chunk_id": row["chunk_id"],
                    "source_hash": row["source_file_sha256"],
                    "content": row["chunk_text"],
                })
            except KeyError as error:
                raise ValueError(f"승인 청크 {line_number}행 필수 필드 누락: {error.args[0]}") from error
    canonical = sorted(chunks, key=lambda item: item["chunk_id"])
    payload = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper(), len(chunks)


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
    changed_paths = []
    if status is not None:
        changed_paths = [line[3:] for line in status.splitlines() if len(line) > 3]
    return {
        "commit_sha": _git("rev-parse", "HEAD"),
        "branch": _git("branch", "--show-current"),
        "working_tree_status_available": status is not None,
        "working_tree_clean": status == "" if status is not None else None,
        "changed_path_count": len(changed_paths) if status is not None else None,
        "changed_paths": changed_paths,
    }


def _first_relevant_rank(ranked_ids: list[str], expected_ids: list[str]) -> int | None:
    expected = set(expected_ids)
    return next(
        (rank for rank, chunk_id in enumerate(ranked_ids, start=1) if chunk_id in expected),
        None,
    )


def _recall_at_k(ranked_ids: list[str], expected_ids: list[str], k: int) -> float:
    if not expected_ids:
        return 1.0
    hits = len(set(ranked_ids[:k]).intersection(expected_ids))
    return hits / len(set(expected_ids))


def _validate_inputs(
    profile: dict[str, Any],
    dataset: dict[str, Any],
    index_manifest: dict[str, Any],
    verification: dict[str, Any],
    canonical_chunk_hash: str,
    chunk_count: int,
) -> None:
    expected = profile["expected"]
    cases = dataset["cases"]
    positive_count = sum(case["case_type"] == "POSITIVE" for case in cases)
    policy_count = len(cases) - positive_count
    checks = {
        "profile must be smoke-only": profile.get("official_comparison_baseline") is False,
        "chunk count": chunk_count == expected["chunk_count"] == index_manifest["chunk_count"],
        "canonical chunk hash": (
            canonical_chunk_hash == index_manifest["chunk_set_sha256"]
            == verification["chunk_set_sha256"]
        ),
        "case count": len(cases) == expected["case_count"],
        "positive case count": positive_count == expected["positive_case_count"],
        "policy block case count": policy_count == expected["policy_block_case_count"],
        "embedding model": (
            verification["embedding_model"] == expected["embedding_model"]
            == index_manifest["model_name"]
        ),
        "embedding revision": (
            verification["embedding_model_version"] == expected["embedding_revision"]
            == index_manifest["model_revision"]
        ),
        "embedding dimension": (
            verification["dimension"] == expected["embedding_dimension"]
            == index_manifest["dimension"]
        ),
        "top k": verification["top_k"] == expected["top_k"],
        "score threshold": verification["score_threshold"] == expected["score_threshold"],
        "source verification passed": verification["verification_status"] == "PASS",
        "database provenance passed": verification["database_provenance_passed"] is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("Legacy Smoke 입력 정합성 실패: " + ", ".join(failed))

    dataset_ids = {case["case_id"] for case in cases}
    verification_ids = {case["case_id"] for case in verification["cases"]}
    if dataset_ids != verification_ids:
        raise ValueError("평가 Dataset과 pgvector 보고서의 Case ID가 다릅니다.")


def build_smoke_artifacts(
    profile_path: Path,
    output_directory: Path | None = None,
) -> dict[str, Any]:
    """Legacy Smoke 산출물을 만들고 요약을 반환한다."""
    profile = _load_json(profile_path)
    inputs = {name: _resolve(path) for name, path in profile["inputs"].items()}
    dataset = _load_json(inputs["retrieval_dataset"])
    index_manifest = _load_json(inputs["index_manifest"])
    verification = _load_json(inputs["verification_report"])
    canonical_chunk_hash, chunk_count = _canonical_chunk_set_sha256(inputs["approved_chunks"])
    _validate_inputs(
        profile,
        dataset,
        index_manifest,
        verification,
        canonical_chunk_hash,
        chunk_count,
    )

    evidence_mode = "HISTORICAL_SNAPSHOT"
    run_status = "SNAPSHOT_COMPLETE"

    dataset_by_id = {case["case_id"]: case for case in dataset["cases"]}
    case_results: list[dict[str, Any]] = []
    for source_case in verification["cases"]:
        expected_case = dataset_by_id[source_case["case_id"]]
        ranked_ids = source_case["ranked_chunk_ids"]
        expected_ids = expected_case["expected_chunk_ids"]
        is_positive = expected_case["case_type"] == "POSITIVE"
        first_rank = _first_relevant_rank(ranked_ids, expected_ids) if is_positive else None
        case_results.append({
            "case_id": source_case["case_id"],
            "case_type": expected_case["case_type"],
            "evaluation_bucket": "RETRIEVAL_POSITIVE" if is_positive else "POLICY_BLOCK",
            "query": expected_case["query"],
            "product_model_code": expected_case["product_model_code"],
            "execution_path": source_case["execution_path"],
            "expected_chunk_ids": expected_ids,
            "ranked_chunk_ids": ranked_ids,
            "scores": source_case["scores"],
            "first_relevant_rank": first_rank,
            "recall_at_1": _recall_at_k(ranked_ids, expected_ids, 1) if is_positive else None,
            "recall_at_3": _recall_at_k(ranked_ids, expected_ids, 3) if is_positive else None,
            "recall_at_5": _recall_at_k(ranked_ids, expected_ids, 5) if is_positive else None,
            "mrr": (1.0 / first_rank) if first_rank else (0.0 if is_positive else None),
            "expected_no_evidence": expected_case["expected_no_evidence"],
            "no_evidence_passed": (
                not expected_case["expected_no_evidence"] or not ranked_ids
            ),
            "forbidden_hits": source_case["forbidden_hits"],
            "source_case_passed": source_case["passed"],
        })

    positive = [case for case in case_results if case["evaluation_bucket"] == "RETRIEVAL_POSITIVE"]
    policy = [case for case in case_results if case["evaluation_bucket"] == "POLICY_BLOCK"]
    mean = lambda field: sum(case[field] for case in positive) / len(positive)
    leak_case = next(case for case in positive if case["case_id"] == "RAG-POS-LEAK")
    all_contract_passed = all(case["source_case_passed"] for case in case_results)
    forbidden_hit_count = sum(len(case["forbidden_hits"]) for case in case_results)

    summary = {
        "profile_id": profile["profile_id"],
        "run_status": run_status,
        "evidence_mode": evidence_mode,
        "fresh_reproduction": False,
        "metrics_publishable_as_current_run": False,
        "smoke_contract_passed": all_contract_passed and forbidden_hit_count == 0,
        "case_counts": {
            "total": len(case_results),
            "retrieval_positive": len(positive),
            "policy_block": len(policy),
        },
        "retrieval_positive_metrics": {
            "mean_recall_at_1": round(mean("recall_at_1"), 6),
            "mean_recall_at_3": round(mean("recall_at_3"), 6),
            "mean_recall_at_5": round(mean("recall_at_5"), 6),
            "mean_mrr": round(mean("mrr"), 6),
        },
        "policy_metrics": {
            "blocked_case_count": len(policy),
            "no_evidence_passed_count": sum(case["no_evidence_passed"] for case in policy),
            "forbidden_hit_count": forbidden_hit_count,
        },
        "known_weakness": {
            "case_id": leak_case["case_id"],
            "first_relevant_rank": leak_case["first_relevant_rank"],
            "reciprocal_rank": leak_case["mrr"],
        },
        "interpretation_guard": {
            "candidate_chunk_count": chunk_count,
            "top_k": profile["expected"]["top_k"],
            "random_single_relevant_recall_at_5_reference": round(
                profile["expected"]["top_k"] / chunk_count, 6
            ),
            "official_comparison_baseline": False,
        },
        "source_verification": {
            "path": profile["inputs"]["verification_report"],
            "verified_at": verification["verified_at"],
            "verification_status": verification["verification_status"],
        },
        "publication_limits": profile["publication_limits"],
    }

    generated_at = _utc_now().isoformat()
    manifest = {
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "run_status": run_status,
        "generated_at": generated_at,
        "evidence_mode": evidence_mode,
        "fresh_reproduction": False,
        "runtime": {
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
        },
        "git": _git_facts(),
        "inputs": {
            name: {"path": _relative(path), "sha256": _sha256(path)}
            for name, path in inputs.items()
        },
        "canonical_chunk_set_sha256": canonical_chunk_hash,
        "embedding": {
            "model": verification["embedding_model"],
            "revision": verification["embedding_model_version"],
            "dimension": verification["dimension"],
        },
        "vector_store": {
            "provider": "pgvector",
            "search_type": verification["search_type"],
            "index_version": verification["index_version"],
            "top_k": verification["top_k"],
            "score_threshold": verification["score_threshold"],
            "database": None,
            "database_provenance_passed": verification["database_provenance_passed"],
        },
        "limitations": profile["publication_limits"],
    }

    output = output_directory or _resolve(profile["output_directory"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "case_results.jsonl").write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in case_results),
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Legacy 7청크 회귀·Smoke 산출물 생성")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--output-directory")
    args = parser.parse_args()

    profile_path = _resolve(args.profile)
    output_directory = _resolve(args.output_directory) if args.output_directory else None
    summary = build_smoke_artifacts(
        profile_path,
        output_directory,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
