"""첫 검색 실습: 공백·문장부호 기준으로 나눈 키워드의 겹침 수로 검색.

표준 라이브러리만 사용. 정답 파일은 --demo 질문 목록으로만 읽고,
실제 점수 계산에는 사용하지 않는다.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "mini_corpus.json"
GOLD = ROOT / "data" / "gold" / "mini3_gold_v0.1.json"


def tokenize(text: str) -> set[str]:
    """문장을 소문자 키워드 집합으로 변환한다. 한국어 조사·동의어 처리는 하지 않는다."""
    return set(re.findall(r"[가-힣a-z0-9]+", text.casefold()))


def search(query: str, chunks: list[dict], top_k: int = 3) -> list[dict]:
    """검색 문장과 겹치는 단어가 있는 청크만 점수순으로 반환한다."""
    if top_k < 1:
        raise ValueError("top_k는 1 이상이어야 합니다")
    query_words = tokenize(query)
    ranked = []
    for chunk in chunks:
        document_words = tokenize(chunk["section"] + " " + chunk["text"])
        common = sorted(query_words & document_words)
        if not common:
            continue
        ranked.append({
            "chunk_id": chunk["chunk_id"],
            "page": chunk["page"],
            "section": chunk["section"],
            "score": len(common),  # 겹치는 서로 다른 단어 하나당 1점
            "matched_keywords": common,
        })
    return sorted(ranked, key=lambda r: (-r["score"], r["chunk_id"]))[:top_k]


def show(query: str, chunks: list[dict], top_k: int) -> None:
    print(f"\n질문: {query}")
    rows = search(query, chunks, top_k)
    if not rows:
        print("  검색 결과 없음 (일치하는 키워드가 없음)")
        return
    for rank, row in enumerate(rows, 1):
        print(f'  {rank}위 | {row["chunk_id"]} | {row["page"]}쪽 '
              f'| {row["section"]} | 점수 {row["score"]}')
        print("      겹친 키워드: " + ", ".join(row["matched_keywords"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="WaterBridge 첫 키워드 검색 실습")
    parser.add_argument("query", nargs="?", help='검색 질문. 예: "제품 누수 발생"')
    parser.add_argument("--demo", action="store_true", help="3개 고객 질문과 매뉴얼 표현을 비교")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    chunks = corpus["chunks"]
    if args.demo:
        print("[A] 매뉴얼의 표현을 그대로 검색")
        for chunk in chunks:
            show(chunk["section"], chunks, args.top_k)
        print("\n[B] 고객의 자연어 질문으로 검색 (정답지는 점수 계산에 사용하지 않음)")
        for case in json.loads(GOLD.read_text(encoding="utf-8"))["cases"]:
            show(case["question"], chunks, args.top_k)
    elif args.query:
        show(args.query, chunks, args.top_k)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
