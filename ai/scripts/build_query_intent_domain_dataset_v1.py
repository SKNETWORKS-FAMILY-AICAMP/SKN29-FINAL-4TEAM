#!/usr/bin/env python3
"""Build and validate the B2-2 expression-variation Dataset draft."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ai.evaluation.file_integrity import file_sha256
from ai.scripts.run_full_corpus_baseline_v1 import REPOSITORY_ROOT


DATASET_VERSION = "1.0.0-draft.1"
MODEL = "WPUJAC104DWH"
DOCUMENT = "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00"
DEFAULT_DATASET = REPOSITORY_ROOT / "ai/evaluation/datasets/experiments/query_intent_domain_v1.jsonl"
DEFAULT_MANIFEST = REPOSITORY_ROOT / "ai/evaluation/datasets/experiments/query_intent_domain_v1_manifest.json"
DEFAULT_SCHEMA = REPOSITORY_ROOT / "ai/evaluation/schemas/query_intent_domain_case_v1.schema.json"


def _evidence(page: int, section_id: str, unit_id: str) -> list[dict[str, Any]]:
    return [{
        "document_id": DOCUMENT,
        "page_refs": [page],
        "section_id": section_id,
        "evidence_unit_id": unit_id,
    }]


BLOCK_CASES = [
    ("COMMERCIAL_CONTRACT", "EXP-INTENT-COMMERCIAL-001", "제휴카드로 결제하면 할인 금액이 얼마나 되나요?"),
    ("COMMERCIAL_CONTRACT", "EXP-INTENT-COMMERCIAL-001", "이 정수기의 월 렌탈료와 납부 금액을 알려주세요."),
    ("COMMERCIAL_CONTRACT", "EXP-INTENT-COMMERCIAL-001", "계약 요금에 적용되는 할인 혜택이 궁금합니다."),
    ("PART_PURCHASE", "EXP-INTENT-PART-PURCHASE-001", "교체용 필터 가격이 지금 얼마인가요?"),
    ("PART_PURCHASE", "EXP-INTENT-PART-PURCHASE-001", "정품 필터 구매처와 구입 방법을 알려주세요."),
    ("PART_PURCHASE", "EXP-INTENT-PART-PURCHASE-001", "소모품 필터를 파는 곳과 구매 비용이 궁금합니다."),
    ("PRODUCT_OPTION", "EXP-INTENT-PRODUCT-OPTION-001", "선택 가능한 제품 외관 색상은 무엇인가요?"),
    ("PRODUCT_OPTION", "EXP-INTENT-PRODUCT-OPTION-001", "주문할 때 고를 수 있는 제품 컬러 옵션을 알려주세요."),
    ("PRODUCT_OPTION", "EXP-INTENT-PRODUCT-OPTION-001", "이 모델은 어떤 외관 색상 종류로 판매되나요?"),
]

ALLOW_CASES = [
    ("렌탈 중인 정수기에서 갑자기 물이 나오지 않아요.", 37, "JAC104-SECTION-TROUBLESHOOTING", "EVD-WPUJAC104DWH-NO-WATER-001"),
    ("렌탈 제품의 냉수가 미지근한데 무엇을 확인하나요?", 37, "JAC104-SECTION-TROUBLESHOOTING", "EVD-WPUJAC104DWH-COLD-TEMPERATURE-001"),
    ("렌탈해서 쓰는 정수기에서 평소와 다른 소음이 납니다.", 37, "JAC104-SECTION-TROUBLESHOOTING", "EVD-WPUJAC104DWH-NOISE-001"),
    ("필터 교체 방법과 주의사항을 알려주세요.", 26, "JAC104-SECTION-P026", "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P026"),
    ("이 필터는 얼마마다 교체해야 하나요?", 31, "JAC104-SECTION-P031", "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P031"),
    ("필터 가격이 아니라 교체 주기를 알고 싶습니다.", 31, "JAC104-SECTION-P031", "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P031"),
    ("제품 외관에 얼룩이 생겼는데 어떻게 청소하나요?", 32, "JAC104-SECTION-P032", "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P032"),
    ("외관 색상이 변색된 것 같은데 어떤 세척제로 닦나요?", 32, "JAC104-SECTION-P032", "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P032"),
    ("제품 표시창과 조작 버튼 위치를 알려주세요.", 12, "JAC104-SECTION-P012", "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P012"),
]


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for family, rule_id, query in BLOCK_CASES:
        cases.append({
            "case_id": "",
            "dataset_version": DATASET_VERSION,
            "split": "DEV",
            "query": query,
            "product_model_code": MODEL,
            "expected_decision": "BLOCK",
            "expected_rule_id": rule_id,
            "intent_family": family,
            "challenge_type": "UNSUPPORTED_PARAPHRASE",
            "expected_evidence": [],
            "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
            "review_status": "UNREVIEWED_DRAFT",
            "reviewer_ids": [],
            "review_notes": "표현 변형과 정책 경계는 사람 2인 검수 전 Draft로만 사용",
        })
    for query, page, section_id, unit_id in ALLOW_CASES:
        cases.append({
            "case_id": "",
            "dataset_version": DATASET_VERSION,
            "split": "DEV",
            "query": query,
            "product_model_code": MODEL,
            "expected_decision": "ALLOW",
            "expected_rule_id": None,
            "intent_family": "MANUAL_SUPPORT",
            "challenge_type": "OVERLAP_HARD_NEGATIVE",
            "expected_evidence": _evidence(page, section_id, unit_id),
            "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
            "review_status": "UNREVIEWED_DRAFT",
            "reviewer_ids": [],
            "review_notes": "표현 변형과 정책 경계는 사람 2인 검수 전 Draft로만 사용",
        })
    for index, case in enumerate(cases, 1):
        case["case_id"] = f"QIDOM-V1-{index:04d}"
    return cases


def _jsonl_bytes(cases: list[dict[str, Any]]) -> bytes:
    return ("\n".join(
        json.dumps(case, ensure_ascii=False, separators=(",", ":"))
        for case in cases
    ) + "\n").encode("utf-8")


def build_dataset(
    dataset_path: Path = DEFAULT_DATASET,
    manifest_path: Path = DEFAULT_MANIFEST,
    schema_path: Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    cases = build_cases()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for case in cases:
        validator.validate(case)
    if len({case["query"] for case in cases}) != len(cases):
        raise ValueError("B2-2 Dataset에 중복 Query가 있습니다.")

    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_bytes(_jsonl_bytes(cases))
    distribution = {
        key: dict(sorted(Counter(case[key] for case in cases).items()))
        for key in ("expected_decision", "intent_family", "challenge_type", "review_status")
    }
    manifest = {
        "dataset_id": "QUERY-INTENT-DOMAIN-V1",
        "dataset_version": DATASET_VERSION,
        "status": "DRAFT_EXPERIMENT_ONLY_HUMAN_REVIEW_PENDING",
        "dataset": {
            "path": dataset_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "records": len(cases),
            "sha256": file_sha256(dataset_path),
        },
        "schema": {
            "path": schema_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": file_sha256(schema_path),
        },
        "distribution": distribution,
        "approval_policy": {
            "required_reviewer_count": 2,
            "current_approved_records": 0,
            "automatic_label_approval": False,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    print(json.dumps(build_dataset(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
