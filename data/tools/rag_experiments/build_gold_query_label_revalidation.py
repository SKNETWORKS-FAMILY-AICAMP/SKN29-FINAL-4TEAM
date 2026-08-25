"""확정된 Gold 질문을 원본 라벨과 다시 대조한 검수 패킷을 생성한다."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
GENERATED_AT = "2026-08-24T00:00:00+09:00"
GOLD_PATH = "ai/evaluation/datasets/gold/rag_gold_v1.jsonl"
QUERY_PROPOSAL_PATH = "data/config/rag/gold_v1_query_rewrite_proposals.json"
QUERY_REVIEW_PATH = (
    "data/processed/validation/rag_experiments/"
    "gold_v1_query_human_review_working.json"
)
PRIMARY_PACKET_PATH = (
    "data/processed/validation/rag_experiments/gold_v1_primary_review_packet.json"
)
DEFAULT_OUTPUT = (
    "data/processed/validation/rag_experiments/"
    "gold_v1_post_query_label_revalidation_packet.json"
)
EXPECTED_GOLD_SHA256 = (
    "9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A"
)


CHANGE_PROPOSALS: dict[str, list[dict[str, Any]]] = {
    "RAGV2-GOLD-0001": [
        {
            "field": "expected_guidance_policy",
            "current_value": "PARTIAL_STOP",
            "proposed_value": "PENDING_CONSULTATION",
            "reason": "확정 질문이 자가 점검보다 빠른 수리 요청을 명시하므로 상담 전환 의도를 반영한다.",
            "evidence_basis": ["EVD-WPUJAC104DWH-NO-WATER-001"],
        }
    ],
    "RAGV2-GOLD-0016": [
        {
            "field": "expected_guidance_policy",
            "current_value": "NORMAL",
            "proposed_value": "PENDING_CONSULTATION",
            "reason": "전원 정상 상태에서 2시간이 지나도 냉수가 차갑지 않으면 매뉴얼이 상담을 안내한다.",
            "evidence_basis": ["EVD-WPUJAC104DWH-COLD-TEMPERATURE-001"],
        }
    ],
    "RAGV2-GOLD-0017": [
        {
            "field": "expected_guidance_policy",
            "current_value": "NORMAL",
            "proposed_value": "PENDING_CONSULTATION",
            "reason": "확정 질문은 정상 팬 소리가 아니라 너무 큰 소리를 명시하며 매뉴얼의 상담 조건에 해당한다.",
            "evidence_basis": ["EVD-WPUJAC104DWH-NOISE-001"],
        }
    ],
    "RAGV2-GOLD-0028": [
        {
            "field": "expected_guidance_policy",
            "current_value": "NORMAL",
            "proposed_value": "PENDING_CONSULTATION",
            "reason": "확정 질문이 저유량 자가 점검이 아니라 서비스 주체의 조치를 직접 요구한다.",
            "evidence_basis": ["EVD-WPUJAC104DWH-LOW-FLOW-001"],
        }
    ],
    "RAGV2-GOLD-0033": [
        {
            "field": "expected_guidance_policy",
            "current_value": "NORMAL",
            "proposed_value": "PENDING_CONSULTATION",
            "reason": "확정 질문의 핵심은 단순 작동음이 아니라 매우 큰 소리와 고장 여부이며 매뉴얼은 과도한 소음을 상담으로 전환한다.",
            "evidence_basis": ["EVD-WPUJAC104DWH-NOISE-001"],
        }
    ],
    "RAGV2-GOLD-0039": [
        {
            "field": "query_variant_type",
            "current_value": "COMPOUND",
            "proposed_value": "DIRECT",
            "reason": "작동 소리는 별도 이상 증상이 아니라 버튼 입력에 대한 상황 설명으로 확정됐다.",
            "evidence_basis": ["EVD-WPUJAC104DWH-NO-WATER-001"],
        },
        {
            "field": "expected_evidence/evidence_match_policy",
            "current_value": {
                "evidence_unit_ids": [
                    "EVD-WPUJAC104DWH-NO-WATER-001",
                    "EVD-WPUJAC104DWH-NOISE-001",
                ],
                "policy": "ALL",
            },
            "proposed_value": {
                "evidence_unit_ids": ["EVD-WPUJAC104DWH-NO-WATER-001"],
                "policy": "ANY",
            },
            "reason": "질문이 요구하는 답은 무출수 점검이며 소음 Evidence를 반드시 만족시킬 이유가 없어졌다.",
            "evidence_basis": ["EVD-WPUJAC104DWH-NO-WATER-001"],
        },
    ],
    "RAGV2-GOLD-0047": [
        {
            "field": "expected_risk_level/expected_guidance_policy",
            "current_value": {"risk": "danger", "guidance": "TOTAL_STOP"},
            "proposed_value": {"risk": "caution", "guidance": "PARTIAL_STOP"},
            "reason": "확정 질문은 사고 발생 후 전면 중단 상황이 아니라 아이의 접촉을 예방하는 사용법 질문이다. 화상 주의는 유지하고 온수 기능에 한정한 사용 제한으로 낮춘다.",
            "evidence_basis": ["MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P006"],
        }
    ],
}

SAFETY_SOURCE_CHECK_CASES = {
    f"RAGV2-GOLD-{number:04d}" for number in (41, 42, 43, 44, 45, 46, 48, 49, 50)
}
NO_EVIDENCE_SOURCE_CHECK_CASES = {
    f"RAGV2-GOLD-{number:04d}" for number in range(51, 61)
}

SOURCE_CHECK_PROPOSALS: dict[str, list[dict[str, Any]]] = {
    "RAGV2-GOLD-0045": [
        {
            "field": "expected_evidence/evidence_match_policy",
            "current_value": {
                "evidence_unit_ids": ["MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P004"],
                "policy": "ANY",
            },
            "proposed_value": {
                "evidence_unit_ids": [
                    "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P004",
                    "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P005",
                ],
                "policy": "ALL",
            },
            "reason": "1차 검수자의 0045-B 결정을 반영한 조건부 제안이다. P004의 물 유입 위험과 P005의 사고 후 조치를 원본 화면에서 함께 확인해야 한다.",
            "evidence_basis": [
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P004",
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P005",
            ],
        }
    ],
    "RAGV2-GOLD-0049": [
        {
            "field": "expected_evidence/evidence_match_policy",
            "current_value": {
                "evidence_unit_ids": ["MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P004"],
                "policy": "ANY",
            },
            "proposed_value": {
                "evidence_unit_ids": [
                    "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P004",
                    "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P005",
                ],
                "policy": "ALL",
            },
            "reason": "0049-H-B로 질문을 정수기에서 타는 냄새가 나는 상황으로 명확히 교정했다. P004의 살충제 사용 위험과 P005의 사고 후 조치를 모두 요구한다.",
            "evidence_basis": [
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P004",
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P005",
            ],
        }
    ],
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(output_path: Path) -> dict[str, Any]:
    gold_path = REPOSITORY_ROOT / GOLD_PATH
    proposal_path = REPOSITORY_ROOT / QUERY_PROPOSAL_PATH
    query_review_path = REPOSITORY_ROOT / QUERY_REVIEW_PATH
    primary_packet_path = REPOSITORY_ROOT / PRIMARY_PACKET_PATH
    if _sha256(gold_path) != EXPECTED_GOLD_SHA256:
        raise RuntimeError("Gold source hash changed; label revalidation aborted")

    gold = {row["case_id"]: row for row in _read_jsonl(gold_path)}
    proposals = {
        row["case_id"]: row
        for row in _read_json(proposal_path)["proposals"]
    }
    query_review = _read_json(query_review_path)
    decisions = {row["case_id"]: row for row in query_review["decisions"]}
    primary_context = {
        row["case_id"]: row["source_review_context"]
        for row in _read_json(primary_packet_path)["reviews"]
    }
    if not (set(gold) == set(proposals) == set(decisions) == set(primary_context)):
        raise RuntimeError("Gold/query review/primary packet case sets differ")

    reviews: list[dict[str, Any]] = []
    for case_id in sorted(gold):
        source = gold[case_id]
        decision = decisions[case_id]
        proposed_changes = CHANGE_PROPOSALS.get(
            case_id, SOURCE_CHECK_PROPOSALS.get(case_id, [])
        )
        if decision["decision"] == "QUERY_REJECTION_PROPOSED":
            assessment = "REJECT_PROPOSED"
            priority = "HIGH"
            reason = "1차 검수자가 질문 제외를 제안했다. 원본 삭제나 평가 제외는 두 번째 검수자와 AI 담당자 승인 전까지 확정하지 않는다."
            required = ["QUERY_REJECTION_DECISION"]
        elif case_id in CHANGE_PROPOSALS:
            assessment = "CHANGE_PROPOSED"
            priority = "HIGH"
            reason = "확정 질문의 의미와 원본 Gold 라벨 사이에 수정이 필요한 차이가 확인됐다."
            required = ["PROPOSED_LABEL_CHANGE_DECISION"]
        elif case_id in SAFETY_SOURCE_CHECK_CASES:
            assessment = "SOURCE_CHECK_REQUIRED"
            priority = "HIGH"
            reason = "안전 질문의 근거와 조치 강도는 매뉴얼 원본 화면을 사람이 직접 대조해야 확정할 수 있다."
            required = ["ORIGINAL_PAGE_VISUAL_CONFIRMATION"]
        elif case_id in NO_EVIDENCE_SOURCE_CHECK_CASES:
            assessment = "SOURCE_CHECK_REQUIRED"
            priority = "HIGH"
            reason = "검색 Corpus 전체에 답이 없다는 판정은 자동 검사가 아니라 사람이 질문 의미와 검색 범위를 확인해야 한다."
            required = ["NO_EVIDENCE_CORPUS_ABSENCE"]
        else:
            assessment = "SUPPORTED"
            priority = "MEDIUM" if source["query_variant_type"] == "COMPOUND" else "NORMAL"
            reason = "확정 질문을 기준으로 Evidence 의미, 정책, 위험도와 안내 정책을 다시 대조했으며 변경 사유를 찾지 못했다."
            required = []

        if case_id in {"RAGV2-GOLD-0036", "RAGV2-GOLD-0037", "RAGV2-GOLD-0038"}:
            required.append("COMPOUND_ALL_EVIDENCE_CONFIRMATION")
        if case_id in SOURCE_CHECK_PROPOSALS:
            required.append("CONDITIONAL_EVIDENCE_CHANGE_DECISION")
        required.extend(
            [
                "RISK_AND_GUIDANCE_APPROPRIATENESS",
                "RECORD_SECOND_REVIEWER_DECISION_AND_REVIEWED_AT",
            ]
        )

        reviews.append(
            {
                "case_id": case_id,
                "approved_query": decision["approved_query"],
                "query_decision": decision["decision"],
                "intent_change": proposals[case_id]["intent_change"],
                "assistant_assessment": assessment,
                "assistant_reason": reason,
                "review_priority": priority,
                "human_signoff_status": "PENDING",
                "current_labels": {
                    "query_variant_type": source["query_variant_type"],
                    "expected_no_evidence": source["expected_no_evidence"],
                    "evidence_match_policy": source["evidence_match_policy"],
                    "expected_evidence": source["expected_evidence"],
                    "expected_risk_level": source["expected_risk_level"],
                    "expected_guidance_policy": source["expected_guidance_policy"],
                },
                "proposed_changes": proposed_changes,
                "source_review_context": primary_context[case_id],
                "required_human_checks": required,
            }
        )

    counts = Counter(row["assistant_assessment"] for row in reviews)
    packet = {
        "schema_version": "1.0.0",
        "status": "GOLD_POST_QUERY_LABEL_REVALIDATION_READY_HUMAN_SIGNOFF_PENDING",
        "generated_at": GENERATED_AT,
        "source_dataset": {
            "path": GOLD_PATH,
            "sha256": EXPECTED_GOLD_SHA256,
            "record_count": len(gold),
        },
        "source_query_proposals": {
            "path": QUERY_PROPOSAL_PATH,
            "sha256": _sha256(proposal_path),
        },
        "source_query_review": {
            "path": QUERY_REVIEW_PATH,
            "sha256": _sha256(query_review_path),
            "status": query_review["status"],
        },
        "summary": {
            "assessment_counts": dict(sorted(counts.items())),
            "reviewed_records": len(reviews),
            "human_signed_records": 0,
            "human_signoff_status": "PENDING",
            "automatic_gold_update": False,
        },
        "reviews": reviews,
    }
    _write_json(output_path, packet)
    return packet


def main() -> int:
    packet = build(REPOSITORY_ROOT / DEFAULT_OUTPUT)
    print(json.dumps(packet["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
