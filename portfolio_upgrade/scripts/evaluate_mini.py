"""WaterBridge 실습 04: 이미 저장된 검색 결과를 정답지와 독립 비교한다.

새로운 임베딩 연산이나 외부 패키지는 필요하지 않다.
실행 위치: 저장소 루트 (예: C:\\SKN projects\\final)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "experiments" / "step03" / "embedding_comparison.json"
DEFAULT_GOLD = ROOT / "data" / "gold" / "mini10_gold_step02.json"
DEFAULT_JSON = ROOT / "experiments" / "step04" / "metrics_recomputed.json"
DEFAULT_MD = ROOT / "experiments" / "step04" / "metrics_recomputed.md"


def score_one(retrieved_ids: list[str], acceptable_ids: list[str], k: int) -> dict:
    """정답 근거 하나라도 찾으면 Hit. 첫 정답의 순위가 RR을 결정한다."""
    if k < 1 or not acceptable_ids:
        raise ValueError("k는 1 이상이고 정답 후보 목록은 비어 있으면 안 됩니다.")
    if len(retrieved_ids) != len(set(retrieved_ids)):
        raise ValueError("중복 검색 청크 ID가 있습니다. 검색 결과를 먼저 검증하세요.")
    correct = set(acceptable_ids)
    rank = next((i for i, cid in enumerate(retrieved_ids[:k], 1) if cid in correct), None)
    return {
        "hit_at_1": int(rank == 1),
        f"hit_at_{k}": int(rank is not None),
        "first_gold_rank": rank,
        f"rr_at_{k}": (1 / rank) if rank else 0.0,
    }


def evaluate_saved_report(saved: dict, gold: dict, *, k: int | None = None) -> dict:
    """저장된 점수는 읽지 않고 순위 + 별도 Gold로 모든 질문을 다시 평가한다."""
    stored_k = saved["top_k"]
    k = stored_k if k is None else k
    if not isinstance(k, int) or not 1 <= k <= stored_k:
        raise ValueError(f"Hit@{k}는 저장된 Top-{stored_k} 결과로 계산할 수 없습니다.")
    cases = gold["cases"]
    gold_by_id = {c["case_id"]: c for c in cases}
    if len(gold_by_id) != len(cases):
        raise ValueError("Gold에 중복된 case_id가 있습니다.")

    # 사용자가 실행한 step03에는 정확히 3개 방법이 들어 있다.
    methods = ("overlap", "bm25", "embedding")
    index = {}
    for row in saved["cases"]:
        key = (row["method"], row["case_id"])
        if row["method"] not in methods or row["case_id"] not in gold_by_id:
            raise ValueError(f"알 수 없는 검색 결과: {key}")
        if key in index:
            raise ValueError(f"중복 결과: {key}")
        # 결과 파일 안의 gold_ids는 신뢰하지 않고 원래 정답지와 대조한다.
        if "gold_ids" in row and set(row["gold_ids"]) != set(
            gold_by_id[row["case_id"]]["acceptable_chunk_ids"]
        ):
            raise ValueError(f"검색 결과와 원본 정답지가 다릅니다: {key}")
        index[key] = row

    rows, summary = [], {}
    for method in methods:
        subset = []
        for case in cases:  # 검색이 실패하거나 행 자체가 없어도 분모에서 제외하지 않는다.
            item = index.get((method, case["case_id"]))
            if item is None:
                ids, status = [], "MISSING_RESULT"
            elif item.get("error_type") or item.get("error"):
                ids, status = [], "SEARCH_ERROR"
            else:
                candidates = item.get("retrieved", [])
                if not isinstance(candidates, list):
                    raise ValueError(f"검색 결과 배열 형식이 아닙니다: {method}/{case['case_id']}")
                if len(candidates) > stored_k:
                    raise ValueError(f"저장된 Top-{stored_k}보다 긴 순위: {method}/{case['case_id']}")
                ids = [v["chunk_id"] for v in candidates]
                status = "OK" if ids else "NO_RESULTS"
            scored = score_one(ids, case["acceptable_chunk_ids"], k)
            subset.append({"case_id": case["case_id"], "method": method, "status": status,
                           "retrieved_ids": ids[:k], "acceptable_ids": case["acceptable_chunk_ids"], **scored})
        n = len(subset)
        summary[method] = {
            "n_questions": n,
            "hit_at_1": sum(v["hit_at_1"] for v in subset),
            f"hit_at_{k}": sum(v[f"hit_at_{k}"] for v in subset),
            f"mrr_at_{k}": round(sum(v[f"rr_at_{k}"] for v in subset) / n, 4),
            "missing_count": sum(v["status"] == "MISSING_RESULT" for v in subset),
            "error_count": sum(v["status"] == "SEARCH_ERROR" for v in subset),
            "no_results_count": sum(v["status"] == "NO_RESULTS" for v in subset),
        }
        rows.extend(subset)
    return {
        "scope": "LEARNING_ONLY: 8 related manual passages and 10 correlated questions; NOT independent performance evidence",
        "source_results": "saved ranked results", "source_gold": "separate gold dataset",
        "k": k, "summary": summary, "cases": rows,
    }


def to_markdown(report: dict) -> str:
    k = report["k"]
    lines = ["# WaterBridge 실습 04 — 독립 계산한 검색 지표", "",
             "> 실습용 8개 문단·10개 상관된 질문. 실제 서비스 성능이 아님.", "",
             f"| 방식 | Hit@1 | Hit@{k} | MRR@{k} | 행 누락 | 검색 오류 |",
             "|---|---:|---:|---:|---:|---:|"]
    for method, s in report["summary"].items():
        n = s["n_questions"]
        lines.append(f"| {method} | {s['hit_at_1']}/{n} | {s[f'hit_at_{k}']}/{n} | "
                     f"{s[f'mrr_at_{k}']:.4f} | {s['missing_count']} | {s['error_count']} |")
    lines += ["", "## 주의", "", "- 모든 질문을 분모에 포함하며, 오류·결과 없음의 RR은 0점이다.",
              "- `acceptable_chunk_ids`는 **하나라도 맞으면 성공**이라는 대체 정답 목록이다. 모든 근거가 필수인 Recall과는 다르다.",
              "- 실제 상위 K개를 저장한 경우에만 Hit@K/MRR@K를 계산할 수 있다.", ""]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Step03 검색 결과를 원본 Gold로 재채점")
    p.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    p.add_argument("--k", type=int, default=None, help="기본값: 저장된 결과의 top_k")
    p.add_argument("--case", default="Q002", help="자세히 볼 질문 ID (기본 Q002)")
    p.add_argument("--out", type=Path, default=DEFAULT_JSON)
    p.add_argument("--md", type=Path, default=DEFAULT_MD)
    args = p.parse_args()
    if not args.results.exists():
        p.error(f"저장된 결과가 없습니다: {args.results}\n실습 03의 --demo를 먼저 실행하세요.")
    saved = json.loads(args.results.read_text(encoding="utf-8"))
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    report = evaluate_saved_report(saved, gold, k=args.k)
    report["source_results_path"] = str(args.results)
    report["source_gold_path"] = str(args.gold)
    print(to_markdown(report))
    print(f"[문항 상세] {args.case}")
    for row in report["cases"]:
        if row["case_id"] == args.case:
            rr = row[f"rr_at_{report['k']}"]
            print(f" {row['method']:9s} 순위={row['retrieved_ids']}, "
                  f"첫 정답 순위={row['first_gold_rank']}, "
                  f"Hit@1={row['hit_at_1']}, RR@{report['k']}={rr:.4f}")
    for path, value in ((args.out, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
                        (args.md, to_markdown(report) + "\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        print("저장:", path)


if __name__ == "__main__":
    main()
