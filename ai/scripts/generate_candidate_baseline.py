"""현재 작업 트리의 AI/RAG 후보 기준선을 재현 가능한 Hash와 함께 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.scripts.build_vector_index import _chunk_set_sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CURRENT_CONTRACT_VERSION = "4.0.0"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_contract_sha256(contract_root: Path | None = None) -> str:
    """상대 경로와 정렬된 JSON 내용을 묶어 계약 전체의 Canonical Hash를 만든다."""
    root = contract_root or (REPOSITORY_ROOT / "contracts" / "ai")
    schema_paths = sorted(root.rglob("*.schema.json"), key=lambda item: item.as_posix())
    if not schema_paths:
        raise RuntimeError(f"계약 Schema가 없습니다: {root}")
    canonical = [
        {
            "path": path.relative_to(root).as_posix(),
            "schema": json.loads(path.read_text(encoding="utf-8")),
        }
        for path in schema_paths
    ]
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def _load_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _dataset_entry(relative_path: str, case_count: int) -> dict[str, Any]:
    path = REPOSITORY_ROOT / relative_path
    return {
        "path": relative_path,
        "case_count": case_count,
        "file_sha256": file_sha256(path),
    }


def build_candidate_baseline(unit_test_result: str, unit_test_exit_code: int) -> dict[str, Any]:
    retrieval_path = "data/config/rag/jac104_retrieval_cases.json"
    safety_path = "ai/evaluation/datasets/safety/safety_eval_dataset.json"
    structuring_path = "ai/evaluation/datasets/structuring/symptom_eval_dataset.json"
    approved_chunks_path = "data/processed/structured/rag/mvp/rag_verified_sample.jsonl"
    offline_report_path = "ai/evaluation/reports/latest_eval_report.json"
    structuring_report_path = "ai/evaluation/reports/structuring_evaluation_20260807.json"
    pgvector_report_path = "ai/evaluation/reports/pgvector_verification.json"
    latency_report_path = "ai/evaluation/reports/pgvector_latency_baseline_20260806.json"

    retrieval_dataset = _load_json(retrieval_path)
    safety_dataset = json.loads((REPOSITORY_ROOT / safety_path).read_text(encoding="utf-8"))
    structuring_dataset = _load_json(structuring_path)
    offline_report = _load_json(offline_report_path)
    structuring_report = _load_json(structuring_report_path)
    pgvector_report = _load_json(pgvector_report_path)
    latency_report = _load_json(latency_report_path)
    manifest = _load_json("ai/configs/index_manifest.json")
    retry_policy = yaml.safe_load(
        (REPOSITORY_ROOT / "ai" / "configs" / "retry_policy.yaml").read_text(encoding="utf-8")
    )

    chunks = ChunkLoader().load_verified_chunks()
    canonical_chunk_set = _chunk_set_sha256(chunks)
    if canonical_chunk_set != manifest["chunk_set_sha256"]:
        raise RuntimeError("현재 승인 청크의 Canonical Hash가 Index Manifest와 다릅니다.")
    if structuring_report["status"] != "PASS":
        raise RuntimeError("구조화 평가가 PASS가 아니므로 후보 기준선을 생성할 수 없습니다.")
    if unit_test_exit_code != 0:
        raise RuntimeError("단위 테스트 실패 상태에서는 후보 기준선을 생성할 수 없습니다.")

    schema_paths = sorted((REPOSITORY_ROOT / "contracts" / "ai").rglob("*.schema.json"))
    contract_versions = {
        json.loads(path.read_text(encoding="utf-8")).get("x-contract-version")
        for path in schema_paths
    }
    contract_versions.discard(None)
    if contract_versions != {CURRENT_CONTRACT_VERSION}:
        raise RuntimeError(f"AI 계약 Version이 단일하지 않습니다: {sorted(contract_versions)}")

    dirty_lines = [line for line in _git("status", "--porcelain").splitlines() if line]
    return {
        "status": "CANDIDATE_REQUIRES_TEAM_DB_RERUN_AND_COMMIT",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_commit": _git("rev-parse", "HEAD"),
        "working_tree_committed": not dirty_lines,
        "working_tree_changed_path_count": len(dirty_lines),
        "runtime": {
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
            "dependency_lock": "ai/requirements.lock",
            "unit_tests": {
                "command": r".\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q",
                "result": unit_test_result,
                "exit_code": unit_test_exit_code,
            },
            "retry_policy": {
                "ai_internal_retry_enabled": retry_policy["ai_internal_retry"]["enabled"],
                "max_retry_count": retry_policy["ai_internal_retry"]["max_retry_count"],
                "backoff_factor_seconds": retry_policy["ai_internal_retry"]["backoff_factor"],
                "backend_retry_count": retry_policy["backend_integration"]["backend_retry_count"],
                "overall_timeout_seconds": retry_policy["backend_integration"]["overall_timeout_seconds"],
                "retry_scope": "transient retrieval provider errors only",
            },
        },
        "contract": {
            "version": CURRENT_CONTRACT_VERSION,
            "schema_draft": "2020-12",
            "schema_file_count": len(schema_paths),
            "canonical_rule": "sorted relative schema path + recursively key-sorted JSON; UTF-8; compact separators",
            "evaluated_contract_sha256": canonical_contract_sha256(),
            "parity_result": "PASS",
        },
        "embedding": {
            "model": manifest["model_name"],
            "revision": manifest["model_revision"],
            "dimension": manifest["dimension"],
            "normalization": True,
        },
        "datasets": {
            "retrieval": _dataset_entry(retrieval_path, len(retrieval_dataset["cases"])),
            "safety": _dataset_entry(safety_path, len(safety_dataset)),
            "structuring": {
                **_dataset_entry(structuring_path, len(structuring_dataset["cases"])),
                "dataset_id": structuring_dataset["dataset_id"],
                "version": structuring_dataset["version"],
            },
            "approved_chunks": {
                "path": approved_chunks_path,
                "chunk_count": len(chunks),
                "file_sha256": file_sha256(REPOSITORY_ROOT / approved_chunks_path),
                "canonical_chunk_set_sha256": canonical_chunk_set,
            },
        },
        "current_offline_evaluation": {
            "report": offline_report_path,
            "report_file_sha256": file_sha256(REPOSITORY_ROOT / offline_report_path),
            "rag": {
                "status": offline_report["rag_evaluation"]["status"],
                "case_count": offline_report["rag_evaluation"]["total_cases"],
                "metrics_publishable": False,
            },
            "safety": {
                "evaluation_mode": offline_report["safety_evaluation"]["evaluation_mode"],
                "case_count": offline_report["safety_evaluation"]["total_cases"],
                "passed_count": offline_report["safety_evaluation"]["compliant_cases"],
                "compliance_rate_percent": offline_report["safety_evaluation"]["safety_compliance_rate"],
            },
            "structuring": {
                "report": structuring_report_path,
                "report_file_sha256": file_sha256(REPOSITORY_ROOT / structuring_report_path),
                **structuring_report["summary"],
            },
        },
        "isolated_pgvector_historical_evidence": {
            "report": pgvector_report_path,
            "report_file_sha256": file_sha256(REPOSITORY_ROOT / pgvector_report_path),
            "verified_at": pgvector_report["verified_at"],
            "postgresql": pgvector_report["database"]["postgres_version"].split()[0],
            "pgvector": pgvector_report["database"]["pgvector_version"],
            "case_count": pgvector_report["summary"]["case_count"],
            "passed_count": pgvector_report["summary"]["passed_count"],
            "mean_positive_recall_at_5": pgvector_report["summary"]["mean_positive_recall_at_5"],
            "mean_positive_mrr": pgvector_report["summary"]["mean_positive_mrr"],
            "forbidden_hit_count": pgvector_report["summary"]["forbidden_hit_count"],
            "scope": "isolated disposable database; not team database completion evidence",
        },
        "isolated_pgvector_latency_baseline": {
            "report": latency_report_path,
            "report_file_sha256": file_sha256(REPOSITORY_ROOT / latency_report_path),
            "measured_at": latency_report["measured_at"],
            "scope": "personal isolated single-user baseline; not team DB or HTTP/Backend E2E evidence",
            "cold_runs": latency_report["methodology"]["cold_runs"],
            "warm_runs": latency_report["methodology"]["warm_runs"],
            "warm_retrieval_total_mean_ms": latency_report["warm"]["retrieval_total_ms"]["mean_ms"],
            "warm_retrieval_total_p50_ms": latency_report["warm"]["retrieval_total_ms"]["p50_ms"],
            "warm_retrieval_total_p95_ms": latency_report["warm"]["retrieval_total_ms"]["p95_ms"],
            "failed_request_count": latency_report["validation"]["failed_request_count"],
        },
        "mvp_scope": {
            "allowed_model": "WPUJAC104DWH",
            "allowed_generation": "D",
            "official_document": "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00",
            "blocked_models": ["WPUIAC425SNW", "WPU-IAC506"],
            "unverified_faq_as_sole_evidence": False,
        },
        "pending_gates": {
            "team_db_migration_and_rerun": True,
            "backend_storage_e2e": True,
            "data_owner_approved_post_retrieval_policy_case_13": True,
            "candidate_commit": True,
        },
        "publication_limits": [
            "Do not publish offline RAG zero metrics as retrieval quality metrics.",
            "Do not represent isolated pgvector evidence as a current team database rerun.",
            "Do not generalize the 12-case structuring baseline beyond the covered deterministic rules.",
            "Do not claim model training, fine-tuning, external LLM generation, or multi-agent completion.",
            "Commit this candidate and rerun pgvector evaluation against the approved team database before integration approval.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AI/RAG 후보 기준선 JSON 생성")
    parser.add_argument(
        "--output",
        default="ai/evaluation/reports/official_mvp_baseline_20260803.json",
    )
    parser.add_argument("--unit-test-result", required=True)
    parser.add_argument("--unit-test-exit-code", type=int, required=True)
    args = parser.parse_args()

    baseline = build_candidate_baseline(args.unit_test_result, args.unit_test_exit_code)
    output = REPOSITORY_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dirty_lines = [line for line in _git("status", "--porcelain").splitlines() if line]
    baseline["working_tree_committed"] = not dirty_lines
    baseline["working_tree_changed_path_count"] = len(dirty_lines)
    output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": baseline["status"],
        "source_commit": baseline["source_commit"],
        "working_tree_committed": baseline["working_tree_committed"],
        "output": args.output,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
