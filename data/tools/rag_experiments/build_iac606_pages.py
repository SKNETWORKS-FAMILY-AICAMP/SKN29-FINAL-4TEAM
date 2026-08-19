"""WPU-IAC606 REV.00 PDF를 확장 참고용 48페이지 JSONL로 생성한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = "data/processed/documents/manuals/expansion/manual_pages_iac606.jsonl"
DEFAULT_INVENTORY = "data/processed/metadata/source_inventory.csv"
DEFAULT_GENERATED_AT = "2026-08-18T00:00:00+09:00"
SOURCE_INVENTORY_ID = "SRC-IAC606-MANUAL"
DOCUMENT_ID = "MAN-SKMAGIC-WPU-IAC606-REV00"
VISUALLY_REVIEWED_PAGES = {1, 5, 39, 40, 41, 42, 43, 44, 48}

SECTION_RANGES = (
    (1, 1, "COVER", "표지"),
    (2, 2, "CONTENTS", "목차"),
    (3, 7, "SAFETY", "안전을 위한 주의사항"),
    (8, 8, "INSTALLATION", "설치하기"),
    (9, 9, "FEATURES", "특장점"),
    (10, 11, "PARTS", "각 부의 명칭과 부속품"),
    (12, 15, "CONTROL-PANEL", "표시/조작부"),
    (16, 21, "USAGE", "사용하기"),
    (22, 30, "FUNCTIONS", "기능 사용하기"),
    (31, 33, "FILTER-REPLACEMENT", "필터 교체하기"),
    (34, 35, "PURIFICATION-SYSTEM", "정수시스템"),
    (36, 39, "CLEANING", "청소하기"),
    (40, 43, "TROUBLESHOOTING", "고장 신고 전 확인하기"),
    (44, 45, "SPECIFICATIONS", "제품규격"),
    (46, 46, "DISPOSAL", "폐 전자제품 처리하기"),
    (47, 47, "WARRANTY", "제품보증서"),
    (48, 48, "BACK-COVER", "뒷표지"),
)

PAGE_REPLACEMENTS = {
    1: (("Water Puri/f_ier with Ice Dispenser", "Water Purifier with Ice Dispenser"),),
    39: (("작은 홀작은 홀", "작은 홀"),),
}

PAGE_48_TRANSCRIPTION = """SK매직 고객상담센터 1600-1661
www.skmagic.com
고객상담센터에서는 고객서비스의 일환으로 고객께서 구입·사용중인 제품중에서 소모품 / 액세서리인 식기세척기 세제, 린스 / 공기청정기 필터 / 정수기 필터 / 비데 필터 / 연수기 재생용액 / 가스레인지 및 가스오븐레인지 건전지, 버너캡, 버너헤드, 삼발이 / 전기오븐 오븐용기, 스팀용기, 오븐장갑, 구이석쇠, 물통 등을 통신판매 하고 있습니다."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _source_inventory(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        matches = [
            row for row in csv.DictReader(stream)
            if row.get("data_id") == SOURCE_INVENTORY_ID
        ]
    if len(matches) != 1:
        raise ValueError(f"{SOURCE_INVENTORY_ID} Inventory 행이 단일하지 않습니다.")
    return matches[0]


def _section(page: int) -> tuple[str, str]:
    for start, end, code, title in SECTION_RANGES:
        if start <= page <= end:
            return f"IAC606-SECTION-{code}", title
    raise ValueError(f"Section 범위를 찾을 수 없는 페이지: {page}")


def normalize_extracted_text(raw_text: str, page: int) -> tuple[str, list[str]]:
    normalized_lines: list[str] = []
    for raw_line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"[\t ]+", " ", raw_line).strip()
        if not line:
            continue
        if not normalized_lines and line == str(page):
            continue
        normalized_lines.append(line)
    text = "\n".join(normalized_lines)
    correction_ids: list[str] = []
    for index, (before, after) in enumerate(PAGE_REPLACEMENTS.get(page, ()), start=1):
        if before not in text:
            raise ValueError(f"{page}쪽 보정 대상 문자열이 없습니다: {before}")
        text = text.replace(before, after)
        correction_ids.append(f"IAC606-P{page:03d}-CORRECTION-{index:02d}")
    return text, correction_ids


def build_rows(
    pdf_path: Path,
    inventory_path: Path,
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> list[dict[str, Any]]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("IAC606 PDF 추출에는 pypdf가 필요합니다.") from error

    inventory = _source_inventory(inventory_path)
    actual_hash = _sha256_file(pdf_path)
    if actual_hash != inventory["sha256"]:
        raise ValueError(f"IAC606 원본 Hash 불일치: {actual_hash} != {inventory['sha256']}")
    if pdf_path.stat().st_size != int(inventory["file_size_bytes"]):
        raise ValueError("IAC606 원본 파일 크기가 Inventory와 다릅니다.")

    reader = PdfReader(str(pdf_path))
    expected_page_count = int(inventory["page_count"])
    if len(reader.pages) != expected_page_count:
        raise ValueError(f"IAC606 페이지 수 불일치: {len(reader.pages)} != {expected_page_count}")

    rows: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text, correction_ids = normalize_extracted_text(page.extract_text() or "", page_number)
        extraction_method = "pypdf_text"
        content_status = "EXTRACTED_TEXT"
        verification_status = "TEXT_EXTRACTED"
        if correction_ids:
            extraction_method = "pypdf_text_with_manual_corrections"
            content_status = "EXTRACTED_TEXT_CORRECTED"
        if page_number in VISUALLY_REVIEWED_PAGES:
            verification_status = "VISUALLY_REVIEWED"
        if page_number == 48:
            text = PAGE_48_TRANSCRIPTION
            correction_ids = ["IAC606-P048-VISUAL-TRANSCRIPTION-01"]
            extraction_method = "manual_visual_transcription"
            content_status = "VISUAL_TEXT_TRANSCRIBED"
            verification_status = "VISUALLY_REVIEWED"
        if not text.strip():
            raise ValueError(f"IAC606 {page_number}쪽 본문이 비어 있습니다.")

        section_id, section_title = _section(page_number)
        rows.append({
            "page_id": f"{DOCUMENT_ID}-P{page_number:03d}",
            "document_id": DOCUMENT_ID,
            "source_inventory_id": SOURCE_INVENTORY_ID,
            "source_type": "official_manual",
            "provider": "SK매직",
            "exact_sales_code": inventory["exact_sales_code"],
            "product_model": inventory["product_model"],
            "model_family": inventory["product_model"],
            "product_generation": "IAC606",
            "scope_role": "expansion",
            "mvp_use": False,
            "allowed_use": "REFERENCE_ONLY",
            "version": inventory["version"],
            "page": page_number,
            "page_count": expected_page_count,
            "section_id": section_id,
            "section_title": section_title,
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
            "source_file_sha256": inventory["sha256"],
            "extraction_method": extraction_method,
            "content_status": content_status,
            "verification_status": verification_status,
            "manual_correction_ids": correction_ids,
            "source_url": inventory["source_url"],
            "generated_at": generated_at,
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="IAC606 REV.00 48페이지 JSONL 생성")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args()

    output_path = (REPOSITORY_ROOT / args.output).resolve()
    output_path.relative_to(REPOSITORY_ROOT.resolve())
    rows = build_rows(
        Path(args.pdf).resolve(),
        (REPOSITORY_ROOT / args.inventory).resolve(),
        generated_at=args.generated_at,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "status": "IAC606_PAGE_DATASET_CREATED",
        "output": output_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "page_count": len(rows),
        "source_sha256": rows[0]["source_file_sha256"],
        "visually_reviewed_pages": sorted(VISUALLY_REVIEWED_PAGES),
        "visual_transcription_pages": [48],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
