#!/usr/bin/env python3
"""Gold v2와 Evidence Group·Child·Corpus의 연결 계약을 검증한다.

이 검증기는 원문 내용의 타당성을 판정하지 않는다. Gold가 참조하는 의미 단위
Evidence Group이 같은 제품의 Child Registry와 검색 가능한 Corpus Chunk까지
손실 없이 연결되는지만 확인한다.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_VERSION = "gold_corpus_compatibility_v2"
EVIDENCE_GROUP_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/schemas/evidence_group_registry_v2.schema.json"
)

SOURCE_GOLD = "gold"
SOURCE_GROUPS = "evidence_groups"
SOURCE_CHILDREN = "children"
SOURCE_CORPUS = "corpus"

ALLOWED_POLICY_BLOCK_PATHS = {
    "POLICY_BLOCK_PRODUCT_MISMATCH",
    "POLICY_BLOCK_UNSUPPORTED_MODEL",
    "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
    "POLICY_BLOCK_UNVERIFIED_SOURCE",
}
ALLOWED_CHILD_USE_VALUES = {"EXPERIMENT_ONLY", "RAG_HANDOFF_ONLY"}
REQUIRED_CORPUS_ALLOWED_USE = "EXPERIMENT_ONLY"
REQUIRED_VERIFICATION_STATUS = "TEXT_AND_VISUAL_VERIFIED"
SHA256_PATTERN = re.compile(r"^[0-9A-Fa-f]{64}$")


@dataclass(frozen=True)
class JsonlRow:
    line: int
    value: dict[str, Any]


def _error(
    code: str,
    source: str,
    line: int | None = None,
    *,
    related_source: str | None = None,
    related_line: int | None = None,
) -> dict[str, Any]:
    """Create a diagnostic without copying identifiers, text, or secret values."""

    item: dict[str, Any] = {"code": code, "source": source}
    if line is not None:
        item["line"] = line
    if related_source is not None:
        item["related_source"] = related_source
    if related_line is not None:
        item["related_line"] = related_line
    return item


def _load_jsonl(path: Path, source: str) -> tuple[list[JsonlRow], list[dict[str, Any]]]:
    rows: list[JsonlRow] = []
    errors: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return [], [_error("INPUT_FILE_MISSING", source)]
    except OSError:
        return [], [_error("INPUT_FILE_READ_ERROR", source)]

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            errors.append(_error("BLANK_JSONL_LINE", source, line_number))
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            errors.append(_error("INVALID_JSON", source, line_number))
            continue
        if not isinstance(value, dict):
            errors.append(_error("ROW_NOT_OBJECT", source, line_number))
            continue
        rows.append(JsonlRow(line=line_number, value=value))
    return rows, errors


def _index_unique(
    rows: Iterable[JsonlRow],
    field: str,
    source: str,
    missing_code: str,
    duplicate_code: str,
    errors: list[dict[str, Any]],
) -> dict[str, JsonlRow]:
    indexed: dict[str, JsonlRow] = {}
    for row in rows:
        identifier = row.value.get(field)
        if not isinstance(identifier, str) or not identifier:
            errors.append(_error(missing_code, source, row.line))
            continue
        if identifier in indexed:
            errors.append(
                _error(
                    duplicate_code,
                    source,
                    row.line,
                    related_source=source,
                    related_line=indexed[identifier].line,
                )
            )
            continue
        indexed[identifier] = row
    return indexed


def _validate_evidence_group_schema(
    rows: Iterable[JsonlRow],
    errors: list[dict[str, Any]],
) -> None:
    """Fail closed when a Registry row does not match the canonical v2 schema."""

    try:
        schema = json.loads(EVIDENCE_GROUP_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError):
        errors.append(_error("GROUP_SCHEMA_CONTRACT_INVALID", SOURCE_GROUPS))
        return

    validator = Draft202012Validator(schema)
    for row in rows:
        if any(validator.iter_errors(row.value)):
            errors.append(
                _error("GROUP_SCHEMA_VALIDATION_ERROR", SOURCE_GROUPS, row.line)
            )


def _string_list(
    row: JsonlRow,
    field: str,
    source: str,
    errors: list[dict[str, Any]],
    invalid_code: str,
    duplicate_code: str,
) -> list[str]:
    value = row.value.get(field)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(_error(invalid_code, source, row.line))
        return []
    if len(value) != len(set(value)):
        errors.append(_error(duplicate_code, source, row.line))
    return value


def _group_ids_attached(corpus: dict[str, Any]) -> set[str]:
    attached: set[str] = set()
    singular = corpus.get("evidence_group_id")
    if isinstance(singular, str) and singular:
        attached.add(singular)
    for field in ("evidence_group_ids", "evidence_unit_ids"):
        value = corpus.get(field)
        if isinstance(value, list):
            attached.update(item for item in value if isinstance(item, str) and item)
    return attached


def _same_page_lineage(left: Any, right: Any) -> bool:
    return (
        isinstance(left, list)
        and isinstance(right, list)
        and bool(left)
        and bool(right)
        and all(isinstance(page, int) and page >= 1 for page in left + right)
        and set(left) == set(right)
    )


def _child_page_within_group(child_pages: Any, group_pages: Any) -> bool:
    return (
        isinstance(child_pages, list)
        and isinstance(group_pages, list)
        and bool(child_pages)
        and bool(group_pages)
        and all(
            isinstance(page, int) and page >= 1
            for page in child_pages + group_pages
        )
        and set(child_pages).issubset(set(group_pages))
    )


def _child_matches_group(
    group: JsonlRow,
    child: JsonlRow,
    group_id: str,
    errors: list[dict[str, Any]],
) -> bool:
    valid = True
    checks = (
        (
            child.value.get("evidence_group_id") == group_id,
            "CHILD_GROUP_LINEAGE_MISMATCH",
        ),
        (
            child.value.get("exact_sales_code") == group.value.get("exact_sales_code"),
            "CHILD_PRODUCT_LINEAGE_MISMATCH",
        ),
        (
            child.value.get("document_id") == group.value.get("document_id"),
            "CHILD_DOCUMENT_LINEAGE_MISMATCH",
        ),
        (
            _child_page_within_group(
                child.value.get("page_refs"), group.value.get("page_refs")
            ),
            "CHILD_PAGE_LINEAGE_MISMATCH",
        ),
        (
            str(child.value.get("record_type", "")).lower() == "child",
            "CHILD_RECORD_TYPE_INVALID",
        ),
        (
            child.value.get("retrieval_role") == "SEARCH_CANDIDATE",
            "CHILD_RETRIEVAL_ROLE_INVALID",
        ),
        (
            child.value.get("allowed_use") in ALLOWED_CHILD_USE_VALUES,
            "CHILD_ALLOWED_USE_INVALID",
        ),
        (
            child.value.get("verification_status")
            == REQUIRED_VERIFICATION_STATUS,
            "CHILD_VERIFICATION_STATUS_INVALID",
        ),
        (
            isinstance(child.value.get("source_file_sha256"), str)
            and SHA256_PATTERN.fullmatch(child.value["source_file_sha256"])
            is not None,
            "CHILD_SOURCE_FILE_SHA256_INVALID",
        ),
        (
            isinstance(child.value.get("child_text_sha256"), str)
            and SHA256_PATTERN.fullmatch(child.value["child_text_sha256"])
            is not None,
            "CHILD_TEXT_SHA256_INVALID",
        ),
    )
    for passed, code in checks:
        if not passed:
            errors.append(
                _error(
                    code,
                    SOURCE_CHILDREN,
                    child.line,
                    related_source=SOURCE_GROUPS,
                    related_line=group.line,
                )
            )
            valid = False
    return valid


def _corpus_matches_child(
    corpus: JsonlRow,
    child: JsonlRow,
    group: JsonlRow,
    group_id: str,
    errors: list[dict[str, Any]],
) -> bool:
    valid = True
    record_type = str(corpus.value.get("record_type", "")).upper()
    if record_type != "CHILD":
        errors.append(
            _error(
                "CORPUS_NON_CHILD_CANNOT_SATISFY_GROUP",
                SOURCE_CORPUS,
                corpus.line,
                related_source=SOURCE_CHILDREN,
                related_line=child.line,
            )
        )
        valid = False
    checks = (
        (
            corpus.value.get("retrieval_role") == "SEARCH_CANDIDATE",
            "CORPUS_RETRIEVAL_ROLE_INVALID",
        ),
        (
            corpus.value.get("allowed_use") == REQUIRED_CORPUS_ALLOWED_USE,
            "CORPUS_ALLOWED_USE_INVALID",
        ),
        (
            corpus.value.get("source_verification_status")
            == REQUIRED_VERIFICATION_STATUS,
            "CORPUS_VERIFICATION_STATUS_INVALID",
        ),
        (
            corpus.value.get("exact_sales_code") == child.value.get("exact_sales_code"),
            "CORPUS_PRODUCT_LINEAGE_MISMATCH",
        ),
        (
            corpus.value.get("document_id") == child.value.get("document_id"),
            "CORPUS_DOCUMENT_LINEAGE_MISMATCH",
        ),
        (
            _same_page_lineage(
                corpus.value.get("page_refs"), child.value.get("page_refs")
            ),
            "CORPUS_PAGE_LINEAGE_MISMATCH",
        ),
        (
            group_id in _group_ids_attached(corpus.value),
            "CORPUS_GROUP_LINK_MISSING",
        ),
    )
    for passed, code in checks:
        if not passed:
            errors.append(
                _error(
                    code,
                    SOURCE_CORPUS,
                    corpus.line,
                    related_source=SOURCE_CHILDREN,
                    related_line=child.line,
                )
            )
            valid = False

    corpus_variant = corpus.value.get("source_variant_id")
    child_variant = child.value.get("source_variant_id")
    if (
        not isinstance(corpus_variant, str)
        or not corpus_variant
        or corpus_variant != child_variant
    ):
        errors.append(
            _error(
                "CORPUS_SOURCE_VARIANT_LINEAGE_MISMATCH",
                SOURCE_CORPUS,
                corpus.line,
                related_source=SOURCE_CHILDREN,
                related_line=child.line,
            )
        )
        valid = False

    corpus_hash = corpus.value.get("source_file_sha256")
    child_hash = child.value.get("source_file_sha256")
    if (
        not isinstance(corpus_hash, str)
        or SHA256_PATTERN.fullmatch(corpus_hash) is None
        or corpus_hash != child_hash
    ):
        errors.append(
            _error(
                "CORPUS_SOURCE_FILE_LINEAGE_MISMATCH",
                SOURCE_CORPUS,
                corpus.line,
                related_source=SOURCE_CHILDREN,
                related_line=child.line,
            )
        )
        valid = False

    corpus_text_hash = corpus.value.get("text_sha256")
    child_text_hash = child.value.get("child_text_sha256")
    if (
        not isinstance(corpus_text_hash, str)
        or SHA256_PATTERN.fullmatch(corpus_text_hash) is None
        or corpus_text_hash != child_text_hash
    ):
        errors.append(
            _error(
                "CORPUS_CHILD_TEXT_SHA256_MISMATCH",
                SOURCE_CORPUS,
                corpus.line,
                related_source=SOURCE_CHILDREN,
                related_line=child.line,
            )
        )
        valid = False

    if corpus.value.get("source_record_id") != child.value.get("child_id"):
        errors.append(
            _error(
                "CORPUS_CHILD_LINK_MISMATCH",
                SOURCE_CORPUS,
                corpus.line,
                related_source=SOURCE_CHILDREN,
                related_line=child.line,
            )
        )
        valid = False
    if corpus.value.get("exact_sales_code") != group.value.get("exact_sales_code"):
        valid = False
    return valid


def build_compatibility_report(
    gold_path: Path,
    evidence_groups_path: Path,
    children_path: Path,
    corpus_path: Path,
) -> dict[str, Any]:
    """Return a structural compatibility report for the four JSONL inputs."""

    gold_rows, gold_errors = _load_jsonl(gold_path, SOURCE_GOLD)
    group_rows, group_errors = _load_jsonl(evidence_groups_path, SOURCE_GROUPS)
    child_rows, child_errors = _load_jsonl(children_path, SOURCE_CHILDREN)
    corpus_rows, corpus_errors = _load_jsonl(corpus_path, SOURCE_CORPUS)
    errors = [*gold_errors, *group_errors, *child_errors, *corpus_errors]

    _validate_evidence_group_schema(group_rows, errors)

    _index_unique(
        gold_rows,
        "case_id",
        SOURCE_GOLD,
        "GOLD_CASE_ID_MISSING",
        "DUPLICATE_GOLD_CASE_ID",
        errors,
    )
    groups_by_id = _index_unique(
        group_rows,
        "evidence_group_id",
        SOURCE_GROUPS,
        "EVIDENCE_GROUP_ID_MISSING",
        "DUPLICATE_EVIDENCE_GROUP_ID",
        errors,
    )
    children_by_id = _index_unique(
        child_rows,
        "child_id",
        SOURCE_CHILDREN,
        "CHILD_ID_MISSING",
        "DUPLICATE_CHILD_ID",
        errors,
    )
    _index_unique(
        corpus_rows,
        "chunk_id",
        SOURCE_CORPUS,
        "CORPUS_CHUNK_ID_MISSING",
        "DUPLICATE_CORPUS_CHUNK_ID",
        errors,
    )
    corpus_by_source_record = _index_unique(
        corpus_rows,
        "source_record_id",
        SOURCE_CORPUS,
        "CORPUS_SOURCE_RECORD_ID_MISSING",
        "DUPLICATE_CORPUS_SOURCE_RECORD_ID",
        errors,
    )

    active_cases = 0
    active_evidence_cases = 0
    active_no_evidence_cases = 0
    required_references: dict[str, list[tuple[JsonlRow, str]]] = defaultdict(list)
    supporting_references: dict[str, list[tuple[JsonlRow, str]]] = defaultdict(list)
    condition_references: list[tuple[JsonlRow, set[str], str]] = []

    for case in gold_rows:
        status = case.value.get("evaluation_status")
        if status in {"EXCLUDED", "REJECTED"}:
            continue
        if status != "ACTIVE":
            errors.append(_error("GOLD_EVALUATION_STATUS_INVALID", SOURCE_GOLD, case.line))
            continue

        active_cases += 1
        product = case.value.get("product_model_code")
        if not isinstance(product, str) or not product:
            errors.append(_error("GOLD_PRODUCT_MODEL_CODE_INVALID", SOURCE_GOLD, case.line))
            product = ""

        required = _string_list(
            case,
            "required_evidence_group_ids",
            SOURCE_GOLD,
            errors,
            "GOLD_REQUIRED_GROUP_IDS_INVALID",
            "GOLD_REQUIRED_GROUP_ID_DUPLICATE",
        )
        supporting = _string_list(
            case,
            "supporting_evidence_group_ids",
            SOURCE_GOLD,
            errors,
            "GOLD_SUPPORTING_GROUP_IDS_INVALID",
            "GOLD_SUPPORTING_GROUP_ID_DUPLICATE",
        )
        if set(required).intersection(supporting):
            errors.append(_error("GOLD_REQUIRED_SUPPORTING_OVERLAP", SOURCE_GOLD, case.line))
        condition_ids = (
            _string_list(
                case,
                "consultation_condition_ids",
                SOURCE_GOLD,
                errors,
                "GOLD_CONDITION_IDS_INVALID",
                "GOLD_CONDITION_ID_DUPLICATE",
            )
            if "consultation_condition_ids" in case.value
            else []
        )
        for condition_id in condition_ids:
            condition_references.append(
                (case, set(required).union(supporting), condition_id)
            )

        outcome = case.value.get("expected_retrieval_outcome")
        execution_path = case.value.get("expected_execution_path")
        match_policy = case.value.get("evidence_match_policy")
        if outcome == "EVIDENCE":
            active_evidence_cases += 1
            if execution_path != "PGVECTOR_QUERY":
                errors.append(
                    _error(
                        "GOLD_EVIDENCE_EXECUTION_PATH_INVALID",
                        SOURCE_GOLD,
                        case.line,
                    )
                )
            if match_policy not in {"ANY", "ALL"}:
                errors.append(_error("GOLD_EVIDENCE_MATCH_POLICY_INVALID", SOURCE_GOLD, case.line))
            if not required:
                code = (
                    "GOLD_SUPPORTING_ONLY_POSITIVE"
                    if supporting
                    else "GOLD_POSITIVE_REQUIRED_GROUP_MISSING"
                )
                errors.append(_error(code, SOURCE_GOLD, case.line))
            for group_id in required:
                required_references[group_id].append((case, product))
            for group_id in supporting:
                supporting_references[group_id].append((case, product))
        elif outcome == "NO_EVIDENCE":
            active_no_evidence_cases += 1
            if required or supporting:
                errors.append(_error("GOLD_NO_EVIDENCE_GROUPS_NOT_EMPTY", SOURCE_GOLD, case.line))
            if match_policy != "NONE":
                errors.append(
                    _error(
                        "GOLD_NO_EVIDENCE_MATCH_POLICY_INVALID",
                        SOURCE_GOLD,
                        case.line,
                    )
                )
            if (
                execution_path != "PGVECTOR_QUERY"
                and execution_path not in ALLOWED_POLICY_BLOCK_PATHS
            ):
                errors.append(
                    _error(
                        "GOLD_NO_EVIDENCE_EXECUTION_PATH_INVALID",
                        SOURCE_GOLD,
                        case.line,
                    )
                )
        else:
            errors.append(_error("GOLD_RETRIEVAL_OUTCOME_INVALID", SOURCE_GOLD, case.line))

    group_children: dict[str, list[JsonlRow]] = {}
    condition_owner_by_id: dict[str, str] = {}
    # Registry 입력 전체를 검사해야 Gold에 아직 편입되지 않은 Candidate Group도
    # Data QA 단계에서 Child·Corpus 누락을 숨기지 않는다.
    for group_id in sorted(groups_by_id):
        references = [
            *required_references.get(group_id, []),
            *supporting_references.get(group_id, []),
        ]
        group = groups_by_id.get(group_id)
        if group is None:
            for case, _product in references:
                errors.append(
                    _error(
                        "GOLD_EVIDENCE_GROUP_NOT_FOUND",
                        SOURCE_GOLD,
                        case.line,
                    )
                )
            continue

        for case, product in references:
            if group.value.get("exact_sales_code") != product:
                errors.append(
                    _error(
                        "GOLD_GROUP_PRODUCT_MISMATCH",
                        SOURCE_GOLD,
                        case.line,
                        related_source=SOURCE_GROUPS,
                        related_line=group.line,
                    )
                )
            forbidden_documents = {
                value
                for value in case.value.get("forbidden_document_ids", [])
                if isinstance(value, str)
            }
            forbidden_models = {
                value
                for value in case.value.get("forbidden_model_codes", [])
                if isinstance(value, str)
            }
            if group.value.get("document_id") in forbidden_documents:
                errors.append(
                    _error(
                        "GOLD_GROUP_DOCUMENT_FORBIDDEN",
                        SOURCE_GOLD,
                        case.line,
                        related_source=SOURCE_GROUPS,
                        related_line=group.line,
                    )
                )
            if group.value.get("exact_sales_code") in forbidden_models:
                errors.append(
                    _error(
                        "GOLD_GROUP_MODEL_FORBIDDEN",
                        SOURCE_GOLD,
                        case.line,
                        related_source=SOURCE_GROUPS,
                        related_line=group.line,
                    )
                )

        child_ids = _string_list(
            group,
            "child_ids",
            SOURCE_GROUPS,
            errors,
            "GROUP_CHILD_IDS_INVALID",
            "GROUP_CHILD_ID_DUPLICATE",
        )
        source_variant_ids = _string_list(
            group,
            "source_variant_ids",
            SOURCE_GROUPS,
            errors,
            "GROUP_SOURCE_VARIANT_IDS_INVALID",
            "GROUP_SOURCE_VARIANT_ID_DUPLICATE",
        )
        if not child_ids:
            errors.append(_error("GROUP_CHILD_IDS_EMPTY", SOURCE_GROUPS, group.line))
        if not source_variant_ids:
            errors.append(_error("GROUP_SOURCE_VARIANT_IDS_EMPTY", SOURCE_GROUPS, group.line))
        if len(child_ids) != len(source_variant_ids):
            errors.append(
                _error(
                    "GROUP_CHILD_VARIANT_CARDINALITY_MISMATCH",
                    SOURCE_GROUPS,
                    group.line,
                )
            )

        conditions = group.value.get("consultation_conditions", [])
        if not isinstance(conditions, list):
            errors.append(
                _error("GROUP_CONSULTATION_CONDITIONS_INVALID", SOURCE_GROUPS, group.line)
            )
            conditions = []
        for condition in conditions:
            if not isinstance(condition, dict):
                errors.append(
                    _error("GROUP_CONSULTATION_CONDITION_INVALID", SOURCE_GROUPS, group.line)
                )
                continue
            condition_id = condition.get("condition_id")
            if not isinstance(condition_id, str) or not condition_id:
                errors.append(
                    _error("GROUP_CONDITION_ID_INVALID", SOURCE_GROUPS, group.line)
                )
                continue
            if condition_id in condition_owner_by_id:
                errors.append(
                    _error("DUPLICATE_GROUP_CONDITION_ID", SOURCE_GROUPS, group.line)
                )
            else:
                condition_owner_by_id[condition_id] = group_id
            source_child_ids = condition.get("source_child_ids")
            source_page_refs = condition.get("source_page_refs")
            source_child_ids_valid = not (
                not isinstance(source_child_ids, list)
                or not source_child_ids
                or any(
                    not isinstance(value, str) or not value
                    for value in source_child_ids
                )
                or not set(source_child_ids).issubset(set(child_ids))
            )
            if not source_child_ids_valid:
                errors.append(
                    _error("GROUP_CONDITION_CHILD_LINEAGE_INVALID", SOURCE_GROUPS, group.line)
                )

            selected_child_pages: set[int] = set()
            if source_child_ids_valid:
                for source_child_id in source_child_ids:
                    source_child = children_by_id.get(source_child_id)
                    child_pages = (
                        source_child.value.get("page_refs")
                        if source_child is not None
                        else None
                    )
                    if not isinstance(child_pages, list) or any(
                        not isinstance(value, int) or value < 1
                        for value in child_pages
                    ):
                        source_child_ids_valid = False
                        break
                    selected_child_pages.update(child_pages)

            if (
                not isinstance(source_page_refs, list)
                or not source_page_refs
                or any(
                    not isinstance(value, int) or value < 1
                    for value in source_page_refs
                )
                or not set(source_page_refs).issubset(set(group.value.get("page_refs", [])))
                or not source_child_ids_valid
                or not set(source_page_refs).issubset(selected_child_pages)
            ):
                errors.append(
                    _error("GROUP_CONDITION_PAGE_LINEAGE_INVALID", SOURCE_GROUPS, group.line)
                )

        declared_children: list[JsonlRow] = []
        for child_id in child_ids:
            child = children_by_id.get(child_id)
            if child is None:
                errors.append(_error("GROUP_CHILD_NOT_FOUND", SOURCE_GROUPS, group.line))
                continue
            declared_children.append(child)
            _child_matches_group(group, child, group_id, errors)
            if child.value.get("source_variant_id") not in source_variant_ids:
                errors.append(
                    _error(
                        "CHILD_SOURCE_VARIANT_LINEAGE_MISMATCH",
                        SOURCE_CHILDREN,
                        child.line,
                        related_source=SOURCE_GROUPS,
                        related_line=group.line,
                    )
                )

        declared_variants = [
            child.value.get("source_variant_id")
            for child in declared_children
            if isinstance(child.value.get("source_variant_id"), str)
        ]
        if Counter(declared_variants) != Counter(source_variant_ids):
            errors.append(
                _error(
                    "GROUP_CHILD_SOURCE_VARIANT_COVERAGE_MISMATCH",
                    SOURCE_GROUPS,
                    group.line,
                )
            )

        declared_child_ids = set(child_ids)
        for child in child_rows:
            if (
                child.value.get("evidence_group_id") == group_id
                and child.value.get("child_id") not in declared_child_ids
            ):
                errors.append(
                    _error(
                        "GROUP_UNDECLARED_CHILD_REFERENCE",
                        SOURCE_CHILDREN,
                        child.line,
                        related_source=SOURCE_GROUPS,
                        related_line=group.line,
                    )
                )
        group_children[group_id] = declared_children

    for child in child_rows:
        group_id = child.value.get("evidence_group_id")
        if not isinstance(group_id, str) or group_id not in groups_by_id:
            errors.append(_error("CHILD_GROUP_NOT_FOUND", SOURCE_CHILDREN, child.line))

    for case, case_group_ids, condition_id in condition_references:
        owner_group_id = condition_owner_by_id.get(condition_id)
        if owner_group_id is None:
            errors.append(_error("GOLD_CONDITION_NOT_FOUND", SOURCE_GOLD, case.line))
        elif owner_group_id not in case_group_ids:
            errors.append(
                _error("GOLD_CONDITION_GROUP_NOT_REFERENCED", SOURCE_GOLD, case.line)
            )

    for corpus in corpus_rows:
        attached_registered_groups = _group_ids_attached(corpus.value).intersection(
            groups_by_id
        )
        if not attached_registered_groups:
            continue
        source_record_id = corpus.value.get("source_record_id")
        child = (
            children_by_id.get(source_record_id)
            if isinstance(source_record_id, str)
            else None
        )
        for group_id in sorted(attached_registered_groups):
            if child is None or child.value.get("evidence_group_id") != group_id:
                errors.append(
                    _error(
                        "CORPUS_GROUP_ATTACHED_TO_UNREGISTERED_CHILD",
                        SOURCE_CORPUS,
                        corpus.line,
                    )
                )

    valid_candidate_by_group: dict[str, bool] = {}
    linked_group_children = 0
    for group_id, declared_children in sorted(group_children.items()):
        group = groups_by_id[group_id]
        group_has_valid_candidate = False
        for child in declared_children:
            child_id = child.value.get("child_id")
            corpus = (
                corpus_by_source_record.get(child_id)
                if isinstance(child_id, str)
                else None
            )
            if corpus is None:
                errors.append(
                    _error(
                        "GROUP_CHILD_CORPUS_LINK_MISSING",
                        SOURCE_CHILDREN,
                        child.line,
                        related_source=SOURCE_GROUPS,
                        related_line=group.line,
                    )
                )
                continue
            if _corpus_matches_child(corpus, child, group, group_id, errors):
                linked_group_children += 1
                group_has_valid_candidate = True
        valid_candidate_by_group[group_id] = group_has_valid_candidate

    linked_required_groups = 0
    for group_id in sorted(required_references):
        group = groups_by_id.get(group_id)
        if group is None:
            continue
        if valid_candidate_by_group.get(group_id, False):
            linked_required_groups += 1
        else:
            errors.append(
                _error(
                    "REQUIRED_GROUP_SEARCH_CANDIDATE_MISSING",
                    SOURCE_GROUPS,
                    group.line,
                )
            )

    linked_supporting_groups = 0
    for group_id in sorted(supporting_references):
        group = groups_by_id.get(group_id)
        if group is None:
            continue
        if valid_candidate_by_group.get(group_id, False):
            linked_supporting_groups += 1
        else:
            errors.append(
                _error(
                    "SUPPORTING_GROUP_SEARCH_CANDIDATE_MISSING",
                    SOURCE_GROUPS,
                    group.line,
                )
            )

    error_code_counts = dict(sorted(Counter(error["code"] for error in errors).items()))
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "FAIL" if errors else "PASS",
        "counts": {
            "gold_rows": len(gold_rows),
            "evidence_group_rows": len(group_rows),
            "child_rows": len(child_rows),
            "corpus_rows": len(corpus_rows),
            "active_cases": active_cases,
            "active_evidence_cases": active_evidence_cases,
            "active_no_evidence_cases": active_no_evidence_cases,
            "referenced_required_groups": len(required_references),
            "referenced_supporting_groups": len(supporting_references),
            "linked_required_groups": linked_required_groups,
            "linked_supporting_groups": linked_supporting_groups,
            "linked_evidence_groups": sum(valid_candidate_by_group.values()),
            "linked_group_children": linked_group_children,
            "referenced_conditions": len(condition_references),
            "registered_conditions": len(condition_owner_by_id),
            "errors": len(errors),
        },
        "error_code_counts": error_code_counts,
        "errors": errors,
    }


def _resolve_input(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gold v2와 Evidence Group·Child·Corpus 연결 계약 검증"
    )
    parser.add_argument("--gold", required=True)
    parser.add_argument("--evidence-groups", required=True)
    parser.add_argument("--children", required=True)
    parser.add_argument("--corpus", required=True)
    args = parser.parse_args()

    report = build_compatibility_report(
        _resolve_input(args.gold),
        _resolve_input(args.evidence_groups),
        _resolve_input(args.children),
        _resolve_input(args.corpus),
    )
    # CLI에는 원문, 식별자, 경로 또는 Secret 값을 출력하지 않는다.
    print(
        json.dumps(
            {
                "status": report["status"],
                "counts": report["counts"],
                "error_code_counts": report["error_code_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(1 if report["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
