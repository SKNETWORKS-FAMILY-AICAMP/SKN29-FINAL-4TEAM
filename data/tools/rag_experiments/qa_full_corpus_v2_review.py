"""Full Corpus v2·Gold 검수 인계 산출물을 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .build_full_corpus_v2_review import (
    CANDIDATE_SCHEMA,
    CONFIG_PATH,
    CORPUS_SCHEMA,
    COVERAGE_SCHEMA,
    DEFAULT_CANDIDATE_OUTPUT,
    DEFAULT_CORPUS_OUTPUT,
    DEFAULT_COVERAGE_OUTPUT,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_REVIEW_OUTPUT,
    GENERATED_AT,
    REPOSITORY_ROOT,
    REVIEW_SCHEMA,
)


DEFAULT_QA_OUTPUT = (
    "data/processed/validation/rag_experiments/full_corpus_v2_qa.json"
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _schema_errors(instance: Any, schema_path: str) -> list[str]:
    schema = _read_json(REPOSITORY_ROOT / schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{list(error.absolute_path)}:{error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
    ]


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in _all_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_strings(child)]
    return []


def build_qa_report(
    corpus_path: Path,
    coverage_path: Path,
    review_path: Path,
    candidate_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    corpus = _read_jsonl(corpus_path)
    coverage = _read_json(coverage_path)
    review = _read_json(review_path)
    candidates = _read_json(candidate_path)
    manifest = _read_json(manifest_path)
    config = _read_json(REPOSITORY_ROOT / CONFIG_PATH)
    parents = _read_jsonl(
        REPOSITORY_ROOT / config["inputs"]["parents"]["path"]
    )
    groups = _read_jsonl(
        REPOSITORY_ROOT / config["inputs"]["evidence_groups"]["path"]
    )
    gold = _read_jsonl(
        REPOSITORY_ROOT / config["inputs"]["gold_dataset"]["path"]
    )
    source_cases = _read_json(
        REPOSITORY_ROOT / config["inputs"]["three_model_evaluation"]["path"]
    )["cases"]

    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    schema_errors: list[str] = []
    for index, row in enumerate(corpus):
        schema_errors.extend(
            f"corpus[{index}]:{message}"
            for message in _schema_errors(row, CORPUS_SCHEMA)
        )
    schema_errors.extend(
        f"coverage:{message}" for message in _schema_errors(coverage, COVERAGE_SCHEMA)
    )
    schema_errors.extend(
        f"review:{message}" for message in _schema_errors(review, REVIEW_SCHEMA)
    )
    schema_errors.extend(
        f"candidates:{message}" for message in _schema_errors(candidates, CANDIDATE_SCHEMA)
    )
    checks.append({"check_id": "SCHEMA", "status": "PASS" if not schema_errors else "FAIL", "detail": schema_errors})
    errors.extend(schema_errors)

    counts_ok = len(corpus) == 111
    product_counts = Counter(row["exact_sales_code"] for row in corpus)
    type_counts = Counter(row["record_type"] for row in corpus)
    counts_ok = counts_ok and product_counts == Counter({"WPUJAC104DWH": 59, "WPUIAC425SNW": 52})
    counts_ok = counts_ok and type_counts == Counter({"SOURCE_PAGE": 91, "CHILD": 15, "PRESERVATION": 5})
    checks.append({"check_id": "CORPUS_COUNTS", "status": "PASS" if counts_ok else "FAIL", "detail": {"total": len(corpus), "products": dict(product_counts), "record_types": dict(type_counts)}})
    if not counts_ok:
        errors.append("corpus_count_mismatch")

    chunk_ids = [row["chunk_id"] for row in corpus]
    unique_ok = len(chunk_ids) == len(set(chunk_ids)) and [row["chunk_index"] for row in corpus] == list(range(1, 112))
    checks.append({"check_id": "ID_AND_INDEX_UNIQUENESS", "status": "PASS" if unique_ok else "FAIL", "detail": "111 unique IDs and contiguous indexes"})
    if not unique_ok:
        errors.append("id_or_index_mismatch")

    hash_failures = [row["chunk_id"] for row in corpus if _sha256_text(row["text"]) != row["text_sha256"]]
    checks.append({"check_id": "TEXT_HASHES", "status": "PASS" if not hash_failures else "FAIL", "detail": hash_failures})
    errors.extend(f"text_hash:{chunk_id}" for chunk_id in hash_failures)

    coverage_failures: list[str] = []
    for page in coverage["pages"]:
        numbers = [row["line_number"] for row in page["assignments"]]
        if numbers != list(range(1, page["total_lines"] + 1)):
            coverage_failures.append(f"page={page['page']}")
    checks.append({"check_id": "LINE_COVERAGE", "status": "PASS" if not coverage_failures else "FAIL", "detail": coverage_failures})
    errors.extend(f"coverage:{page}" for page in coverage_failures)

    parent_ids = {
        row["parent_id"] for row in parents if row["exact_sales_code"] == "WPUJAC104DWH"
    }
    group_ids = {row["evidence_group_id"] for row in groups}
    child_failures: list[str] = []
    preservation_failures: list[str] = []
    for row in corpus:
        if row["record_type"] == "CHILD":
            if (
                len(row["evidence_unit_ids"]) != 1
                or row["evidence_unit_ids"][0] not in group_ids
                or row.get("parent_id") not in parent_ids
            ):
                child_failures.append(row["chunk_id"])
        if row["record_type"] == "PRESERVATION" and row["evidence_unit_ids"] != [row["chunk_id"]]:
            preservation_failures.append(row["chunk_id"])
    lineage_ok = not child_failures and not preservation_failures
    checks.append({"check_id": "CHILD_AND_PRESERVATION_LINEAGE", "status": "PASS" if lineage_ok else "FAIL", "detail": {"children": child_failures, "preservation": preservation_failures}})
    errors.extend(f"child_lineage:{item}" for item in child_failures)
    errors.extend(f"preservation_lineage:{item}" for item in preservation_failures)

    gold_queries = {row["query"].strip() for row in gold}
    copied = [row["chunk_id"] for row in corpus if row["record_type"] != "SOURCE_PAGE" and row["text"].strip() in gold_queries]
    checks.append({"check_id": "GOLD_QUERY_COPY", "status": "PASS" if not copied else "FAIL", "detail": copied})
    errors.extend(f"gold_query_copy:{item}" for item in copied)

    review_ids = [row["case_id"] for row in review["reviews"]]
    review_ok = len(review_ids) == 60 and set(review_ids) == {row["case_id"] for row in gold}
    review_ok = review_ok and all(row["human_signoff_status"] == "PENDING" for row in review["reviews"])
    review_ok = review_ok and all(
        row["case_snapshot"]["query"] == next(
            case["query"] for case in gold if case["case_id"] == row["case_id"]
        )
        and row["required_human_checks"][-1]
        == "RECORD_REVIEWER_ID_DECISION_AND_REVIEWED_AT"
        for row in review["reviews"]
    )
    review_ok = review_ok and review["summary"]["human_signed_records"] == 0
    checks.append({"check_id": "GOLD_REVIEW_PACKET", "status": "PASS" if review_ok else "FAIL", "detail": review["summary"]})
    if not review_ok:
        errors.append("gold_review_packet_mismatch")

    positive_iac = {
        row["case_id"]: row
        for row in source_cases
        if row["case_type"] == "POSITIVE" and row["exact_sales_code"] == "WPUIAC425SNW"
    }
    candidate_rows = candidates["candidates"]
    candidate_ok = len(candidate_rows) == 18
    candidate_ok = candidate_ok and {row["source_case_id"] for row in candidate_rows} == set(positive_iac)
    candidate_ok = candidate_ok and all(
        row["query"] == positive_iac[row["source_case_id"]]["query"]
        and row["human_review_status"] == "HUMAN_REVIEW_PENDING"
        and all(variant["evidence_unit_id"] in group_ids for variant in row["expected_evidence_variants"])
        for row in candidate_rows
    )
    checks.append({"check_id": "IAC425_CANDIDATES", "status": "PASS" if candidate_ok else "FAIL", "detail": {"actual": len(candidate_rows), "expected": 18, "excluded_negative_cases": 1}})
    if not candidate_ok:
        errors.append("iac425_candidate_mismatch")

    manifest_hash_ok = all(
        manifest["outputs"][name]["sha256"] == _sha256_file(path)
        for name, path in {
            "corpus": corpus_path,
            "coverage": coverage_path,
            "gold_review": review_path,
            "iac425_candidates": candidate_path,
        }.items()
    )
    checks.append({"check_id": "MANIFEST_OUTPUT_HASHES", "status": "PASS" if manifest_hash_ok else "FAIL", "detail": manifest["outputs"]})
    if not manifest_hash_ok:
        errors.append("manifest_output_hash_mismatch")

    local_path_pattern = re.compile(r"(?:[A-Za-z]:[\\/]|/Users/)")
    exposed_paths = sorted(
        value for value in _all_strings([coverage, review, candidates, manifest]) if local_path_pattern.search(value)
    )
    checks.append({"check_id": "NO_LOCAL_ABSOLUTE_PATH", "status": "PASS" if not exposed_paths else "FAIL", "detail": exposed_paths})
    errors.extend(f"local_path:{value}" for value in exposed_paths)

    return {
        "schema_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "generated_at": GENERATED_AT,
        "checks": checks,
        "counts": {
            "search_candidates": len(corpus),
            "gold_reviews": len(review["reviews"]),
            "iac425_candidates": len(candidate_rows),
            "errors": len(errors),
        },
        "errors": errors,
        "promotion_status": "NOT_APPROVED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_OUTPUT)
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE_OUTPUT)
    parser.add_argument("--review", default=DEFAULT_REVIEW_OUTPUT)
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--output", default=DEFAULT_QA_OUTPUT)
    args = parser.parse_args()
    report = build_qa_report(
        REPOSITORY_ROOT / args.corpus,
        REPOSITORY_ROOT / args.coverage,
        REPOSITORY_ROOT / args.review,
        REPOSITORY_ROOT / args.candidates,
        REPOSITORY_ROOT / args.manifest,
    )
    _write_json(REPOSITORY_ROOT / args.output, report)
    print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
