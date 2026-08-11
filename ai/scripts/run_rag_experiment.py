#!/usr/bin/env python3
"""재현 가능한 RAG 실험 산출물 계약을 제공하는 A3 CLI Runner."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ai.evaluation.file_integrity import file_sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = "experiment_runner_contract_v1"
DEFAULT_DATASET = "rag_gold_v1"
DEFAULT_SPLIT = "DEV"
RESULT_FILES = {
    "manifest": "manifest.json",
    "case_results": "case_results.jsonl",
    "retrieval_summary": "retrieval_summary.json",
    "generation_summary": "generation_summary.json",
    "safety_summary": "safety_summary.json",
    "performance_summary": "performance_summary.json",
}


def _resolve_repo_path(path_value: str) -> Path:
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


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()


def _display_path(path: Path) -> str:
    try:
        return _relative(path)
    except ValueError:
        return path.resolve().as_posix()


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


def _ram_mb() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_phys", ctypes.c_ulonglong),
                ("avail_phys", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("avail_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("avail_virtual", ctypes.c_ulonglong),
                ("avail_extended_virtual", ctypes.c_ulonglong),
            ]
        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.total_phys / (1024 * 1024))
        return None
    if hasattr(os, "sysconf"):
        try:
            return round(
                os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
                / (1024 * 1024)
            )
        except (ValueError, OSError):
            return None
    return None


def _resolve_profile(profile_value: str) -> Path:
    candidate = Path(profile_value)
    if candidate.suffix:
        return _resolve_repo_path(profile_value)
    return _resolve_repo_path(f"ai/configs/experiments/{profile_value}.yaml")


def _validate_run_id(run_id: str) -> str:
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]+", run_id) is None:
        raise ValueError("run_id는 영문 소문자·숫자로 시작하고 ._-만 사용할 수 있습니다.")
    return run_id


def _corpus_facts(profile: dict[str, Any]) -> dict[str, Any]:
    files = []
    for definition in profile["corpus"]["files"]:
        path = _resolve_repo_path(definition["path"])
        files.append({
            "role": definition["role"],
            "path": _relative(path),
            "sha256": _sha256(path),
        })
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":"))
    return {
        "version": profile["corpus"]["version"],
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper(),
        "files": files,
    }


def _validate_artifacts(
    schema_path: Path,
    manifest: dict[str, Any],
    cases: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> None:
    schema = _load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for label, item in [
        ("manifest", manifest),
        *[(f"case:{row['case_id']}", row) for row in cases],
        *[(f"summary:{row['summary_type']}", row) for row in summaries],
    ]:
        errors.extend(
            f"{label}: {error.message}"
            for error in validator.iter_errors(item)
        )
    if errors:
        raise ValueError("Result Schema 검증 실패: " + " | ".join(errors[:10]))


def run_validation_only(
    *,
    profile_path: Path,
    dataset_alias: str,
    split: str,
    run_id: str,
    output_directory: Path | None = None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    profile = _load_json(profile_path)
    if profile.get("execution_mode") != "VALIDATE_ONLY":
        raise ValueError("A3 Runner는 현재 VALIDATE_ONLY Profile만 지원합니다.")
    if dataset_alias != profile["dataset"]["alias"]:
        raise ValueError(
            f"Profile Dataset alias 불일치: expected={profile['dataset']['alias']}"
        )
    if split not in {"DEV", "TEST", "SAFETY"}:
        raise ValueError(f"지원하지 않는 Split: {split}")

    dataset_path = _resolve_repo_path(profile["dataset"]["path"])
    dataset_manifest_path = _resolve_repo_path(profile["dataset"]["manifest_path"])
    dataset_manifest = _load_json(dataset_manifest_path)
    all_cases = _load_jsonl(dataset_path)
    selected = [case for case in all_cases if case["split"] == split]
    if not selected:
        raise ValueError(f"선택된 Case가 없습니다: split={split}")

    output = output_directory or _resolve_repo_path(
        f"{profile['output_root']}/{run_id}"
    )
    output.mkdir(parents=True, exist_ok=True)
    result_schema_path = _resolve_repo_path(profile["result_schema"])
    case_results = [
        {
            "artifact_type": "EXPERIMENT_CASE_RESULT",
            "schema_version": "1.0.0",
            "run_id": run_id,
            "case_id": case["case_id"],
            "split": case["split"],
            "query_variant_type": case["query_variant_type"],
            "query": case["query"],
            "execution_status": "NOT_EXECUTED_VALIDATION_ONLY",
            "expected": {
                "evidence": case["expected_evidence"],
                "evidence_match_policy": case["evidence_match_policy"],
                "no_evidence": case["expected_no_evidence"],
                "risk_level": case["expected_risk_level"],
                "guidance_policy": case["expected_guidance_policy"],
                "forbidden_document_ids": case["forbidden_document_ids"],
                "forbidden_model_codes": case["forbidden_model_codes"],
                "review_status": case["review_status"],
            },
            "actual": None,
            "metrics": None,
            "error": None,
        }
        for case in selected
    ]

    summary_limit = "VALIDATE_ONLY: 모델·검색·생성 미실행, 성능 지표 없음"
    summaries = [
        {
            "artifact_type": "EXPERIMENT_SUMMARY",
            "schema_version": "1.0.0",
            "run_id": run_id,
            "summary_type": summary_type,
            "status": "NOT_EXECUTED_VALIDATION_ONLY",
            "selected_case_count": len(selected),
            "executed_case_count": 0,
            "metrics": {},
            "limitations": [summary_limit],
        }
        for summary_type in ["RETRIEVAL", "GENERATION", "SAFETY", "PERFORMANCE"]
    ]

    completed_at = datetime.now(timezone.utc)
    execution_seconds = round(time.perf_counter() - started_clock, 6)
    review_counts = Counter(case["review_status"] for case in selected)
    manifest = {
        "artifact_type": "EXPERIMENT_MANIFEST",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "run_status": "VALIDATION_ONLY_COMPLETE",
        "execution_mode": "VALIDATE_ONLY",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "execution_seconds": execution_seconds,
        "profile": {
            "profile_id": profile["profile_id"],
            "profile_version": profile["profile_version"],
            "path": _relative(profile_path),
            "sha256": _sha256(profile_path),
        },
        "dataset": {
            "dataset_id": profile["dataset"]["dataset_id"],
            "dataset_version": dataset_manifest["dataset_version"],
            "path": _relative(dataset_path),
            "sha256": _sha256(dataset_path),
            "manifest_path": _relative(dataset_manifest_path),
            "manifest_sha256": _sha256(dataset_manifest_path),
            "split": split,
            "total_case_count": len(all_cases),
            "selected_case_count": len(selected),
            "review_status_counts": dict(sorted(review_counts.items())),
            "gold_approved_for_official_metrics": all(
                case["review_status"] == "TWO_PERSON_APPROVED" for case in selected
            ),
        },
        "corpus": _corpus_facts(profile),
        "chunking": profile["chunking"],
        "embedding": profile["embedding"],
        "retrieval": profile["retrieval"],
        "generation": profile["generation"],
        "runtime": {
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
            "cpu": platform.processor() or platform.machine(),
            "gpu": None,
            "ram_mb": _ram_mb(),
            "vram_mb": None,
            "hardware_detection_note": "GPU/VRAM은 VALIDATE_ONLY에서 탐지하지 않음",
        },
        "git": _git_facts(),
        "outputs": {
            name: f"{_display_path(output)}/{filename}"
            for name, filename in RESULT_FILES.items()
        },
        "publication_limits": profile["publication_limits"],
    }

    _validate_artifacts(result_schema_path, manifest, case_results, summaries)
    (output / RESULT_FILES["manifest"]).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / RESULT_FILES["case_results"]).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in case_results),
        encoding="utf-8",
    )
    for summary, key in zip(
        summaries,
        ["retrieval_summary", "generation_summary", "safety_summary", "performance_summary"],
        strict=True,
    ):
        (output / RESULT_FILES[key]).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="A3 RAG Experiment Runner")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--mode", default="validate-only", choices=["validate-only"])
    parser.add_argument("--run-id")
    parser.add_argument("--output-directory")
    args = parser.parse_args()

    run_id = _validate_run_id(args.run_id or (
        "rag-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ))
    profile_path = _resolve_profile(args.profile)
    output_directory = (
        _resolve_repo_path(args.output_directory)
        if args.output_directory
        else None
    )
    manifest = run_validation_only(
        profile_path=profile_path,
        dataset_alias=args.dataset,
        split=args.split,
        run_id=run_id,
        output_directory=output_directory,
    )
    print(json.dumps({
        "run_id": manifest["run_id"],
        "run_status": manifest["run_status"],
        "execution_mode": manifest["execution_mode"],
        "selected_case_count": manifest["dataset"]["selected_case_count"],
        "gold_approved_for_official_metrics": manifest["dataset"][
            "gold_approved_for_official_metrics"
        ],
        "outputs": manifest["outputs"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
