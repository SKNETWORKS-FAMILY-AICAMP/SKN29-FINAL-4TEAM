#!/usr/bin/env python3
"""Gold Evaluation Dataset v2의 Schema와 평가 의미 계약을 검증한다.

이 검증기는 Gold Case 자체의 의미 계약만 확인한다. Evidence Group Registry와
Corpus Child의 실제 연결은 별도 Gold-Corpus 호환성 검증기의 책임이다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = "ai/evaluation/datasets/gold/rag_gold_v2.jsonl"
DEFAULT_SCHEMA = "ai/evaluation/schemas/gold_evaluation_case_v2.schema.json"
SCHEMA_VERSION = "2.0.0-draft.1"
DATASET_VERSION = "2.0.0-draft.1"
POLICY_BLOCK_PATHS = {
    "POLICY_BLOCK_PRODUCT_MISMATCH",
    "POLICY_BLOCK_UNSUPPORTED_MODEL",
    "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
    "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
    "POLICY_BLOCK_UNVERIFIED_SOURCE",
}
IMMEDIATE_CONSULTATION_BASIS_CODES = {
    "SOURCE_CONDITION_MET",
    "DANGER_SAFETY",
    "NO_EVIDENCE",
    "POLICY_BLOCK",
}


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


def _append_logic_error(
    errors: list[dict[str, Any]],
    case_id: Any,
    code: str,
    message: str,
) -> None:
    errors.append({"case_id": case_id, "code": code, "message": message})


def validate_case_logic(row: dict[str, Any]) -> list[dict[str, Any]]:
    """JSON Schema만으로 설명하기 어려운 Case 간 필드 관계를 검사한다."""

    errors: list[dict[str, Any]] = []
    case_id = row.get("case_id")
    outcome = row.get("expected_retrieval_outcome")
    execution_path = row.get("expected_execution_path")
    required = row.get("required_evidence_group_ids", [])
    supporting = row.get("supporting_evidence_group_ids", [])
    match_policy = row.get("evidence_match_policy")

    if set(required).intersection(supporting):
        _append_logic_error(
            errors,
            case_id,
            "EVIDENCE_GROUP_ROLE_OVERLAP",
            "Required와 Supporting Evidence Group은 중복될 수 없음",
        )

    if outcome == "EVIDENCE":
        if execution_path != "PGVECTOR_QUERY":
            _append_logic_error(
                errors,
                case_id,
                "EVIDENCE_REQUIRES_QUERY_PATH",
                "EVIDENCE 결과는 PGVECTOR_QUERY 실행 경로만 허용",
            )
        if not required:
            _append_logic_error(
                errors,
                case_id,
                "EVIDENCE_REQUIRES_REQUIRED_GROUP",
                "EVIDENCE 결과에는 Required Evidence Group이 1개 이상 필요",
            )
        if match_policy not in {"ANY", "ALL"}:
            _append_logic_error(
                errors,
                case_id,
                "EVIDENCE_REQUIRES_ANY_OR_ALL",
                "EVIDENCE 결과의 Match Policy는 ANY 또는 ALL이어야 함",
            )

    if outcome == "NO_EVIDENCE":
        if required or supporting:
            _append_logic_error(
                errors,
                case_id,
                "NO_EVIDENCE_REQUIRES_EMPTY_GROUPS",
                "NO_EVIDENCE 결과에는 Required와 Supporting Group을 둘 수 없음",
            )
        if match_policy != "NONE":
            _append_logic_error(
                errors,
                case_id,
                "NO_EVIDENCE_REQUIRES_NONE",
                "NO_EVIDENCE 결과의 Match Policy는 NONE이어야 함",
            )

    if match_policy == "NONE":
        if outcome != "NO_EVIDENCE":
            _append_logic_error(
                errors,
                case_id,
                "NONE_REQUIRES_NO_EVIDENCE",
                "NONE Match Policy는 NO_EVIDENCE 결과에만 사용",
            )
        if required or supporting:
            _append_logic_error(
                errors,
                case_id,
                "NONE_REQUIRES_EMPTY_GROUPS",
                "NONE Match Policy에서는 Evidence Group 배열이 비어 있어야 함",
            )

    if execution_path in POLICY_BLOCK_PATHS and outcome != "NO_EVIDENCE":
        _append_logic_error(
            errors,
            case_id,
            "POLICY_BLOCK_REQUIRES_NO_EVIDENCE",
            "Policy Block 실행 경로는 NO_EVIDENCE 결과여야 함",
        )

    risk = row.get("expected_risk_level")
    usage = row.get("expected_usage_guidance_status")
    consultation = row.get("expected_consultation_requirement")
    basis_codes = row.get("consultation_basis_codes", [])
    basis_set = set(basis_codes)
    condition_ids = row.get("consultation_condition_ids", [])
    has_source_condition_basis = bool(
        basis_set.intersection({"SOURCE_CONDITION_PENDING", "SOURCE_CONDITION_MET"})
    )

    if has_source_condition_basis and not condition_ids:
        _append_logic_error(
            errors,
            case_id,
            "SOURCE_CONDITION_REFERENCE_REQUIRED",
            "Source 조건 상담 근거에는 consultation_condition_ids가 필요",
        )
    if not has_source_condition_basis and condition_ids:
        _append_logic_error(
            errors,
            case_id,
            "CONDITION_REFERENCE_WITHOUT_SOURCE_BASIS",
            "Source 조건 근거가 없으면 consultation_condition_ids는 비어 있어야 함",
        )

    if "NONE" in basis_set:
        if basis_set != {"NONE"} or len(basis_codes) != 1:
            _append_logic_error(
                errors,
                case_id,
                "NONE_BASIS_MUST_BE_EXCLUSIVE",
                "NONE 상담 근거는 다른 코드와 공존할 수 없음",
            )
        if consultation != "NONE":
            _append_logic_error(
                errors,
                case_id,
                "NONE_BASIS_REQUIRES_NONE",
                "상담 근거 [NONE]은 상담 필요도 NONE을 요구",
            )

    if "SOURCE_CONDITION_PENDING" in basis_set:
        if basis_set != {"SOURCE_CONDITION_PENDING"} or len(basis_codes) != 1:
            _append_logic_error(
                errors,
                case_id,
                "PENDING_BASIS_MUST_BE_EXCLUSIVE",
                "SOURCE_CONDITION_PENDING은 즉시 상담 근거와 공존할 수 없음",
            )
        if consultation != "CONDITIONAL":
            _append_logic_error(
                errors,
                case_id,
                "PENDING_BASIS_REQUIRES_CONDITIONAL",
                "SOURCE_CONDITION_PENDING은 상담 필요도 CONDITIONAL을 요구",
            )

    if basis_set.intersection(IMMEDIATE_CONSULTATION_BASIS_CODES) and (
        consultation != "REQUIRED"
    ):
        _append_logic_error(
            errors,
            case_id,
            "IMMEDIATE_BASIS_REQUIRES_REQUIRED",
            "즉시 상담 근거는 상담 필요도 REQUIRED를 요구",
        )

    if outcome == "NO_EVIDENCE" and not basis_set.intersection({
        "NO_EVIDENCE", "POLICY_BLOCK",
    }):
        _append_logic_error(
            errors,
            case_id,
            "NO_EVIDENCE_REQUIRES_BASIS",
            "NO_EVIDENCE 결과에는 NO_EVIDENCE 또는 POLICY_BLOCK 근거가 필요",
        )
    if outcome == "NO_EVIDENCE" and execution_path == "PGVECTOR_QUERY":
        if "NO_EVIDENCE" not in basis_set or "POLICY_BLOCK" in basis_set:
            _append_logic_error(
                errors,
                case_id,
                "CORPUS_ABSENCE_BASIS_MISMATCH",
                "PGVECTOR_QUERY 후 NO_EVIDENCE는 NO_EVIDENCE 근거만 사용",
            )
    if execution_path in POLICY_BLOCK_PATHS and "POLICY_BLOCK" not in basis_set:
        _append_logic_error(
            errors,
            case_id,
            "POLICY_BLOCK_REQUIRES_BASIS",
            "Policy Block 실행 경로에는 POLICY_BLOCK 상담 근거가 필요",
        )
    if execution_path in POLICY_BLOCK_PATHS and "NO_EVIDENCE" in basis_set:
        _append_logic_error(
            errors,
            case_id,
            "POLICY_BLOCK_CANNOT_USE_NO_EVIDENCE_BASIS",
            "검색 전 Policy Block에는 검색 후 근거 부재 코드를 함께 쓸 수 없음",
        )
    if "NO_EVIDENCE" in basis_set and (
        outcome != "NO_EVIDENCE" or execution_path != "PGVECTOR_QUERY"
    ):
        _append_logic_error(
            errors,
            case_id,
            "NO_EVIDENCE_BASIS_PATH_MISMATCH",
            "NO_EVIDENCE 근거는 PGVECTOR_QUERY 후 NO_EVIDENCE에만 사용",
        )
    if "POLICY_BLOCK" in basis_set and execution_path not in POLICY_BLOCK_PATHS:
        _append_logic_error(
            errors,
            case_id,
            "POLICY_BLOCK_BASIS_PATH_MISMATCH",
            "POLICY_BLOCK 근거는 POLICY_BLOCK_* 실행 경로에만 사용",
        )
    if basis_set.intersection({"SOURCE_CONDITION_PENDING", "SOURCE_CONDITION_MET"}) and (
        outcome != "EVIDENCE"
    ):
        _append_logic_error(
            errors,
            case_id,
            "SOURCE_CONDITION_REQUIRES_EVIDENCE",
            "Source 조건 상담 근거는 Evidence Group이 있는 EVIDENCE Case에만 사용",
        )

    if usage == "PENDING_CONSULTATION" and consultation != "REQUIRED":
        _append_logic_error(
            errors,
            case_id,
            "PENDING_CONSULTATION_REQUIRES_REQUIRED",
            "PENDING_CONSULTATION은 상담 필요도 REQUIRED를 요구",
        )
    if risk == "danger" and consultation != "REQUIRED":
        _append_logic_error(
            errors,
            case_id,
            "DANGER_REQUIRES_CONSULTATION",
            "danger 위험도는 상담 필요도 REQUIRED를 요구",
        )
    if usage == "TOTAL_STOP" and consultation != "REQUIRED":
        _append_logic_error(
            errors,
            case_id,
            "TOTAL_STOP_REQUIRES_CONSULTATION",
            "TOTAL_STOP은 상담 필요도 REQUIRED를 요구",
        )
    if (risk == "danger" or usage == "TOTAL_STOP") and "DANGER_SAFETY" not in basis_set:
        _append_logic_error(
            errors,
            case_id,
            "DANGER_REQUIRES_SAFETY_BASIS",
            "danger 또는 TOTAL_STOP에는 DANGER_SAFETY 상담 근거가 필요",
        )
    if risk == "danger" and usage not in {"PARTIAL_STOP", "TOTAL_STOP"}:
        _append_logic_error(
            errors,
            case_id,
            "DANGER_USAGE_STATUS_INVALID",
            "danger는 PARTIAL_STOP 또는 TOTAL_STOP 사용 상태만 허용",
        )
    if "DANGER_SAFETY" in basis_set and risk != "danger":
        _append_logic_error(
            errors,
            case_id,
            "DANGER_BASIS_REQUIRES_DANGER_RISK",
            "DANGER_SAFETY 상담 근거는 danger 위험도에만 사용",
        )
    if usage == "TOTAL_STOP" and risk != "danger":
        _append_logic_error(
            errors,
            case_id,
            "TOTAL_STOP_REQUIRES_DANGER_RISK",
            "TOTAL_STOP 사용 상태는 danger 위험도를 요구",
        )
    if row.get("product_model_code") in set(row.get("forbidden_model_codes", [])):
        _append_logic_error(
            errors,
            case_id,
            "TARGET_MODEL_FORBIDDEN",
            "평가 대상 제품을 forbidden_model_codes에 함께 둘 수 없음",
        )
    evaluation_status = row.get("evaluation_status")
    review_status = row.get("review_status")
    if evaluation_status == "ACTIVE" and review_status == "REJECTED":
        _append_logic_error(
            errors,
            case_id,
            "ACTIVE_CASE_CANNOT_BE_REJECTED",
            "ACTIVE Case의 review_status는 REJECTED일 수 없음",
        )
    if evaluation_status == "REJECTED" and review_status != "REJECTED":
        _append_logic_error(
            errors,
            case_id,
            "REJECTED_CASE_REVIEW_STATUS_MISMATCH",
            "REJECTED Case는 review_status도 REJECTED여야 함",
        )
    return errors


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def build_qa_report(dataset_path: Path, schema_path: Path) -> dict[str, Any]:
    rows, errors = _load_jsonl(dataset_path)
    warnings: list[dict[str, Any]] = []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    schema_valid_rows: list[dict[str, Any]] = []

    for line_number, row in enumerate(rows, start=1):
        schema_errors = sorted(
            validator.iter_errors(row),
            key=lambda item: list(item.path),
        )
        for error in schema_errors:
            errors.append({
                "code": "SCHEMA_VALIDATION_ERROR",
                "line": line_number,
                "case_id": row.get("case_id"),
                "path": "/".join(str(part) for part in error.path),
                "message": error.message,
            })
        if not schema_errors:
            schema_valid_rows.append(row)

    if not rows:
        errors.append({"code": "DATASET_EMPTY"})

    case_ids = [row.get("case_id") for row in rows]
    duplicate_case_ids = sorted(
        str(case_id)
        for case_id, count in Counter(case_ids).items()
        if count > 1
    )
    if duplicate_case_ids:
        errors.append({"code": "DUPLICATE_CASE_ID", "case_ids": duplicate_case_ids})

    normalized_model_queries = [
        (
            str(row.get("product_model_code", "")),
            " ".join(str(row.get("query", "")).split()),
        )
        for row in rows
    ]
    duplicate_model_queries = sorted(
        [
            {"product_model_code": model_code, "query": query}
            for (model_code, query), count in Counter(normalized_model_queries).items()
            if query and count > 1
        ],
        key=lambda item: (item["product_model_code"], item["query"]),
    )
    if duplicate_model_queries:
        errors.append({
            "code": "DUPLICATE_MODEL_QUERY",
            "items": duplicate_model_queries,
        })

    logical_policy_errors = [
        error
        for row in schema_valid_rows
        for error in validate_case_logic(row)
    ]
    if logical_policy_errors:
        errors.append({"code": "LOGICAL_POLICY_ERROR", "items": logical_policy_errors})

    known_sources = _source_case_ids()
    source_reference_errors: list[dict[str, Any]] = []
    review_policy_errors: list[dict[str, Any]] = []
    for row in schema_valid_rows:
        case_id = row.get("case_id")
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

    if source_reference_errors:
        errors.append({"code": "SOURCE_CASE_REFERENCE_ERROR", "items": source_reference_errors})
    if review_policy_errors:
        errors.append({"code": "REVIEW_POLICY_ERROR", "items": review_policy_errors})

    active_rows = [
        row for row in schema_valid_rows if row.get("evaluation_status") == "ACTIVE"
    ]
    approved_active_count = sum(
        row.get("review_status") == "TWO_PERSON_APPROVED" for row in active_rows
    )
    pending_active_count = len(active_rows) - approved_active_count
    if pending_active_count:
        warnings.append({
            "code": "HUMAN_REVIEW_PENDING",
            "pending_active_records": pending_active_count,
            "approved_active_records": approved_active_count,
            "message": "2인 검수 전 ACTIVE Case는 Draft 평가에만 사용",
        })

    if errors:
        status = "FAIL"
    elif pending_active_count:
        status = "STRUCTURAL_PASS_HUMAN_REVIEW_PENDING"
    else:
        status = "PASS"

    return {
        "qa_id": "GOLD-EVALUATION-V2-QA",
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "path": _display_path(dataset_path),
            "record_count": len(rows),
        },
        "schema": {"path": _display_path(schema_path)},
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "records_found": len(rows),
            "active_records": len(active_rows),
            "approved_active_records": approved_active_count,
            "review_pending_active_records": pending_active_count,
            "evaluation_status_counts": dict(sorted(Counter(
                str(row.get("evaluation_status", "<MISSING>")) for row in rows
            ).items())),
            "retrieval_outcome_counts": dict(sorted(Counter(
                str(row.get("expected_retrieval_outcome", "<MISSING>")) for row in rows
            ).items())),
            "execution_path_counts": dict(sorted(Counter(
                str(row.get("expected_execution_path", "<MISSING>")) for row in rows
            ).items())),
        },
        "errors": errors,
        "warnings": warnings,
        "decision": {
            "case_contract": "READY" if not errors else "BLOCKED",
            "gold_corpus_compatibility": "NOT_CHECKED_BY_THIS_VALIDATOR",
            "draft_evaluation_use": "READY" if not errors else "BLOCKED",
            "official_metric_use": (
                "READY" if not errors and pending_active_count == 0 else "BLOCKED"
            ),
            "automatic_label_approval": "PROHIBITED",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gold Evaluation Dataset v2 QA")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--output")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = REPOSITORY_ROOT / dataset_path
    schema_path = Path(args.schema)
    if not schema_path.is_absolute():
        schema_path = REPOSITORY_ROOT / schema_path

    report = build_qa_report(dataset_path.resolve(), schema_path.resolve())
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = REPOSITORY_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "gold_corpus_compatibility": report["decision"]["gold_corpus_compatibility"],
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
