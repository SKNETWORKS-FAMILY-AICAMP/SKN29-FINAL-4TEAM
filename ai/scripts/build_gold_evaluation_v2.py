#!/usr/bin/env python3
"""승인된 JAC104 질문을 Gold v2 Draft 계약으로 결정적으로 변환한다.

이 Builder는 Data 원본을 수정하지 않는다. Full Corpus v3의 Evidence Group을
참조하는 AI 소유 Gold 산출물과, 아직 승인되지 않은 IAC425 후보 산출물을 서로
분리한다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from ai.evaluation.file_integrity import file_sha256


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "2.0.0-draft.2"
DATASET_VERSION = SCHEMA_VERSION
OUTPUT_DATASET = "ai/evaluation/datasets/gold/rag_gold_v2.jsonl"
OUTPUT_MANIFEST = "ai/evaluation/datasets/gold/rag_gold_v2_manifest.json"
OUTPUT_IAC425_CANDIDATES = (
    "ai/evaluation/datasets/candidates/iac425_gold_v2_candidates.jsonl"
)
OUTPUT_IAC425_CANDIDATE_MANIFEST = (
    "ai/evaluation/datasets/candidates/"
    "iac425_gold_v2_candidates_manifest.json"
)
SCHEMA_PATH = "ai/evaluation/schemas/gold_evaluation_case_v2.schema.json"
BASE_GOLD_PATH = "ai/evaluation/datasets/gold/rag_gold_v1.jsonl"
QUERY_REVIEW_PACKET_PATH = (
    "data/processed/validation/rag_experiments/"
    "gold_v1_post_query_label_revalidation_packet.json"
)
IAC425_SOURCE_PATH = "data/config/rag/iac425_gold_candidates.json"
EVIDENCE_GROUP_REGISTRY_PATH = (
    "ai/evaluation/datasets/gold/"
    "full_corpus_v3_evidence_groups_gold_v2.jsonl"
)
CHILD_REGISTRY_PATH = (
    "data/processed/structured/rag/experimental/full_corpus_v3_children.jsonl"
)
CORPUS_PATH = (
    "data/processed/structured/rag/experimental/full_corpus_chunks_v3.jsonl"
)

JAC_MODEL = "WPUJAC104DWH"
JAC_DOCUMENT = "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00"

GROUP_NO_WATER = "EVD-WPUJAC104DWH-NO-WATER-001"
GROUP_COLD_NORMAL = "EVD-WPUJAC104DWH-COLD-TEMPERATURE-NORMAL-001"
GROUP_COLD_FAULT = "EVD-WPUJAC104DWH-COLD-TEMPERATURE-FAULT-001"
GROUP_NOISE = "EVD-WPUJAC104DWH-NOISE-001"
GROUP_LEAK = "EVD-WPUJAC104DWH-LEAK-001"
GROUP_TASTE_ODOR = "EVD-WPUJAC104DWH-TASTE-ODOR-001"
GROUP_LOW_FLOW = "EVD-WPUJAC104DWH-LOW-FLOW-001"
GROUP_HOT_STEAM = "EVD-WPUJAC104DWH-HOT-STEAM-001"
GROUP_BURNING_ODOR = "EVD-WPUJAC104DWH-BURNING-ODOR-RESPONSE-001"
GROUP_SPRAY_PREVENTION = "EVD-WPUJAC104DWH-SPRAY-FIRE-PREVENTION-001"

COND_NO_WATER_AFTER_FILTER = (
    "COND-WPUJAC104DWH-NO-WATER-AFTER-FILTER-001"
)
COND_COLD_AFTER_2H = "COND-WPUJAC104DWH-COLD-AFTER-2H-001"
COND_LOW_FLOW_AFTER_FILTER = (
    "COND-WPUJAC104DWH-LOW-FLOW-AFTER-FILTER-001"
)
COND_HOT_STEAM_PERSISTS = "COND-WPUJAC104DWH-HOT-STEAM-PERSISTS-001"

IAC425_CONDITION_BY_GROUP = {
    "EVD-WPUIAC425SNW-COLD-TEMPERATURE-FAULT-001": (
        "COND-WPUIAC425SNW-COLD-AFTER-2H-001"
    ),
    "EVD-WPUIAC425SNW-HOT-STEAM-001": (
        "COND-WPUIAC425SNW-HOT-STEAM-PERSISTENCE-001"
    ),
    "EVD-WPUIAC425SNW-LOW-FLOW-001": (
        "COND-WPUIAC425SNW-LOW-FLOW-AFTER-FILTER-001"
    ),
    "EVD-WPUIAC425SNW-NO-HOT-WATER-001": (
        "COND-WPUIAC425SNW-NO-HOT-AFTER-UNLOCK-001"
    ),
    "EVD-WPUIAC425SNW-NO-WATER-001": (
        "COND-WPUIAC425SNW-NO-WATER-AFTER-FILTER-001"
    ),
    "EVD-WPUIAC425SNW-PARTICLES-001": (
        "COND-WPUIAC425SNW-PARTICLES-PERSISTENCE-001"
    ),
}

IAC425_QUERY_OVERRIDES = {
    "RAGV2-IAC425-CAND-002": (
        "전원은 정상인데 두 시간이 지나도 WPU-IAC425 냉수가 차갑지 않아요. "
        "어떻게 해야 하나요?"
    ),
    "RAGV2-IAC425-CAND-003": (
        "WPU-IAC425 냉수가 평소보다 미지근해요. "
        "먼저 무엇을 확인해야 하나요?"
    ),
    "RAGV2-IAC425-CAND-010": (
        "WPU-IAC425 안쪽에서 물이 흐르거나 제품 주변에 물이 고여 있어요. "
        "지금 어떻게 해야 하나요?"
    ),
}

EXCLUDED_REASONS = {
    "RAGV2-GOLD-0017": (
        "소음 크기 조건은 현 Condition trigger enum으로 정확히 표현할 수 없어 제외"
    ),
    "RAGV2-GOLD-0033": (
        "소음 크기 조건은 현 Condition trigger enum으로 정확히 표현할 수 없어 제외"
    ),
    "RAGV2-GOLD-0040": (
        "누수와 온수 분사 복합 질문의 2차 검수 제외 결정을 보존"
    ),
    "RAGV2-GOLD-0043": (
        "P003 전기 안전 Source Page에 대응하는 검증 Evidence Group이 없어 제외"
    ),
    "RAGV2-GOLD-0047": (
        "P006 온수 접촉 예방 Source Page에 대응하는 검증 Evidence Group이 없어 제외"
    ),
}

QUERY_OVERRIDES = {
    "RAGV2-GOLD-0045": (
        "정수기 안쪽에서 실제로 물이 흘러나오고 전원이 켜져 있어요. "
        "지금 어떻게 해야 하나요?"
    ),
    "RAGV2-GOLD-0055": (
        "WPUJAC104DWH 정수기 누수 대응법을 인터넷 FAQ에서 봤는데 "
        "공식 확인 없이 그대로 따라도 될까요?"
    ),
}

PENDING_CONDITIONS: dict[str, list[str]] = {
    **{
        case_id: [COND_NO_WATER_AFTER_FILTER]
        for case_id in (
            "RAGV2-GOLD-0001",
            "RAGV2-GOLD-0008",
            "RAGV2-GOLD-0025",
            "RAGV2-GOLD-0031",
            "RAGV2-GOLD-0039",
        )
    },
    **{
        case_id: [COND_COLD_AFTER_2H]
        for case_id in (
            "RAGV2-GOLD-0002",
            "RAGV2-GOLD-0009",
            "RAGV2-GOLD-0022",
            "RAGV2-GOLD-0030",
            "RAGV2-GOLD-0032",
        )
    },
    **{
        case_id: [COND_LOW_FLOW_AFTER_FILTER]
        for case_id in (
            "RAGV2-GOLD-0006",
            "RAGV2-GOLD-0013",
            "RAGV2-GOLD-0020",
            "RAGV2-GOLD-0023",
            "RAGV2-GOLD-0028",
            "RAGV2-GOLD-0035",
            "RAGV2-GOLD-0038",
        )
    },
    **{
        case_id: [COND_HOT_STEAM_PERSISTS]
        for case_id in (
            "RAGV2-GOLD-0007",
            "RAGV2-GOLD-0014",
            "RAGV2-GOLD-0029",
        )
    },
    "RAGV2-GOLD-0036": [
        COND_COLD_AFTER_2H,
        COND_LOW_FLOW_AFTER_FILTER,
    ],
}

MET_CONDITIONS: dict[str, list[str]] = {
    "RAGV2-GOLD-0015": [COND_NO_WATER_AFTER_FILTER],
    "RAGV2-GOLD-0016": [COND_COLD_AFTER_2H],
}

NO_EVIDENCE_EXECUTION_PATHS = {
    "RAGV2-GOLD-0051": "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
    "RAGV2-GOLD-0052": "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
    "RAGV2-GOLD-0053": "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
    "RAGV2-GOLD-0054": "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
    "RAGV2-GOLD-0055": "POLICY_BLOCK_UNVERIFIED_SOURCE",
    "RAGV2-GOLD-0056": "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
    "RAGV2-GOLD-0057": "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
    "RAGV2-GOLD-0058": "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
    "RAGV2-GOLD-0059": "POLICY_BLOCK_UNSUPPORTED_MODEL",
    "RAGV2-GOLD-0060": "POLICY_BLOCK_UNSUPPORTED_MODEL",
}


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPOSITORY_ROOT / candidate


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL 행은 객체여야 합니다: {path}:{line_number}")
        rows.append(value)
    return rows


def _jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return (
        "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in rows
        )
        + "\n"
    ).encode("utf-8")


def _approved_queries(packet_path: Path) -> dict[str, str | None]:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    reviews = packet.get("reviews")
    if not isinstance(reviews, list):
        raise ValueError("Query revalidation packet의 reviews 배열이 필요합니다")
    queries: dict[str, str | None] = {}
    for review in reviews:
        case_id = review.get("case_id")
        if not isinstance(case_id, str) or case_id in queries:
            raise ValueError("Query revalidation packet의 Case ID가 유일하지 않습니다")
        approved_query = review.get("approved_query")
        if approved_query is not None and not isinstance(approved_query, str):
            raise ValueError(f"approved_query 형식 오류: {case_id}")
        queries[case_id] = approved_query
    return queries


def _mapped_evidence(case_id: str, base: dict[str, Any]) -> tuple[list[str], list[str]]:
    if case_id == "RAGV2-GOLD-0039":
        return [GROUP_NO_WATER], []
    if case_id == "RAGV2-GOLD-0045":
        return [GROUP_LEAK], []
    if case_id == "RAGV2-GOLD-0049":
        return [GROUP_BURNING_ODOR], [GROUP_SPRAY_PREVENTION]
    if case_id == "RAGV2-GOLD-0043":
        return ["UNRESOLVED-EVIDENCE-GROUP-RAGV2-GOLD-0043"], []
    if case_id == "RAGV2-GOLD-0047":
        return ["UNRESOLVED-EVIDENCE-GROUP-RAGV2-GOLD-0047"], []

    required: list[str] = []
    supporting: list[str] = []
    old_ids = [
        evidence.get("evidence_unit_id")
        for evidence in base.get("expected_evidence", [])
    ]
    for old_id in old_ids:
        if old_id == "EVD-WPUJAC104DWH-COLD-TEMPERATURE-001":
            if case_id == "RAGV2-GOLD-0016":
                required.append(GROUP_COLD_FAULT)
                supporting.append(GROUP_COLD_NORMAL)
            else:
                required.append(GROUP_COLD_NORMAL)
                supporting.append(GROUP_COLD_FAULT)
        elif old_id == "EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001":
            required.append(GROUP_HOT_STEAM)
        elif old_id == f"{JAC_DOCUMENT}-P005":
            required.append(
                GROUP_LEAK
                if case_id in {
                    "RAGV2-GOLD-0041",
                    "RAGV2-GOLD-0046",
                    "RAGV2-GOLD-0048",
                }
                else GROUP_BURNING_ODOR
            )
        elif old_id == f"{JAC_DOCUMENT}-P004":
            raise ValueError(f"P004 Case는 명시적 의미 매핑이 필요합니다: {case_id}")
        elif old_id == f"{JAC_DOCUMENT}-P003":
            required.append("UNRESOLVED-EVIDENCE-GROUP-RAGV2-GOLD-0043")
        elif old_id == f"{JAC_DOCUMENT}-P006":
            required.append("UNRESOLVED-EVIDENCE-GROUP-RAGV2-GOLD-0047")
        elif isinstance(old_id, str):
            required.append(old_id)
        else:
            raise ValueError(f"Evidence ID 형식 오류: {case_id}")
    return list(dict.fromkeys(required)), list(dict.fromkeys(supporting))


def _query_for_case(
    case_id: str,
    base_query: str,
    approved_queries: dict[str, str | None],
) -> str:
    if case_id in QUERY_OVERRIDES:
        return QUERY_OVERRIDES[case_id]
    approved_query = approved_queries.get(case_id)
    if isinstance(approved_query, str) and approved_query.strip():
        return approved_query
    if case_id == "RAGV2-GOLD-0040":
        return base_query
    raise ValueError(f"승인 질문이 없습니다: {case_id}")


def _review_note(case_id: str) -> str:
    notes = [
        "Gold v2 Draft이며 TWO_PERSON_APPROVED 전 공식 Metric 사용 금지",
    ]
    if case_id in QUERY_OVERRIDES:
        notes.append("AI 2차 기술 검수 결정에 따른 의미 한정 재작성")
    else:
        notes.append("post-query revalidation packet의 approved_query 사용")
    if case_id in EXCLUDED_REASONS:
        notes.append(EXCLUDED_REASONS[case_id])
    if case_id in PENDING_CONDITIONS:
        notes.append("Source 조건 미충족 상태의 조건부 상담을 Derived Registry로 추적")
    if case_id in MET_CONDITIONS:
        notes.append("질문에서 Source 상담 조건이 이미 충족됨")
    return "; ".join(notes)


def _consultation_fields(
    case_id: str,
    *,
    risk: str,
    outcome: str,
    execution_path: str,
) -> tuple[str, list[str], list[str]]:
    if risk == "danger":
        return "REQUIRED", ["DANGER_SAFETY"], []
    if outcome == "NO_EVIDENCE":
        basis = "NO_EVIDENCE" if execution_path == "PGVECTOR_QUERY" else "POLICY_BLOCK"
        return "REQUIRED", [basis], []
    if case_id in MET_CONDITIONS:
        return "REQUIRED", ["SOURCE_CONDITION_MET"], MET_CONDITIONS[case_id]
    if case_id in PENDING_CONDITIONS:
        return (
            "CONDITIONAL",
            ["SOURCE_CONDITION_PENDING"],
            PENDING_CONDITIONS[case_id],
        )
    return "NONE", ["NONE"], []


def build_cases(
    *,
    base_gold_path: str | Path = BASE_GOLD_PATH,
    query_packet_path: str | Path = QUERY_REVIEW_PACKET_PATH,
) -> list[dict[str, Any]]:
    base_rows = _load_jsonl(_resolve(base_gold_path))
    approved_queries = _approved_queries(_resolve(query_packet_path))
    if len(base_rows) != 60 or len(approved_queries) != 60:
        raise ValueError("Gold v1과 Query Packet은 각각 정확히 60건이어야 합니다")

    base_ids = [str(row.get("case_id")) for row in base_rows]
    expected_ids = [f"RAGV2-GOLD-{index:04d}" for index in range(1, 61)]
    if base_ids != expected_ids or set(approved_queries) != set(expected_ids):
        raise ValueError("기존 60개 Case ID와 Query Packet Case ID가 일치하지 않습니다")

    cases: list[dict[str, Any]] = []
    for base in base_rows:
        case_id = str(base["case_id"])
        required, supporting = _mapped_evidence(case_id, base)
        no_evidence = case_id in NO_EVIDENCE_EXECUTION_PATHS
        outcome = "NO_EVIDENCE" if no_evidence else "EVIDENCE"
        execution_path = NO_EVIDENCE_EXECUTION_PATHS.get(case_id, "PGVECTOR_QUERY")

        if no_evidence:
            required, supporting = [], []
            risk, usage = "caution", "PENDING_CONSULTATION"
        elif case_id in {
            "RAGV2-GOLD-0007",
            "RAGV2-GOLD-0014",
            "RAGV2-GOLD-0029",
        }:
            risk, usage = "caution", "PARTIAL_STOP"
        else:
            risk = str(base["expected_risk_level"])
            usage = str(base["expected_guidance_policy"])

        consultation, basis_codes, condition_ids = _consultation_fields(
            case_id,
            risk=risk,
            outcome=outcome,
            execution_path=execution_path,
        )
        product_model_code = str(base["product_model_code"])
        forbidden_models = [
            value
            for value in base.get("forbidden_model_codes", [])
            if value != product_model_code
        ]
        forbidden_documents = list(base.get("forbidden_document_ids", []))
        if product_model_code == JAC_MODEL:
            forbidden_documents = [
                value for value in forbidden_documents if value != JAC_DOCUMENT
            ]

        match_policy = "NONE" if no_evidence else (
            "ALL" if len(required) > 1 else "ANY"
        )
        query_variant_type = (
            "DIRECT" if case_id == "RAGV2-GOLD-0039"
            else str(base["query_variant_type"])
        )
        cases.append({
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "dataset_version": DATASET_VERSION,
            "evaluation_status": (
                "EXCLUDED" if case_id in EXCLUDED_REASONS else "ACTIVE"
            ),
            "split": base["split"],
            "query_variant_type": query_variant_type,
            "query": _query_for_case(
                case_id,
                str(base["query"]),
                approved_queries,
            ),
            "product_model_code": product_model_code,
            "expected_retrieval_outcome": outcome,
            "expected_execution_path": execution_path,
            "required_evidence_group_ids": required,
            "supporting_evidence_group_ids": supporting,
            "evidence_match_policy": match_policy,
            "expected_risk_level": risk,
            "expected_usage_guidance_status": usage,
            "expected_consultation_requirement": consultation,
            "consultation_basis_codes": basis_codes,
            "consultation_condition_ids": condition_ids,
            "forbidden_document_ids": sorted(set(forbidden_documents)),
            "forbidden_model_codes": sorted(set(forbidden_models)),
            "source_query_origin": base["source_query_origin"],
            "source_case_ids": base["source_case_ids"],
            "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
            "review_status": "UNREVIEWED_DRAFT",
            "reviewer_ids": [],
            "review_notes": _review_note(case_id),
        })

    if Counter(case["evaluation_status"] for case in cases) != {
        "ACTIVE": 55,
        "EXCLUDED": 5,
    }:
        raise ValueError("Gold v2 상태 분포는 ACTIVE 55 / EXCLUDED 5여야 합니다")
    return cases


def build_iac425_candidates(
    source_path: str | Path = IAC425_SOURCE_PATH,
) -> list[dict[str, Any]]:
    source = json.loads(_resolve(source_path).read_text(encoding="utf-8"))
    candidates = source.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 18:
        raise ValueError("IAC425 Gold 후보는 정확히 18건이어야 합니다")

    output: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        source_candidate_id = str(candidate["candidate_id"])
        expected_source_candidate_id = f"RAGV2-IAC425-CAND-{index:03d}"
        if source_candidate_id != expected_source_candidate_id:
            raise ValueError(
                "IAC425 후보 ID 순서가 예상과 다릅니다: "
                f"{source_candidate_id} != {expected_source_candidate_id}"
            )
        variants = candidate.get("expected_evidence_variants", [])
        group_ids = list(dict.fromkeys(
            str(variant["evidence_unit_id"]) for variant in variants
        ))
        condition_ids = [
            IAC425_CONDITION_BY_GROUP[group_id]
            for group_id in group_ids
            if group_id in IAC425_CONDITION_BY_GROUP
        ]
        proposed_risk = str(candidate["proposed_risk_level"])
        if source_candidate_id == "RAGV2-IAC425-CAND-002":
            consultation = "REQUIRED"
            basis_codes = ["SOURCE_CONDITION_MET"]
        elif proposed_risk == "danger":
            consultation = "REQUIRED"
            basis_codes = ["DANGER_SAFETY"]
            condition_ids = []
        elif condition_ids:
            consultation = "CONDITIONAL"
            basis_codes = ["SOURCE_CONDITION_PENDING"]
        else:
            consultation = "NONE"
            basis_codes = ["NONE"]

        source_usage = str(candidate["proposed_guidance_policy"])
        usage = "NORMAL" if source_usage == "PENDING_CONSULTATION" else source_usage
        if proposed_risk == "danger":
            usage = "TOTAL_STOP"
        source_child_ids = list(dict.fromkeys(
            str(variant["child_id"]) for variant in variants
        ))
        review_notes = [
            "IAC425 별도 Candidate Diagnostic이며 rag_gold_v2 본체에 포함하지 않음",
            f"source_candidate_id={source_candidate_id}",
            f"source_case_id={candidate['source_case_id']}",
            f"source_child_ids={','.join(source_child_ids)}",
            "TWO_PERSON_APPROVED 전 공식 Metric 사용 금지",
        ]
        if source_candidate_id in IAC425_QUERY_OVERRIDES:
            review_notes.append("관찰 가능 증상과 Source 조건을 드러내도록 질문 재작성")
        if source_candidate_id == "RAGV2-IAC425-CAND-015":
            review_notes.append(
                "소음 지속·크기 조건은 현 trigger enum으로 표현하지 않아 상담 조건 미채점"
            )
        output.append({
            "schema_version": SCHEMA_VERSION,
            "case_id": f"RAGV2-GOLD-{index + 60:04d}",
            "dataset_version": DATASET_VERSION,
            "evaluation_status": "ACTIVE",
            "split": candidate["proposed_split"],
            "query_variant_type": candidate["query_variant_type"],
            "query": IAC425_QUERY_OVERRIDES.get(
                source_candidate_id,
                str(candidate["query"]),
            ),
            "product_model_code": candidate["product_model_code"],
            "expected_retrieval_outcome": "EVIDENCE",
            "expected_execution_path": "PGVECTOR_QUERY",
            "required_evidence_group_ids": group_ids,
            "supporting_evidence_group_ids": [],
            "evidence_match_policy": "ANY",
            "expected_risk_level": proposed_risk,
            "expected_usage_guidance_status": usage,
            "expected_consultation_requirement": consultation,
            "consultation_basis_codes": basis_codes,
            "consultation_condition_ids": condition_ids,
            "forbidden_document_ids": [],
            "forbidden_model_codes": sorted(set(
                str(model_code)
                for model_code in candidate["forbidden_model_codes"]
                if model_code != candidate["product_model_code"]
            )),
            "source_query_origin": "CURATED_VARIANT",
            "source_case_ids": [],
            "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
            "review_status": "UNREVIEWED_DRAFT",
            "reviewer_ids": [],
            "review_notes": "; ".join(review_notes),
        })
    return output


def _iac425_candidate_manifest(
    candidates: list[dict[str, Any]],
    *,
    candidate_path: Path,
) -> dict[str, Any]:
    condition_ids = sorted({
        condition_id
        for candidate in candidates
        for condition_id in candidate["consultation_condition_ids"]
    })
    return {
        "dataset_id": "RAG-GOLD-V2-IAC425-CANDIDATE-DIAGNOSTIC",
        "dataset_version": DATASET_VERSION,
        "status": "HUMAN_REVIEW_PENDING_NOT_IN_MAIN_GOLD",
        "generated_at": "2026-08-26T00:00:00+09:00",
        "official_metrics_publishable": False,
        "included_in_main_gold_records": 0,
        "dataset": {
            "path": _display_path(candidate_path),
            "records": len(candidates),
            "active_records": sum(
                candidate["evaluation_status"] == "ACTIVE"
                for candidate in candidates
            ),
            "sha256": file_sha256(candidate_path),
        },
        "schema": {
            "path": SCHEMA_PATH,
            "sha256": file_sha256(_resolve(SCHEMA_PATH)),
        },
        "evidence_group_registry": {
            "path": EVIDENCE_GROUP_REGISTRY_PATH,
            "sha256": file_sha256(_resolve(EVIDENCE_GROUP_REGISTRY_PATH)),
        },
        "condition_ids": condition_ids,
        "source": {
            "path": IAC425_SOURCE_PATH,
            "sha256": file_sha256(_resolve(IAC425_SOURCE_PATH)),
        },
        "review_policy": {
            "required_reviewer_count": 2,
            "current_approved_active_records": 0,
            "automatic_label_approval": False,
            "main_gold_merge": "BLOCKED",
            "official_metric_use": "BLOCKED",
            "diagnostic_use": "READY_AFTER_STRUCTURAL_AND_COMPATIBILITY_QA",
        },
    }


def _distribution(cases: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    fields = (
        "evaluation_status",
        "query_variant_type",
        "split",
        "expected_retrieval_outcome",
        "expected_execution_path",
        "review_status",
    )
    return {
        field: dict(sorted(Counter(str(case[field]) for case in cases).items()))
        for field in fields
    }


def _manifest(
    cases: list[dict[str, Any]],
    iac_candidates: list[dict[str, Any]],
    *,
    dataset_path: Path,
    iac_output_path: Path,
    iac_manifest_path: Path,
) -> dict[str, Any]:
    source_paths = [
        BASE_GOLD_PATH,
        QUERY_REVIEW_PACKET_PATH,
        IAC425_SOURCE_PATH,
        EVIDENCE_GROUP_REGISTRY_PATH,
        CHILD_REGISTRY_PATH,
        CORPUS_PATH,
    ]
    return {
        "dataset_id": "RAG-GOLD-V2",
        "dataset_version": DATASET_VERSION,
        "status": "DRAFT_REVIEW_REQUIRED",
        "generated_at": "2026-08-26T00:00:00+09:00",
        "official_metrics_publishable": False,
        "dataset": {
            "path": _display_path(dataset_path),
            "records": len(cases),
            "active_records": sum(
                case["evaluation_status"] == "ACTIVE" for case in cases
            ),
            "excluded_records": sum(
                case["evaluation_status"] == "EXCLUDED" for case in cases
            ),
            "sha256": file_sha256(dataset_path),
        },
        "schema": {
            "path": SCHEMA_PATH,
            "sha256": file_sha256(_resolve(SCHEMA_PATH)),
        },
        "iac425_candidates": {
            "path": _display_path(iac_output_path),
            "records": len(iac_candidates),
            "included_in_gold_records": 0,
            "sha256": file_sha256(iac_output_path),
            "manifest_path": _display_path(iac_manifest_path),
            "manifest_sha256": file_sha256(iac_manifest_path),
            "official_metrics_publishable": False,
        },
        "distribution": _distribution(cases),
        "excluded_case_ids": sorted(EXCLUDED_REASONS),
        "condition_contract": {
            "registry_path": EVIDENCE_GROUP_REGISTRY_PATH,
            "condition_ids": [
                COND_NO_WATER_AFTER_FILTER,
                COND_COLD_AFTER_2H,
                COND_LOW_FLOW_AFTER_FILTER,
                COND_HOT_STEAM_PERSISTS,
            ],
            "noise_severity_status": "EXCLUDED_PENDING_TRIGGER_SCHEMA",
        },
        "source_files": [
            {"path": path, "sha256": file_sha256(_resolve(path))}
            for path in source_paths
        ],
        "approval_policy": {
            "required_reviewer_count": 2,
            "current_approved_active_records": 0,
            "automatic_label_approval": False,
            "official_metric_use": "BLOCKED",
            "note": "ACTIVE는 Draft 평가 대상이며 사람 2인 승인과 동일하지 않음",
        },
        "provenance": {
            "full_corpus_v3_data_commit": (
                "15577db51795eec63f2eab9dc34d5ef23b7c9bf1"
            ),
            "query_source": "post-query revalidation packet approved_query",
            "case_id_policy": "PRESERVE_RAGV2_GOLD_0001_TO_0060",
        },
    }


def write_outputs(
    *,
    output_dataset: str | Path = OUTPUT_DATASET,
    output_manifest: str | Path = OUTPUT_MANIFEST,
    output_iac425_candidates: str | Path = OUTPUT_IAC425_CANDIDATES,
    output_iac425_candidate_manifest: str | Path = (
        OUTPUT_IAC425_CANDIDATE_MANIFEST
    ),
    base_gold_path: str | Path = BASE_GOLD_PATH,
    query_packet_path: str | Path = QUERY_REVIEW_PACKET_PATH,
    iac425_source_path: str | Path = IAC425_SOURCE_PATH,
) -> dict[str, Any]:
    cases = build_cases(
        base_gold_path=base_gold_path,
        query_packet_path=query_packet_path,
    )
    iac_candidates = build_iac425_candidates(iac425_source_path)
    dataset_path = _resolve(output_dataset)
    iac_output_path = _resolve(output_iac425_candidates)
    iac_manifest_path = _resolve(output_iac425_candidate_manifest)
    manifest_path = _resolve(output_manifest)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    iac_output_path.parent.mkdir(parents=True, exist_ok=True)
    iac_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_bytes(_jsonl_bytes(cases))
    iac_output_path.write_bytes(_jsonl_bytes(iac_candidates))
    iac_manifest = _iac425_candidate_manifest(
        iac_candidates,
        candidate_path=iac_output_path,
    )
    iac_manifest_path.write_text(
        json.dumps(iac_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = _manifest(
        cases,
        iac_candidates,
        dataset_path=dataset_path,
        iac_output_path=iac_output_path,
        iac_manifest_path=iac_manifest_path,
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Gold Evaluation Dataset v2 Builder")
    parser.add_argument("--output-dataset", default=OUTPUT_DATASET)
    parser.add_argument("--output-manifest", default=OUTPUT_MANIFEST)
    parser.add_argument(
        "--output-iac425-candidates",
        default=OUTPUT_IAC425_CANDIDATES,
    )
    parser.add_argument(
        "--output-iac425-candidate-manifest",
        default=OUTPUT_IAC425_CANDIDATE_MANIFEST,
    )
    args = parser.parse_args()
    manifest = write_outputs(
        output_dataset=args.output_dataset,
        output_manifest=args.output_manifest,
        output_iac425_candidates=args.output_iac425_candidates,
        output_iac425_candidate_manifest=(
            args.output_iac425_candidate_manifest
        ),
    )
    print(json.dumps({
        "status": manifest["status"],
        "records": manifest["dataset"]["records"],
        "active_records": manifest["dataset"]["active_records"],
        "excluded_records": manifest["dataset"]["excluded_records"],
        "iac425_candidate_records": manifest["iac425_candidates"]["records"],
        "official_metrics_publishable": manifest["official_metrics_publishable"],
        "dataset_sha256": manifest["dataset"]["sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
