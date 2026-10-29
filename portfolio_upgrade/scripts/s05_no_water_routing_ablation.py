r"""S05 exploratory DEV-only ablation: rank across product vs prefilter NO_WATER.

This runs BGE-M3 again, without OpenAI API, pgvector, or LangGraph.
It deliberately uses a tiny handcrafted rule informed by DEV errors, so results
are exploratory, NOT independent evidence of generalization. Gold is used only
AFTER ranking, to compute Hit@5. Holdout is not loaded.

Place beside existing s05_offline_bge_rag.py in portfolio_upgrade/scripts.
Windows CMD (repository root):
  python portfolio_upgrade\scripts\s05_no_water_routing_ablation.py --preview
  python portfolio_upgrade\scripts\s05_no_water_routing_ablation.py --run
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from s05_offline_bge_rag import (
    TOP_K, SCORE_THRESHOLD, MODEL_ID, MODEL_REVISION,
    gold_ids, load_cases, make_embeddings, rank_for_case,
    retrieval_query,
)
from s05_oracle_pilot import read_jsonl

GROUP_FILE = "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"


def is_total_no_water(text: str) -> bool:
    """Simple raw-text heuristic. May miss paraphrases; no gold/expectation used."""
    text = re.sub(r"\s+", " ", text)
    # Avoid conflating ice-only and hot-water-only failures with total no-water.
    if re.search(r"얼음|제빙", text):
        return False
    if "온수" in text and "냉수" not in text and "정수" not in text:
        return False
    if re.search(r"(?:전혀|하나도|아예)\s*안\s*나", text):
        return True
    return bool(re.search(
        r"(?:물(?:이|은|도|을)?|출수)(?:.{0,22}?)(?:안\s*나|나오지\s*않|출수되지\s*않)",
        text,
    ))


def group_is_no_water(group: dict) -> bool:
    topic = str(group.get("topic_code", "")).strip().lower()
    return topic in {"no_water", "symptom_no_water"}


def select_candidates(candidates: list[dict], group_by_id: dict, *, query: str, model_code: str):
    """Apply source metadata filter BEFORE cosine top-k, or leave unchanged."""
    if not is_total_no_water(query):
        return list(range(len(candidates))), "UNFILTERED"
    keep = [
        i for i, c in enumerate(candidates)
        if c["exact_sales_code"] != model_code
        or group_is_no_water(group_by_id[c["evidence_group_id"]])
    ]
    if not any(candidates[i]["exact_sales_code"] == model_code for i in keep):
        # Never return an empty all-model pool on a heuristic guess: fallback.
        return list(range(len(candidates))), "FALLBACK_NO_TOPIC_CANDIDATE"
    return keep, "PREFILTER_NO_WATER"


def main() -> None:
    parser = argparse.ArgumentParser(description="S05 DEV-only no-water routing ablation")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size는 1 이상이어야 합니다.")

    root = Path(__file__).resolve().parents[2]
    dev, scenarios, chunks, digests = load_cases(root)
    groups = {g["evidence_group_id"]: g for g in read_jsonl(root / GROUP_FILE)}
    for chunk in chunks:
        if chunk["evidence_group_id"] not in groups:
            raise ValueError(f"근거 그룹 누락: {chunk['child_id']}")
    queries = [retrieval_query(scenarios[r["scenario_id"]]) for r in dev]
    print("[S05] DEV-only comparison: plain BGE vs raw-query no-water prefilter")
    print("Note: a new rule motivated by DEV misses; NOT tested on blind holdout.")
    for row, query in zip(dev, queries, strict=True):
        indices, route = select_candidates(chunks, groups, query=query, model_code=row["model_code"])
        eligible = sum(chunks[i]["exact_sales_code"] == row["model_code"] for i in indices)
        print(f"  {row['scenario_id']:16s} {route:31s} eligible={eligible}")
    if args.preview:
        print("PREVIEW: no embedding or API requests; no output file.")
        return

    vecs, qvecs = make_embeddings(chunks, queries, device=args.device, batch_size=args.batch_size)
    import numpy as np
    records=[]
    for row, query, qvec in zip(dev, queries, qvecs, strict=True):
        model=row["model_code"]
        baseline=rank_for_case(chunks, vecs, qvec, model_code=model)
        indices,route=select_candidates(chunks, groups, query=query, model_code=model)
        selected=[chunks[i] for i in indices]
        scored=rank_for_case(selected,vecs[np.array(indices)],qvec,model_code=model)
        gold=set(gold_ids(row)) # EVALUATION ONLY, used after ranking
        baseline_groups={x["evidence_group_id"] for x in baseline}
        routed_groups={x["evidence_group_id"] for x in scored}
        hit_base=bool(gold & baseline_groups) if gold else None
        hit_routed=bool(gold & routed_groups) if gold else None
        record={
            "case_id": row["scenario_id"], "model_code": model,
            "query": query, "route": route,
            "gold_ids_evaluation_only": sorted(gold),
            "baseline": {"hit_at_5":hit_base, "ranked": baseline},
            "routed": {"hit_at_5":hit_routed, "ranked":scored},
            "config": {"embedding":MODEL_ID,"revision":MODEL_REVISION,"top_k":TOP_K,
                       "threshold":SCORE_THRESHOLD, "offline_only":True,
                       "ablation":"prefilter source metadata topic for explicit total no-water wording",
                       "limitation":"heuristic chosen after DEV failures; not held-out performance; not production pipeline"},
            "input_sha256":digests,
        }
        records.append(record)
        def mark(hit):return "HIT" if hit is True else "MISS" if hit is False else "NO_GOLD"
        first_old=baseline[0]["evidence_group_id"] if baseline else "NONE"
        first_new=scored[0]["evidence_group_id"] if scored else "NONE"
        print(f"  {row['scenario_id']} | baseline {mark(hit_base)} -> routed {mark(hit_routed)} | top1 {first_old} -> {first_new}")
    positives=[r for r in records if r["baseline"]["hit_at_5"] is not None]
    b=sum(r["baseline"]["hit_at_5"] is True for r in positives)
    s=sum(r["routed"]["hit_at_5"] is True for r in positives)
    print(f"\nDEV exploratory Hit@5: baseline {b}/{len(positives)}, prefiltered {s}/{len(positives)}")
    outdir=root/"portfolio_upgrade"/"experiments"/"s05_retrieval"
    outdir.mkdir(parents=True,exist_ok=True)
    filename=outdir/f"ablation_no_water_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{os.getpid()}.jsonl"
    with filename.open("x",encoding="utf-8",newline="\n") as out:
        for item in records:
            out.write(json.dumps(item,ensure_ascii=False)+"\n")
    print(f"Saved: {filename}")
    print("Never tune this rule or claim final success from pilot holdout. Validate with new unseen paraphrases.")


if __name__ == "__main__":
    main()
