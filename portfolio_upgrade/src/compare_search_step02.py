"""실습 02: 같은 질문·같은 청크로 '단어 겹침' 검색과 BM25 비교.

외부 라이브러리 없음. 기존 step01 keyword_search.search()를 그대로 사용한다.
정답 데이터는 결과 평가에만 쓰며 검색 점수 계산에는 쓰지 않는다.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from keyword_search import search as overlap_search, tokenize

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "mini_corpus_step02.json"
GOLD_PATH = ROOT / "data" / "gold" / "mini10_gold_step02.json"


def load_inputs():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["chunks"]
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))["cases"]
    assert len({c["chunk_id"] for c in corpus}) == len(corpus), "중복 청크 ID"
    assert all(set(c["acceptable_chunk_ids"]) <= {x["chunk_id"] for x in corpus} for c in gold), "없는 정답 청크"
    return corpus, gold


def bm25_search(query: str, chunks: list[dict], top_k: int = 3, *, k1: float = 1.5, b: float = 0.75):
    """Okapi BM25. step01과 똑같은 tokenize(공백/문장부호 기반)를 사용한다."""
    if top_k < 1:
        raise ValueError("top_k는 1 이상이어야 합니다")
    if not chunks:
        return []
    # step01 tokenize은 단어 집합이므로 문서 출현 횟수(tf)가 사라진다.
    # 차이를 잘 이해하도록 이 실습에서는 BM25에 한해서 단어 '빈도'도 센다.
    import re
    tokenize_list = lambda s: re.findall(r"[가-힣a-z0-9]+", s.casefold())
    counts = [Counter(tokenize_list(c["section"] + " " + c["text"])) for c in chunks]
    lengths = [sum(c.values()) for c in counts]
    n = len(chunks)
    avgdl = sum(lengths) / n
    docfreq = Counter(term for counter in counts for term in counter)
    query_terms = tokenize(query)  # 반복 질의 단어는 하나로 취급
    ranked = []
    for chunk, counter, dl in zip(chunks, counts, lengths):
        score = 0.0
        matched = []
        for term in sorted(query_terms):
            tf = counter.get(term, 0)
            if tf == 0:
                continue
            matched.append(term)
            df = docfreq[term]
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            score += idf * (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * dl / avgdl))
        if score > 0.0:
            ranked.append({
                "chunk_id": chunk["chunk_id"],
                "page": chunk["page"],
                "section": chunk["section"],
                "score": round(score, 6),
                "matched_keywords": matched,
            })
    return sorted(ranked, key=lambda x: (-x["score"], x["chunk_id"]))[:top_k]


def evaluate(results: list[dict], acceptable_ids: list[str], *, k: int = 3) -> dict:
    """Gold를 검색기에 전달하지 않고, 순위가 정해진 뒤에만 채점한다."""
    expected = set(acceptable_ids)
    if not expected:
        raise ValueError("이 단계는 근거가 있는 양성 질문만 다룹니다")
    ids = [x["chunk_id"] for x in results]
    rank = next((i for i, x in enumerate(ids[:k], 1) if x in expected), None)
    return {
        "hit_at_1": int(bool(ids) and ids[0] in expected),
        f"hit_at_{k}": int(rank is not None),
        f"mrr_at_{k}": round(1 / rank, 6) if rank else 0.0,
        "first_gold_rank": rank,
    }


def compare(chunks: list[dict], gold: list[dict], *, top_k: int = 3):
    records = []
    for case in gold:
        for method, search in (("overlap", overlap_search), ("bm25", bm25_search)):
            results = search(case["question"], chunks, top_k=top_k)
            scores = evaluate(results, case["acceptable_chunk_ids"], k=top_k)
            records.append({
                "case_id": case["case_id"], "question": case["question"],
                "scenario_group": case["scenario_group"], "label_type": case["label_type"],
                "method": method, "gold_ids": case["acceptable_chunk_ids"],
                **scores, "retrieved": results,
            })
    return records


def summary(records):
    out = {}
    for method in ("overlap", "bm25"):
        rows = [r for r in records if r["method"] == method]
        count = len(rows)
        if not count:
            continue
        score_k = next(k for k in rows[0] if k.startswith("hit_at_") and k != "hit_at_1")
        mrr_k = next(k for k in rows[0] if k.startswith("mrr_at_"))
        out[method] = {
            "n_questions": count,
            "hit_at_1": {"correct": sum(r["hit_at_1"] for r in rows), "total": count},
            score_k: {"correct": sum(r[score_k] for r in rows), "total": count},
            mrr_k: round(sum(r[mrr_k] for r in rows) / count, 4),
        }
    return out


def main():
    p = argparse.ArgumentParser(description="WaterBridge 연습용 단어 겹침 vs BM25 비교")
    p.add_argument("--demo", action="store_true", help="10문항 두 검색 방식 비교")
    p.add_argument("--query", help="원하는 질문을 하나 검색")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--out", type=Path, help="문항별 결과 JSON을 저장할 파일")
    args = p.parse_args()
    if args.top_k < 1:
        p.error("--top-k는 1 이상이어야 합니다")
    chunks, gold = load_inputs()
    if args.query:
        for name, search in (("overlap", overlap_search), ("bm25", bm25_search)):
            print(f"\n[{name}] {args.query}")
            for rank, r in enumerate(search(args.query, chunks, args.top_k), 1):
                print(f' {rank}위: {r["chunk_id"]} | {r["section"]} | {r["score"]:.4f} | 겹친 단어: {", ".join(r["matched_keywords"])}')
        return
    if not args.demo and args.out is None:
        p.print_help()
        return
    rows = compare(chunks, gold, top_k=args.top_k)
    stats = summary(rows)
    for case in gold:
        r = [x for x in rows if x["case_id"] == case["case_id"]]
        print(f'\n{case["case_id"]}: {case["question"]}')
        print(' 정답 청크:', ', '.join(case['acceptable_chunk_ids']))
        for x in r:
            first = x["retrieved"][0] if x["retrieved"] else None
            print(f'  {x["method"]:7s} 1위={first["chunk_id"] if first else "없음"}  Hit@1={x["hit_at_1"]} MRR@{args.top_k}={x[f"mrr_at_{args.top_k}"]}')
    print("\n[요약: 학습용 질문, 서로 독립적인 평가셋 아님]")
    for name, s in stats.items():
        print(f' {name}: Hit@1={s["hit_at_1"]["correct"]}/{s["n_questions"]}, Hit@{args.top_k}={s[f"hit_at_{args.top_k}"]["correct"]}/{s["n_questions"]}, MRR@{args.top_k}={s[f"mrr_at_{args.top_k}"]:.4f}')
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "scope": "EDUCATIONAL_ONLY; 8 passages from 3 sections; 10 correlated questions; not a real-service performance benchmark",
            "corpus_id": "waterbridge-mini8-corpus-step02",
            "gold_id": "waterbridge-mini10-gold-step02",
            "top_k": args.top_k,
            "summary": stats,
            "cases": rows,
        }
        args.out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n', encoding="utf-8")
        print(f'\n저장: {args.out}')


if __name__ == "__main__":
    main()
