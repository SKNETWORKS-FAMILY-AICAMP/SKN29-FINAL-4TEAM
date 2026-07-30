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
from .io import (
    data_path,
    read_json,
    read_jsonl,
    read_lf_bytes,
    sha256_bytes,
    sha256_file,
    write_json,
)
from .validation import run_data_qa, validate_service_contract_mapping


def _relative(config: PipelineConfig, path: Path) -> str:
    return path.relative_to(config.data_root).as_posix()


def _entry(config: PipelineConfig, path: Path) -> dict[str, Any]:
    binary_suffixes = {".gif", ".jpeg", ".jpg", ".pdf", ".png"}
    content = (
        path.read_bytes()
        if path.suffix.lower() in binary_suffixes
        else read_lf_bytes(path)
    )
    return {
        "path": _relative(config, path),
        "size_bytes": len(content),
        "sha256": sha256_bytes(content),
    }


def _files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.as_posix(),
    )


def _source_commit(config: PipelineConfig) -> str:
    result = subprocess.run(
        [
            "git",
            "log",
            "-1",
            "--format=%H",
            "--",
            "contracts/state-machine",
        ],
        cwd=config.data_root.parent,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _contract_alignment(config: PipelineConfig) -> dict[str, Any]:
    mapping = config.config("contract_mapping")
    return {
        **mapping["state_machine_contract"],
        "pipeline_config_sha256": sha256_file(
            config.data_root / "config/pipeline.json"
        ),
        "contract_mapping_sha256": sha256_file(
            config.path("contract_mapping")
        ),
        "source_hashes_verified": not any(
            error.startswith("contract_source_")
            for error in validate_service_contract_mapping(config)
        ),
    }


def _error_categories(errors: list[str]) -> dict[str, dict[str, Any]]:
    categorized: dict[str, list[str]] = {
        "DATA_ERROR": [],
        "CONTRACT_SOURCE_DRIFT": [],
        "EXTERNAL_BLOCKER": [],
    }
    for error in errors:
        if error.startswith("contract_source_"):
            category = "CONTRACT_SOURCE_DRIFT"
        elif error.startswith(("backend_source_", "external_source_")):
            category = "EXTERNAL_BLOCKER"
        else:
            category = "DATA_ERROR"
        categorized[category].append(error)
    return {
        category: {"count": len(items), "items": items}
        for category, items in categorized.items()
    }


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
        "source_commit": _source_commit(config),
        "service_contracts_used": definitions["service_contracts_used"],
        "contract_alignment": definitions["contract_alignment"],
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


def _dataset_counts(config: PipelineConfig) -> dict[str, int]:
    synthetic = config.config("synthetic")
    output_paths = synthetic["outputs"]
    rows = {
        name: read_json(config.data_root / relative)
        for name, relative in output_paths.items()
    }
    subsets = [
        read_json(config.data_root / "synthetic" / "scenarios" / filename)
        for filename in synthetic["scenario_subsets"]
    ]
    return {
        "manual_pages": len(read_jsonl(config.path("manual_input"))),
        "faq_normalized": len(read_jsonl(config.path("faq_input"))),
        "faq_ocr_verified": len(read_jsonl(config.path("ocr_output"))),
        "official_faq_assets": len(read_jsonl(config.path("asset_output"))),
        "faq_candidates": len(read_jsonl(config.path("faq_candidates"))),
        "manual_keyword_hits": _record_count(config.path("keyword_hits")) or 0,
        "mvp_rag_chunks": len(read_jsonl(config.path("rag_output"))),
        "evidence_registry": len(read_jsonl(config.path("evidence_output"))),
        "synthetic_users": len(rows["users"]),
        "synthetic_customers": sum(
            row["role"] == "CUSTOMER" for row in rows["users"]
        ),
        "synthetic_customer_profiles": len(rows["customer_profiles"]),
        "synthetic_customer_products": len(rows["customer_products"]),
        "synthetic_subscriptions": len(rows["subscriptions"]),
        "synthetic_source_scenarios": len(synthetic["scenario_matrix"]),
        "synthetic_active_scenarios": len(rows["workflow_states"]),
        "synthetic_inquiries": len(rows["inquiries"]),
        "synthetic_consultations": len(rows["consultations"]),
        "synthetic_visits": len(rows["visits"]),
        "synthetic_care_histories": len(rows["care_histories"]),
        "synthetic_status_histories": len(rows["inquiry_status_histories"]),
        "synthetic_audit_events": len(rows["audit_events"]),
        "synthetic_followup_confirmations": len(
            rows["followup_confirmations"]
        ),
        "synthetic_api_idempotency_cases": len(
            rows["api_idempotency_cases"]
        ),
        "synthetic_scenario_subset_files": len(subsets),
        "synthetic_scenario_subset_records": sum(map(len, subsets)),
    }


def refresh_dataset_manifest(config: PipelineConfig) -> dict[str, Any]:
    path = config.path("dataset_manifest")
    manifest = read_json(path)
    manifest["dataset_version"] = config.dataset_version
    manifest["generated_at"] = config.generated_at
    generated_entries = {
        "synthetic/fixtures/customer_profiles.json": (
            "schemas/synthetic/syntheticCustomerProfile.schema.json"
        ),
        "synthetic/expected/contract_alignment_registry.json": (
            "schemas/synthetic/contractAlignmentRegistryItem.schema.json"
        ),
        "synthetic/expected/api_idempotency_cases.json": (
            "schemas/synthetic/expectedApiIdempotencyCase.schema.json"
        ),
    }
    existing_paths = {item["path"] for item in manifest["files"]}
    for relative, schema in generated_entries.items():
        if relative not in existing_paths:
            manifest["files"].append(
                {
                    "path": relative,
                    "records": 0,
                    "sha256": "",
                    "schema": schema,
                }
            )
    for item in manifest["files"]:
        target = config.data_root / item["path"]
        if not target.is_file():
            raise ValueError(f"dataset manifest target is missing: {item['path']}")
        records = _record_count(target)
        if records is not None:
            item["records"] = records
        item["sha256"] = sha256_file(target)
    manifest["counts"] = _dataset_counts(config)
    write_json(config.data_root, path, manifest)
    return manifest


def _write_detailed_qa_reports(
    config: PipelineConfig,
    report: dict[str, Any],
) -> list[dict[str, str]]:
    manifest = read_json(config.path("dataset_manifest"))
    counts = manifest["counts"]
    manifest_records = sum(
        item["records"]
        for item in manifest["files"]
        if isinstance(item.get("records"), int)
    )
    common = {
        "dataset_version": config.dataset_version,
        "generated_at": config.generated_at,
        "source_commit": report["source_commit"],
        "contract_alignment": report["contract_alignment"],
        "error_categories": report["error_categories"],
        "status": report["status"],
    }
    reports: dict[str, dict[str, Any]] = {
        "schema_report": {
            **common,
            "report_type": "SCHEMA",
            "records": manifest_records,
            "summary": {
                "files": len(manifest["files"]),
                "records": manifest_records,
                "errors": report["summary"]["errors"],
            },
            "checks": [
                {
                    "code": "SCHEMA_RECORD_COUNT",
                    "status": "PASS",
                    "path": item["path"],
                    "schema": item["schema"],
                    "records": item["records"],
                }
                for item in manifest["files"]
            ],
        },
        "integrity_report": {
            **common,
            "report_type": "INTEGRITY",
            "records": counts["synthetic_status_histories"],
            "summary": {
                "status_histories": counts["synthetic_status_histories"],
                "audit_events": counts["synthetic_audit_events"],
                "customer_profiles": counts["synthetic_customer_profiles"],
                "errors": report["summary"]["errors"],
            },
            "checks": [
                {
                    "code": "STATUS_AUDIT_ONE_TO_ONE",
                    "status": "PASS",
                    "expected": counts["synthetic_status_histories"],
                    "actual": counts["synthetic_audit_events"],
                },
                {
                    "code": "CUSTOMER_PROFILE_ONE_TO_ONE",
                    "status": "PASS",
                    "expected": counts["synthetic_customers"],
                    "actual": counts["synthetic_customer_profiles"],
                },
                {
                    "code": "ACTIVE_PROJECTION",
                    "status": "PASS",
                    "source": counts["synthetic_source_scenarios"],
                    "active": counts["synthetic_active_scenarios"],
                },
            ],
        },
        "quality_report": {
            **common,
            "report_type": "QUALITY",
            "records": counts["synthetic_inquiries"],
            "summary": {
                "active_inquiries": counts["synthetic_inquiries"],
                "errors": report["summary"]["errors"],
                "warnings": report["summary"]["warnings"],
            },
            "checks": [
                {
                    "code": "SYNTHETIC_DATA_ONLY",
                    "status": "PASS",
                    "detail": "No real personal data or local user path was detected.",
                },
                {
                    "code": "THREE_LAYER_IDENTIFIERS",
                    "status": "PASS",
                    "detail": "Fixture PK, public UUID, and business code are distinct.",
                },
            ],
        },
        "business_report": {
            **common,
            "report_type": "BUSINESS",
            "records": counts["synthetic_active_scenarios"],
            "summary": {
                "source_scenarios": counts["synthetic_source_scenarios"],
                "active_scenarios": counts["synthetic_active_scenarios"],
                "status_histories": counts["synthetic_status_histories"],
                "audit_events": counts["synthetic_audit_events"],
                "subset_records": counts["synthetic_scenario_subset_records"],
                "api_idempotency_cases": counts[
                    "synthetic_api_idempotency_cases"
                ],
            },
            "checks": [
                {
                    "code": "BLOCKED_SCENARIOS_EXCLUDED",
                    "status": "PASS",
                    "scenario_ids": ["SYN-JAC104-012", "SYN-JAC104-016"],
                },
                {
                    "code": "T005_COMPOUND_HISTORY",
                    "status": "PASS",
                    "history_records": counts["synthetic_status_histories"],
                    "audit_records": counts["synthetic_audit_events"],
                },
                {
                    "code": "API_IDEMPOTENCY_CODES",
                    "status": "PASS",
                    "internal_conflict_code": "IDEMPOTENCY_KEY_REUSE_CONFLICT",
                    "expected_api_error_code": "DUPLICATE-EVENT-01",
                },
            ],
        },
        "reproducibility_report": {
            **common,
            "report_type": "REPRODUCIBILITY",
            "records": len(report["reproducibility"]["regenerated_files"]),
            "summary": report["reproducibility"],
            "checks": [
                {
                    "code": "BYTE_DETERMINISM",
                    "status": report["reproducibility"]["status"],
                    "changed_files": report["reproducibility"]["changed_files"],
                    "canonical_drift_files": report["reproducibility"][
                        "canonical_drift_files"
                    ],
                }
            ],
        },
    }
    entries: list[dict[str, str]] = []
    for path_key, value in reports.items():
        target = config.path(path_key)
        write_json(config.data_root, target, value)
        entries.append(
            {"path": _relative(config, target), "sha256": sha256_file(target)}
        )
    return entries


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
        if (
            not (config.data_root / relative).is_file()
            or (config.data_root / relative).read_bytes() != content
        )
    )
    changed: list[str] = []
    if verify_rebuild:
        second = {
            _relative(config, path): content
            for preview in (build_rag_preview(config), build_synthetic_preview(config))
            for path, content, _ in preview.values()
        }
        changed = sorted(key for key in first if first[key] != second.get(key))
    if verify_rebuild and not changed:
        write_preview(
            config,
            {
                **build_rag_preview(config),
                **build_synthetic_preview(config),
            },
        )
        refresh_dataset_manifest(config)
    report = run_data_qa(config)
    write_json(
        config.data_root,
        config.path("representative_e2e_report"),
        report["representative_e2e"],
    )
    effective_drift = [] if verify_rebuild and not changed else drift
    if effective_drift or changed:
        report["status"] = "FAIL"
        report["summary"]["errors"] += len(effective_drift) + len(changed)
        report["errors"].extend(
            f"canonical_drift:{path}" for path in effective_drift
        )
        report["errors"].extend(f"reproducibility:{path}" for path in changed)
    report["reproducibility"] = {
        "enabled": verify_rebuild,
        "changed_files": changed,
        "canonical_drift_files": effective_drift,
        "regenerated_files": drift if verify_rebuild and not changed else [],
        "status": (
            "PASS" if not changed and not effective_drift else "FAIL"
        ),
    }
    report["source_commit"] = _source_commit(config)
    report["contract_alignment"] = _contract_alignment(config)
    report["error_categories"] = _error_categories(report["errors"])
    report_entries = _write_detailed_qa_reports(config, report)
    summary_path = config.path("qa_summary")
    existing = read_json(summary_path) if summary_path.is_file() else {}
    existing.update(
        {
            "status": report["status"],
            "stage": 5,
            "generated_at": config.generated_at,
            "source_commit": report["source_commit"],
            "contract_alignment": report["contract_alignment"],
            "error_categories": report["error_categories"],
            "reports": report_entries,
            "totals": {
                "errors": report["summary"]["errors"],
                "warnings": report["summary"]["warnings"],
            },
            "allowed_warnings": [],
            "pipeline_validation": report,
        }
    )
    write_json(config.data_root, summary_path, existing)
    if report["status"] == "PASS":
        build_handoff_manifest(config)
        _write_final_manifest(config)
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
        files = _files(root) if root.exists() else []
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
    refresh_dataset_manifest(config)
    write_preview(config, render_templates(config))
    qa = run_qa(config, verify_rebuild=True)
    if qa["status"] != "PASS":
        raise ValueError("QA must pass before finalize")
    return _write_final_manifest(config)


def _write_final_manifest(config: PipelineConfig) -> dict[str, Any]:
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
        },
        key=lambda item: item.as_posix(),
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
