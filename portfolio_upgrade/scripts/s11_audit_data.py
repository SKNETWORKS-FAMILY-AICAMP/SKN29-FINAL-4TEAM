"""S11: offline, read-only-on-inputs audit of the *unapproved* WaterBridge train draft.

Run from the repository root:
  python portfolio_upgrade/scripts/s11_audit_data.py --check
  python portfolio_upgrade/scripts/s11_audit_data.py --write

This script does NOT produce training examples, access Holdout/Dev, call a model,
fetch PDFs, decide copyright permissions, or modify the existing S07/S09 files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIN_REL = "portfolio_upgrade/data/training/train_draft_s07_reviewed_v1.jsonl"
PREVIEW_REL = "portfolio_upgrade/experiments/m2_training_readiness/s09_train_retrieval_preview.jsonl"
REVIEW_REL = "portfolio_upgrade/experiments/m2_training_readiness/m2_retrieval_review_26.json"
OUT_REL = "portfolio_upgrade/experiments/s11_readiness"
ACTIONS = {"ANSWER", "ASK", "ESCALATE", "EXPLAIN_UNSUPPORTED"}
CATEGORIES = {"추가 근거", "순위 위험", "부분 누락", "조건 검토", "구조 통과"}

# Explicit proposals from the earlier M2 human review, not newly verified PDF claims.
FIX_ACTIONS = {
    "SYN-IAC425-101": "냉수 잠금 해제 상세 절차(p.27)가 실제 검색 근거로 제공되는지 확인",
    "SYN-IAC606-101": "냉수 잠금 해제 상세 절차(p.24)가 실제 검색 근거로 제공되는지 확인; p.40의 오기 교차 참조 주의",
    "SYN-IAC425-108": "물받이 넘침 확인(p.5)과 누수 안전 안내(p.45)가 함께 제공되는지 확인",
    "SYN-IAC606-104": "BASE의 냉매 순환/제상 관련 Gold 누락과 답변 지시 사이의 불일치 해결",
    "SYN-JAC104-028": "PAR1 소음 질문에서 무관한 온수 근거가 먼저 오는 현상 재평가",
    "SYN-JAC104-026": "PAR1 냉수 질문에서 온수 안전 근거가 먼저 오는 현상 재평가",
    "SYN-IAC425-103": "일시적인 온도 변화와 2시간 지속 이상을 구별하는 후보 순위·답변 조건 재평가",
    "SYN-JAC104-027": "2시간 경과·지속 이상 조건을 정답·검색 근거·재표현에서 모두 확인",
}
CATEGORY_PRIORITY = {"부분 누락": "P1", "추가 근거": "P1", "순위 위험": "P2", "조건 검토": "P2", "구조 통과": "P3"}
CATEGORY_STATUS = {
    "부분 누락": "Gold 누락 가능성; BASE/PAR1 실제 누락 여부 각각 확인",
    "추가 근거": "필요 조치가 검색 본문에 없는 것으로 수동 검토됨",
    "순위 위험": "Top-1에 무관한 근거가 먼저 올 가능성",
    "조건 검토": "조건부 조치의 전제 누락·혼합 위험",
    "구조 통과": "이전 수동 검토의 구조 점검 통과; 학습 승인 아님",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def ensure_unique(rows: list[dict], key: str, where: str) -> dict[str, dict]:
    ids = [r.get(key) for r in rows]
    if None in ids or len(set(ids)) != len(ids):
        raise ValueError(f"{where}: {key} 누락·중복")
    return {r[key]: r for r in rows}


def verify_and_summarize(train: list[dict], preview: list[dict], review: dict, hashes: dict[str, str]):
    if len(train) != 26 or len(preview) != 26 or len(review.get("cases", [])) != 26:
        raise ValueError("S07/S09/M2 검수는 각각 26행이어야 합니다")
    a = ensure_unique(train, "example_id", "S07")
    b = ensure_unique(preview, "example_id", "S09")
    c = ensure_unique(review["cases"], "example_id", "M2")
    if set(a) != set(b) or set(a) != set(c):
        raise ValueError("S07/S09/M2 example_id 목록이 일치하지 않습니다")
    expected_sha = review.get("summary", {}).get("raw_file_sha256")
    if expected_sha and hashes["s09_preview"] != expected_sha:
        raise ValueError("S09 검색 미리보기 SHA-256이 M2 검수 기록과 다릅니다. 재검수 전에는 진행하지 마세요.")
    per_action, per_category = Counter(), Counter()
    source_cases: dict[str, list[dict]] = defaultdict(list)
    action_sources: dict[str, set[str]] = defaultdict(set)
    semantic_to_actions: dict[str, set[str]] = defaultdict(set)
    at_least_one, all_gold, valid_id_membership = 0, 0, 0
    for ex_id, r in a.items():
        p, v = b[ex_id], c[ex_id]
        source_id = r["provenance"]["source_scenario_id"]
        group = r["provenance"]["semantic_group_id"]
        action = r["target"]["action"]
        if action not in ACTIONS:
            raise ValueError(f"{ex_id}: 행동 라벨 미지원: {action}")
        if r["provenance"].get("split") != "train" or p["audit_only"].get("split") != "train" or v.get("split") != "train":
            raise ValueError(f"{ex_id}: train 이외 분할 발견")
        if source_id != p["audit_only"].get("source_scenario_id") or source_id != v.get("source_scenario_id"):
            raise ValueError(f"{ex_id}: 원본 시나리오 불일치")
        if group != p["audit_only"].get("semantic_group_id"):
            raise ValueError(f"{ex_id}: 의미 그룹 불일치")
        if action != v.get("expected_action"):
            raise ValueError(f"{ex_id}: 행동 라벨 불일치")
        if p.get("status") != "PREVIEW_NOT_TRAIN_READY":
            raise ValueError(f"{ex_id}: 검수용 상태만 허용합니다")
        if r.get("review", {}).get("training_ready") is not False or r.get("s07", {}).get("training_ready") is not False:
            raise ValueError(f"{ex_id}: 학습 승인 상태 변경. 권리·근거 재검토 필요")
        if r.get("s07", {}).get("source_use_approved_for_training") is not False:
            raise ValueError(f"{ex_id}: 사용 승인 상태 변경. 근거 서류 검토 후 별도 결정 필요")
        if p["audit_only"].get("data_use_authorized_for_sft") is not False or p["audit_only"].get("training_ready") is not False:
            raise ValueError(f"{ex_id}: 미리보기의 학습 금지 상태가 바뀌었습니다")
        if len(p.get("messages", [])) != 3 or [x.get("role") for x in p["messages"]] != ["system", "user", "assistant"]:
            raise ValueError(f"{ex_id}: 메시지 구조 오류")
        user_content = p["messages"][1]["content"]
        if "gold_evidence_ids" in user_content or "audit_only" in user_content:
            raise ValueError(f"{ex_id}: 모델 입력으로 평가 Gold/감사 필드 누출")
        user_obj = json.loads(user_content)
        target = json.loads(p["messages"][2]["content"])
        if not {"action", "customer_message", "cited_evidence_ids", "missing_fields"}.issubset(target):
            raise ValueError(f"{ex_id}: JSON 출력 필수 필드 누락")
        if target.get("action") != action or target.get("customer_message") != r["target"].get("assistant_message"):
            raise ValueError(f"{ex_id}: 학습 목표와 검수된 정답 불일치")
        if user_obj.get("customer_message") != r["input"].get("customer_message") or user_obj.get("product_code") != r["input"].get("product_code"):
            raise ValueError(f"{ex_id}: 입력 고객 발화·제품 코드 불일치")
        retrieved = [x["id"] for x in user_obj.get("retrieved_evidence", [])]
        gold = set(r["provenance"].get("gold_evidence_ids", []))
        if not retrieved or len(retrieved) != len(set(retrieved)):
            raise ValueError(f"{ex_id}: 검색 근거가 없거나 ID 중복")
        if gold != set(v.get("gold_evidence_ids", [])) or retrieved != v.get("retrieved_evidence_ids", []):
            raise ValueError(f"{ex_id}: S09 근거와 기존 M2 검수 기록이 다름")
        if set(retrieved).intersection(gold):
            at_least_one += 1
        if gold.issubset(set(retrieved)):
            all_gold += 1
        if set(target["cited_evidence_ids"]).issubset(set(retrieved)):
            valid_id_membership += 1
        category = v.get("review_category")
        if category not in CATEGORIES:
            raise ValueError(f"{ex_id}: 알 수 없는 기존 검수 분류: {category}")
        source_cases[source_id].append({"id": ex_id, "action": action, "group": group, "variant":r["s07"]["variant_kind"], "first_gold_rank": v.get("first_gold_rank"), "missing_gold": sorted(gold.difference(retrieved)), "category": category, "review_note":v.get("review_note", "")})
        per_action[action] += 1
        per_category[category] += 1
        action_sources[action].add(source_id)
        semantic_to_actions[group].add(action)
    if len(source_cases) != 13 or len(semantic_to_actions) != 6:
        raise ValueError("예상한 원본 13 / 의미 그룹 6 구조가 아닙니다")
    if any(len(cases) != 2 or {x["variant"] for x in cases} != {"source", "paraphrase"} for cases in source_cases.values()):
        raise ValueError("원본 및 재표현은 반드시 시나리오별 1쌍이어야 합니다")
    queue = []
    category_source_count = Counter()
    for source_id, cases in sorted(source_cases.items()):
        source_categories = {x["category"] for x in cases}
        if len(source_categories) != 1:
            raise ValueError(f"{source_id}: 원본/재표현의 검수 분류가 서로 다릅니다")
        cat = next(iter(source_categories))
        category_source_count[cat] += 1
        base = next(x for x in cases if x["variant"] == "source")
        para = next(x for x in cases if x["variant"] == "paraphrase")
        queue.append({
            "priority":CATEGORY_PRIORITY[cat],
            "scenario_id":source_id,
            "semantic_group_id":base["group"],
            "expected_action":base["action"],
            "review_category_from_m2":cat,
            "base_first_gold_rank":base["first_gold_rank"],
            "paraphrase_first_gold_rank":para["first_gold_rank"],
            "base_missing_gold_ids":";".join(base["missing_gold"]),
            "paraphrase_missing_gold_ids":";".join(para["missing_gold"]),
            "risk_explanation":CATEGORY_STATUS[cat],
            "required_followup":FIX_ACTIONS.get(source_id, "기존 검수 결과와 실제 근거·필수 조치를 재확인"),
            "human_review_note_from_m2":base["review_note"],
            "training_approved":"NO",
        })
    queue.sort(key=lambda x: (int(x["priority"][1:]),x["scenario_id"]))
    blocks = [
        "매뉴얼 유래 자료의 학습 목적 이용 근거가 미확정",
        "검색 근거의 완전성·인용의 주장 지원 여부가 일부 미확정",
        "독립 의미 그룹 6개만 존재하고 EXPLAIN_UNSUPPORTED 학습 사례가 없음",
        "실제 검색 문맥 전체 토큰 길이 및 SFT 후 JSON 스키마 신뢰성 미검증",
    ]
    summary = {
        "status":"S11_AUDIT_DONE_TRAINING_NOT_APPROVED",
        "purpose":"Prioritize known issues in existing S07/S09; not new PDF/legal review and not SFT",
        "source_sha256":hashes,
        "n_train_rows":len(train),
        "original_scenarios":len(source_cases),
        "semantic_groups":len(semantic_to_actions),
        "variant_counts":{"source":13,"paraphrase":13},
        "action_rows":{name:per_action.get(name,0) for name in ["ANSWER","ASK","ESCALATE","EXPLAIN_UNSUPPORTED"]},
        "action_original_scenarios":{name:len(action_sources[name]) for name in ["ANSWER","ASK","ESCALATE","EXPLAIN_UNSUPPORTED"]},
        "s11_key_gap":"EXPLAIN_UNSUPPORTED: 0 independent Train scenarios",
        "declared_semantic_groups_with_multiple_expected_actions":{g:sorted(x) for g,x in semantic_to_actions.items() if len(x)>1},
        "retrieval":{"at_least_one_gold_top5":at_least_one,"all_declared_gold_top5":all_gold,"citation_ids_in_retrieved_list":valid_id_membership},
        "m2_human_review_categories_26_rows":dict(sorted(per_category.items())),
        "m2_human_review_categories_13_scenarios":dict(sorted(category_source_count.items())),
        "source_use_approved_count":0,
        "training_ready_count":0,
        "next_steps":blocks,
        "notes":"Gold 하나 이상 존재/모든 ID 존재/인용 ID 멤버십은 내용의 정확성 또는 합법성 증거가 아님. M2 카테고리는 이전 사람 검수의 기록이며 이 스크립트가 PDF를 읽어 재검증한 것이 아님.",
    }
    return summary,queue


def audit(root:Path):
    paths={"s07_train":root/TRAIN_REL,"s09_preview":root/PREVIEW_REL,"m2_review":root/REVIEW_REL}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f"파일이 없습니다: {path} (프로젝트 루트에 ZIP을 풀었는지 확인)")
    train=read_jsonl(paths["s07_train"])
    preview=read_jsonl(paths["s09_preview"])
    review=json.loads(paths["m2_review"].read_text(encoding="utf-8-sig"))
    return verify_and_summarize(train,preview,review,{name:sha256(path) for name,path in paths.items()})


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="S11 data readiness audit; no model, GPU, copyrighted-manual export or training")
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check",action="store_true",help="Validate and show counts, without writing")
    group.add_argument("--write",action="store_true",help="Write derived audit files; existing training data untouched")
    args=parser.parse_args(argv)
    summary,queue=audit(ROOT)
    print(f"[S11] AUDIT PASS | {summary['n_train_rows']} Train rows / {summary['original_scenarios']} sources / {summary['semantic_groups']} semantic groups")
    print("[S11] Action coverage: " + ", ".join(f"{k}={v}" for k,v in summary["action_rows"].items()))
    print(f"[S11] Retrieved: Gold any {summary['retrieval']['at_least_one_gold_top5']}/26, all declared Gold {summary['retrieval']['all_declared_gold_top5']}/26")
    print(f"[S11] Cases to prioritize: P1={sum(x['priority']=='P1' for x in queue)} / P2={sum(x['priority']=='P2' for x in queue)} / P3={sum(x['priority']=='P3' for x in queue)}")
    print("[S11] Rights approval: NO | SFT training-ready: 0 | Dev/Holdout and GPU not used")
    if args.write:
        dest=ROOT/OUT_REL
        dest.mkdir(parents=True,exist_ok=True)
        summ=dest/"s11_audit_summary.json"
        cases=dest/"s11_case_queue.csv"
        summ.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        with cases.open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(queue[0]))
            writer.writeheader()
            writer.writerows(queue)
        print(f"[S11] WRITE PASS | {summ.relative_to(ROOT)} | {cases.relative_to(ROOT)}")
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except (ValueError,FileNotFoundError,KeyError,TypeError) as exc:
        print(f"[S11] ERROR: {exc}",file=sys.stderr)
        sys.exit(1)
