"""3모델 제한 RAG 인계 산출물의 계보·anchor·관계·건수 Gate를 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .build_three_model_handoff import (
    DEFAULT_CHILD_OUTPUT,
    DEFAULT_EVALUATION_OUTPUT,
    DEFAULT_EVIDENCE_OUTPUT,
    DEFAULT_PARENT_OUTPUT,
    GENERATED_AT,
    REPOSITORY_ROOT,
    SUPPORTED_PRODUCTS,
    _read_jsonl,
    _sha256_file,
    _sha256_text,
)
from .qa_manual_pages import _validate_schema


DEFAULT_OUTPUT = "data/processed/validation/rag_experiments/three_model_handoff_qa.json"
PARENT_SCHEMA = "data/schemas/processed/ragParentPage.schema.json"
CHILD_SCHEMA = "data/schemas/processed/ragChildChunk.schema.json"
EVIDENCE_SCHEMA = "data/schemas/processed/ragEvidenceGroup.schema.json"


def _error(errors: list[dict[str, Any]], code: str, detail: Any) -> None:
    errors.append({"code": code, "detail": detail})


def build_qa_report(
    parent_path: Path,
    child_path: Path,
    evidence_path: Path,
    evaluation_path: Path,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    parents = _read_jsonl(parent_path.relative_to(REPOSITORY_ROOT).as_posix())
    children = _read_jsonl(child_path.relative_to(REPOSITORY_ROOT).as_posix())
    groups = _read_jsonl(evidence_path.relative_to(REPOSITORY_ROOT).as_posix())
    evaluations = json.loads(evaluation_path.read_text(encoding="utf-8"))
    products_doc = json.loads((REPOSITORY_ROOT / SUPPORTED_PRODUCTS).read_text(encoding="utf-8"))
    products = {row["exact_sales_code"]: row for row in products_doc["products"]}

    for rows, schema_path, name in (
        (parents, PARENT_SCHEMA, "parent"),
        (children, CHILD_SCHEMA, "child"),
        (groups, EVIDENCE_SCHEMA, "evidence"),
    ):
        schema = json.loads((REPOSITORY_ROOT / schema_path).read_text(encoding="utf-8"))
        for issue in _validate_schema(rows, schema):
            _error(errors, f"{name.upper()}_{issue['code']}", issue)

    expected_counts = {"parents": 15, "children": 53, "groups": 43, "cases": 49}
    actual_counts = {
        "parents": len(parents),
        "children": len(children),
        "groups": len(groups),
        "cases": len(evaluations.get("cases", [])),
    }
    if actual_counts != expected_counts:
        _error(errors, "COUNT_GATE", {"expected": expected_counts, "actual": actual_counts})

    parent_by_id = {row["parent_id"]: row for row in parents}
    child_by_id = {row["child_id"]: row for row in children}
    group_by_id = {row["evidence_group_id"]: row for row in groups}
    for field, rows in (("parent_id", parents), ("child_id", children), ("evidence_group_id", groups)):
        duplicates = sorted(key for key, count in Counter(row[field] for row in rows).items() if count > 1)
        if duplicates:
            _error(errors, "DUPLICATE_ID", {"field": field, "values": duplicates})

    expected_model_counts = {
        "WPUJAC104DWH": {"parents": 5, "children": 15, "groups": 7},
        "WPUIAC425SNW": {"parents": 5, "children": 19, "groups": 18},
        "WPUIAC606SNW": {"parents": 5, "children": 19, "groups": 18},
    }
    actual_model_counts: dict[str, dict[str, int]] = {}
    for code in products:
        actual_model_counts[code] = {
            "parents": sum(row["exact_sales_code"] == code for row in parents),
            "children": sum(row["exact_sales_code"] == code for row in children),
            "groups": sum(row["exact_sales_code"] == code for row in groups),
        }
    if actual_model_counts != expected_model_counts:
        _error(errors, "MODEL_COUNT_GATE", {"expected": expected_model_counts, "actual": actual_model_counts})

    for parent in parents:
        code = parent["exact_sales_code"]
        product = products.get(code)
        if product is None or parent["document_id"] != product["document_id"]:
            _error(errors, "PARENT_MODEL_LINEAGE", parent["parent_id"])
        if _sha256_text(parent["parent_text"]) != parent["parent_text_sha256"]:
            _error(errors, "PARENT_TEXT_HASH", parent["parent_id"])
        if parent["parent_text_sha256"] != parent["source_page_text_sha256"]:
            _error(errors, "PARENT_SOURCE_PAGE_HASH", parent["parent_id"])

    for child in children:
        parent = parent_by_id.get(child["parent_id"])
        group = group_by_id.get(child["evidence_group_id"])
        if parent is None:
            _error(errors, "ORPHAN_PARENT", child["child_id"])
            continue
        if group is None:
            _error(errors, "ORPHAN_EVIDENCE_GROUP", child["child_id"])
            continue
        linked = {
            child["exact_sales_code"], parent["exact_sales_code"], group["exact_sales_code"]
        }
        documents = {child["document_id"], parent["document_id"], group["document_id"]}
        if len(linked) != 1 or len(documents) != 1:
            _error(errors, "CROSS_MODEL_LINEAGE", child["child_id"])
        if child["page_id"] != parent["page_id"] or child["page_refs"] != parent["page_refs"]:
            _error(errors, "CHILD_PARENT_PAGE", child["child_id"])
        if child["parent_text_sha256"] != parent["parent_text_sha256"]:
            _error(errors, "CHILD_PARENT_HASH", child["child_id"])
        if _sha256_text(child["child_text"]) != child["child_text_sha256"]:
            _error(errors, "CHILD_TEXT_HASH", child["child_id"])
        span = child["source_span"]
        lines = parent["parent_text"].splitlines()
        start = span["line_start"]
        end = span["line_end"]
        selected = lines[start - 1 : end]
        if not selected or selected[0] != span["start_anchor"] or selected[-1] != span["end_anchor"]:
            _error(errors, "SOURCE_ANCHOR", child["child_id"])
        elif _sha256_text("\n".join(selected)) != span["raw_span_sha256"]:
            _error(errors, "SOURCE_SPAN_HASH", child["child_id"])
        if "FAQ" in child["document_id"] or "FAQ" in child["child_id"]:
            _error(errors, "UNVERIFIED_FAQ_INCLUDED", child["child_id"])

    for group in groups:
        if len(group["child_ids"]) != len(set(group["child_ids"])):
            _error(errors, "DUPLICATE_GROUP_CHILD", group["evidence_group_id"])
        for child_id in group["child_ids"]:
            child = child_by_id.get(child_id)
            if child is None or child["evidence_group_id"] != group["evidence_group_id"]:
                _error(errors, "GROUP_CHILD_LINK", {"group": group["evidence_group_id"], "child": child_id})
        expected_variants = [child_by_id[child_id]["source_variant_id"] for child_id in group["child_ids"] if child_id in child_by_id]
        if group["source_variant_ids"] != expected_variants:
            _error(errors, "GROUP_VARIANT_LINK", group["evidence_group_id"])

    cases = evaluations.get("cases", [])
    positive = [row for row in cases if row.get("case_type") == "POSITIVE"]
    negative = [row for row in cases if row.get("case_type") == "NEGATIVE"]
    if (len(positive), len(negative)) != (43, 6):
        _error(errors, "EVALUATION_COUNT", {"positive": len(positive), "negative": len(negative)})
    child_texts = {row["child_text"] for row in children}
    all_codes = set(products)
    for case in positive:
        code = case["exact_sales_code"]
        expected_groups = case["expected_evidence_group_ids"]
        if len(expected_groups) != 1 or expected_groups[0] not in group_by_id:
            _error(errors, "POSITIVE_EXPECTED_GROUP", case["case_id"])
        elif group_by_id[expected_groups[0]]["exact_sales_code"] != code:
            _error(errors, "POSITIVE_MODEL_GROUP", case["case_id"])
        if set(case["forbidden_model_codes"]) != all_codes - {code}:
            _error(errors, "POSITIVE_FORBIDDEN_MODELS", case["case_id"])
        if case["query"] in child_texts:
            _error(errors, "GOLD_QUESTION_COPIED_SOURCE", case["case_id"])
    for case in negative:
        if not case.get("expected_no_evidence") or case.get("expected_evidence_group_ids"):
            _error(errors, "NEGATIVE_EXPECTATION", case["case_id"])

    status_values = {
        case.get("data_status") for case in cases
    } | {evaluations.get("status")}
    review_values = {
        case.get("human_review_status") for case in cases
    } | {evaluations.get("human_review_status")}
    if status_values != {"DATA_READY_AI_NOT_RUN"}:
        _error(errors, "EVALUATION_STATUS", sorted(str(value) for value in status_values))
    if review_values != {"HUMAN_REVIEW_PENDING"}:
        _error(errors, "HUMAN_REVIEW_STATUS", sorted(str(value) for value in review_values))

    pdfs_in_data = sorted(path.relative_to(REPOSITORY_ROOT).as_posix() for path in (REPOSITORY_ROOT / "data").rglob("*.pdf"))
    if pdfs_in_data:
        _error(errors, "SOURCE_PDF_IN_DATA", pdfs_in_data)

    return {
        "qa_id": "RAG-3MODEL-HANDOFF-QA-V1",
        "status": "PASS" if not errors else "FAIL",
        "generated_at": GENERATED_AT,
        "counts": {
            **actual_counts,
            "positive_cases": len(positive),
            "negative_cases": len(negative),
            "source_pdf_in_data": len(pdfs_in_data),
        },
        "model_counts": actual_model_counts,
        "inputs": [
            {"path": path.relative_to(REPOSITORY_ROOT).as_posix(), "sha256": _sha256_file(path)}
            for path in (parent_path, child_path, evidence_path, evaluation_path)
        ],
        "gates": {
            "exact_sales_code_pre_score_filter_required": products_doc["retrieval_policy"]["filter_required_before_scoring"],
            "cross_model_fallback": products_doc["retrieval_policy"]["cross_model_fallback"],
            "model_unverified_faq_included": products_doc["retrieval_policy"]["model_unverified_faq_included"],
            "runtime_activation": "NOT_VERIFIED",
            "ai_retrieval_evaluation": "NOT_RUN",
        },
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="3모델 RAG 인계 QA")
    parser.add_argument("--parents", default=DEFAULT_PARENT_OUTPUT)
    parser.add_argument("--children", default=DEFAULT_CHILD_OUTPUT)
    parser.add_argument("--evidence", default=DEFAULT_EVIDENCE_OUTPUT)
    parser.add_argument("--evaluations", default=DEFAULT_EVALUATION_OUTPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_qa_report(
        REPOSITORY_ROOT / args.parents,
        REPOSITORY_ROOT / args.children,
        REPOSITORY_ROOT / args.evidence,
        REPOSITORY_ROOT / args.evaluations,
    )
    output = REPOSITORY_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": report["status"], **report["counts"]}, ensure_ascii=False, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
