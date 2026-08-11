#!/usr/bin/env python3
"""A2 Gold Evaluation Dataset v1의 Schema·참조·분포·검수 상태를 검증한다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ai.evaluation.file_integrity import file_sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = "ai/evaluation/datasets/gold/rag_gold_v1.jsonl"
DEFAULT_MANIFEST = "ai/evaluation/datasets/gold/rag_gold_v1_manifest.json"
DEFAULT_SCHEMA = "ai/evaluation/schemas/gold_evaluation_case_v1.schema.json"
DEFAULT_OUTPUT = "ai/evaluation/reports/dataset_qa/rag_gold_v1_qa.json"
EXPECTED_TYPE_COUNTS = {
    "DIRECT": 20,
    "COLLOQUIAL": 10,
    "TYPO_ABBREVIATION": 5,
    "COMPOUND": 5,
    "SAFETY": 10,
    "NO_EVIDENCE": 5,
    "CROSS_PRODUCT": 5,
}
EXPECTED_SPLIT_COUNTS = {"DEV": 35, "TEST": 15, "SAFETY": 10}


def _sha256(path: Path) -> str:
    return file_sha256(path)


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            errors.append({"code": "BLANK_JSONL_LINE", "line": line_number})
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append({
                "code": "INVALID_JSON",
                "line": line_number,
                "message": error.msg,
            })
            continue
        if not isinstance(row, dict):
            errors.append({"code": "ROW_NOT_OBJECT", "line": line_number})
            continue
        rows.append(row)
    return rows, errors


def _source_case_ids() -> dict[str, set[str]]:
    retrieval = json.loads((
        REPOSITORY_ROOT / "data/config/rag/jac104_retrieval_cases.json"
    ).read_text(encoding="utf-8"))["cases"]
    rag_eval = json.loads((
        REPOSITORY_ROOT / "ai/evaluation/datasets/rag_eval_dataset.json"
    ).read_text(encoding="utf-8"))
    safety = json.loads((
        REPOSITORY_ROOT / "ai/evaluation/datasets/safety/safety_eval_dataset.json"
    ).read_text(encoding="utf-8"))
    structuring = json.loads((
        REPOSITORY_ROOT / "ai/evaluation/datasets/structuring/symptom_eval_dataset.json"
    ).read_text(encoding="utf-8"))["cases"]
    faq_rows, _ = _load_jsonl(
        REPOSITORY_ROOT / "data/processed/documents/faq/faq_snapshot_normalized.jsonl"
    )
    return {
        "EXISTING_RETRIEVAL_CASE": {row["case_id"] for row in retrieval},
        "EXISTING_RAG_EVAL": {row["eval_id"] for row in rag_eval},
        "EXISTING_SAFETY_CASE": {row["eval_id"] for row in safety},
        "EXISTING_STRUCTURING_CASE": {row["case_id"] for row in structuring},
        "EXISTING_FAQ": {row["faq_id"] for row in faq_rows},
    }


def build_qa_report(
    dataset_path: Path,
    manifest_path: Path,
    schema_path: Path,
) -> dict[str, Any]:
    rows, errors = _load_jsonl(dataset_path)
    warnings: list[dict[str, Any]] = []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for index, row in enumerate(rows, start=1):
        for error in sorted(validator.iter_errors(row), key=lambda item: list(item.path)):
            errors.append({
                "code": "SCHEMA_VALIDATION_ERROR",
                "line": index,
                "path": "/".join(str(part) for part in error.path),
                "message": error.message,
            })

    case_ids = [row.get("case_id") for row in rows]
    expected_case_ids = [f"RAGV2-GOLD-{index:04d}" for index in range(1, 61)]
    if case_ids != expected_case_ids:
        errors.append({"code": "CASE_ID_SEQUENCE_MISMATCH"})
    duplicate_queries = sorted(
        query
        for query, count in Counter(
            " ".join(row.get("query", "").split()) for row in rows
        ).items()
        if count > 1
    )
    if duplicate_queries:
        errors.append({"code": "DUPLICATE_QUERY", "queries": duplicate_queries})

    type_counts = Counter(row.get("query_variant_type") for row in rows)
    split_counts = Counter(row.get("split") for row in rows)
    review_counts = Counter(row.get("review_status") for row in rows)
    if dict(type_counts) != EXPECTED_TYPE_COUNTS:
        errors.append({
            "code": "TYPE_DISTRIBUTION_MISMATCH",
            "expected": EXPECTED_TYPE_COUNTS,
            "actual": dict(type_counts),
        })
    if dict(split_counts) != EXPECTED_SPLIT_COUNTS:
        errors.append({
            "code": "SPLIT_DISTRIBUTION_MISMATCH",
            "expected": EXPECTED_SPLIT_COUNTS,
            "actual": dict(split_counts),
        })

    registry_rows, registry_errors = _load_jsonl(
        REPOSITORY_ROOT / "data/processed/structured/evidence/jac104_evidence_registry.jsonl"
    )
    errors.extend(registry_errors)
    registry_by_id = {
        row["evidence_id"]: row
        for row in registry_rows
        if row.get("evidence_class") == "MANUAL" and row.get("rag_policy") == "INCLUDE"
    }
    manual_rows, manual_errors = _load_jsonl(
        REPOSITORY_ROOT / "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl"
    )
    errors.extend(manual_errors)
    manual_by_page_id = {row["page_id"]: row for row in manual_rows}
    known_sources = _source_case_ids()

    evidence_reference_errors: list[dict[str, Any]] = []
    source_reference_errors: list[dict[str, Any]] = []
    logical_policy_errors: list[dict[str, Any]] = []
    review_policy_errors: list[dict[str, Any]] = []
    for row in rows:
        case_id = row.get("case_id")
        evidence = row.get("expected_evidence", [])
        expected_none = row.get("expected_no_evidence") is True
        match_policy = row.get("evidence_match_policy")
        if expected_none != (len(evidence) == 0):
            logical_policy_errors.append({
                "case_id": case_id,
                "reason": "expected_no_evidence와 expected_evidence 불일치",
            })
        if (expected_none and match_policy != "NONE") or (
            not expected_none and match_policy == "NONE"
        ):
            logical_policy_errors.append({
                "case_id": case_id,
                "reason": "Evidence match policy 불일치",
            })
        if row.get("split") == "SAFETY" and row.get("query_variant_type") != "SAFETY":
            logical_policy_errors.append({
                "case_id": case_id,
                "reason": "SAFETY Split에 비-Safety Case 포함",
            })
        if row.get("query_variant_type") == "SAFETY" and (
            row.get("expected_risk_level") != "danger"
            or row.get("expected_guidance_policy") != "TOTAL_STOP"
        ):
            logical_policy_errors.append({
                "case_id": case_id,
                "reason": "Safety Case의 danger/TOTAL_STOP 정책 불일치",
            })
        for unit in evidence:
            unit_id = unit.get("evidence_unit_id")
            if unit_id in registry_by_id:
                source = registry_by_id[unit_id]
                if (
                    unit.get("document_id") != source.get("document_id")
                    or unit.get("page_refs") != source.get("page_refs")
                ):
                    evidence_reference_errors.append({
                        "case_id": case_id,
                        "evidence_unit_id": unit_id,
                        "reason": "Evidence Registry Lineage 불일치",
                    })
            elif unit_id in manual_by_page_id:
                page_row = manual_by_page_id[unit_id]
                if (
                    unit.get("document_id") != page_row.get("document_id")
                    or page_row.get("page") not in unit.get("page_refs", [])
                ):
                    evidence_reference_errors.append({
                        "case_id": case_id,
                        "evidence_unit_id": unit_id,
                        "reason": "Manual Page Lineage 불일치",
                    })
            else:
                evidence_reference_errors.append({
                    "case_id": case_id,
                    "evidence_unit_id": unit_id,
                    "reason": "존재하지 않는 Evidence Unit",
                })

        origin = row.get("source_query_origin")
        source_ids = row.get("source_case_ids", [])
        if origin in known_sources:
            unknown = sorted(set(source_ids).difference(known_sources[origin]))
            if not source_ids or unknown:
                source_reference_errors.append({
                    "case_id": case_id,
                    "origin": origin,
                    "unknown_source_ids": unknown,
                })
        elif origin in {"CURATED_VARIANT", "CURATED_NEGATIVE"} and source_ids:
            source_reference_errors.append({
                "case_id": case_id,
                "origin": origin,
                "reason": "Curated Case는 source_case_ids를 비워야 함",
            })

        reviewer_count = len(row.get("reviewer_ids", []))
        review_status = row.get("review_status")
        expected_reviewer_counts = {
            "UNREVIEWED_DRAFT": {0},
            "ONE_PERSON_REVIEWED": {1},
            "TWO_PERSON_APPROVED": {2},
            "REJECTED": {1, 2},
        }
        if reviewer_count not in expected_reviewer_counts.get(review_status, set()):
            review_policy_errors.append({
                "case_id": case_id,
                "review_status": review_status,
                "reviewer_count": reviewer_count,
            })

    if evidence_reference_errors:
        errors.append({
            "code": "EVIDENCE_REFERENCE_ERROR",
            "items": evidence_reference_errors,
        })
    if source_reference_errors:
        errors.append({
            "code": "SOURCE_CASE_REFERENCE_ERROR",
            "items": source_reference_errors,
        })
    if logical_policy_errors:
        errors.append({"code": "LOGICAL_POLICY_ERROR", "items": logical_policy_errors})
    if review_policy_errors:
        errors.append({"code": "REVIEW_POLICY_ERROR", "items": review_policy_errors})

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_hash = _sha256(dataset_path)
    schema_hash = _sha256(schema_path)
    if manifest.get("dataset", {}).get("sha256") != dataset_hash:
        errors.append({"code": "MANIFEST_DATASET_HASH_MISMATCH"})
    if manifest.get("schema", {}).get("sha256") != schema_hash:
        errors.append({"code": "MANIFEST_SCHEMA_HASH_MISMATCH"})
    if manifest.get("dataset", {}).get("records") != len(rows):
        errors.append({"code": "MANIFEST_RECORD_COUNT_MISMATCH"})

    approved_count = review_counts.get("TWO_PERSON_APPROVED", 0)
    if approved_count < len(rows):
        warnings.append({
            "code": "HUMAN_REVIEW_PENDING",
            "pending_records": len(rows) - approved_count,
            "approved_records": approved_count,
            "message": "2인 검수 완료 전에는 Draft Dataset으로만 사용",
        })

    status = "FAIL" if errors else "STRUCTURAL_PASS_HUMAN_REVIEW_PENDING"
    return {
        "qa_id": "A2-GOLD-EVALUATION-V1-QA",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "path": dataset_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": dataset_hash,
            "record_count": len(rows),
        },
        "manifest": {
            "path": manifest_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(manifest_path),
        },
        "schema": {
            "path": schema_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": schema_hash,
        },
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "records_expected": 60,
            "records_found": len(rows),
            "query_variant_type_counts": dict(sorted(type_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
            "review_status_counts": dict(sorted(review_counts.items())),
            "duplicate_queries": duplicate_queries,
            "approved_records": approved_count,
            "review_pending_records": len(rows) - approved_count,
        },
        "errors": errors,
        "warnings": warnings,
        "decision": {
            "schema_and_lineage": "READY" if not errors else "BLOCKED",
            "experiment_draft_use": "READY" if not errors else "BLOCKED",
            "gold_approved_use": "BLOCKED" if approved_count < len(rows) else "READY",
            "automatic_label_approval": "PROHIBITED",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A2 Gold Evaluation Dataset v1 QA")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    dataset_path = (REPOSITORY_ROOT / args.dataset).resolve()
    manifest_path = (REPOSITORY_ROOT / args.manifest).resolve()
    schema_path = (REPOSITORY_ROOT / args.schema).resolve()
    output_path = (REPOSITORY_ROOT / args.output).resolve()
    output_path.relative_to(REPOSITORY_ROOT.resolve())
    report = build_qa_report(dataset_path, manifest_path, schema_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "output": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
        **report["summary"],
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
