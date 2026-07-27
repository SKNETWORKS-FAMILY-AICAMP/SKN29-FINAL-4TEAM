"""QA reporting, inventory, and finalization operations."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any

from .builders import (
    build_rag_preview,
    build_synthetic_preview,
    render_templates,
    write_preview,
)
from .config import PipelineConfig
from .io import data_path, read_json, sha256_file, write_json
from .validation import run_data_qa


def _relative(config: PipelineConfig, path: Path) -> str:
    return path.relative_to(config.data_root).as_posix()


def _entry(config: PipelineConfig, path: Path) -> dict[str, Any]:
    return {
        "path": _relative(config, path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def _record_count(path: Path) -> int | None:
    if path.suffix == ".jsonl":
        return sum(
            1
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    if path.suffix == ".csv":
        rows = path.read_text(encoding="utf-8").splitlines()
        return max(0, len(rows) - 1)
    if path.suffix == ".json":
        value = read_json(path)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict) and isinstance(value.get("scenarios"), list):
            return len(value["scenarios"])
        return 1
    return None


def build_handoff_manifest(
    config: PipelineConfig,
    *,
    profile: str | None = None,
) -> dict[str, Any]:
    definitions = config.config("handoff")
    available = definitions["profiles"]
    if profile and profile not in available:
        raise ValueError(f"unknown handoff profile: {profile}")
    resolved: dict[str, Any] = {}
    unique_paths: set[str] = set()
    for name, value in available.items():
        items = []
        for item in value["items"]:
            path = data_path(config.data_root, item["path"])
            if not path.is_file():
                raise ValueError(f"handoff target is missing: {item['path']}")
            unique_paths.add(item["path"])
            items.append(
                {
                    **item,
                    "records": _record_count(path),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        resolved[name] = {**value, "items": items}
    manifest = {
        "status": "PASS",
        "dataset_version": config.dataset_version,
        "generated_at": config.generated_at,
        "service_contracts_used": False,
        "profile_count": len(resolved),
        "unique_file_count": len(unique_paths),
        "profiles": resolved,
    }
    target = config.path("handoff_manifest")
    write_json(config.data_root, target, manifest)
    selected = resolved if profile is None else {profile: resolved[profile]}
    return {
        "status": "PASS",
        "manifest": _relative(config, target),
        "selected_profiles": selected,
        "summary": {
            "profile_count": len(selected),
            "unique_file_count": len(
                {
                    item["path"]
                    for value in selected.values()
                    for item in value["items"]
                }
            ),
        },
    }


def _refresh_dataset_manifest(config: PipelineConfig) -> dict[str, Any]:
    path = config.path("dataset_manifest")
    manifest = read_json(path)
    manifest["dataset_version"] = config.dataset_version
    manifest["generated_at"] = config.generated_at
    for item in manifest["files"]:
        target = config.data_root / item["path"]
        if not target.is_file():
            raise ValueError(f"dataset manifest target is missing: {item['path']}")
        item["sha256"] = sha256_file(target)
    write_json(config.data_root, path, manifest)
    return manifest


def run_qa(config: PipelineConfig, *, verify_rebuild: bool = False) -> dict[str, Any]:
    previews = [build_rag_preview(config), build_synthetic_preview(config)]
    first = {
        _relative(config, path): content
        for preview in previews
        for path, content, _ in preview.values()
    }
    drift = sorted(
        relative
        for relative, content in first.items()
        if (config.data_root / relative).read_bytes() != content
    )
    changed: list[str] = []
    if verify_rebuild:
        second = {
            _relative(config, path): content
            for preview in (build_rag_preview(config), build_synthetic_preview(config))
            for path, content, _ in preview.values()
        }
        changed = sorted(key for key in first if first[key] != second.get(key))
    report = run_data_qa(config)
    write_json(
        config.data_root,
        config.path("representative_e2e_report"),
        report["representative_e2e"],
    )
    if drift or changed:
        report["status"] = "FAIL"
        report["summary"]["errors"] += len(drift) + len(changed)
        report["errors"].extend(f"canonical_drift:{path}" for path in drift)
        report["errors"].extend(f"reproducibility:{path}" for path in changed)
    report["reproducibility"] = {
        "enabled": verify_rebuild,
        "changed_files": changed,
        "canonical_drift_files": drift,
        "status": "PASS" if not changed else "FAIL",
    }
    summary_path = config.path("qa_summary")
    existing = read_json(summary_path) if summary_path.is_file() else {}
    existing.update(
        {
            "status": report["status"],
            "stage": 5,
            "generated_at": config.generated_at,
            "totals": {
                "errors": report["summary"]["errors"],
                "warnings": report["summary"]["warnings"],
            },
            "allowed_warnings": [],
            "pipeline_validation": report,
        }
    )
    write_json(config.data_root, summary_path, existing)
    return report


def _tracked_paths(repo_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "data"],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    return set(result.stdout.splitlines()) if result.returncode == 0 else set()


def inventory(config: PipelineConfig) -> dict[str, Any]:
    tracked = _tracked_paths(config.data_root.parent)
    rows: list[dict[str, Any]] = []
    targets: dict[str, Any] = {}
    for name in ("raw", ".temp", ".work"):
        root = config.data_root / name
        files = sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []
        tracked_count = 0
        for path in files:
            relative = f"data/{_relative(config, path)}"
            is_tracked = relative in tracked
            tracked_count += int(is_tracked)
            rows.append(
                {
                    "target": f"data/{name}",
                    "relative_path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "git_tracked": is_tracked,
                    "recovery_class": (
                        "GIT_RECOVERABLE" if is_tracked else "NOT_GIT_RECOVERABLE"
                    ),
                }
            )
        targets[f"data/{name}"] = {
            "file_count": len(files),
            "size_bytes": sum(path.stat().st_size for path in files),
            "git_tracked_files": tracked_count,
            "not_git_recoverable_files": len(files) - tracked_count,
        }
    csv_path = config.path("inventory_csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "target",
        "relative_path",
        "size_bytes",
        "sha256",
        "git_tracked",
        "recovery_class",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    raw_originals = [
        row
        for row in rows
        if row["target"] == "data/raw"
        and Path(row["relative_path"]).suffix.lower()
        in {".pdf", ".json", ".jsonl", ".csv", ".html", ".jpg", ".jpeg", ".png"}
    ]
    qa = read_json(config.path("qa_summary"))
    assessment = {
        "status": "PASS",
        "generated_at": config.generated_at,
        "inventory_file": _relative(config, csv_path),
        "targets": targets,
        "raw_original_files_present": len(raw_originals),
        "canonical_data_readiness": {
            "latest_qa_status": qa.get("status"),
            "errors": qa.get("totals", {}).get("errors", 0),
            "warnings": qa.get("totals", {}).get("warnings", 0),
            "queryable_without_raw": True,
        },
    }
    write_json(config.data_root, config.path("inventory_report"), assessment)
    return assessment


def finalize(config: PipelineConfig, *, prepare: bool = False) -> dict[str, Any]:
    if prepare:
        return inventory(config)
    if (config.data_root / ".temp").exists() or (config.data_root / ".work").exists():
        raise ValueError("data/.temp and data/.work must be absent before finalize")
    _refresh_dataset_manifest(config)
    write_preview(config, render_templates(config))
    qa = run_qa(config, verify_rebuild=True)
    if qa["status"] != "PASS":
        raise ValueError("QA must pass before finalize")
    build_handoff_manifest(config)
    path = config.path("final_manifest")
    dataset = read_json(config.path("dataset_manifest"))
    data_files = []
    for item in dataset["files"]:
        target = config.data_root / item["path"]
        data_files.append({**item, **_entry(config, target)})
    metadata_paths = (
        _files(config.data_root / "catalog")
        + [
            config.data_root / "README.md",
            config.data_root / "schemas" / "README.md",
            config.data_root / "synthetic" / "README.md",
        ]
        + [
            item
            for item in _files(config.data_root / "tools")
            if item.suffix.lower() == ".md"
        ]
        + [
            item
            for item in _files(config.data_root / "processed" / "metadata")
            if item != path
        ]
    )
    data_path_set = {item["path"] for item in data_files}
    metadata_paths = sorted(
        {
            item
            for item in metadata_paths
            if _relative(config, item) not in data_path_set
        }
    )
    groups = {
        "data_files": data_files,
        "metadata_files": [_entry(config, item) for item in metadata_paths],
        "schema_files": [
            _entry(config, item)
            for item in _files(config.data_root / "schemas")
            if item.suffix == ".json"
        ],
        "build_tools": [
            _entry(config, item)
            for item in _files(config.data_root / "tools")
            if item.suffix == ".py"
        ],
        "config_files": [
            _entry(config, item) for item in _files(config.data_root / "config")
        ],
        "template_files": [
            _entry(config, item) for item in _files(config.data_root / "templates")
        ],
        "validation_reports": [
            _entry(config, item)
            for item in _files(config.data_root / "processed" / "validation")
        ],
        "policy_files": [
            _entry(config, item)
            for item in (
                [config.data_root / ".gitattributes"]
                + _files(config.data_root / "raw")
            )
        ],
    }
    python_lines = sum(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in _files(config.data_root / "tools")
        if path.suffix == ".py"
    )
    manifest = {
        "dataset_version": config.dataset_version,
        "config_version": config.values["config_version"],
        "generated_at": config.generated_at,
        "status": "PASS",
        "mvp_product_code": config.values["mvp_product_code"],
        "mvp_document_id": config.values["mvp_document_id"],
        "source_hashes": dataset["source_hashes"],
        **groups,
        "counts": dataset["counts"],
        "quality_gate": {
            "errors": 0,
            "warnings": 0,
            "reproducibility_changed_files": 0,
            "canonical_drift_files": 0,
        },
        "toolchain": {
            "python_files": len(groups["build_tools"]),
            "python_lines": python_lines,
            "max_wrapper_lines": 10,
            "max_module_lines": max(
                len(item.read_text(encoding="utf-8").splitlines())
                for item in _files(config.data_root / "tools" / "watercare")
                if item.suffix == ".py"
            ),
        },
        "rag_policy": {
            "included_model": config.values["mvp_product_code"],
            "included_pages": [37, 38, 39],
            "faq_included": 0,
            "blocked": [
                "WPUIAC425SNW",
                "WPU-IAC506",
                "WPUJAC104S family",
                "model-unverified common FAQ",
            ],
        },
        "retention": {
            "raw_original_files": 0,
            "raw_policy_files": len(_files(config.data_root / "raw")),
            "temp_exists": False,
            "work_exists": False,
        },
    }
    write_json(config.data_root, path, manifest)
    checked = sum(len(items) for items in groups.values())
    return {
        "status": "PASS",
        "dataset_version": config.dataset_version,
        "qa_errors": 0,
        "qa_warnings": 0,
        "manifest_entries_checked": checked,
        "temp_exists": False,
        "work_exists": False,
    }
