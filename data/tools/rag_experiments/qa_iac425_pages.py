"""IAC425 52페이지 확장 Dataset의 A1-2 최소 QA를 수행한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .build_iac425_pages import (
    DEFAULT_GENERATED_AT,
    DOCUMENT_ID,
    REPOSITORY_ROOT,
    SOURCE_INVENTORY_ID,
)
from .qa_manual_pages import MOJIBAKE_MARKERS, _load_jsonl, _sha256_file, _validate_schema


DEFAULT_DATASET = (
    "data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl"
)
DEFAULT_SCHEMA = "data/schemas/processed/experimentalManualPage.schema.json"
DEFAULT_OUTPUT = (
    "data/processed/validation/rag_experiments/iac425_manual_pages_qa.json"
)


def build_qa_report(dataset_path: Path, schema_path: Path) -> dict[str, Any]:
    rows, errors = _load_jsonl(dataset_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors.extend(_validate_schema(rows, schema))
    warnings: list[dict[str, Any]] = []

    pages = [row.get("page") for row in rows if isinstance(row.get("page"), int)]
    expected_pages = list(range(1, 53))
    missing_pages = sorted(set(expected_pages).difference(pages))
    duplicate_pages = sorted(page for page, count in Counter(pages).items() if count > 1)
    if missing_pages:
        errors.append({"code": "MISSING_PAGE", "pages": missing_pages})
    if duplicate_pages:
        errors.append({"code": "DUPLICATE_PAGE", "pages": duplicate_pages})

    duplicate_page_ids = sorted(
        page_id
        for page_id, count in Counter(row.get("page_id") for row in rows).items()
        if count > 1
    )
    if duplicate_page_ids:
        errors.append({"code": "DUPLICATE_PAGE_ID", "page_ids": duplicate_page_ids})

    text_hash_mismatch_pages: list[int] = []
    mojibake_pages: list[int] = []
    normalized_text_pages: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        page = row.get("page")
        text = row.get("text", "")
        actual_hash = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
        if actual_hash != row.get("text_sha256"):
            text_hash_mismatch_pages.append(page)
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            mojibake_pages.append(page)
        normalized = " ".join(text.split())
        normalized_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()
        normalized_text_pages[normalized_hash].append(page)
        expected_page_id = f"{DOCUMENT_ID}-P{page:03d}"
        if row.get("page_id") != expected_page_id:
            errors.append({"code": "PAGE_ID_MISMATCH", "page": page})

    duplicate_text_groups = sorted(
        sorted(group) for group in normalized_text_pages.values() if len(group) > 1
    )
    blank_text_pages = sorted(row["page"] for row in rows if not row.get("text", "").strip())
    if text_hash_mismatch_pages:
        errors.append({"code": "TEXT_HASH_MISMATCH", "pages": text_hash_mismatch_pages})
    if mojibake_pages:
        errors.append({"code": "MOJIBAKE_DETECTED", "pages": mojibake_pages})
    if duplicate_text_groups:
        errors.append({"code": "DUPLICATE_TEXT", "page_groups": duplicate_text_groups})
    if blank_text_pages:
        errors.append({"code": "BLANK_TEXT", "pages": blank_text_pages})

    expected_invariants = {
        "document_id": DOCUMENT_ID,
        "source_inventory_id": SOURCE_INVENTORY_ID,
        "exact_sales_code": "WPUIAC425SNW",
        "product_model": "WPU-IAC425",
        "scope_role": "expansion",
        "mvp_use": False,
        "allowed_use": "REFERENCE_ONLY",
        "version": "REV.02",
        "page_count": 52,
        "source_file_sha256": (
            "97C027CE75BEC40386307C867DD3983513CB70FAC687F2D2DB6F1167EC9CAEC8"
        ),
    }
    invariant_values: dict[str, list[Any]] = {}
    for field, expected in expected_invariants.items():
        values = sorted({row.get(field) for row in rows}, key=str)
        invariant_values[field] = values
        if values != [expected]:
            errors.append({
                "code": "INVARIANT_MISMATCH",
                "field": field,
                "expected": expected,
                "actual": values,
            })

    verification_counts = Counter(row.get("verification_status") for row in rows)
    visual_review_pending_pages = sorted(
        row["page"] for row in rows if row.get("verification_status") == "TEXT_EXTRACTED"
    )
    if visual_review_pending_pages:
        warnings.append({
            "code": "VISUAL_REVIEW_PENDING",
            "count": len(visual_review_pending_pages),
            "message": "실험용 텍스트 사용은 가능하나 Gold·Production 승인을 의미하지 않음",
        })

    selected_pages = {5, 43, 44, 45, 46}
    selected_pending = sorted(selected_pages.intersection(visual_review_pending_pages))
    if selected_pending:
        errors.append({
            "code": "RAG_SELECTED_PAGE_VISUAL_REVIEW_PENDING",
            "pages": selected_pending,
        })

    status = "FAIL" if errors else "RAG_SELECTED_PAGES_VERIFIED_REFERENCE_READY"
    return {
        "qa_id": "A1-2-IAC425-FULL-PAGE-QA",
        "status": status,
        "generated_at": DEFAULT_GENERATED_AT,
        "scope": {
            "included": "WPU-IAC425 REV.02 실험용 52페이지 JSONL",
            "excluded": ["MVP 검색", "Chunking", "Embedding", "Vector DB", "Production 승인"],
        },
        "dataset": {
            "path": dataset_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256_file(dataset_path),
            "record_count": len(rows),
        },
        "schema": {
            "path": schema_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256_file(schema_path),
        },
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "pages_expected": 52,
            "pages_found": len(pages),
            "unique_pages": len(set(pages)),
            "missing_pages": missing_pages,
            "duplicate_pages": duplicate_pages,
            "duplicate_text_groups": duplicate_text_groups,
            "blank_text_pages": blank_text_pages,
            "text_hash_mismatch_pages": sorted(text_hash_mismatch_pages),
            "mojibake_pages": sorted(mojibake_pages),
            "visual_review_pending_count": len(visual_review_pending_pages),
        },
        "verification_coverage": {
            "status_counts": dict(sorted(verification_counts.items())),
            "visual_review_pending_pages": visual_review_pending_pages,
            "manual_correction_pages": sorted(
                row["page"] for row in rows if row.get("manual_correction_ids")
            ),
        },
        "metadata_invariants": invariant_values,
        "errors": errors,
        "warnings": warnings,
        "decision": {
            "experimental_corpus_text_use": "READY" if not errors else "BLOCKED",
            "mvp_search_use": "BLOCKED",
            "gold_evidence_use": "REVIEW_REQUIRED",
            "rag_handoff_candidate": "READY" if not errors else "BLOCKED",
            "production_corpus_expansion": "NOT_INDEXED",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A1-2 IAC425 52페이지 최소 QA")
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
