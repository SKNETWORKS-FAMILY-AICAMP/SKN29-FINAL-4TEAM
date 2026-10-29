r"""S05 (DEV ONLY): safety-first routing guard for the offline no-water prefilter.

This is an exploratory retrieval rule, NOT an implemented WaterBridge safety
classifier, not an approved runtime path, and not an independent benchmark.

Put this file into portfolio_upgrade/scripts/ alongside:
  - s05_offline_bge_rag.py
  - s05_oracle_pilot.py

From repository root on Windows CMD:
  python portfolio_upgrade\scripts\s05_safe_routing_guard.py --check
  python portfolio_upgrade\scripts\s05_safe_routing_guard.py --preview
  python portfolio_upgrade\scripts\s05_safe_routing_guard.py --compare

--check: 20 counterexamples, no external model/API/corpus
--preview: original Dev six queries + rule decisions, no external model/API
--compare: re-run offline BGE-M3 on Dev only, output JSONL; no OpenAI API

Never use Gold labels or the pilot Holdout to choose a retrieval route.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

# Only these routes change the candidate pool. Everything else is unfiltered.
NO_WATER = "PREFILTER_NO_WATER"
SAFETY = "SAFETY_FIRST_UNFILTERED"
LOW_FLOW = "LOW_FLOW_UNFILTERED"
NON_TOTAL = "NEGATED_NON_TOTAL_UNFILTERED"
MODE = "MODE_SPECIFIC_UNFILTERED"
GENERAL = "UNFILTERED"
FALLBACK = "FALLBACK_NO_TOPIC_CANDIDATE"

# Conservative, deliberately broad. This does NOT provide a final safety decision.
_DANGER = re.compile(
    r"누수|물\s*샘|물\s*새(?:요|는|어|고|서|었)|물이\s*새|"
    r"물이\s*흘러\s*나|바닥에\s*물이\s*(?:고|번|새)|"
    r"제품\s*(?:안|밑|아래|주변).*물(?:이|이\s*)?(?:고|새|번|흘러)|"
    r"스파크|불꽃|감전|찌릿|전선\s*노출|전기\s*충격|연기|"
    r"타는\s*냄새|탄\s*냄새|화재|플러그.*(?:녹|타|과열)",
    re.IGNORECASE,
)
_NEGATED_NO_WATER = re.compile(
    r"(?:안\s*나오(?:는|지\s*않)는?|나오지\s*않(?:는|았))\s*(?:건|것은|게|건\s*아니|건\s*아닌)\s*(?:아니|아닌|아니라)|"
    r"안\s*나오는\s*(?:건|게|것은)\s*아니|"
    r"나오지\s*않는\s*(?:건|게|것은)\s*아니|"
    r"안\s*나오는\s*것보다|안\s*나오는\s*건\s*아니",
    re.IGNORECASE,
)
_LOW_FLOW = re.compile(
    r"조금씩|찔끔|졸졸|쫄쫄|약하게|적게|"
    r"물줄기.{0,10}약|출수량.{0,10}적|수압.{0,10}약|"
    r"물\s*은?\s*나오는데|물이\s*나오긴|물이\s*나오지만",
    re.IGNORECASE,
)
# Treat specific modes as ambiguous unless ALL modes are explicitly failed;
# rather than trying to infer that from a small sample, never prefilter them.
_MODE_OR_TEMP = re.compile(
    r"얼음|제빙|온수|냉수|정수(?!기)|뜨겁게|뜨거운\s*물|미지근|차갑지|"
    r"따뜻하지|물\s*온도|온도가",
    re.IGNORECASE,
)
_TOTAL_NO_WATER = re.compile(
    r"(?:물(?:이|은|도|을)?|출수)\s*.{0,24}?"
    r"(?:안\s*나|나오지\s*않|출수되지\s*않|안\s*되)|"
    r"(?:전혀|아예|하나도|한\s*방울도)\s*.{0,16}?(?:안\s*나|나오지\s*않)|"
    r"(?:무출수|미출수|출수되지\s*않|출수가\s*안\s*(?:되|돼))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str


def decide_route(query: str) -> RouteDecision:
    """Return a query-only routing hint. Never read Gold/expected answers."""
    text = re.sub(r"\s+", " ", query).strip()
    if _DANGER.search(text):
        return RouteDecision(SAFETY, "위험 신호 가능성: 주제 필터로 근거를 제거하지 않음")
    if _NEGATED_NO_WATER.search(text):
        return RouteDecision(NON_TOTAL, "완전 미출수를 부정함: 무출수 필터 금지")
    if _MODE_OR_TEMP.search(text):
        return RouteDecision(MODE, "특정 기능/물 종류/온도 문제: 무출수 단정 금지")
    if _LOW_FLOW.search(text):
        return RouteDecision(LOW_FLOW, "적은 출수량: 완전 미출수와 구별")
    if _TOTAL_NO_WATER.search(text):
        return RouteDecision(NO_WATER, "명시적인 전체 무출수 표현")
    return RouteDecision(GENERAL, "유형 불확실: 검색 후보를 좁히지 않음")


def choose_model_candidates(
    candidates: list[dict], group_by_id: dict, *, query: str, model_code: str
) -> tuple[list[dict], RouteDecision]:
    """Only candidates of the customer's model; optional topic restriction."""
    model_candidates = [c for c in candidates if c["exact_sales_code"] == model_code]
    decision = decide_route(query)
    if decision.route != NO_WATER:
        return model_candidates, decision
    selected = [
        c for c in model_candidates
        if group_by_id[c["evidence_group_id"]].get("topic_code", "").lower()
        in {"no_water", "symptom_no_water"}
    ]
    if not selected:
        return model_candidates, RouteDecision(
            FALLBACK, "해당 모델의 검증된 무출수 청크가 없어 전체 모델 후보로 복귀"
        )
    return selected, decision


# Independent, deliberately adversarial route tests. These are not blind data.
COUNTEREXAMPLES: list[tuple[str, str]] = [
    ("물이 전혀 안 나와요", NO_WATER),
    ("정수기 물이 갑자기 안 나옵니다", NO_WATER),
    ("물이 하나도 안 나와요", NO_WATER),
    ("정수기에서 물이 나오지 않습니다", NO_WATER),
    ("출수가 안 돼요", NO_WATER),
    ("물 한 방울도 안 나옵니다", NO_WATER),
    ("물이 전혀 안 나오는데 바닥에 물이 새요", SAFETY),
    ("물이 안 나오고 플러그에서 스파크가 튀어요", SAFETY),
    ("정수기 안쪽에서 물이 흘러나와요", SAFETY),
    ("물이 안 나오면서 타는 냄새도 납니다", SAFETY),
    ("물이 안 나오는 건 아니고 물줄기가 약해요", NON_TOTAL),
    ("안 나오는 게 아니라 물이 조금씩 나와요", NON_TOTAL),
    ("필터를 교체했는데도 물이 졸졸 나와요", LOW_FLOW),
    ("물이 적게 나오고 수압이 약해요", LOW_FLOW),
    ("물이 뜨겁게 안 나와요", MODE),
    ("온수만 안 나와요", MODE),
    ("냉수만 나오지 않아요", MODE),
    ("얼음이 안 나와요", MODE),
    ("정수기 소음이 커졌어요", GENERAL),
    ("물을 받으면 냄새가 나요", GENERAL),
]


def run_check() -> None:
    failed = []
    for idx, (query, expected) in enumerate(COUNTEREXAMPLES, start=1):
        actual = decide_route(query)
        okay = actual.route == expected
        print(f"{idx:02d} {'PASS' if okay else 'FAIL'} | {actual.route:32s} | {query}")
        if not okay:
            failed.append((query, expected, actual.route))
    print(f"\nSynthetic route tests: {len(COUNTEREXAMPLES)-len(failed)}/{len(COUNTEREXAMPLES)}")
    print("이 테스트는 직접 만든 반례 검사이며 실제 고객 안전성·일반화 성능을 보장하지 않음.")
    if failed:
        raise SystemExit(f"Routing checks failed: {failed}")


def load_dev(root: Path):
    from s05_offline_bge_rag import load_cases, retrieval_query
    dev, scenarios, chunks, digests = load_cases(root)
    return dev, scenarios, chunks, digests, retrieval_query


def run_preview(root: Path) -> None:
    from s05_oracle_pilot import read_jsonl
    dev, scenarios, chunks, _, retrieval_query = load_dev(root)
    groups = {g["evidence_group_id"]: g for g in read_jsonl(
        root / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
    )}
    print("[S05] DEV six queries: safety-first routing preview (no BGE/API)")
    for row in dev:
        query = retrieval_query(scenarios[row["scenario_id"]])
        candidates, decision = choose_model_candidates(
            chunks, groups, query=query, model_code=row["model_code"]
        )
        print(f"  {row['scenario_id']}: {decision.route} | candidates={len(candidates)}")
    print("PREVIEW ONLY. Holdout is not accessed. Public runtime is unchanged.")


def run_compare(root: Path, args) -> None:
    from s05_offline_bge_rag import (
        MODEL_ID, MODEL_REVISION, TOP_K, SCORE_THRESHOLD,
        gold_ids, make_embeddings, rank_for_case, distinct_evidence,
    )
    from s05_oracle_pilot import read_jsonl
    dev, scenarios, chunks, digests, retrieval_query = load_dev(root)
    groups = {g["evidence_group_id"]: g for g in read_jsonl(
        root / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
    )}
    queries = [retrieval_query(scenarios[row["scenario_id"]]) for row in dev]
    docvec, queryvec = make_embeddings(chunks, queries, device=args.device, batch_size=args.batch_size)
    import numpy as np
    records = []
    for row, query, qvec in zip(dev, queries, queryvec, strict=True):
        baseline = rank_for_case(chunks, docvec, qvec, model_code=row["model_code"])
        filtered, decision = choose_model_candidates(
            chunks, groups, query=query, model_code=row["model_code"]
        )
        id_to_index = {c["child_id"]: i for i, c in enumerate(chunks)}
        filtered_vec = docvec[np.asarray([id_to_index[c["child_id"]] for c in filtered], dtype=int)]
        ranked = rank_for_case(filtered, filtered_vec, qvec, model_code=row["model_code"])
        gold = set(gold_ids(row))  # evaluation AFTER retrieval; NOT used for routing
        bhit = bool(gold & {x["evidence_group_id"] for x in baseline}) if gold else None
        hit = bool(gold & {x["evidence_group_id"] for x in ranked}) if gold else None
        records.append({
            "case_id": row["scenario_id"], "query": query, "model_code": row["model_code"],
            "route": decision.route, "route_reason": decision.reason,
            "baseline": {"hit_at_5": bhit, "ranked": baseline},
            "safe_routed": {"hit_at_5": hit, "ranked": ranked, "evidence": distinct_evidence(ranked)},
            "gold_ids_evaluation_only": sorted(gold), "input_sha256": digests,
            "config": {
                "embedding": MODEL_ID, "revision": MODEL_REVISION, "top_k": TOP_K,
                "threshold": SCORE_THRESHOLD, "offline_only": True,
                "not_included": ["pgvector", "LangGraph", "safety stage", "live product gates"],
                "not_an_independent_benchmark": True,
            },
        })
        label = lambda h: "HIT" if h is True else "MISS" if h is False else "NO_GOLD"
        print(f"  {row['scenario_id']}: {decision.route:30s} "
              f"{label(bhit):7s} -> {label(hit):7s}")
    assessed=[r for r in records if r["baseline"]["hit_at_5"] is not None]
    before=sum(x["baseline"]["hit_at_5"] is True for x in assessed)
    after=sum(x["safe_routed"]["hit_at_5"] is True for x in assessed)
    output_dir=root/"portfolio_upgrade"/"experiments"/"s05_retrieval"
    output_dir.mkdir(parents=True, exist_ok=True)
    path=output_dir/f"safe_routing_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{os.getpid()}.jsonl"
    with path.open("x", encoding="utf-8", newline="\n") as h:
        for r in records:
            h.write(json.dumps(r, ensure_ascii=False)+"\n")
    print(f"DEV positive Hit@5: unfiltered {before}/{len(assessed)}, safe-routed {after}/{len(assessed)}")
    print(f"결과 파일: {path}")
    print("DEV에서 맞춤형으로 만든 규칙이므로 실제 성능 상승으로 일반화하지 않음.")
    print("안전 신호가 있으면 사전 필터를 적용하지 않을 뿐, 별도 Safety Stage는 실행하지 않음.")


def main() -> None:
    p=argparse.ArgumentParser(description="S05 guardrail for offline NO_WATER routing (DEV only)")
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="20개 합성 반례 빠른 검사")
    modes.add_argument("--preview", action="store_true", help="Dev 6건의 분기만 확인")
    modes.add_argument("--compare", action="store_true", help="Dev 6건 BGE-M3 검색 재평가")
    p.add_argument("--device", choices=["cpu","cuda"], default="cpu")
    p.add_argument("--batch-size",type=int,default=4)
    args=p.parse_args()
    if args.batch_size < 1:
        p.error("--batch-size는 1 이상")
    if args.check:
        run_check()
    elif args.preview:
        run_preview(Path(__file__).resolve().parents[2])
    else:
        run_compare(Path(__file__).resolve().parents[2],args)


if __name__=="__main__":
    main()
