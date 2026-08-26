"""Full Corpus v3와 Evidence Group–Child 인계 산출물을 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .build_full_corpus_v3_handoff import (
    CHILD_SCHEMA,
    CONFIG_PATH,
    CORPUS_SCHEMA,
    COVERAGE_SCHEMA,
    DEFAULT_CHILD_OUTPUT,
    DEFAULT_CORPUS_OUTPUT,
    DEFAULT_COVERAGE_OUTPUT,
    DEFAULT_GROUP_OUTPUT,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_PARENT_OUTPUT,
    GENERATED_AT,
    GROUP_SCHEMA,
    PARENT_SCHEMA,
    REPOSITORY_ROOT,
    SOURCE_REVIEW_SCHEMA,
)


DEFAULT_QA_OUTPUT = (
    "data/processed/validation/rag_experiments/full_corpus_v3_qa.json"
)
SOURCE_REVIEW_PATH = (
    "data/processed/validation/rag_experiments/"
    "full_corpus_v3_source_span_human_review.json"
)
V2_CORPUS_PATH = (
    "data/processed/structured/rag/experimental/full_corpus_chunks_v2.jsonl"
)
V2_CORPUS_SHA256 = (
    "2D4A022A8FEABD376C9F5D42E7D28BA8E18571274D19A05794D066B7113D6FC6"
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
        for error in sorted(
            validator.iter_errors(instance), key=lambda item: list(item.absolute_path)
        )
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
    parent_path: Path,
    child_path: Path,
    group_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    corpus = _read_jsonl(corpus_path)
    coverage = _read_json(coverage_path)
    parents = _read_jsonl(parent_path)
    children = _read_jsonl(child_path)
    groups = _read_jsonl(group_path)
    manifest = _read_json(manifest_path)
    config = _read_json(REPOSITORY_ROOT / CONFIG_PATH)
    review = _read_json(REPOSITORY_ROOT / SOURCE_REVIEW_PATH)
    gold = _read_jsonl(
        REPOSITORY_ROOT / config["inputs"]["gold_dataset"]["path"]
    )
    contract = _read_json(
        REPOSITORY_ROOT / config["inputs"]["gold_v2_group_contract"]["path"]
    )
    manual_rows: dict[tuple[str, int], dict[str, Any]] = {}
    for replacement in config["replacements"]:
        for row in _read_jsonl(
            REPOSITORY_ROOT / config["inputs"][replacement["manual_input"]]["path"]
        ):
            if str(row["page"]) in replacement["pages"]:
                manual_rows[(replacement["document_id"], row["page"])] = row

    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    schema_failures: list[str] = []
    for label, rows, schema in (
        ("corpus", corpus, CORPUS_SCHEMA),
        ("parents", parents, PARENT_SCHEMA),
        ("children", children, CHILD_SCHEMA),
        ("groups", groups, GROUP_SCHEMA),
    ):
        for index, row in enumerate(rows):
            schema_failures.extend(
                f"{label}[{index}]:{message}"
                for message in _schema_errors(row, schema)
            )
    schema_failures.extend(
        f"coverage:{message}"
        for message in _schema_errors(coverage, COVERAGE_SCHEMA)
    )
    schema_failures.extend(
        f"source_review:{message}"
        for message in _schema_errors(review, SOURCE_REVIEW_SCHEMA)
    )
    checks.append(
        {
            "check_id": "SCHEMA",
            "status": "PASS" if not schema_failures else "FAIL",
            "detail": schema_failures,
        }
    )
    errors.extend(schema_failures)

    product_counts = Counter(row["exact_sales_code"] for row in corpus)
    type_counts = Counter(row["record_type"] for row in corpus)
    count_ok = (
        len(corpus) == 132
        and product_counts
        == Counter({"WPUIAC425SNW": 68, "WPUJAC104DWH": 64})
        and type_counts
        == Counter({"SOURCE_PAGE": 85, "CHILD": 37, "PRESERVATION": 10})
        and len(parents) == 11
        and len(children) == 37
        and len(groups) == 34
    )
    checks.append(
        {
            "check_id": "FIXED_COUNTS",
            "status": "PASS" if count_ok else "FAIL",
            "detail": {
                "search_candidates": len(corpus),
                "products": dict(product_counts),
                "record_types": dict(type_counts),
                "context_parents": len(parents),
                "registry_children": len(children),
                "evidence_groups": len(groups),
            },
        }
    )
    if not count_ok:
        errors.append("fixed_count_mismatch")

    ids = [row["chunk_id"] for row in corpus]
    id_ok = (
        len(ids) == len(set(ids))
        and [row["chunk_index"] for row in corpus]
        == list(range(1, len(corpus) + 1))
        and len({row["parent_id"] for row in parents}) == len(parents)
        and len({row["child_id"] for row in children}) == len(children)
        and len({row["evidence_group_id"] for row in groups}) == len(groups)
    )
    checks.append(
        {
            "check_id": "ID_AND_INDEX_UNIQUENESS",
            "status": "PASS" if id_ok else "FAIL",
            "detail": "Corpus index contiguous; Parent, Child, Group IDs unique",
        }
    )
    if not id_ok:
        errors.append("id_or_index_mismatch")

    hash_failures = [
        row["chunk_id"]
        for row in corpus
        if _sha256_text(row["text"]) != row["text_sha256"]
    ]
    hash_failures.extend(
        row["child_id"]
        for row in children
        if _sha256_text(row["child_text"]) != row["child_text_sha256"]
    )
    checks.append(
        {
            "check_id": "TEXT_HASHES",
            "status": "PASS" if not hash_failures else "FAIL",
            "detail": hash_failures,
        }
    )
    errors.extend(f"text_hash:{item}" for item in hash_failures)

    coverage_failures: list[str] = []
    for page in coverage["pages"]:
        numbers = [row["line_number"] for row in page["assignments"]]
        key = (page["document_id"], page["page"])
        if (
            numbers != list(range(1, page["total_lines"] + 1))
            or page["total_lines"]
            != len(manual_rows[key]["text"].split("\n"))
        ):
            coverage_failures.append(
                f"{page['exact_sales_code']}:P{page['page']:03d}"
            )
    checks.append(
        {
            "check_id": "LINE_COVERAGE",
            "status": "PASS" if not coverage_failures else "FAIL",
            "detail": coverage_failures,
        }
    )
    errors.extend(f"coverage:{item}" for item in coverage_failures)

    parent_by_id = {row["parent_id"]: row for row in parents}
    group_by_id = {row["evidence_group_id"]: row for row in groups}
    corpus_children = {
        row["source_record_id"]: row
        for row in corpus
        if row["record_type"] == "CHILD"
    }
    lineage_failures: list[str] = []
    for child in children:
        parent = parent_by_id.get(child["parent_id"])
        group = group_by_id.get(child["evidence_group_id"])
        corpus_row = corpus_children.get(child["child_id"])
        if (
            parent is None
            or group is None
            or corpus_row is None
            or parent["exact_sales_code"] != child["exact_sales_code"]
            or parent["document_id"] != child["document_id"]
            or child["child_id"] not in group["child_ids"]
            or corpus_row["evidence_unit_ids"] != [child["evidence_group_id"]]
            or corpus_row["source_variant_id"] != child["source_variant_id"]
            or corpus_row["source_file_sha256"] != child["source_file_sha256"]
            or corpus_row["text_sha256"] != child["child_text_sha256"]
        ):
            lineage_failures.append(child["child_id"])
    for group in groups:
        variants = [
            child
            for child in children
            if child["evidence_group_id"] == group["evidence_group_id"]
        ]
        variants.sort(key=lambda row: (row["page_refs"][0], row["child_id"]))
        if (
            group["child_ids"] != [row["child_id"] for row in variants]
            or group["source_variant_ids"]
            != [row["source_variant_id"] for row in variants]
        ):
            lineage_failures.append(group["evidence_group_id"])
    preservation_failures = [
        row["chunk_id"]
        for row in corpus
        if row["record_type"] == "PRESERVATION"
        and row["evidence_unit_ids"] != [row["chunk_id"]]
    ]
    checks.append(
        {
            "check_id": "GROUP_CHILD_CORPUS_LINEAGE",
            "status": "PASS"
            if not lineage_failures and not preservation_failures
            else "FAIL",
            "detail": {
                "lineage": lineage_failures,
                "preservation": preservation_failures,
            },
        }
    )
    errors.extend(f"lineage:{item}" for item in lineage_failures)
    errors.extend(f"preservation:{item}" for item in preservation_failures)

    contract_by_id = {
        row["evidence_group_id"]: row for row in contract["groups"]
    }
    contract_failures = [
        group_id
        for group_id, expected in contract_by_id.items()
        if group_by_id.get(group_id) != expected
    ]
    checks.append(
        {
            "check_id": "AI_GROUP_CONTRACT_ACK",
            "status": "PASS" if not contract_failures else "FAIL",
            "detail": {
                "contract_groups": len(contract_by_id),
                "mismatches": contract_failures,
            },
        }
    )
    errors.extend(f"contract:{item}" for item in contract_failures)

    iac_groups = [
        row for row in groups if row["exact_sales_code"] == "WPUIAC425SNW"
    ]
    iac_children = [
        row for row in children if row["exact_sales_code"] == "WPUIAC425SNW"
    ]
    iac_ok = (
        len(iac_groups) == 18
        and len(iac_children) == 19
        and all(row["child_id"] in corpus_children for row in iac_children)
    )
    checks.append(
        {
            "check_id": "IAC425_GROUP_CHILD_LINKS",
            "status": "PASS" if iac_ok else "FAIL",
            "detail": {
                "evidence_groups": len(iac_groups),
                "children": len(iac_children),
                "linked_children": sum(
                    row["child_id"] in corpus_children for row in iac_children
                ),
            },
        }
    )
    if not iac_ok:
        errors.append("iac425_group_child_link_mismatch")

    decision_by_code = {row["decision_code"]: row for row in review["decisions"]}
    review_failures: list[str] = []
    for code in ("1-A", "2-A", "3-A", "4-A"):
        decision = decision_by_code.get(code)
        if decision is None:
            review_failures.append(code)
            continue
        source = manual_rows[(review["document_id"], decision["page"])]
        lines = source["text"].split("\n")
        raw_span = "\n".join(
            lines[decision["line_start"] - 1 : decision["line_end"]]
        )
        child = next(
            (
                row
                for row in children
                if row["child_id"] == decision["child_id"]
            ),
            None,
        )
        if (
            _sha256_text(raw_span) != decision["raw_span_sha256"]
            or child is None
            or child["evidence_group_id"] != decision["evidence_group_id"]
            or child["source_span"]["raw_span_sha256"]
            != decision["raw_span_sha256"]
        ):
            review_failures.append(code)
    review_ok = (
        not review_failures
        and review["status"] == "DATA_QA_SOURCE_SPAN_VERIFIED"
        and review["gold_signoff_status"] == "HUMAN_SIGNOFF_PENDING"
    )
    checks.append(
        {
            "check_id": "HUMAN_SOURCE_SPAN_DECISIONS",
            "status": "PASS" if review_ok else "FAIL",
            "detail": {"decision_codes": sorted(decision_by_code), "failures": review_failures},
        }
    )
    if not review_ok:
        errors.append("source_span_human_review_mismatch")

    gold_queries = {row["query"].strip() for row in gold}
    copied = [
        row["chunk_id"]
        for row in corpus
        if row["record_type"] != "SOURCE_PAGE"
        and row["text"].strip() in gold_queries
    ]
    checks.append(
        {
            "check_id": "GOLD_QUERY_COPY",
            "status": "PASS" if not copied else "FAIL",
            "detail": copied,
        }
    )
    errors.extend(f"gold_query_copy:{item}" for item in copied)

    input_failures = [
        name
        for name, spec in config["inputs"].items()
        if _sha256_file(REPOSITORY_ROOT / spec["path"]) != spec["sha256"]
    ]
    if _sha256_file(REPOSITORY_ROOT / V2_CORPUS_PATH) != V2_CORPUS_SHA256:
        input_failures.append("preserved_full_corpus_v2")
    checks.append(
        {
            "check_id": "PINNED_INPUTS_AND_V2_PRESERVATION",
            "status": "PASS" if not input_failures else "FAIL",
            "detail": input_failures,
        }
    )
    errors.extend(f"input_hash:{item}" for item in input_failures)

    output_paths = {
        "corpus": corpus_path,
        "coverage": coverage_path,
        "context_parents": parent_path,
        "children": child_path,
        "evidence_groups": group_path,
    }
    manifest_failures = [
        name
        for name, path in output_paths.items()
        if manifest["outputs"][name]["sha256"] != _sha256_file(path)
    ]
    checks.append(
        {
            "check_id": "MANIFEST_OUTPUT_HASHES",
            "status": "PASS" if not manifest_failures else "FAIL",
            "detail": manifest_failures,
        }
    )
    errors.extend(f"manifest_hash:{item}" for item in manifest_failures)

    product_documents: dict[str, set[str]] = defaultdict(set)
    for row in corpus:
        product_documents[row["exact_sales_code"]].add(row["document_id"])
    product_mix_ok = product_documents == {
        "WPUJAC104DWH": {"MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00"},
        "WPUIAC425SNW": {"MAN-SKMAGIC-WPU-IAC425-REV02"},
    }
    checks.append(
        {
            "check_id": "PRODUCT_DOCUMENT_ISOLATION",
            "status": "PASS" if product_mix_ok else "FAIL",
            "detail": {key: sorted(value) for key, value in product_documents.items()},
        }
    )
    if not product_mix_ok:
        errors.append("product_document_mix")

    local_path_pattern = re.compile(r"(?:[A-Za-z]:[\\/]|/Users/)")
    exposed_paths = sorted(
        value
        for value in _all_strings([coverage, review, manifest])
        if local_path_pattern.search(value)
    )
    checks.append(
        {
            "check_id": "NO_LOCAL_ABSOLUTE_PATH",
            "status": "PASS" if not exposed_paths else "FAIL",
            "detail": exposed_paths,
        }
    )
    errors.extend(f"local_path:{value}" for value in exposed_paths)

    return {
        "schema_version": "1.0.0",
        "status": "PASS" if not errors else "FAIL",
        "generated_at": GENERATED_AT,
        "checks": checks,
        "counts": {
            "search_candidates": len(corpus),
            "context_only_parents": len(parents),
            "evidence_groups": len(groups),
            "children": len(children),
            "iac425_evidence_groups": len(iac_groups),
            "iac425_children": len(iac_children),
            "source_span_decisions": len(review["decisions"]),
            "errors": len(errors),
        },
        "errors": errors,
        "gold_signoff_status": "HUMAN_SIGNOFF_PENDING",
        "promotion_status": "NOT_APPROVED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_OUTPUT)
    parser.add_argument("--coverage", default=DEFAULT_COVERAGE_OUTPUT)
    parser.add_argument("--parents", default=DEFAULT_PARENT_OUTPUT)
    parser.add_argument("--children", default=DEFAULT_CHILD_OUTPUT)
    parser.add_argument("--groups", default=DEFAULT_GROUP_OUTPUT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_OUTPUT)
    parser.add_argument("--output", default=DEFAULT_QA_OUTPUT)
    args = parser.parse_args()
    report = build_qa_report(
        REPOSITORY_ROOT / args.corpus,
        REPOSITORY_ROOT / args.coverage,
        REPOSITORY_ROOT / args.parents,
        REPOSITORY_ROOT / args.children,
        REPOSITORY_ROOT / args.groups,
        REPOSITORY_ROOT / args.manifest,
    )
    _write_json(REPOSITORY_ROOT / args.output, report)
    print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
