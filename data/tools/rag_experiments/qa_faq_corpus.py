"""FAQ 119건 정규화 Dataset의 A1-3 최소 QA를 수행한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .qa_manual_pages import (
    MOJIBAKE_MARKERS,
    REPOSITORY_ROOT,
    _load_jsonl,
    _sha256_file,
    _validate_schema,
)


DEFAULT_DATASET = "data/processed/documents/faq/faq_snapshot_normalized.jsonl"
DEFAULT_SCHEMA = "data/schemas/processed/faqNormalized.schema.json"
DEFAULT_OUTPUT = "data/processed/validation/rag_experiments/faq_corpus_qa.json"
EXPECTED_SOURCE_SHA256 = (
    "670C739A69B3ACF811D763FF17F21C53EB661F7BAE1F7D505275B571FF4D3FF8"
)
SOURCE_LABEL = "external_backup/메뉴얼 원본, 크롤링 원본/Q&A 크롤링.md"
FAQ_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
IMAGE_URL = re.compile(r"!\[[^\]]*\]\((https?://[^)]+)\)")


def _canonical_text(value: str) -> str:
    return " ".join(value.replace("\u00a0", " ").split())


def parse_source_snapshot(source_path: Path) -> list[dict[str, Any]]:
    """원문 Markdown에서 번호·제목·게시자 본문·이미지 URL을 읽는다."""
    source = source_path.read_text(encoding="utf-8")
    matches = list(FAQ_HEADING.finditer(source))
    entries: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        block = source[match.end():block_end]
        answer_block = block.split("### 원문에 포함된 링크", 1)[0]
        image_urls = IMAGE_URL.findall(answer_block)
        answer_lines = [
            line.strip()
            for line in answer_block.splitlines()
            if line.strip()
            and not line.lstrip().startswith("![")
            and line.strip() != "---"
        ]
        entries.append({
            "ordinal": int(match.group(1)),
            "title": match.group(2).strip(),
            "answer_text": "\n".join(answer_lines),
            "image_urls": image_urls,
        })
    return entries


def build_qa_report(
    dataset_path: Path,
    schema_path: Path,
    source_path: Path | None = None,
) -> dict[str, Any]:
    rows, errors = _load_jsonl(dataset_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors.extend(_validate_schema(rows, schema))
    warnings: list[dict[str, Any]] = []

    ordinals = [row.get("ordinal") for row in rows if isinstance(row.get("ordinal"), int)]
    expected_ordinals = list(range(1, 120))
    missing_ordinals = sorted(set(expected_ordinals).difference(ordinals))
    duplicate_ordinals = sorted(
        ordinal for ordinal, count in Counter(ordinals).items() if count > 1
    )
    duplicate_faq_ids = sorted(
        faq_id
        for faq_id, count in Counter(row.get("faq_id") for row in rows).items()
        if count > 1
    )
    if missing_ordinals:
        errors.append({"code": "MISSING_ORDINAL", "ordinals": missing_ordinals})
    if duplicate_ordinals:
        errors.append({"code": "DUPLICATE_ORDINAL", "ordinals": duplicate_ordinals})
    if duplicate_faq_ids:
        errors.append({"code": "DUPLICATE_FAQ_ID", "faq_ids": duplicate_faq_ids})

    answer_hash_mismatch_ids: list[str] = []
    mojibake_ids: list[str] = []
    logical_status_error_ids: list[str] = []
    title_groups: dict[str, list[str]] = defaultdict(list)
    answer_groups: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        faq_id = row.get("faq_id")
        title = row.get("title", "")
        answer = row.get("answer_text", "")
        actual_hash = hashlib.sha256(answer.encode("utf-8")).hexdigest().upper()
        if actual_hash != row.get("answer_text_sha256"):
            answer_hash_mismatch_ids.append(faq_id)
        if any(marker in f"{title}\n{answer}" for marker in MOJIBAKE_MARKERS):
            mojibake_ids.append(faq_id)
        title_groups[_canonical_text(title)].append(faq_id)
        if _canonical_text(answer):
            answer_groups[_canonical_text(answer)].append(faq_id)

        image_only = row.get("content_status") == "IMAGE_ONLY"
        if image_only and (
            answer.strip()
            or row.get("retrieval_eligible") is not False
            or row.get("retrieval_scope") != "EXCLUDED"
            or row.get("text_status") != "NOT_TRANSCRIBED"
        ):
            logical_status_error_ids.append(faq_id)
        if not image_only and not answer.strip():
            logical_status_error_ids.append(faq_id)
        if row.get("mvp_rag_eligible") is not False:
            logical_status_error_ids.append(faq_id)

    duplicate_title_groups = sorted(
        sorted(group) for group in title_groups.values() if len(group) > 1
    )
    duplicate_answer_groups = sorted(
        sorted(group) for group in answer_groups.values() if len(group) > 1
    )
    if answer_hash_mismatch_ids:
        errors.append({
            "code": "ANSWER_HASH_MISMATCH",
            "faq_ids": sorted(answer_hash_mismatch_ids),
        })
    if mojibake_ids:
        errors.append({"code": "MOJIBAKE_DETECTED", "faq_ids": sorted(mojibake_ids)})
    if logical_status_error_ids:
        errors.append({
            "code": "CONTENT_STATUS_POLICY_MISMATCH",
            "faq_ids": sorted(set(logical_status_error_ids)),
        })

    content_status_counts = Counter(row.get("content_status") for row in rows)
    text_status_counts = Counter(row.get("text_status") for row in rows)
    publisher_text_ids = sorted(
        row["faq_id"] for row in rows if row.get("text_status") == "PUBLISHER_TEXT"
    )
    ocr_verified_ids = sorted(
        row["faq_id"] for row in rows if row.get("text_status") == "OCR_VERIFIED"
    )
    image_only_ids = sorted(
        row["faq_id"] for row in rows if row.get("text_status") == "NOT_TRANSCRIBED"
    )
    model_unspecified_ids = sorted(
        row["faq_id"] for row in rows if not row.get("publisher_model_codes")
    )
    conditional_text_ids = sorted(publisher_text_ids + ocr_verified_ids)

    if image_only_ids:
        warnings.append({
            "code": "IMAGE_ONLY_EXCLUDED",
            "count": len(image_only_ids),
            "faq_ids": image_only_ids,
            "message": "전사되지 않은 이미지 전용 FAQ는 실험 검색에서도 제외",
        })
    if model_unspecified_ids:
        warnings.append({
            "code": "MODEL_SCOPE_UNVERIFIED",
            "count": len(model_unspecified_ids),
            "message": "게시자 모델 코드가 없는 FAQ는 조건부 참고만 허용",
        })

    expected_invariants = {
        "snapshot_id": "SRC-WATER-FAQ-20260715",
        "source_type": "official_faq_snapshot",
        "provider": "SK매직",
        "source_file_sha256": EXPECTED_SOURCE_SHA256,
        "mvp_rag_eligible": False,
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

    source_verification: dict[str, Any]
    if source_path is None:
        source_verification = {
            "status": "NOT_PROVIDED",
            "source_label": SOURCE_LABEL,
            "expected_sha256": EXPECTED_SOURCE_SHA256,
        }
    else:
        source_hash = _sha256_file(source_path)
        source_rows = parse_source_snapshot(source_path)
        source_by_ordinal = {row["ordinal"]: row for row in source_rows}
        title_mismatch_ids: list[str] = []
        image_url_mismatch_ids: list[str] = []
        publisher_text_mismatch_ids: list[str] = []
        for row in rows:
            source_row = source_by_ordinal.get(row["ordinal"])
            if source_row is None:
                continue
            if row["title"] != source_row["title"]:
                title_mismatch_ids.append(row["faq_id"])
            if row["image_urls"] != source_row["image_urls"]:
                image_url_mismatch_ids.append(row["faq_id"])
            if (
                row["text_status"] == "PUBLISHER_TEXT"
                and _canonical_text(row["answer_text"])
                != _canonical_text(source_row["answer_text"])
            ):
                publisher_text_mismatch_ids.append(row["faq_id"])
        if source_hash != EXPECTED_SOURCE_SHA256:
            errors.append({
                "code": "SOURCE_HASH_MISMATCH",
                "expected": EXPECTED_SOURCE_SHA256,
                "actual": source_hash,
            })
        if len(source_rows) != 119:
            errors.append({
                "code": "SOURCE_RECORD_COUNT_MISMATCH",
                "expected": 119,
                "actual": len(source_rows),
            })
        if title_mismatch_ids:
            errors.append({"code": "SOURCE_TITLE_MISMATCH", "faq_ids": title_mismatch_ids})
        if image_url_mismatch_ids:
            errors.append({
                "code": "SOURCE_IMAGE_URL_MISMATCH",
                "faq_ids": image_url_mismatch_ids,
            })
        if publisher_text_mismatch_ids:
            errors.append({
                "code": "SOURCE_PUBLISHER_TEXT_MISMATCH",
                "faq_ids": publisher_text_mismatch_ids,
            })
        source_verification = {
            "status": "PASS" if source_hash == EXPECTED_SOURCE_SHA256 else "FAIL",
            "source_label": SOURCE_LABEL,
            "sha256": source_hash,
            "expected_sha256": EXPECTED_SOURCE_SHA256,
            "records_found": len(source_rows),
            "title_mismatch_ids": title_mismatch_ids,
            "image_url_mismatch_ids": image_url_mismatch_ids,
            "publisher_text_mismatch_ids": publisher_text_mismatch_ids,
        }

    if errors:
        status = "FAIL"
    elif source_path is None:
        status = "STRUCTURAL_PASS_SOURCE_NOT_PROVIDED"
    else:
        status = "STRUCTURAL_PASS_SCOPE_REVIEW_REQUIRED"

    return {
        "qa_id": "A1-3-FAQ-CORPUS-QA",
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "included": "정수기 FAQ 119건 원문 등록 상태와 조건부 실험 사용 범위",
            "excluded": [
                "Chunking",
                "Embedding",
                "Vector DB",
                "MVP 검색 편입",
                "미전사 이미지 OCR",
                "Gold Evidence 승인",
            ],
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
        "source_verification": source_verification,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "records_expected": 119,
            "records_found": len(rows),
            "unique_ordinals": len(set(ordinals)),
            "missing_ordinals": missing_ordinals,
            "duplicate_ordinals": duplicate_ordinals,
            "duplicate_faq_ids": duplicate_faq_ids,
            "duplicate_title_groups": duplicate_title_groups,
            "duplicate_answer_groups": duplicate_answer_groups,
            "answer_hash_mismatch_ids": sorted(answer_hash_mismatch_ids),
            "mojibake_ids": sorted(mojibake_ids),
            "publisher_text_count": len(publisher_text_ids),
            "ocr_verified_count": len(ocr_verified_ids),
            "conditional_text_count": len(conditional_text_ids),
            "image_only_excluded_count": len(image_only_ids),
            "model_unspecified_count": len(model_unspecified_ids),
        },
        "classification": {
            "content_status_counts": dict(sorted(content_status_counts.items())),
            "text_status_counts": dict(sorted(text_status_counts.items())),
            "ocr_verified_ids": ocr_verified_ids,
            "image_only_excluded_ids": image_only_ids,
        },
        "metadata_invariants": invariant_values,
        "errors": errors,
        "warnings": warnings,
        "decision": {
            "conditional_experimental_text_use": "READY" if not errors else "BLOCKED",
            "conditional_experimental_record_count": len(conditional_text_ids),
            "image_only_use": "BLOCKED",
            "mvp_search_use": "BLOCKED",
            "exact_model_evidence_use": "REVIEW_REQUIRED",
            "gold_evidence_use": "REVIEW_REQUIRED",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A1-3 FAQ 119건 원문 등록 최소 QA")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    parser.add_argument("--source")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    dataset_path = (REPOSITORY_ROOT / args.dataset).resolve()
    schema_path = (REPOSITORY_ROOT / args.schema).resolve()
    source_path = Path(args.source).resolve() if args.source else None
    output_path = (REPOSITORY_ROOT / args.output).resolve()
    output_path.relative_to(REPOSITORY_ROOT.resolve())
    report = build_qa_report(dataset_path, schema_path, source_path)
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
