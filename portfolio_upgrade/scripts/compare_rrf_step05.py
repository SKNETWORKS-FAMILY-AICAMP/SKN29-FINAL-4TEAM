r"""S02: 기존 저장 검색 순위를 RRF로 재결합하고 동일 Gold로 다시 채점.

Windows CMD / 저장소 루트:
    python portfolio_upgrade\scripts\compare_rrf_step05.py
    python portfolio_upgrade\scripts\compare_rrf_step05.py --save

외부 패키지, 모델 재다운로드, GPU 모두 불필요.
--save는 원시 JSON 1개와 기존 notes/week01.md의 S02 절만 갱신한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rrf_fusion import fuse_rrf  # noqa: E402
from evaluate_mini import score_one  # noqa: E402 -- 기존 지표 함수를 재사용한다

DEFAULT_RANKINGS = ROOT / "experiments" / "step04" / "metrics_recomputed.json"
DEFAULT_GOLD = ROOT / "data" / "gold" / "mini10_gold_step02.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "step05_rrf" / "rrf_comparison.json"
DEFAULT_NOTES = ROOT / "notes" / "week01.md"
START_MARKER = "<!-- S02_RRF_START -->"
END_MARKER = "<!-- S02_RRF_END -->"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _score(ids: list[str], gold_ids: list[str], top_k: int) -> dict:
    """기존 S01 평가기를 그대로 사용. 새 지표 수식은 만들지 않는다."""
    return score_one(ids, gold_ids, top_k)


def evaluate_rrf(
    saved: dict, gold: dict, *, rank_constant: int = 60, candidate_k: int = 3, top_k: int = 3
) -> dict:
    if not 1 <= top_k <= candidate_k <= saved.get("k", 0):
        raise ValueError("top_k <= candidate_k <= 기존 저장 결과 k 여야 합니다")
    gold_cases = gold["cases"]
    by_case = {case["case_id"]: case for case in gold_cases}
    if len(by_case) != len(gold_cases):
        raise ValueError("Gold case_id가 중복되었습니다")

    data: dict[tuple[str, str], dict] = {}
    for record in saved["cases"]:
        key = (record["case_id"], record["method"])
        if key in data:
            raise ValueError(f"같은 질문/검색기가 중복되었습니다: {key}")
        data[key] = record
    if set(case_id for case_id, _ in data) != set(by_case):
        raise ValueError("Gold와 저장 결과의 case_id가 불일치합니다")

    methods = ("bm25", "embedding")
    summary_scores: dict[str, list[dict]] = {"bm25": [], "embedding": [], "rrf": []}
    cases: list[dict] = []
    for case_id in sorted(by_case):
        case = by_case[case_id]
        gold_ids = case["acceptable_chunk_ids"]
        ranked_lists: dict[str, list[str]] = {}
        source_metrics: dict[str, dict] = {}
        for method in methods:
            if (case_id, method) not in data:
                raise ValueError(f"{case_id}/{method} 결과가 누락되었습니다")
            record = data[(case_id, method)]
            if record["status"] not in {"OK", "NO_RESULTS"}:
                raise ValueError(f"{case_id}/{method}의 검색 실패는 RRF 순위 결합에 사용할 수 없습니다")
            if set(record["acceptable_ids"]) != set(gold_ids):
                raise ValueError(f"{case_id}/{method} 저장된 정답과 현재 Gold가 다릅니다")
            ids = record["retrieved_ids"][:candidate_k]
            if len(ids) != len(set(ids)) or len(record["retrieved_ids"]) > saved["k"]:
                raise ValueError(f"{case_id}/{method}의 저장 순위가 유효하지 않습니다")
            if record["status"] == "NO_RESULTS" and ids:
                raise ValueError(f"{case_id}/{method} 결과 상태와 청크 목록이 모순됩니다")
            ranked_lists[method] = ids
            scored = _score(ids, gold_ids, top_k)
            source_metrics[method] = scored
            summary_scores[method].append(scored)

        fused = fuse_rrf(ranked_lists, rank_constant=rank_constant, limit=top_k)
        fused_ids = [entry["chunk_id"] for entry in fused]
        scored = _score(fused_ids, gold_ids, top_k)
        summary_scores["rrf"].append(scored)
        cases.append({
            "case_id": case_id,
            "question": case["question"],
            "gold_ids": gold_ids,
            "source_ranking": ranked_lists,
            "rrf_ranking": fused,
            "metrics": {**source_metrics, "rrf": scored},
        })

    if len(summary_scores["rrf"]) != len(gold_cases):
        raise AssertionError("일부 질문이 평가에서 누락되었습니다")

    summaries: dict[str, dict] = {}
    for method, metrics in summary_scores.items():
        n = len(metrics)
        summaries[method] = {
            "questions": n,
            "hit_at_1": sum(m["hit_at_1"] for m in metrics),
            f"hit_at_{top_k}": sum(m[f"hit_at_{top_k}"] for m in metrics),
            f"mrr_at_{top_k}": round(sum(m[f"rr_at_{top_k}"] for m in metrics) / n, 4),
        }

    return {
        "scope": "LEARNING_ONLY; same 8 passages and 10 correlated manual questions; not an independent validation",
        "method": "rrf_bm25_plus_e5",
        "rank_constant": rank_constant,
        "candidate_k": candidate_k,
        "top_k": top_k,
        "tie_break": "chunk_id_ascending",
        "source": "Saved BM25 and E5 ranking IDs from step04; no embedding/model rerun",
        "summary": summaries,
        "cases": cases,
    }


def _markdown_section(result: dict, ranking_sha: str, gold_sha: str) -> str:
    s = result["summary"]
    k = result["top_k"]
    n = len(result["cases"])
    rrf = s["rrf"]
    rows = [
        START_MARKER,
        "## S02 — RRF Hybrid Search (저장 순위 결합)",
        "",
        f"**입력:** S01에서 실제 실행해 저장한 BM25/E5 Top-{result['candidate_k']} 순위, "
        f"RRF rank constant={result['rank_constant']}, 출력 Top-{k}. Gold는 순위 계산에 사용하지 않음.",
        "",
        f"| 검색기 | Hit@1 | Hit@{k} | MRR@{k} |",
        "|---|---:|---:|---:|",
    ]
    for method, label in (("bm25", "BM25"), ("embedding", "E5 Embedding"), ("rrf", "RRF (BM25+E5)")):
        z = s[method]
        rows.append(f"| {label} | {z['hit_at_1']}/{n} | {z[f'hit_at_{k}']}/{n} | {z[f'mrr_at_{k}']:.4f} |")
    rows.extend([
        "",
        "**핵심 관찰:** RRF가 상위 1위 정답 개수를 늘린 것은 아니다. Q007은 임베딩의 1위를 유지했고, "
        "Q008은 BM25의 1위 정답을 RRF에서는 3위로 밀어냈다. Q002도 임베딩 2위 정답이 RRF에서는 3위가 되었다. "
        "Q003은 어느 검색기도 후보에 정답을 넣지 않아 RRF에서도 복구할 수 없었다.",
        "",
        "**채택 결론:** 작은 연습 데이터의 Hit@3/MRR@3는 나아졌지만 Q008의 순위가 퇴행했다. "
        "실제 WaterBridge에서 RRF를 채택할지는 더 많은 독립 질문과 실제 검색 파이프라인 분석 후 결정한다.",
        "",
        f"- 원시 결과: `experiments/step05_rrf/rrf_comparison.json` (Gold 기준으로 직접 재계산).",
        f"- 입력 SHA256: 순위 `{ranking_sha}` / Gold `{gold_sha}`.",
        "- 한계: 검색기별 Top-3만 저장돼 있어 그 밖의 청크는 복구할 수 없음. 10문항은 연관된 학습용 데이터이며 실제 고객 해결률이 아님.",
        "- **학습 확인:** RRF가 원점수를 합산하지 않는 이유, Q008의 BM25→RRF 퇴행 이유, Q003 미검색 원인을 내 말로 설명한다.",
        "",
        END_MARKER,
    ])
    return "\n".join(rows) + "\n"


def update_weekly_notes(path: Path, result: dict, ranking_sha: str, gold_sha: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"통합 기록 파일이 없습니다: {path}")
    original = path.read_text(encoding="utf-8-sig")
    section = _markdown_section(result, ranking_sha, gold_sha)
    if (START_MARKER in original) != (END_MARKER in original):
        raise ValueError("week01.md의 S02 시작/끝 마커가 짝이 맞지 않습니다")
    if START_MARKER in original:
        start = original.index(START_MARKER)
        end = original.index(END_MARKER, start) + len(END_MARKER)
        new = original[:start] + section.rstrip("\n") + original[end:]
    else:
        new = original.rstrip("\n") + "\n\n" + section
    new = new.replace("S02 RRF는 미착수", "S02 RRF는 저장 순위 기반 비교 수행")
    if new != original:
        path.write_text(new, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="S02 RRF Hybrid Search comparison on saved rankings")
    parser.add_argument("--rankings", type=Path, default=DEFAULT_RANKINGS)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--candidate-k", type=int, default=3, help="각 검색기에서 가져올 저장 후보 순위 수")
    parser.add_argument("--top-k", type=int, default=3, help="평가할 최종 결과 수")
    parser.add_argument("--rrf-k", type=int, default=60, help="RRF rank constant. 최종 Top-K와 별개")
    parser.add_argument("--save", action="store_true", help="결과 JSON 저장 + 통합 week01.md 갱신")
    args = parser.parse_args()

    saved, gold = _load(args.rankings), _load(args.gold)
    result = evaluate_rrf(
        saved, gold, rank_constant=args.rrf_k, candidate_k=args.candidate_k, top_k=args.top_k
    )
    rank_sha = hashlib.sha256(args.rankings.read_bytes()).hexdigest()
    gold_sha = hashlib.sha256(args.gold.read_bytes()).hexdigest()
    result["input_sha256"] = {"saved_rankings": rank_sha, "gold": gold_sha}

    print(f"\n=== S02: BM25 + E5 RRF (후보 Top-{args.candidate_k}, RRF-k={args.rrf_k}) ===")
    print(f"{'method':18s} {'Hit@1':>8s} {'Hit@'+str(args.top_k):>8s} {'MRR@'+str(args.top_k):>8s}")
    for method in ("bm25", "embedding", "rrf"):
        s = result["summary"][method]
        n = len(result["cases"])
        print(f"{method:18s} {str(s['hit_at_1'])+'/'+str(n):>8s} {str(s[f'hit_at_{args.top_k}'])+'/'+str(n):>8s} {s[f'mrr_at_{args.top_k}']:>8.4f}")

    print("\n[Q002/Q003/Q007/Q008/Q010 문항별 정답의 최초 순위: 없으면 '-']")
    for case in result["cases"]:
        if case["case_id"] not in {"Q002", "Q003", "Q007", "Q008", "Q010"}:
            continue
        ranks = [case["metrics"][m]["first_gold_rank"] for m in ("bm25", "embedding", "rrf")]
        print(f"{case['case_id']}: BM25={ranks[0] or '-'}, E5={ranks[1] or '-'}, RRF={ranks[2] or '-'} "
              f"| Hybrid Top-3={','.join(x['chunk_id'] for x in case['rrf_ranking'])}")
    print("\n주의: 기존 학습용 순위만 재결합한 실험; 실제 WaterBridge 검색·고객 응답 성능 아님")
    if args.save:
        if (args.candidate_k, args.top_k, args.rrf_k) != (3, 3, 60):
            raise ValueError("이번 S02 주차 기록/결과 저장은 사전 설정 (candidate_k=3, top_k=3, rrf_k=60)만 허용합니다")
        # 하나의 주차 기록만 유지하며 새로운 설명 문서를 만들지 않는다.
        if not DEFAULT_NOTES.is_file():
            raise FileNotFoundError(f"통합 주차 기록이 없어 저장하지 않았습니다: {DEFAULT_NOTES}")
        DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        update_weekly_notes(DEFAULT_NOTES, result, rank_sha, gold_sha)
        print(f"\n저장 완료: {DEFAULT_OUTPUT.relative_to(ROOT)}")
        print(f"통합 기록 갱신: {DEFAULT_NOTES.relative_to(ROOT)} (S02 절 1개만)")
    else:
        print("\n미리보기만 실행됨. 파일을 저장하려면 --save를 추가하세요.")


if __name__ == "__main__":
    main()
