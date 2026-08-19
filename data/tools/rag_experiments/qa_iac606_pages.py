"""IAC606 48페이지 참고 Dataset의 구조·계보·선택 페이지 QA를 수행한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .build_iac606_pages import (
    DEFAULT_GENERATED_AT,
    DOCUMENT_ID,
    REPOSITORY_ROOT,
    SOURCE_INVENTORY_ID,
)
from .qa_manual_pages import MOJIBAKE_MARKERS, _load_jsonl, _sha256_file, _validate_schema


DEFAULT_DATASET = "data/processed/documents/manuals/expansion/manual_pages_iac606.jsonl"
DEFAULT_SCHEMA = "data/schemas/processed/experimentalManualPage.schema.json"
DEFAULT_OUTPUT = "data/processed/validation/rag_experiments/iac606_manual_pages_qa.json"


def build_qa_report(dataset_path: Path, schema_path: Path) -> dict[str, Any]:
    rows, errors = _load_jsonl(dataset_path)
    errors.extend(_validate_schema(rows, json.loads(schema_path.read_text(encoding="utf-8"))))
    warnings: list[dict[str, Any]] = []

    pages = [row.get("page") for row in rows if isinstance(row.get("page"), int)]
    expected_pages = list(range(1, 49))
    missing_pages = sorted(set(expected_pages).difference(pages))
    duplicate_pages = sorted(page for page, count in Counter(pages).items() if count > 1)
    if missing_pages:
        errors.append({"code": "MISSING_PAGE", "pages": missing_pages})
    if duplicate_pages:
        errors.append({"code": "DUPLICATE_PAGE", "pages": duplicate_pages})

    expected_invariants = {
        "document_id": DOCUMENT_ID,
        "source_inventory_id": SOURCE_INVENTORY_ID,
        "exact_sales_code": "WPUIAC606SNW",
        "product_model": "WPU-IAC606",
        "product_generation": "IAC606",
        "scope_role": "expansion",
        "mvp_use": False,
        "allowed_use": "REFERENCE_ONLY",
        "version": "REV.00",
        "page_count": 48,
        "source_file_sha256": "A062C0DD5C2ED17BC3734215C3106DCC82AB69346CF546BDDD9EDD328EA49572",
    }
    invariant_values: dict[str, list[Any]] = {}
    for field, expected in expected_invariants.items():
        values = sorted({row.get(field) for row in rows}, key=str)
        invariant_values[field] = values
        if values != [expected]:
            errors.append({"code": "INVARIANT_MISMATCH", "field": field, "expected": expected, "actual": values})

    blank_pages: list[int] = []
    hash_mismatch_pages: list[int] = []
    mojibake_pages: list[int] = []
    for row in rows:
        text = row.get("text", "")
        page = row.get("page")
        if not text.strip():
            blank_pages.append(page)
        if hashlib.sha256(text.encode("utf-8")).hexdigest().upper() != row.get("text_sha256"):
            hash_mismatch_pages.append(page)
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            mojibake_pages.append(page)
    for code, values in (
        ("BLANK_TEXT", blank_pages),
        ("TEXT_HASH_MISMATCH", hash_mismatch_pages),
        ("MOJIBAKE_DETECTED", mojibake_pages),
    ):
        if values:
            errors.append({"code": code, "pages": sorted(values)})

    pending_pages = sorted(
        row["page"] for row in rows if row.get("verification_status") == "TEXT_EXTRACTED"
    )
    selected_pages = {5, 40, 41, 42, 43}
    selected_pending = sorted(selected_pages.intersection(pending_pages))
    if selected_pending:
        errors.append({"code": "RAG_SELECTED_PAGE_VISUAL_REVIEW_PENDING", "pages": selected_pending})
    if pending_pages:
        warnings.append({
            "code": "REFERENCE_PAGE_VISUAL_REVIEW_PENDING",
            "count": len(pending_pages),
            "message": "선택된 RAG 페이지 외 전체 매뉴얼 페이지는 참고용이며 운영 검색 승인을 의미하지 않음",
        })

    status = "FAIL" if errors else "RAG_SELECTED_PAGES_VERIFIED_REFERENCE_READY"
    return {
        "qa_id": "IAC606-FULL-PAGE-QA",
        "status": status,
        "generated_at": DEFAULT_GENERATED_AT,
        "dataset": {
            "path": dataset_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256_file(dataset_path),
            "record_count": len(rows),
        },
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "pages_expected": 48,
            "pages_found": len(pages),
            "missing_pages": missing_pages,
            "duplicate_pages": duplicate_pages,
            "blank_text_pages": sorted(blank_pages),
            "text_hash_mismatch_pages": sorted(hash_mismatch_pages),
            "mojibake_pages": sorted(mojibake_pages),
            "visual_review_pending_count": len(pending_pages),
        },
        "metadata_invariants": invariant_values,
        "errors": errors,
        "warnings": warnings,
        "decision": {
            "reference_corpus_text_use": "READY" if not errors else "BLOCKED",
            "rag_handoff_candidate": "READY" if not errors else "BLOCKED",
            "runtime_activation": "CONTRACT_BLOCKED_NOT_INDEXED",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="IAC606 48페이지 QA")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dataset_path = (REPOSITORY_ROOT / args.dataset).resolve()
    schema_path = (REPOSITORY_ROOT / args.schema).resolve()
    output_path = (REPOSITORY_ROOT / args.output).resolve()
    output_path.relative_to(REPOSITORY_ROOT.resolve())
    report = build_qa_report(dataset_path, schema_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"]}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
