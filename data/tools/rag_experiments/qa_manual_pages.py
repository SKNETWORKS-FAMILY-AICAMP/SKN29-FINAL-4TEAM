"""JAC104/JCC104 전체 페이지 JSONL의 A1-1 최소 QA를 수행한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET = (
    "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl"
)
DEFAULT_SCHEMA = "data/schemas/processed/manualPage.schema.json"
DEFAULT_OUTPUT = (
    "data/processed/validation/rag_experiments/"
    "jac104_manual_pages_qa.json"
)

EXPECTED_INVARIANTS = {
    "document_id": "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00",
    "source_type": "official_manual",
    "provider": "SK매직",
    "exact_sales_code": "WPUJAC104DWH",
    "product_model": "WPU-JAC104 (D) / WPU-JCC104 (D)",
    "model_family": "WPU-JAC104",
    "product_generation": "D",
    "scope_role": "mvp",
    "version": "REV.00",
    "page_count": 44,
}

ALLOWED_STATUS_COMBINATIONS = {
    ("pdfplumber_text", "EXTRACTED_TEXT", "TEXT_EXTRACTED"),
    ("pdfplumber_text", "EXTRACTED_TEXT", "TEXT_AND_VISUAL_VERIFIED"),
    (
        "manual_visual_transcription",
        "VISUAL_TEXT_TRANSCRIBED",
        "VISUALLY_REVIEWED",
    ),
    (
        "manual_visual_transcription",
        "VISUAL_TEXT_TRANSCRIBED",
        "TEXT_AND_VISUAL_VERIFIED",
    ),
}

MOJIBAKE_MARKERS = ("\ufffd", "Ã", "Â", "ì", "ë", "í")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _resolve_repo_path(relative_path: str) -> Path:
    path = (REPOSITORY_ROOT / relative_path).resolve()
    path.relative_to(REPOSITORY_ROOT.resolve())
    return path


def _issue(code: str, message: str, *, page: int | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "message": message}
    if page is not None:
        value["page"] = page
    return value


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                errors.append(_issue("BLANK_JSONL_LINE", f"빈 JSONL 행: {line_number}"))
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                errors.append(
                    _issue(
                        "INVALID_JSON",
                        f"{line_number}행 JSON 파싱 실패: {error.msg}",
                    )
                )
                continue
            if not isinstance(row, dict):
                errors.append(_issue("ROW_NOT_OBJECT", f"{line_number}행이 객체가 아님"))
                continue
            rows.append(row)
    return rows, errors


def _matches_type(value: Any, expected_type: str | list[str]) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return True


def _valid_format(value: str, format_name: str) -> bool:
    if format_name == "uri":
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    if format_name == "date-time":
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
    return True


def _validate_schema(
    rows: list[dict[str, Any]], schema: dict[str, Any]
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    required = set(schema["required"])
    properties = schema["properties"]
    for row in rows:
        page = row.get("page") if isinstance(row.get("page"), int) else None
        missing = sorted(required.difference(row))
        extra = sorted(set(row).difference(properties))
        if missing:
            errors.append(_issue("SCHEMA_REQUIRED", f"필수 필드 누락: {missing}", page=page))
        if schema.get("additionalProperties") is False and extra:
            errors.append(_issue("SCHEMA_EXTRA", f"허용되지 않은 필드: {extra}", page=page))
        for field, rule in properties.items():
            if field not in row:
                continue
            value = row[field]
            expected_type = rule.get("type")
            if expected_type and not _matches_type(value, expected_type):
                errors.append(
                    _issue(
                        "SCHEMA_TYPE",
                        f"{field} 타입 불일치: expected={expected_type}",
                        page=page,
                    )
                )
                continue
            if isinstance(value, str):
                if len(value) < rule.get("minLength", 0):
                    errors.append(_issue("SCHEMA_LENGTH", f"{field}가 비어 있음", page=page))
                if "pattern" in rule and re.fullmatch(rule["pattern"], value) is None:
                    errors.append(_issue("SCHEMA_PATTERN", f"{field} 형식 불일치", page=page))
                if "format" in rule and not _valid_format(value, rule["format"]):
                    errors.append(_issue("SCHEMA_FORMAT", f"{field} 형식 불일치", page=page))
            if "enum" in rule and value not in rule["enum"]:
                errors.append(_issue("SCHEMA_ENUM", f"{field} 허용값 불일치", page=page))
            if "const" in rule and value != rule["const"]:
                errors.append(_issue("SCHEMA_CONST", f"{field} 고정값 불일치", page=page))
            if isinstance(value, int) and value < rule.get("minimum", value):
                errors.append(_issue("SCHEMA_MINIMUM", f"{field} 최솟값 위반", page=page))
    return errors


def _source_zip_verification(
    source_zip: Path | None,
    source_entry: str | None,
    recorded_hash: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if source_zip is None:
        return {"status": "NOT_PROVIDED"}, []
    if not source_entry:
        raise ValueError("--source-zip 사용 시 --source-entry가 필요합니다.")
    with zipfile.ZipFile(source_zip) as archive:
        try:
            info = archive.getinfo(source_entry)
        except KeyError:
            return (
                {"status": "ENTRY_NOT_FOUND", "archive_name": source_zip.name},
                [_issue("SOURCE_ENTRY_NOT_FOUND", source_entry)],
            )
        digest = hashlib.sha256()
        with archive.open(info) as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        actual_hash = digest.hexdigest().upper()
    matched = actual_hash == recorded_hash
    verification = {
        "status": "VERIFIED" if matched else "HASH_MISMATCH",
        "archive_name": source_zip.name,
        "entry_name": source_entry,
        "entry_bytes": info.file_size,
        "sha256": actual_hash,
        "recorded_sha256": recorded_hash,
        "matched": matched,
    }
    errors = [] if matched else [_issue("SOURCE_HASH_MISMATCH", "원본 PDF Hash 불일치")]
    return verification, errors


def build_qa_report(
    dataset_path: Path,
    schema_path: Path,
    *,
    source_zip: Path | None = None,
    source_entry: str | None = None,
) -> dict[str, Any]:
    rows, errors = _load_jsonl(dataset_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors.extend(_validate_schema(rows, schema))

    warnings: list[dict[str, Any]] = []
    pages = [row.get("page") for row in rows if isinstance(row.get("page"), int)]
    expected_pages = list(range(1, EXPECTED_INVARIANTS["page_count"] + 1))
    duplicate_pages = sorted(page for page, count in Counter(pages).items() if count > 1)
    missing_pages = sorted(set(expected_pages).difference(pages))
    unexpected_pages = sorted(set(pages).difference(expected_pages))
    if duplicate_pages:
        errors.append(_issue("DUPLICATE_PAGE", f"중복 페이지: {duplicate_pages}"))
    if missing_pages:
        errors.append(_issue("MISSING_PAGE", f"누락 페이지: {missing_pages}"))
    if unexpected_pages:
        errors.append(_issue("UNEXPECTED_PAGE", f"범위 밖 페이지: {unexpected_pages}"))

    page_ids = [row.get("page_id") for row in rows]
    duplicate_page_ids = sorted(
        page_id for page_id, count in Counter(page_ids).items() if count > 1
    )
    if duplicate_page_ids:
        errors.append(_issue("DUPLICATE_PAGE_ID", f"중복 page_id: {duplicate_page_ids}"))

    invariant_values: dict[str, list[Any]] = {}
    for field, expected in EXPECTED_INVARIANTS.items():
        values = sorted({row.get(field) for row in rows}, key=str)
        invariant_values[field] = values
        if values != [expected]:
            errors.append(
                _issue(
                    "INVARIANT_MISMATCH",
                    f"{field}: expected={expected!r}, actual={values!r}",
                )
            )

    text_hash_mismatch_pages: list[int] = []
    mojibake_pages: list[int] = []
    control_character_pages: list[int] = []
    page_id_mismatch_pages: list[int] = []
    invalid_status_pages: list[int] = []
    normalized_text_pages: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        page = row.get("page")
        text = row.get("text", "")
        expected_page_id = f"{row.get('document_id')}-P{page:03d}" if isinstance(page, int) else None
        if row.get("page_id") != expected_page_id and isinstance(page, int):
            page_id_mismatch_pages.append(page)
        if isinstance(text, str):
            actual_text_hash = _sha256_bytes(text.encode("utf-8"))
            if actual_text_hash != row.get("text_sha256") and isinstance(page, int):
                text_hash_mismatch_pages.append(page)
            if any(marker in text for marker in MOJIBAKE_MARKERS) and isinstance(page, int):
                mojibake_pages.append(page)
            if any(ord(char) < 32 and char not in "\n\r\t" for char in text) and isinstance(page, int):
                control_character_pages.append(page)
            normalized = " ".join(text.split())
            normalized_text_pages[_sha256_bytes(normalized.encode("utf-8"))].append(page)
        combination = (
            row.get("extraction_method"),
            row.get("content_status"),
            row.get("verification_status"),
        )
        if combination not in ALLOWED_STATUS_COMBINATIONS and isinstance(page, int):
            invalid_status_pages.append(page)

    for code, affected, label in (
        ("PAGE_ID_MISMATCH", page_id_mismatch_pages, "page_id 불일치"),
        ("TEXT_HASH_MISMATCH", text_hash_mismatch_pages, "본문 Hash 불일치"),
        ("MOJIBAKE_DETECTED", mojibake_pages, "문자 깨짐 의심"),
        ("CONTROL_CHARACTER", control_character_pages, "제어문자 포함"),
        ("STATUS_COMBINATION", invalid_status_pages, "상태 조합 불일치"),
    ):
        if affected:
            errors.append(_issue(code, f"{label}: {sorted(affected)}"))

    duplicate_text_groups = sorted(
        sorted(group)
        for group in normalized_text_pages.values()
        if len(group) > 1
    )
    if duplicate_text_groups:
        errors.append(_issue("DUPLICATE_TEXT", f"중복 본문 페이지: {duplicate_text_groups}"))

    source_hashes = sorted({row.get("source_file_sha256") for row in rows})
    if len(source_hashes) != 1:
        errors.append(_issue("SOURCE_HASH_NOT_UNIFORM", f"원본 Hash 값: {source_hashes}"))
    recorded_source_hash = source_hashes[0] if len(source_hashes) == 1 else None
    source_verification, source_errors = _source_zip_verification(
        source_zip,
        source_entry,
        recorded_source_hash,
    )
    errors.extend(source_errors)

    status_counts = Counter(row.get("verification_status") for row in rows)
    pending_visual_pages = sorted(
        row["page"]
        for row in rows
        if row.get("verification_status") == "TEXT_EXTRACTED"
    )
    if pending_visual_pages:
        warnings.append(
            _issue(
                "VISUAL_REVIEW_PENDING",
                f"시각 검수 대기 {len(pending_visual_pages)}쪽",
            )
        )

    if errors:
        status = "FAIL"
    elif pending_visual_pages:
        status = "STRUCTURAL_PASS_VISUAL_REVIEW_PENDING"
    else:
        status = "PASS"

    return {
        "qa_id": "A1-1-JAC104-FULL-PAGE-QA",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "included": "JAC104/JCC104 기존 44페이지 JSONL",
            "excluded": ["IAC425", "FAQ", "Chunking", "Embedding", "Vector DB"],
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
        "source_binary_verification": source_verification,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "pages_expected": len(expected_pages),
            "pages_found": len(pages),
            "unique_pages": len(set(pages)),
            "unique_page_ids": len(set(page_ids)),
            "missing_pages": missing_pages,
            "duplicate_pages": duplicate_pages,
            "duplicate_text_groups": duplicate_text_groups,
            "blank_text_pages": sorted(
                row["page"] for row in rows if not str(row.get("text", "")).strip()
            ),
            "text_hash_mismatch_pages": sorted(text_hash_mismatch_pages),
            "mojibake_pages": sorted(mojibake_pages),
            "visual_review_pending_count": len(pending_visual_pages),
        },
        "verification_coverage": {
            "status_counts": dict(sorted(status_counts.items())),
            "visual_review_pending_pages": pending_visual_pages,
            "experiment_text_ready_pages": sorted(pages) if not errors else [],
            "production_or_gold_approval_not_inferred": True,
        },
        "metadata_invariants": invariant_values,
        "errors": errors,
        "warnings": warnings,
        "decision": {
            "experimental_corpus_text_use": "READY" if not errors else "BLOCKED",
            "gold_evidence_use": "REVIEW_REQUIRED" if pending_visual_pages else "READY",
            "production_corpus_expansion": "NOT_AUTHORIZED",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A1-1 JAC104 44페이지 최소 QA")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--source-zip")
    parser.add_argument("--source-entry")
    args = parser.parse_args()

    dataset_path = _resolve_repo_path(args.dataset)
    schema_path = _resolve_repo_path(args.schema)
    output_path = _resolve_repo_path(args.output)
    source_zip = Path(args.source_zip).resolve() if args.source_zip else None
    report = build_qa_report(
        dataset_path,
        schema_path,
        source_zip=source_zip,
        source_entry=args.source_entry,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "output": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
        **report["summary"],
        "source_binary": report["source_binary_verification"]["status"],
    }, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
