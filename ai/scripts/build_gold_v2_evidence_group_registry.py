#!/usr/bin/env python3
"""Build the Gold v2 Evidence Group registry consultation-condition overlay.

The canonical Full Corpus v3 registry under ``data/**`` is read-only input.  This
builder copies its 34 rows and appends only SHA-pinned, lineage-verified
consultation conditions for AI evaluation.  It deliberately does not promote
the overlay to canonical Data or to human-approved Gold.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/contracts/full_corpus_v3_consultation_conditions_v1.json"
)
DEFAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/datasets/gold/full_corpus_v3_evidence_groups_gold_v2.jsonl"
)
DEFAULT_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/datasets/gold/"
    "full_corpus_v3_evidence_groups_gold_v2_manifest.json"
)

CONDITION_ID_PATTERN = re.compile(r"^COND-[A-Z0-9-]+-[0-9]{3}$")
SHA256_PATTERN = re.compile(r"^[0-9A-F]{64}$")
ALLOWED_TRIGGERS = {"PERSISTENCE", "RECURRENCE", "AFTER_CHECK"}
ALLOWED_CHILD_USE = {"EXPERIMENT_ONLY", "RAG_HANDOFF_ONLY"}

EXPECTED_CONTRACT_KEYS = {
    "schema_version",
    "overlay_id",
    "generated_at",
    "status",
    "publication_scope",
    "source_files",
    "schema",
    "output",
    "condition_policy",
    "conditions",
    "excluded_condition_families",
}
EXPECTED_CONDITION_KEYS = {
    "condition_id",
    "condition_semantics_code",
    "evidence_group_id",
    "trigger_type",
    "source_child_ids",
    "source_page_refs",
    "source_condition_sha256",
    "gold_pending_basis_code",
    "gold_met_basis_code",
    "review_status",
}


class OverlayBuildError(ValueError):
    """Raised when a pinned input or lineage invariant does not hold."""


def _fail(code: str) -> None:
    raise OverlayBuildError(code)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise OverlayBuildError("INPUT_READ_ERROR") from exc


def _resolve_repository_path(value: Any, code: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        _fail(code)
    repository = REPOSITORY_ROOT.resolve()
    candidate = (repository / value).resolve()
    try:
        candidate.relative_to(repository)
    except ValueError:
        _fail(code)
    return candidate


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError:
        return "EXTERNAL_TEST_INPUT"


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OverlayBuildError(code) from exc
    if not isinstance(value, dict):
        _fail(code)
    return value


def _read_jsonl(path: Path, code: str) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise OverlayBuildError(code) from exc
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            _fail(code)
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OverlayBuildError(code) from exc
        if not isinstance(value, dict):
            _fail(code)
        rows.append(value)
    return rows


def _require_exact_keys(value: dict[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        _fail(code)


def _index_unique(
    rows: Iterable[dict[str, Any]], key: str, code: str
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = row.get(key)
        if not isinstance(identifier, str) or not identifier or identifier in index:
            _fail(code)
        index[identifier] = row
    return index


def _require_string_list(value: Any, code: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        _fail(code)
    return value


def _require_page_list(value: Any, code: str) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 1 for item in value)
        or len(value) != len(set(value))
    ):
        _fail(code)
    return value


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_exact_keys(contract, EXPECTED_CONTRACT_KEYS, "CONTRACT_KEYS_INVALID")
    if contract.get("schema_version") != "1.0.0":
        _fail("CONTRACT_VERSION_INVALID")
    if contract.get("overlay_id") != "full_corpus_v3_consultation_conditions_v1":
        _fail("OVERLAY_ID_INVALID")
    if contract.get("status") != "HUMAN_SIGNOFF_PENDING":
        _fail("SIGNOFF_STATUS_INVALID")
    if contract.get("publication_scope") != "AI_EVALUATION_OVERLAY_NOT_CANONICAL_DATA":
        _fail("PUBLICATION_SCOPE_INVALID")

    sources = contract.get("source_files")
    if not isinstance(sources, dict) or set(sources) != {
        "evidence_groups",
        "children",
        "corpus",
    }:
        _fail("SOURCE_FILES_INVALID")
    for source in sources.values():
        if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
            _fail("SOURCE_FILE_CONTRACT_INVALID")
        if not isinstance(source.get("path"), str) or not source["path"]:
            _fail("SOURCE_PATH_INVALID")
        if not isinstance(source.get("sha256"), str) or not SHA256_PATTERN.fullmatch(
            source["sha256"]
        ):
            _fail("SOURCE_SHA256_INVALID")

    schema = contract.get("schema")
    if not isinstance(schema, dict) or set(schema) != {"path", "sha256"}:
        _fail("SCHEMA_CONTRACT_INVALID")
    if not isinstance(schema.get("sha256"), str) or not SHA256_PATTERN.fullmatch(
        schema["sha256"]
    ):
        _fail("SCHEMA_SHA256_INVALID")

    output = contract.get("output")
    if not isinstance(output, dict) or set(output) != {
        "registry_path",
        "manifest_path",
        "expected_group_count",
        "expected_condition_count",
    }:
        _fail("OUTPUT_CONTRACT_INVALID")
    if output.get("expected_group_count") != 34:
        _fail("EXPECTED_GROUP_COUNT_INVALID")
    if output.get("expected_condition_count") != 10:
        _fail("EXPECTED_CONDITION_COUNT_INVALID")

    policy = contract.get("condition_policy")
    if policy != {
        "source_condition_binding": "EXACT_UTF8_SHA256",
        "lineage_policy": "GROUP_CHILD_PAGE_CORPUS_EXACT",
        "merge_policy": "APPEND_TO_CANONICAL_GROUP_CONSULTATION_CONDITIONS",
        "review_status": "AI_PROPOSED_PENDING_HUMAN_SIGNOFF",
    }:
        _fail("CONDITION_POLICY_INVALID")

    excluded = contract.get("excluded_condition_families")
    if excluded != [
        {
            "family": "NOISE_SEVERITY",
            "reason_code": "TRIGGER_ENUM_NOT_SUPPORTED",
            "action": "DO_NOT_REGISTER",
        }
    ]:
        _fail("EXCLUDED_CONDITION_POLICY_INVALID")


def _validate_schema_rows(
    rows: Iterable[dict[str, Any]], schema: dict[str, Any], code: str
) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise OverlayBuildError("EVIDENCE_GROUP_SCHEMA_INVALID") from exc
    validator = Draft202012Validator(schema)
    if any(any(validator.iter_errors(row)) for row in rows):
        _fail(code)


def _validate_child_and_corpus_lineage(
    *,
    condition: dict[str, Any],
    group: dict[str, Any],
    children_by_id: dict[str, dict[str, Any]],
    corpus_by_source_record: dict[str, dict[str, Any]],
) -> None:
    source_child_ids = _require_string_list(
        condition.get("source_child_ids"), "CONDITION_CHILD_IDS_INVALID"
    )
    source_pages = _require_page_list(
        condition.get("source_page_refs"), "CONDITION_PAGE_REFS_INVALID"
    )
    if not set(source_child_ids).issubset(set(group.get("child_ids", []))):
        _fail("CONDITION_GROUP_CHILD_LINEAGE_MISMATCH")
    if not set(source_pages).issubset(set(group.get("page_refs", []))):
        _fail("CONDITION_GROUP_PAGE_LINEAGE_MISMATCH")

    expected_condition_hash = condition.get("source_condition_sha256")
    if not isinstance(expected_condition_hash, str) or not SHA256_PATTERN.fullmatch(
        expected_condition_hash
    ):
        _fail("CONDITION_SOURCE_HASH_INVALID")

    matched_condition_count = 0
    selected_child_pages: set[int] = set()
    for child_id in source_child_ids:
        child = children_by_id.get(child_id)
        if child is None:
            _fail("CONDITION_CHILD_NOT_FOUND")
        if child.get("evidence_group_id") != group.get("evidence_group_id"):
            _fail("CONDITION_CHILD_GROUP_LINEAGE_MISMATCH")
        if child.get("exact_sales_code") != group.get("exact_sales_code"):
            _fail("CONDITION_CHILD_PRODUCT_LINEAGE_MISMATCH")
        if child.get("document_id") != group.get("document_id"):
            _fail("CONDITION_CHILD_DOCUMENT_LINEAGE_MISMATCH")
        child_pages = _require_page_list(
            child.get("page_refs"), "CONDITION_CHILD_PAGE_REFS_INVALID"
        )
        selected_child_pages.update(child_pages)
        if not set(child_pages).issubset(set(group.get("page_refs", []))):
            _fail("CONDITION_CHILD_PAGE_LINEAGE_MISMATCH")
        if str(child.get("record_type", "")).lower() != "child":
            _fail("CONDITION_CHILD_RECORD_TYPE_INVALID")
        if child.get("retrieval_role") != "SEARCH_CANDIDATE":
            _fail("CONDITION_CHILD_RETRIEVAL_ROLE_INVALID")
        if child.get("allowed_use") not in ALLOWED_CHILD_USE:
            _fail("CONDITION_CHILD_ALLOWED_USE_INVALID")
        if child.get("verification_status") != "TEXT_AND_VISUAL_VERIFIED":
            _fail("CONDITION_CHILD_VERIFICATION_INVALID")

        source_conditions = child.get("consultation_conditions")
        if (
            not isinstance(source_conditions, list)
            or not source_conditions
            or any(not isinstance(item, str) or not item for item in source_conditions)
        ):
            _fail("CHILD_FREE_TEXT_CONDITION_MISSING")
        matched_condition_count += sum(
            _sha256_bytes(item.encode("utf-8")) == expected_condition_hash
            for item in source_conditions
        )

        corpus = corpus_by_source_record.get(child_id)
        if corpus is None:
            _fail("CONDITION_CORPUS_CHILD_NOT_FOUND")
        if corpus.get("record_type") != "CHILD":
            _fail("CONDITION_CORPUS_RECORD_TYPE_INVALID")
        if corpus.get("retrieval_role") != "SEARCH_CANDIDATE":
            _fail("CONDITION_CORPUS_RETRIEVAL_ROLE_INVALID")
        if corpus.get("allowed_use") != "EXPERIMENT_ONLY":
            _fail("CONDITION_CORPUS_ALLOWED_USE_INVALID")
        if corpus.get("source_verification_status") != "TEXT_AND_VISUAL_VERIFIED":
            _fail("CONDITION_CORPUS_VERIFICATION_INVALID")
        if group.get("evidence_group_id") not in corpus.get("evidence_unit_ids", []):
            _fail("CONDITION_CORPUS_GROUP_LINK_MISSING")
        if corpus.get("exact_sales_code") != child.get("exact_sales_code"):
            _fail("CONDITION_CORPUS_PRODUCT_LINEAGE_MISMATCH")
        if corpus.get("document_id") != child.get("document_id"):
            _fail("CONDITION_CORPUS_DOCUMENT_LINEAGE_MISMATCH")
        if set(corpus.get("page_refs", [])) != set(child_pages):
            _fail("CONDITION_CORPUS_PAGE_LINEAGE_MISMATCH")
        if corpus.get("source_variant_id") != child.get("source_variant_id"):
            _fail("CONDITION_CORPUS_VARIANT_LINEAGE_MISMATCH")
        if corpus.get("source_file_sha256") != child.get("source_file_sha256"):
            _fail("CONDITION_CORPUS_SOURCE_HASH_MISMATCH")
        if corpus.get("text_sha256") != child.get("child_text_sha256"):
            _fail("CONDITION_CORPUS_TEXT_HASH_MISMATCH")

    if not set(source_pages).issubset(selected_child_pages):
        _fail("CONDITION_SELECTED_CHILD_PAGE_LINEAGE_MISMATCH")
    if matched_condition_count != 1:
        _fail("CHILD_FREE_TEXT_CONDITION_HASH_MISMATCH")


def _serialize_jsonl(rows: Iterable[dict[str, Any]]) -> bytes:
    text = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    return text.encode("utf-8")


def _serialize_json(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def build_overlay(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    output_path: Path | None = None,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Validate pinned sources and write deterministic overlay artifacts."""

    contract_path = contract_path.resolve()
    contract = _read_json(contract_path, "CONTRACT_READ_ERROR")
    _validate_contract(contract)

    sources: dict[str, dict[str, str]] = contract["source_files"]
    source_paths = {
        name: _resolve_repository_path(source["path"], "SOURCE_PATH_INVALID")
        for name, source in sources.items()
    }
    for name, path in source_paths.items():
        if _sha256_file(path) != sources[name]["sha256"]:
            _fail(f"SOURCE_HASH_MISMATCH:{name}")

    schema_path = _resolve_repository_path(
        contract["schema"]["path"], "SCHEMA_PATH_INVALID"
    )
    if _sha256_file(schema_path) != contract["schema"]["sha256"]:
        _fail("SCHEMA_HASH_MISMATCH")
    schema = _read_json(schema_path, "SCHEMA_READ_ERROR")

    canonical_groups = _read_jsonl(
        source_paths["evidence_groups"], "EVIDENCE_GROUPS_READ_ERROR"
    )
    children = _read_jsonl(source_paths["children"], "CHILDREN_READ_ERROR")
    corpus = _read_jsonl(source_paths["corpus"], "CORPUS_READ_ERROR")
    if len(canonical_groups) != contract["output"]["expected_group_count"]:
        _fail("CANONICAL_GROUP_COUNT_MISMATCH")
    _validate_schema_rows(canonical_groups, schema, "CANONICAL_GROUP_SCHEMA_MISMATCH")

    groups_by_id = _index_unique(
        canonical_groups, "evidence_group_id", "DUPLICATE_OR_MISSING_GROUP_ID"
    )
    children_by_id = _index_unique(
        children, "child_id", "DUPLICATE_OR_MISSING_CHILD_ID"
    )
    corpus_by_source_record = _index_unique(
        corpus,
        "source_record_id",
        "DUPLICATE_OR_MISSING_CORPUS_SOURCE_RECORD_ID",
    )

    conditions = contract.get("conditions")
    if (
        not isinstance(conditions, list)
        or len(conditions) != contract["output"]["expected_condition_count"]
    ):
        _fail("CONDITION_COUNT_MISMATCH")

    existing_condition_ids: set[str] = set()
    for group in canonical_groups:
        existing = group.get("consultation_conditions")
        if not isinstance(existing, list):
            _fail("CANONICAL_CONDITIONS_INVALID")
        for condition in existing:
            if not isinstance(condition, dict):
                _fail("CANONICAL_CONDITION_INVALID")
            condition_id = condition.get("condition_id")
            if (
                not isinstance(condition_id, str)
                or not condition_id
                or condition_id in existing_condition_ids
            ):
                _fail("CANONICAL_CONDITION_ID_INVALID")
            existing_condition_ids.add(condition_id)

    overlay_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    condition_ids: set[str] = set()
    semantics_codes: set[tuple[str, str]] = set()
    for condition in conditions:
        if not isinstance(condition, dict):
            _fail("CONDITION_ROW_INVALID")
        _require_exact_keys(condition, EXPECTED_CONDITION_KEYS, "CONDITION_KEYS_INVALID")
        condition_id = condition.get("condition_id")
        if (
            not isinstance(condition_id, str)
            or not CONDITION_ID_PATTERN.fullmatch(condition_id)
            or condition_id in condition_ids
            or condition_id in existing_condition_ids
        ):
            _fail("CONDITION_ID_INVALID")
        condition_ids.add(condition_id)
        semantics_code = condition.get("condition_semantics_code")
        group_id = condition.get("evidence_group_id")
        if not isinstance(semantics_code, str) or not semantics_code:
            _fail("CONDITION_SEMANTICS_CODE_INVALID")
        if not isinstance(group_id, str) or group_id not in groups_by_id:
            _fail("CONDITION_GROUP_NOT_FOUND")
        semantics_key = (group_id, semantics_code)
        if semantics_key in semantics_codes:
            _fail("CONDITION_SEMANTICS_DUPLICATE")
        semantics_codes.add(semantics_key)
        if condition.get("trigger_type") not in ALLOWED_TRIGGERS:
            _fail("CONDITION_TRIGGER_INVALID")
        if condition.get("gold_pending_basis_code") != "SOURCE_CONDITION_PENDING":
            _fail("CONDITION_PENDING_BASIS_INVALID")
        if condition.get("gold_met_basis_code") != "SOURCE_CONDITION_MET":
            _fail("CONDITION_MET_BASIS_INVALID")
        if condition.get("review_status") != "AI_PROPOSED_PENDING_HUMAN_SIGNOFF":
            _fail("CONDITION_REVIEW_STATUS_INVALID")

        group = groups_by_id[group_id]
        _validate_child_and_corpus_lineage(
            condition=condition,
            group=group,
            children_by_id=children_by_id,
            corpus_by_source_record=corpus_by_source_record,
        )
        overlay_by_group[group_id].append(
            {
                "condition_id": condition_id,
                "trigger_type": condition["trigger_type"],
                "source_child_ids": condition["source_child_ids"],
                "source_page_refs": condition["source_page_refs"],
            }
        )

    derived_groups = copy.deepcopy(canonical_groups)
    for group in derived_groups:
        additions = overlay_by_group.get(group["evidence_group_id"], [])
        group["consultation_conditions"] = sorted(
            [*group["consultation_conditions"], *additions],
            key=lambda item: item["condition_id"],
        )
    _validate_schema_rows(derived_groups, schema, "DERIVED_GROUP_SCHEMA_MISMATCH")

    for canonical, derived in zip(canonical_groups, derived_groups, strict=True):
        canonical_without_conditions = {
            key: value for key, value in canonical.items() if key != "consultation_conditions"
        }
        derived_without_conditions = {
            key: value for key, value in derived.items() if key != "consultation_conditions"
        }
        if canonical_without_conditions != derived_without_conditions:
            _fail("CANONICAL_GROUP_FIELD_DRIFT")

    output_path = (output_path or DEFAULT_OUTPUT_PATH).resolve()
    manifest_path = (manifest_path or DEFAULT_MANIFEST_PATH).resolve()
    if output_path == source_paths["evidence_groups"]:
        _fail("CANONICAL_DATA_OVERWRITE_FORBIDDEN")
    if output_path == manifest_path:
        _fail("OUTPUT_PATH_COLLISION")

    output_bytes = _serialize_jsonl(derived_groups)
    condition_group_counts = Counter(
        groups_by_id[group_id]["exact_sales_code"] for group_id in overlay_by_group
    )
    condition_product_counts = Counter(
        groups_by_id[condition["evidence_group_id"]]["exact_sales_code"]
        for condition in conditions
    )
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "overlay_id": contract["overlay_id"],
        "generated_at": contract["generated_at"],
        "build_status": "PASS",
        "status": contract["status"],
        "publication_scope": contract["publication_scope"],
        "promotion_status": "NOT_APPROVED",
        "contract": {
            "path": _path_label(contract_path),
            "sha256": _sha256_file(contract_path),
        },
        "source_files": copy.deepcopy(sources),
        "schema": copy.deepcopy(contract["schema"]),
        "output": {
            "path": contract["output"]["registry_path"],
            "sha256": _sha256_bytes(output_bytes),
            "group_count": len(derived_groups),
            "condition_count": len(conditions),
            "condition_group_count": len(overlay_by_group),
            "condition_groups_by_product": dict(sorted(condition_group_counts.items())),
            "conditions_by_product": dict(sorted(condition_product_counts.items())),
        },
        "condition_ids": sorted(condition_ids),
        "excluded_condition_families": copy.deepcopy(
            contract["excluded_condition_families"]
        ),
        "activation_gate": "TWO_PERSON_APPROVED_REQUIRED",
    }
    manifest_bytes = _serialize_json(manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_bytes)
    manifest_path.write_bytes(manifest_bytes)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gold v2 Evidence Group 상담 조건 Overlay 생성"
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()
    try:
        manifest = build_overlay(args.contract, args.output, args.manifest)
    except OverlayBuildError as exc:
        print(json.dumps({"status": "FAIL", "error_code": str(exc)}))
        return 1
    print(
        json.dumps(
            {
                "status": manifest["build_status"],
                "signoff_status": manifest["status"],
                "publication_scope": manifest["publication_scope"],
                "counts": {
                    "groups": manifest["output"]["group_count"],
                    "condition_groups": manifest["output"]["condition_group_count"],
                    "conditions": manifest["output"]["condition_count"],
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
