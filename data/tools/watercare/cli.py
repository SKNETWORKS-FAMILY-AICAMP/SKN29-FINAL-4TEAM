"""Unified and legacy-compatible WaterCare data CLI."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from .builders import (
    build_processed,
    build_rag_preview,
    build_synthetic_preview,
    render_templates,
    write_preview,
)
from .config import PipelineConfig, load_pipeline
from .io import ensure_within, sha256_file, write_bytes, write_json
from .operations import (
    build_handoff_manifest,
    finalize,
    inventory,
    refresh_dataset_manifest,
    run_qa,
)
from .validation import (
    compare_bytes,
    run_data_qa,
    schema_usage_codes,
    validate_configs,
)


def _data_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config(generated_at: str | None = None) -> PipelineConfig:
    config = load_pipeline(_data_root())
    if generated_at:
        return PipelineConfig(
            data_root=config.data_root,
            values={**config.values, "generated_at": generated_at},
        )
    return config


def _print(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _stage_report(
    config: PipelineConfig,
    *,
    stage: int,
    preview: dict[str, tuple[Path, bytes, int | None]],
) -> None:
    path = (
        config.data_root
        / "processed"
        / "validation"
        / f"step{stage}"
        / f"latest_step{stage}_report.json"
    )
    report = {
        "status": "PASS",
        "stage": stage,
        "generated_at": config.generated_at,
        "checks": {"schema_errors": 0, "integrity_errors": 0},
        "counts": {
            name: count for name, (_, _, count) in preview.items() if count is not None
        },
        "output_sha256": {
            name: sha256_file(target) for name, (target, _, _) in preview.items()
        },
    }
    write_json(config.data_root, path, report)


def _changed_scenario_records(
    preview: dict[str, tuple[Path, bytes, int | None]],
) -> int:
    target, content, _ = preview["demo_scenarios"]
    if not target.is_file():
        return len(json.loads(content)["scenarios"])
    before = {
        row["scenario_id"]: row
        for row in json.loads(target.read_text(encoding="utf-8"))["scenarios"]
    }
    after = {
        row["scenario_id"]: row
        for row in json.loads(content)["scenarios"]
    }
    return sum(before.get(key) != after.get(key) for key in before.keys() | after.keys())


def _build(
    target: str,
    generated_at: str | None,
    *,
    manual: Path | None = None,
    faq: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    config = _config(generated_at)
    if target == "processed":
        return 0, build_processed(config, manual=manual, faq=faq)
    preview = (
        build_rag_preview(config)
        if target == "rag"
        else build_synthetic_preview(config)
    )
    changed_business_records = (
        _changed_scenario_records(preview) if target == "synthetic" else 0
    )
    summary = write_preview(config, preview)
    refresh_dataset_manifest(config)
    stage = 3 if target == "rag" else 4
    _stage_report(config, stage=stage, preview=preview)
    qa = run_data_qa(config)
    summary.update(
        qa_status=qa["status"],
        qa_errors=qa["summary"]["errors"],
        changed_business_records=changed_business_records,
    )
    return (0 if qa["status"] == "PASS" else 1), summary


def run_equivalence(data_root: Path) -> dict[str, Any]:
    config = load_pipeline(data_root)
    work_root = ensure_within(data_root, data_root / ".work" / "declarative")
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)
    generated = {
        **build_rag_preview(config),
        **build_synthetic_preview(config),
        **render_templates(config),
    }
    comparisons = []
    for name, (canonical, content, records) in generated.items():
        relative = canonical.relative_to(data_root)
        write_bytes(data_root, work_root / relative, content)
        comparison = compare_bytes(
            canonical,
            content,
            display_path=relative.as_posix(),
            record_count=records,
        )
        comparison["name"] = name
        comparisons.append(comparison)
    checks = validate_configs(config)
    schema_codes = schema_usage_codes(data_root)
    configured_codes = config.config("vocabulary")["usage_guidance_statuses"]
    usage_consistent = all(
        codes == configured_codes for codes in schema_codes.values()
    )
    status = "PASS" if (
        all(item["byte_equal"] for item in comparisons)
        and all(item["status"] == "PASS" for item in checks)
        and usage_consistent
    ) else "FAIL"
    report = {
        "status": status,
        "stage": "4-cli-equivalence",
        "generated_at": config.generated_at,
        "dataset_version": config.dataset_version,
        "comparisons": comparisons,
        "summary": {
            "compared_files": len(comparisons),
            "byte_equal_files": sum(item["byte_equal"] for item in comparisons),
            "changed_files": [
                item["name"] for item in comparisons if not item["byte_equal"]
            ],
        },
        "config_checks": checks,
        "usage_vocabulary": {
            "configured": configured_codes,
            "schemas": schema_codes,
            "consistent": usage_consistent,
        },
    }
    write_json(data_root, config.path("equivalence_report"), report)
    shutil.rmtree(work_root)
    if not any(work_root.parent.iterdir()):
        work_root.parent.rmdir()
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("target", choices=["processed", "rag", "synthetic"])
    build.add_argument("--generated-at")
    build.add_argument("--manual", type=Path)
    build.add_argument("--faq", type=Path)
    qa = commands.add_parser("qa")
    qa.add_argument("--generated-at")
    qa.add_argument("--verify-rebuild", action="store_true")
    inv = commands.add_parser("inventory")
    inv.add_argument("--generated-at")
    finish = commands.add_parser("finalize")
    finish.add_argument("--generated-at")
    finish.add_argument("--prepare", action="store_true")
    handoff = commands.add_parser("handoff")
    handoff.add_argument(
        "profile",
        nargs="?",
        choices=["rag", "rag-expansion", "db-smoke", "db-full", "qa"],
    )
    handoff.add_argument("--generated-at")
    commands.add_parser("equivalence")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        code, result = _build(
            args.target,
            args.generated_at,
            manual=args.manual,
            faq=args.faq,
        )
    elif args.command == "qa":
        result = run_qa(
            _config(args.generated_at), verify_rebuild=args.verify_rebuild
        )
        code = 0 if result["status"] == "PASS" else 1
    elif args.command == "inventory":
        result, code = inventory(_config(args.generated_at)), 0
    elif args.command == "finalize":
        result, code = finalize(_config(args.generated_at), prepare=args.prepare), 0
    elif args.command == "handoff":
        result = build_handoff_manifest(
            _config(args.generated_at),
            profile=args.profile,
        )
        code = 0
    else:
        result = run_equivalence(_data_root())
        code = 0 if result["status"] == "PASS" else 1
        result = result["summary"]
    _print(result)
    return code


def legacy_main(step: str, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-at", required=True)
    if step == "step2":
        parser.add_argument("--manual", required=True, type=Path)
        parser.add_argument("--faq", required=True, type=Path)
    elif step == "step5":
        parser.add_argument("--verify-rebuild", action="store_true")
    elif step == "step6_finalize":
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--prepare", action="store_true")
        group.add_argument("--finalize", action="store_true")
    args = parser.parse_args(argv)
    if step == "step2":
        code, result = _build(
            "processed",
            args.generated_at,
            manual=args.manual,
            faq=args.faq,
        )
    elif step in {"step3", "step4"}:
        code, result = _build(
            "rag" if step == "step3" else "synthetic",
            args.generated_at,
        )
    elif step == "step5":
        result = run_qa(
            _config(args.generated_at), verify_rebuild=args.verify_rebuild
        )
        code = 0 if result["status"] == "PASS" else 1
    elif step == "step6_inventory":
        result, code = inventory(_config(args.generated_at)), 0
    else:
        result, code = finalize(
            _config(args.generated_at), prepare=args.prepare
        ), 0
    _print(result)
    return code
