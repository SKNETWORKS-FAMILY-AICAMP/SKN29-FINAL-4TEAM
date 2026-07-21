from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "data"
MANUAL_OUTPUT = OUTPUT_ROOT / "processed" / "documents" / "manual_pages.jsonl"
HIT_OUTPUT = OUTPUT_ROOT / "processed" / "metadata" / "manual_keyword_hits.csv"
FAQ_OUTPUT = OUTPUT_ROOT / "processed" / "structured" / "selected_faq_candidates.jsonl"
INVENTORY_OUTPUT = OUTPUT_ROOT / "processed" / "metadata" / "source_inventory.csv"

MANUALS = [
    {
        "document_id": "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00",
        "model": "WPU-JAC104D / WPU-JCC104D",
        "exact_sales_code": "WPUJAC104DWH",
        "scope_role": "mvp_primary",
        "version": "REV.00",
        "published_date": "2026-05-13",
        "file": ROOT
        / "data"
        / "raw"
        / "manuals"
        / "SK매직_WPU-JAC104D_JCC104D_사용설명서_REV00.pdf",
        "official_url": "https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUJAC104DWH&tabIndex=3",
        "direct_download_url": "https://www.skintellixservice.com/common/fileDownloadS3.do?atchPath=cnts&atchNm=50f504a46a3843beb767baa6f9f94548&atchOrgNm=(rev00)%20WPU-JAC104%20(D)%2C%20JCC104%20(D)_User_KO_260428.pdf&atchExtNm=pdf",
        "content_key": "50f504a46a3843beb767baa6f9f94548",
        "file_id": "113815",
        "official_filename": "(rev00) WPU-JAC104 (D), JCC104 (D)_User_KO_260428.pdf",
        "official_registered_at": "2026-05-13",
        "official_updated_at": "2026-05-13",
        "filename_date_token": "260428",
        "pdf_creation_timestamp": "2026-04-28T11:42:25+09:00",
        "pdf_modified_timestamp": "2026-04-28T11:42:28+09:00",
        "verified_pages": "37-39",
        "verified_page_numbers": {37, 38, 39},
    },
    {
        "document_id": "MAN-SKMAGIC-WPU-IAC425-REV02",
        "model": "WPU-IAC425",
        "exact_sales_code": "WPUIAC425SNW",
        "scope_role": "expansion_secondary",
        "version": "REV.02",
        "published_date": "2026-01-05",
        "file": ROOT
        / "data"
        / "raw"
        / "manuals"
        / "SK매직_WPU-IAC425_사용설명서_REV02.pdf",
        "official_url": "https://www.skintellixservice.com/web/easy/easyMain.do?inputBasicKeyword=WPUIAC425&tabIndex=3",
        "direct_download_url": "",
        "content_key": "48ee8e11d9e540769f7582f57af395ea",
        "file_id": "103996",
        "official_filename": "(rev02) WPU-IAC425_User_KO_251224.pdf",
        "official_registered_at": "2026-01-05",
        "official_updated_at": "2026-01-05",
        "filename_date_token": "251224",
        "pdf_creation_timestamp": "",
        "pdf_modified_timestamp": "",
        "verified_pages": "37-40, 43-46",
        "verified_page_numbers": {37, 38, 39, 40, 43, 44, 45, 46},
    },
]

KEYWORDS = {
    "low_flow_no_water": ["물이 나오지", "출수량", "출수되지", "물이 안 나"],
    "taste_odor": ["물맛", "맛과 냄새", "불쾌한 맛", "냄새가"],
    "leak": ["누수", "물이 새", "물샘"],
    "cold_temperature": ["냉수가 차갑지", "냉수 온도", "냉수가 미지근"],
    "hot_temperature": ["온수가", "온수 온도", "온수 잠금"],
    "ice_dispense": ["출빙", "얼음이 나오지", "얼음이 부족", "얼음이 만들어"],
    "ice_hygiene": ["아이스룸", "얼음 저장", "얼음보관", "제빙봉", "얼음통"],
    "noise": ["소음", "작동음", "소리가"],
}

# 기존 119건 FAQ에서 이번 모델 전략과 직접 관계있는 항목만 후보로 다시 추출한다.
# 모델 적용이 불명확한 항목은 데이터에서 제거하지 않고 사용 제한을 명시한다.
FAQ_RULES = {
    2: ("WPU-JAC104", "model_family_direct", "조건부 보조 - D/S 세대 미표기이므로 WPU-JAC104D 매뉴얼 우선, FAQ 단독 답변 금지"),
    3: ("WPU-JAC104", "category_common_unverified", "보조 후보 - 매뉴얼과 일치할 때만 사용"),
    4: ("WPU-JAC104", "image_only_unverified", "사용 보류 - 답변 이미지 OCR 및 매뉴얼 대조 필요"),
    8: ("WPU-JAC104", "category_common_unverified", "보조 후보 - 직수형 공통, 매뉴얼 우선"),
    30: ("WPU-JAC104;WPU-IAC425", "category_common_safety", "안전 분기 보조 - 밸브 잠금·전원 차단·상담 연결"),
    38: ("WPU-JAC104;WPU-IAC425", "category_common_safety", "필터 교체 후 누수 보조 - 모델 매뉴얼 우선"),
    95: ("WPU-JAC104;WPU-IAC425", "category_common_unverified", "출수량 저하 보조 - 모델 매뉴얼 우선"),
    103: ("WPU-JAC104;WPU-IAC425", "category_common_safety", "누수 안전 분기 보조"),
    104: ("WPU-JAC104;WPU-IAC425", "category_common_unverified", "온수 이상 보조 - 모델 매뉴얼 우선"),
    107: ("WPU-JAC104;WPU-IAC425", "category_common_unverified", "냉수 이상 보조 - 모델 매뉴얼 우선"),
    111: ("WPU-JAC104;WPU-IAC425", "category_common_unverified", "물맛·냄새 보조 - 수질 안전 단정 금지"),
    115: ("WPU-JAC104;WPU-IAC425", "category_common_unverified", "물맛·냄새 보조 - 모델 매뉴얼 우선"),
    118: ("WPU-JAC104;WPU-IAC425", "category_common_unverified", "냉수 이상 보조 - 모델 매뉴얼 우선"),
    119: ("WPU-JAC104;WPU-IAC425", "category_common_unverified", "소음 보조 - 정상음과 이상음 구분 필요"),
    9: ("WPU-IAC425", "image_only_unverified", "확장 보류 - 직수 얼음정수기 공통 이미지 OCR 필요"),
    25: ("WPU-IAC425", "category_common_unverified", "확장 보조 - 배수 원인은 모델 매뉴얼 우선"),
    26: ("WPU-IAC425", "other_model_only", "사용 금지 - WPUI100·110·200·210 전용"),
    34: ("WPU-IAC425", "category_common_unverified", "확장 보조 - 얼음 상태 설명, 매뉴얼 우선"),
    50: ("WPU-IAC425", "other_product_family", "사용 보류 - all in one 직수 얼음정수기 전용"),
    51: ("WPU-IAC425", "other_product_family", "사용 보류 - all in one 직수 얼음정수기 전용"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def normalize_text(text: str) -> str:
    lines = []
    for line in text.replace("\u00a0", " ").splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def extract_manuals() -> list[dict[str, str]]:
    MANUAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    inventory_rows: list[dict[str, str]] = []
    hit_rows: list[dict[str, str | int]] = []

    with MANUAL_OUTPUT.open("w", encoding="utf-8", newline="\n") as page_file:
        for item in MANUALS:
            path = item["file"]
            if not path.exists():
                raise FileNotFoundError(path)
            reader = PdfReader(str(path))
            for page_number, page in enumerate(reader.pages, start=1):
                text = normalize_text(page.extract_text() or "")
                page_record = {
                    "document_id": item["document_id"],
                    "source_type": "official_manual",
                    "provider": "SK인텔릭스 / SK매직",
                    "exact_sales_code": item["exact_sales_code"],
                    "product_model": item["model"],
                    "scope_role": item["scope_role"],
                    "version": item["version"],
                    "official_registered_at": item["official_registered_at"],
                    "official_updated_at": item["official_updated_at"],
                    "filename_date_token": item["filename_date_token"],
                    "pdf_creation_timestamp": item["pdf_creation_timestamp"],
                    "pdf_modified_timestamp": item["pdf_modified_timestamp"],
                    "page": page_number,
                    "text": text,
                    "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "source_url": item["official_url"],
                    "source_landing_url": item["official_url"],
                    "source_direct_download_url": item["direct_download_url"],
                    "verification_status": (
                        "text_and_visual_verified"
                        if page_number in item["verified_page_numbers"]
                        else "text_extracted_visual_review_pending"
                    ),
                }
                page_file.write(json.dumps(page_record, ensure_ascii=False) + "\n")

                for topic, keywords in KEYWORDS.items():
                    matched = [keyword for keyword in keywords if keyword in text]
                    if matched:
                        hit_rows.append(
                            {
                                "document_id": item["document_id"],
                                "product_model": item["model"],
                                "scope_role": item["scope_role"],
                                "page": page_number,
                                "topic": topic,
                                "matched_keywords": ";".join(matched),
                                "review_status": (
                                    "text_and_visual_verified"
                                    if page_number in item["verified_page_numbers"]
                                    else "visual_review_pending"
                                ),
                            }
                        )

            inventory_rows.append(
                {
                    "data_id": item["document_id"],
                    "source_name": "SK매직 제품 사용설명서",
                    "provider": "SK인텔릭스 / SK매직",
                    "exact_sales_code": item["exact_sales_code"],
                    "product_model": item["model"],
                    "scope_role": item["scope_role"],
                    "source_type": "제품 사용설명서",
                    "version": item["version"],
                    "published_date": item["published_date"],
                    "date_basis": "공식 첨부 등록·수정일",
                    "official_registered_at": item["official_registered_at"],
                    "official_updated_at": item["official_updated_at"],
                    "filename_date_token": item["filename_date_token"],
                    "pdf_creation_timestamp": item["pdf_creation_timestamp"],
                    "pdf_modified_timestamp": item["pdf_modified_timestamp"],
                    "collected_date": "2026-07-21",
                    "page_count": str(len(reader.pages)),
                    "file_size_bytes": str(path.stat().st_size),
                    "sha256": sha256(path),
                    "source_url": item["official_url"],
                    "source_landing_url": item["official_url"],
                    "source_direct_download_url": item["direct_download_url"],
                    "content_key": item["content_key"],
                    "file_id": item["file_id"],
                    "official_filename": item["official_filename"],
                    "local_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "status": "collected_text_extracted_core_pages_visual_verified",
                    "limitations": (
                        "공식 원문 외부 재배포 범위 확인 필요; "
                        f"핵심 {item['verified_pages']}쪽만 시각 검증 완료, 그 외 페이지는 시각 검증 전"
                    ),
                }
            )

    with HIT_OUTPUT.open("w", encoding="utf-8-sig", newline="") as hit_file:
        writer = csv.DictWriter(hit_file, fieldnames=list(hit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(hit_rows)

    return inventory_rows


def parse_faq_sections(markdown: str) -> dict[int, tuple[str, str]]:
    heading = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading.finditer(markdown))
    sections: dict[int, tuple[str, str]] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        title = match.group(2).strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[number] = (title, markdown[start:end].strip())
    return sections


def extract_faq_candidates(inventory_rows: list[dict[str, str]]) -> None:
    faq_path = ROOT / "data" / "raw" / "faq" / "SK매직_정수기공통_FAQ_20260715.md"
    markdown = faq_path.read_text(encoding="utf-8")
    sections = parse_faq_sections(markdown)
    FAQ_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with FAQ_OUTPUT.open("w", encoding="utf-8", newline="\n") as output:
        for faq_number, (target_models, applicability, use_rule) in FAQ_RULES.items():
            if faq_number not in sections:
                raise KeyError(f"FAQ {faq_number} not found")
            title, raw_section = sections[faq_number]
            image_urls = re.findall(r"!\[[^\]]*\]\((https?://[^)]+)\)", raw_section)
            body = re.sub(r"^##.*?$", "", raw_section, count=1, flags=re.MULTILINE)
            body = re.sub(r"### 원문에 포함된 링크.*", "", body, flags=re.DOTALL)
            body = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", body)
            body = normalize_text(body)
            record = {
                "faq_id": f"FAQ-SKMAGIC-{faq_number:03d}",
                "source_type": "official_faq_snapshot",
                "provider": "SK매직",
                "faq_number": faq_number,
                "title": title,
                "target_models": target_models,
                "project_candidate_models": target_models,
                "publisher_model_codes": (
                    "WPUJAC104;WPUJCC104" if faq_number == 2 else ""
                ),
                "exact_sales_code_match": False,
                "generation_scope": (
                    "JAC104 계열 표기만 존재하며 D/S 세대 접미사는 미표기"
                    if faq_number == 2
                    else "공식 본문에 대상 모델 코드 미표기"
                ),
                "applicability": applicability,
                "allowed_use": use_rule,
                "rag_policy": (
                    "conditional_support_after_WPU-JAC104D_manual"
                    if faq_number == 2
                    else "exclude_until_exact_model_verified"
                ),
                "answer_text": body,
                "image_urls": image_urls,
                "source_url": "https://www.skmagic.com/customer/faq/indexFaqList",
                "source_locator_type": "section_heading",
                "source_locator": f"FAQ > 정수기 > {title}",
                "official_page_number": None,
                "source_path": str(faq_path.relative_to(ROOT)).replace("\\", "/"),
                "collected_date": "2026-07-15",
                "reselected_date": "2026-07-21",
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    inventory_rows.append(
        {
            "data_id": "FAQ-SKMAGIC-SELECTED-JAC104-IAC425-20260721",
            "source_name": "SK매직 정수기 FAQ 선택 후보",
            "provider": "SK매직",
            "exact_sales_code": "",
            "product_model": "WPU-JAC104; WPU-IAC425",
            "scope_role": "mvp_and_expansion_support",
            "source_type": "공식 FAQ 재선별본",
            "version": "2026-07-15 수집본 기반",
            "published_date": "미확인",
            "date_basis": "공식 FAQ 화면 확인일",
            "official_registered_at": "",
            "official_updated_at": "",
            "filename_date_token": "",
            "pdf_creation_timestamp": "",
            "pdf_modified_timestamp": "",
            "collected_date": "2026-07-15 / 2026-07-21 재선별",
            "page_count": "",
            "file_size_bytes": str(faq_path.stat().st_size),
            "sha256": sha256(faq_path),
            "source_url": "https://www.skmagic.com/customer/faq/indexFaqList",
            "source_landing_url": "https://www.skmagic.com/customer/faq/indexFaqList",
            "source_direct_download_url": "",
            "content_key": "",
            "file_id": "",
            "official_filename": faq_path.name,
            "local_path": str(FAQ_OUTPUT.relative_to(ROOT)).replace("\\", "/"),
            "status": f"{len(FAQ_RULES)}건 재선별",
            "limitations": "개별 FAQ 영구 URL 없음; 모델 공통·타 모델 전용 항목 혼재; applicability 필수 적용",
        }
    )


def write_inventory(rows: list[dict[str, str]]) -> None:
    INVENTORY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with INVENTORY_OUTPUT.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    inventory_rows = extract_manuals()
    extract_faq_candidates(inventory_rows)
    write_inventory(inventory_rows)
    print(f"manual_pages={sum(1 for _ in MANUAL_OUTPUT.open(encoding='utf-8'))}")
    print(f"faq_candidates={len(FAQ_RULES)}")
    print(f"output={OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
