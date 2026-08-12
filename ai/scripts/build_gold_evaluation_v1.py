#!/usr/bin/env python3
"""A2 Gold Evaluation Dataset v1의 60건 검수 대기 초안을 생성한다."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ai.evaluation.file_integrity import file_sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_VERSION = "1.0.0-draft.2"
OUTPUT_DATASET = "ai/evaluation/datasets/gold/rag_gold_v1.jsonl"
OUTPUT_MANIFEST = "ai/evaluation/datasets/gold/rag_gold_v1_manifest.json"
SCHEMA_PATH = "ai/evaluation/schemas/gold_evaluation_case_v1.schema.json"
JAC_DOCUMENT = "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00"
IAC_DOCUMENT = "MAN-SKMAGIC-WPU-IAC425-REV02"
JAC_MODEL = "WPUJAC104DWH"


EVIDENCE: dict[str, dict[str, Any]] = {
    "NO_WATER": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [37],
        "section_id": "JAC104-SECTION-TROUBLESHOOTING",
        "evidence_unit_id": "EVD-WPUJAC104DWH-NO-WATER-001",
        "risk": "caution",
        "guidance": "PARTIAL_STOP",
    },
    "COLD_TEMPERATURE": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [37],
        "section_id": "JAC104-SECTION-TROUBLESHOOTING",
        "evidence_unit_id": "EVD-WPUJAC104DWH-COLD-TEMPERATURE-001",
        "risk": "general",
        "guidance": "NORMAL",
    },
    "NOISE": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [37],
        "section_id": "JAC104-SECTION-TROUBLESHOOTING",
        "evidence_unit_id": "EVD-WPUJAC104DWH-NOISE-001",
        "risk": "general",
        "guidance": "NORMAL",
    },
    "LEAK": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [5, 7, 38],
        "section_id": "JAC104-SECTION-TROUBLESHOOTING",
        "evidence_unit_id": "EVD-WPUJAC104DWH-LEAK-001",
        "risk": "danger",
        "guidance": "TOTAL_STOP",
    },
    "TASTE_ODOR": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [38],
        "section_id": "JAC104-SECTION-TROUBLESHOOTING",
        "evidence_unit_id": "EVD-WPUJAC104DWH-TASTE-ODOR-001",
        "risk": "caution",
        "guidance": "PARTIAL_STOP",
    },
    "LOW_FLOW": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [38],
        "section_id": "JAC104-SECTION-TROUBLESHOOTING",
        "evidence_unit_id": "EVD-WPUJAC104DWH-LOW-FLOW-001",
        "risk": "general",
        "guidance": "NORMAL",
    },
    "HOT_SAFETY": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [38, 39],
        "section_id": "JAC104-SECTION-TROUBLESHOOTING",
        "evidence_unit_id": "EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001",
        "risk": "danger",
        "guidance": "PENDING_CONSULTATION",
    },
    "SAFETY_POWER": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [3],
        "section_id": "JAC104-SECTION-SAFETY",
        "evidence_unit_id": f"{JAC_DOCUMENT}-P003",
        "risk": "danger",
        "guidance": "TOTAL_STOP",
    },
    "SAFETY_INSTALL": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [4],
        "section_id": "JAC104-SECTION-SAFETY",
        "evidence_unit_id": f"{JAC_DOCUMENT}-P004",
        "risk": "danger",
        "guidance": "TOTAL_STOP",
    },
    "SAFETY_SMOKE": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [5],
        "section_id": "JAC104-SECTION-SAFETY",
        "evidence_unit_id": f"{JAC_DOCUMENT}-P005",
        "risk": "danger",
        "guidance": "TOTAL_STOP",
    },
    "SAFETY_HOT": {
        "document_id": JAC_DOCUMENT,
        "page_refs": [6, 7],
        "section_id": "JAC104-SECTION-SAFETY",
        "evidence_unit_id": f"{JAC_DOCUMENT}-P006",
        "risk": "danger",
        "guidance": "TOTAL_STOP",
    },
}


DIRECT = [
    ("NO_WATER", "정수기에서 물이 나오지 않을 때 무엇을 확인해야 하나요?", "EXISTING_RETRIEVAL_CASE", ["RAG-POS-NO-WATER"]),
    ("COLD_TEMPERATURE", "냉수가 미지근할 때 기다려야 하는 시간과 확인 방법을 알려주세요.", "EXISTING_RETRIEVAL_CASE", ["RAG-POS-COLD-TEMPERATURE"]),
    ("NOISE", "제품에서 평소와 다른 소음이 날 때 확인할 사항은 무엇인가요?", "EXISTING_RETRIEVAL_CASE", ["RAG-POS-NOISE"]),
    ("LEAK", "정수기에서 물이 새는 것 같을 때 안전하게 어떻게 조치해야 하나요?", "EXISTING_RETRIEVAL_CASE", ["RAG-POS-LEAK"]),
    ("TASTE_ODOR", "정수에서 이상한 맛이나 냄새가 날 때 확인할 내용은 무엇인가요?", "EXISTING_RETRIEVAL_CASE", ["RAG-POS-TASTE-ODOR"]),
    ("LOW_FLOW", "출수량이 갑자기 줄었을 때 필터와 원수 상태를 어떻게 확인하나요?", "EXISTING_RETRIEVAL_CASE", ["RAG-POS-LOW-FLOW"]),
    ("HOT_SAFETY", "순간 온수 사용 중 화상 위험이 있을 때 즉시 중단해야 하나요?", "EXISTING_RETRIEVAL_CASE", ["RAG-POS-INSTANT-HOT-WATER-SAFETY"]),
    ("NO_WATER", "정수기에서 물이 안나와요.", "EXISTING_FAQ", ["FAQ-SKMAGIC-0105"]),
    ("COLD_TEMPERATURE", "냉수가 시원하지 않아요.", "EXISTING_FAQ", ["FAQ-SKMAGIC-0107"]),
    ("NOISE", "제품에 소리가 들려요?", "EXISTING_FAQ", ["FAQ-SKMAGIC-0005"]),
    ("LEAK", "제품에 누수가 되고 있어요.", "EXISTING_FAQ", ["FAQ-SKMAGIC-0103"]),
    ("TASTE_ODOR", "물맛이나 냄새가 이상할 때 어떻게 확인하나요?", "EXISTING_FAQ", ["FAQ-SKMAGIC-0115"]),
    ("LOW_FLOW", "냉수 취수량이 적어요.", "EXISTING_FAQ", ["FAQ-SKMAGIC-0096"]),
    ("HOT_SAFETY", "온수 취수 중 물이 튀면 무엇을 주의해야 하나요?", "EXISTING_FAQ", ["FAQ-SKMAGIC-0077"]),
    ("NO_WATER", "필터를 확인했는데도 물이 나오지 않습니다.", "CURATED_VARIANT", []),
    ("COLD_TEMPERATURE", "전원은 정상인데 두 시간이 지나도 냉수가 차갑지 않습니다.", "CURATED_VARIANT", []),
    ("NOISE", "방열팬 쪽 소음이 너무 큰 경우 어떻게 해야 하나요?", "CURATED_VARIANT", []),
    ("LEAK", "제품 내부에서 물이 흘러나올 때 원수 밸브와 전원을 어떻게 해야 하나요?", "CURATED_VARIANT", []),
    ("TASTE_ODOR", "정수에서 비린 맛과 냄새가 계속 나는 경우 점검 방법을 알려주세요.", "CURATED_VARIANT", []),
    ("LOW_FLOW", "원수 밸브는 열려 있는데 출수량이 줄었습니다.", "CURATED_VARIANT", []),
]

COLLOQUIAL = [
    ("LEAK", "정수기 밑이 축축하고 물이 새는 것 같아요.", "EXISTING_RAG_EVAL", ["rag_eval_001"]),
    ("COLD_TEMPERATURE", "냉수가 안 차갑고 계속 미지근해요.", "EXISTING_RAG_EVAL", ["rag_eval_003"]),
    ("LOW_FLOW", "물줄기가 갑자기 졸졸 나와요.", "EXISTING_STRUCTURING_CASE", ["STRUCT-REP-LOW-FLOW"]),
    ("TASTE_ODOR", "물에서 비린내 같은 게 나요.", "EXISTING_STRUCTURING_CASE", ["STRUCT-REP-TASTE-ODOR"]),
    ("NO_WATER", "버튼 눌러도 물이 한 방울도 안 나와요.", "CURATED_VARIANT", []),
    ("NOISE", "정수기가 윙윙거리는데 고장 난 건가요?", "CURATED_VARIANT", []),
    ("LEAK", "바닥에 물이 흥건해졌어요. 뭘 먼저 해야 하죠?", "CURATED_VARIANT", []),
    ("LOW_FLOW", "예전보다 물 나오는 힘이 확 약해졌어요.", "CURATED_VARIANT", []),
    ("HOT_SAFETY", "뜨거운 물이 튈 것 같아서 무서워요.", "CURATED_VARIANT", []),
    ("COLD_TEMPERATURE", "찬물 눌렀는데 그냥 상온 물 같아요.", "CURATED_VARIANT", []),
]

TYPO_ABBREVIATION = [
    ("NO_WATER", "정수기 물이 안나와여", "CURATED_VARIANT", []),
    ("COLD_TEMPERATURE", "냉수가 안차가워요", "CURATED_VARIANT", []),
    ("NOISE", "정수기 소음 넘 커여", "CURATED_VARIANT", []),
    ("LEAK", "정수기에서 물이 세요", "CURATED_VARIANT", []),
    ("LOW_FLOW", "출수량이 갑자기 적어졋어요", "CURATED_VARIANT", []),
]

COMPOUND = [
    (["COLD_TEMPERATURE", "LOW_FLOW"], "냉수가 안 차갑고 졸졸 나와서 물량이 적습니다.", "EXISTING_RAG_EVAL", ["rag_eval_002"]),
    (["LEAK", "NOISE"], "제품 아래로 물이 새면서 평소보다 큰 소리도 납니다.", "CURATED_VARIANT", []),
    (["TASTE_ODOR", "LOW_FLOW"], "정수에서 냄새가 나고 출수량도 줄었습니다.", "CURATED_VARIANT", []),
    (["NO_WATER", "NOISE"], "버튼을 누르면 소리는 나는데 물은 나오지 않습니다.", "CURATED_VARIANT", []),
    (["HOT_SAFETY", "LEAK"], "온수 사용 중 물이 새고 뜨거운 물이 튀었습니다.", "CURATED_VARIANT", []),
]

SAFETY = [
    (["SAFETY_SMOKE"], "정수기 하부 바닥에 누수가 생기고 전원선 주변에 물이 축축합니다.", "EXISTING_SAFETY_CASE", ["safety_eval_001"]),
    (["SAFETY_SMOKE"], "정수기 뒤쪽에서 타는 냄새가 나고 스파크가 튑니다.", "EXISTING_SAFETY_CASE", ["safety_eval_002"]),
    (["SAFETY_POWER"], "젖은 손으로 플러그를 만진 뒤 전원 코드가 뜨거워졌습니다.", "CURATED_VARIANT", []),
    (["SAFETY_SMOKE"], "제품에서 연기와 이상한 냄새가 동시에 납니다.", "CURATED_VARIANT", []),
    (["SAFETY_INSTALL"], "제품 내부에 물이 들어간 뒤 전원이 켜져 있습니다.", "CURATED_VARIANT", []),
    (["SAFETY_SMOKE"], "콘센트 주변에 물이 고이고 정수기에서 누수가 납니다.", "CURATED_VARIANT", []),
    (["SAFETY_HOT"], "아이가 온수 출수구에 손을 대어 화상 위험이 있습니다.", "CURATED_VARIANT", []),
    (["SAFETY_SMOKE"], "제품 주변에 물이 고였는데 계속 사용해도 되나요?", "CURATED_VARIANT", []),
    (["SAFETY_INSTALL"], "정수기 옆에서 가연성 스프레이를 사용한 뒤 이상한 냄새가 납니다.", "CURATED_VARIANT", []),
    (["SAFETY_SMOKE"], "전원을 다시 꽂았더니 타는 냄새와 연기가 납니다.", "CURATED_VARIANT", []),
]

NO_EVIDENCE = [
    ("정수기 월 렌탈료와 제휴카드 할인 금액을 알려주세요.", JAC_MODEL, "CURATED_NEGATIVE", []),
    ("교체용 필터의 현재 판매 가격이 얼마인가요?", JAC_MODEL, "CURATED_NEGATIVE", []),
    ("오늘 방문할 기사님의 정확한 도착 시간을 알려주세요.", JAC_MODEL, "CURATED_NEGATIVE", []),
    ("WPUJAC104DWH 제품의 선택 가능한 외관 색상을 모두 알려주세요.", JAC_MODEL, "CURATED_NEGATIVE", []),
    ("모델 확인이 안 된 FAQ만 근거로 누수 조치를 확정해 주세요.", JAC_MODEL, "EXISTING_RETRIEVAL_CASE", ["RAG-NEG-UNVERIFIED-FAQ"]),
]

CROSS_PRODUCT = [
    ("WPUJAC104DWH에서 얼음이 나오지 않을 때 제빙 기능을 어떻게 켜나요?", JAC_MODEL, "CURATED_NEGATIVE", []),
    ("JAC104 정수기의 얼음 저장고를 분리해서 청소하는 방법을 알려주세요.", JAC_MODEL, "CURATED_NEGATIVE", []),
    ("JAC104에서 얼음 크기와 제빙량을 설정하는 방법이 궁금합니다.", JAC_MODEL, "CURATED_NEGATIVE", []),
    ("WPU-IAC506 필터 교체 방법을 알려주세요.", "WPU-IAC506", "EXISTING_RETRIEVAL_CASE", ["RAG-NEG-IAC506"]),
    ("JAC104 S세대 제품의 냉수 문제 해결법을 알려주세요.", "WPUJAC104SWH", "EXISTING_RETRIEVAL_CASE", ["RAG-NEG-JAC104-S-GENERATION"]),
]


def _sha256(path: Path) -> str:
    return file_sha256(path)


def _expected_evidence(keys: list[str]) -> list[dict[str, Any]]:
    return [
        {field: value for field, value in EVIDENCE[key].items() if field not in {"risk", "guidance"}}
        for key in keys
    ]


def _expected_policy(keys: list[str]) -> tuple[str, str]:
    risk_order = {"general": 0, "caution": 1, "danger": 2}
    guidance_order = {
        "NORMAL": 0,
        "PARTIAL_STOP": 1,
        "PENDING_CONSULTATION": 2,
        "TOTAL_STOP": 3,
    }
    risk = max((EVIDENCE[key]["risk"] for key in keys), key=risk_order.__getitem__)
    guidance = max(
        (EVIDENCE[key]["guidance"] for key in keys),
        key=guidance_order.__getitem__,
    )
    return risk, guidance


def _case(
    *,
    query_variant_type: str,
    query: str,
    split: str,
    evidence_keys: list[str],
    source_query_origin: str,
    source_case_ids: list[str],
    product_model_code: str = JAC_MODEL,
    forbidden_document_ids: list[str] | None = None,
) -> dict[str, Any]:
    expected_no_evidence = not evidence_keys
    if expected_no_evidence:
        risk, guidance = "general", "CONSULTATION_ONLY"
    else:
        risk, guidance = _expected_policy(evidence_keys)
    return {
        "case_id": "",
        "dataset_version": DATASET_VERSION,
        "split": split,
        "query_variant_type": query_variant_type,
        "query": query,
        "product_model_code": product_model_code,
        "expected_evidence": _expected_evidence(evidence_keys),
        "evidence_match_policy": (
            "NONE" if expected_no_evidence else "ALL" if len(evidence_keys) > 1 else "ANY"
        ),
        "expected_no_evidence": expected_no_evidence,
        "expected_risk_level": risk,
        "expected_guidance_policy": guidance,
        "forbidden_document_ids": sorted(set(
            forbidden_document_ids
            if forbidden_document_ids is not None
            else ([JAC_DOCUMENT, IAC_DOCUMENT] if expected_no_evidence else [IAC_DOCUMENT])
        )),
        "forbidden_model_codes": (
            [JAC_MODEL, "WPUIAC425SNW"]
            if expected_no_evidence
            else ["WPUIAC425SNW", "WPUJAC104SWH"]
        ),
        "source_query_origin": source_query_origin,
        "source_case_ids": source_case_ids,
        "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
        "review_status": "UNREVIEWED_DRAFT",
        "reviewer_ids": [],
        "review_notes": "사람 2인 검수 전에는 Gold 정답으로 승인하지 않음",
    }


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    for index, (key, query, origin, source_ids) in enumerate(DIRECT):
        cases.append(_case(
            query_variant_type="DIRECT",
            query=query,
            split="DEV" if index < 14 else "TEST",
            evidence_keys=[key],
            source_query_origin=origin,
            source_case_ids=source_ids,
        ))
    for index, (key, query, origin, source_ids) in enumerate(COLLOQUIAL):
        cases.append(_case(
            query_variant_type="COLLOQUIAL",
            query=query,
            split="DEV" if index < 7 else "TEST",
            evidence_keys=[key],
            source_query_origin=origin,
            source_case_ids=source_ids,
        ))
    for index, (key, query, origin, source_ids) in enumerate(TYPO_ABBREVIATION):
        cases.append(_case(
            query_variant_type="TYPO_ABBREVIATION",
            query=query,
            split="DEV" if index < 3 else "TEST",
            evidence_keys=[key],
            source_query_origin=origin,
            source_case_ids=source_ids,
        ))
    for index, (keys, query, origin, source_ids) in enumerate(COMPOUND):
        cases.append(_case(
            query_variant_type="COMPOUND",
            query=query,
            split="DEV" if index < 3 else "TEST",
            evidence_keys=keys,
            source_query_origin=origin,
            source_case_ids=source_ids,
        ))
    for keys, query, origin, source_ids in SAFETY:
        cases.append(_case(
            query_variant_type="SAFETY",
            query=query,
            split="SAFETY",
            evidence_keys=keys,
            source_query_origin=origin,
            source_case_ids=source_ids,
        ))
    for index, (query, model, origin, source_ids) in enumerate(NO_EVIDENCE):
        cases.append(_case(
            query_variant_type="NO_EVIDENCE",
            query=query,
            split="DEV" if index < 4 else "TEST",
            evidence_keys=[],
            source_query_origin=origin,
            source_case_ids=source_ids,
            product_model_code=model,
        ))
    for index, (query, model, origin, source_ids) in enumerate(CROSS_PRODUCT):
        cases.append(_case(
            query_variant_type="CROSS_PRODUCT",
            query=query,
            split="DEV" if index < 4 else "TEST",
            evidence_keys=[],
            source_query_origin=origin,
            source_case_ids=source_ids,
            product_model_code=model,
        ))

    for index, case in enumerate(cases, start=1):
        case["case_id"] = f"RAGV2-GOLD-{index:04d}"
    return cases


def _jsonl_bytes(cases: list[dict[str, Any]]) -> bytes:
    lines = [
        json.dumps(case, ensure_ascii=False, separators=(",", ":"))
        for case in cases
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> None:
    cases = build_cases()
    if len(cases) != 60:
        raise ValueError(f"Gold Dataset은 정확히 60건이어야 합니다: {len(cases)}")

    output_path = REPOSITORY_ROOT / OUTPUT_DATASET
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_jsonl_bytes(cases))

    source_paths = [
        "data/config/rag/jac104_retrieval_cases.json",
        "data/processed/structured/evidence/jac104_evidence_registry.jsonl",
        "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl",
        "data/processed/documents/faq/faq_snapshot_normalized.jsonl",
        "ai/evaluation/datasets/rag_eval_dataset.json",
        "ai/evaluation/datasets/safety/safety_eval_dataset.json",
        "ai/evaluation/datasets/structuring/symptom_eval_dataset.json",
    ]
    manifest = {
        "dataset_id": "RAG-GOLD-V1",
        "dataset_version": DATASET_VERSION,
        "status": "DRAFT_REVIEW_REQUIRED",
        "generated_at": "2026-08-11T00:00:00+09:00",
        "dataset": {
            "path": OUTPUT_DATASET,
            "records": len(cases),
            "sha256": _sha256(output_path),
        },
        "schema": {
            "path": SCHEMA_PATH,
            "sha256": _sha256(REPOSITORY_ROOT / SCHEMA_PATH),
        },
        "distribution": {
            "query_variant_type": dict(sorted(Counter(
                case["query_variant_type"] for case in cases
            ).items())),
            "split": dict(sorted(Counter(case["split"] for case in cases).items())),
            "review_status": dict(sorted(Counter(
                case["review_status"] for case in cases
            ).items())),
        },
        "source_files": [
            {"path": path, "sha256": _sha256(REPOSITORY_ROOT / path)}
            for path in source_paths
        ],
        "approval_policy": {
            "required_reviewer_count": 2,
            "current_approved_records": 0,
            "automatic_label_approval": False,
            "note": "60건 구성 완료는 Gold 승인 완료를 의미하지 않음",
        },
    }
    manifest_path = REPOSITORY_ROOT / OUTPUT_MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": manifest["status"],
        "dataset": OUTPUT_DATASET,
        "records": len(cases),
        "sha256": manifest["dataset"]["sha256"],
        "distribution": manifest["distribution"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
