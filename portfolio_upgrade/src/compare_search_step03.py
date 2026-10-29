"""실습 03: 같은 8개 매뉴얼 문단·10질문에서 키워드/ BM25 / 임베딩 검색을 비교한다.

'정답 데이터'는 검색 결과가 확정된 뒤 평가에만 사용한다.
실제 임베딩은 다국어 사전학습 모델을 다운로드하고 실행해야 얻을 수 있다.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any

import numpy as np

from compare_search_step02 import bm25_search, evaluate, load_inputs
from keyword_search import search as overlap_search

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "experiments" / "step03" / "embedding_comparison.json"

# E5 모델은 질의와 문서에 각각 'query: ', 'passage: '를 넣도록 학습됐다.
# BGE-M3는 이 실습에서 접두어 없이 그대로 인코딩한다.
MODEL_PRESETS = {
    "e5-small": {
        "model_id": "intfloat/multilingual-e5-small",
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    },
    "bge-m3": {
        "model_id": "BAAI/bge-m3",
        "query_prefix": "",
        "passage_prefix": "",
    },
}


def _normalized_matrix(model: Any, texts: list[str], *, batch_size: int) -> np.ndarray:
    """SentenceTransformer의 출력 벡터를 L2 정규화한다. Mock 모델에도 적용 가능."""
    encoded = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    matrix = np.asarray(encoded, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(texts):
        raise ValueError(f"예상치 못한 임베딩 크기: {matrix.shape}")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if not np.isfinite(matrix).all() or not (norms > 0).all():
        raise ValueError("잘못된 임베딩 값: NaN/Inf 또는 길이 0 벡터")
    return matrix / norms


def embedding_search_all(
    model: Any,
    chunks: list[dict],
    questions: list[str],
    *,
    query_prefix: str,
    passage_prefix: str,
    batch_size: int = 8,
    top_k: int = 3,
) -> list[list[dict]]:
    """문서 임베딩은 1회만 계산, 질문 임베딩을 한 번에 계산해 코사인 순위 반환."""
    if top_k < 1:
        raise ValueError("top_k는 1 이상이어야 합니다")
    if not chunks or not questions:
        return [[] for _ in questions]
    passages = [passage_prefix + c["section"] + " " + c["text"] for c in chunks]
    inputs = [query_prefix + question for question in questions]
    doc_vecs = _normalized_matrix(model, passages, batch_size=batch_size)
    query_vecs = _normalized_matrix(model, inputs, batch_size=batch_size)
    if doc_vecs.shape[1] != query_vecs.shape[1]:
        raise ValueError("질문과 문서 임베딩 차원이 일치하지 않습니다")
    scores = query_vecs @ doc_vecs.T
    return [
        [
            {
                "chunk_id": chunk["chunk_id"],
                "page": chunk["page"],
                "section": chunk["section"],
                "score": round(float(score), 6),
            }
            for score, chunk in sorted(
                zip(row.tolist(), chunks),
                key=lambda t: (-t[0], t[1]["chunk_id"]),
            )[:top_k]
        ]
        for row in scores
    ]


def compare(chunks: list[dict], gold: list[dict], embeddings: list[list[dict]], *, top_k: int):
    rows: list[dict] = []
    for case, dense in zip(gold, embeddings, strict=True):
        for method, ranked in (
            ("overlap", overlap_search(case["question"], chunks, top_k=top_k)),
            ("bm25", bm25_search(case["question"], chunks, top_k=top_k)),
            ("embedding", dense),
        ):
            rows.append({
                "case_id": case["case_id"],
                "question": case["question"],
                "scenario_group": case["scenario_group"],
                "label_type": case["label_type"],
                "method": method,
                "gold_ids": case["acceptable_chunk_ids"],
                **evaluate(ranked, case["acceptable_chunk_ids"], k=top_k),
                "retrieved": ranked,
            })
    return rows


def summarize(records: list[dict], *, top_k: int) -> dict:
    stats = {}
    for method in ("overlap", "bm25", "embedding"):
        rows = [r for r in records if r["method"] == method]
        n = len(rows)
        if n == 0:
            continue
        stats[method] = {
            "count": n,
            "hit_at_1": sum(r["hit_at_1"] for r in rows),
            f"hit_at_{top_k}": sum(r[f"hit_at_{top_k}"] for r in rows),
            f"mrr_at_{top_k}": round(sum(r[f"mrr_at_{top_k}"] for r in rows) / n, 4),
        }
    return stats


def _load_sentence_transformer(model_id: str, device: str | None):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise SystemExit(
            "sentence-transformers가 없습니다. 먼저 실행: python -m pip install sentence-transformers"
        ) from exc
    try:
        return SentenceTransformer(model_id, device=device)
    except Exception as exc:
        raise SystemExit(
            "임베딩 모델을 불러오지 못했습니다. 첫 실행에는 인터넷/모델 다운로드가 필요합니다.\n"
            f"model={model_id}\nerror={type(exc).__name__}: {exc}"
        ) from exc


def print_results(rows: list[dict], gold: list[dict], *, top_k: int, inspect_case: str):
    stats = summarize(rows, top_k=top_k)
    print("\n=== 같은 8문단·10문항 비교 (학습용, 공식 평가 아님) ===")
    for case in gold:
        matched = [r for r in rows if r["case_id"] == case["case_id"]]
        print(f"\n{case['case_id']}: {case['question']}")
        print(f" 정답 후보: {', '.join(case['acceptable_chunk_ids'])}")
        for r in matched:
            first = r["retrieved"][0] if r["retrieved"] else None
            chosen = first["chunk_id"] if first else "없음"
            score = f" (점수 {first['score']:.4f})" if first else ""
            print(
                f"  {r['method']:9s} 1위={chosen}{score}"
                f"  Hit@1={r['hit_at_1']} MRR@{top_k}={r[f'mrr_at_{top_k}']:.4f}"
            )
    print("\n=== 요약 ===")
    for method, result in stats.items():
        n = result["count"]
        print(
            f" {method:9s}: Hit@1={result['hit_at_1']}/{n}, "
            f"Hit@{top_k}={result[f'hit_at_{top_k}']}/{n}, "
            f"MRR@{top_k}={result[f'mrr_at_{top_k}']:.4f}"
        )
    print("\n※ 같은 증상의 변형 질문이 포함되어 독립 표본이 아닙니다. 비교용 연습 지표입니다.")
    if inspect_case:
        items = [r for r in rows if r["case_id"] == inspect_case]
        if not items:
            print(f"\n[상세 보기] {inspect_case} 문항이 없습니다")
        else:
            print(f"\n=== {inspect_case}: 검색 상위 {top_k}개 자세히 ===")
            for r in items:
                print(f" [{r['method']}] (방법 간 점수 단위가 다르므로 점수 크기 직접 비교 금지)")
                for index, candidate in enumerate(r["retrieved"], 1):
                    mark = "<정답>" if candidate["chunk_id"] in r["gold_ids"] else ""
                    print(f"  {index}위 {candidate['chunk_id']} 점수={candidate['score']:.5f} {mark} {candidate['section']}")


def run_cli():
    parser = argparse.ArgumentParser(description="WaterBridge 학습용 Embedding vs BM25 vs Overlap")
    parser.add_argument("--demo", action="store_true", help="10문항 비교 실행")
    parser.add_argument("--query", type=str, help="원하는 질문 1개를 검색해 상위 문서만 출력")
    parser.add_argument("--model", choices=MODEL_PRESETS, default="e5-small", help="임베딩 모델")
    parser.add_argument("--device", default=None, help="예: cpu 또는 cuda (생략하면 자동)")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--inspect", default="Q007", help="상세 순위 출력 문항 (기본 Q007)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="비교 결과 JSON 저장 경로")
    args = parser.parse_args()
    if args.top_k < 1 or args.batch_size < 1:
        parser.error("top-k와 batch-size는 양의 정수여야 합니다")
    if not args.demo and not args.query:
        parser.print_help()
        return

    chunks, gold = load_inputs()
    preset = MODEL_PRESETS[args.model]
    print(f"임베딩 모델 불러오는 중: {preset['model_id']}")
    model = _load_sentence_transformer(preset["model_id"], args.device)
    questions = [args.query] if args.query else [c["question"] for c in gold]
    dense = embedding_search_all(
        model,
        chunks,
        questions,
        query_prefix=preset["query_prefix"],
        passage_prefix=preset["passage_prefix"],
        batch_size=args.batch_size,
        top_k=args.top_k,
    )

    if args.query:
        print(f"\n질문: {args.query}")
        for name, result in (
            ("overlap", overlap_search(args.query, chunks, top_k=args.top_k)),
            ("bm25", bm25_search(args.query, chunks, top_k=args.top_k)),
            ("embedding", dense[0]),
        ):
            print(f"[{name}]")
            for i, item in enumerate(result, 1):
                print(f" {i}위 {item['chunk_id']} 점수={item['score']:.5f} · {item['section']}")
        return

    rows = compare(chunks, gold, dense, top_k=args.top_k)
    print_results(rows, gold, top_k=args.top_k, inspect_case=args.inspect)
    payload = {
        "scope": "LEARNING_ONLY_NOT_INDEPENDENT; 8 passages drawn from user's excerpts of 3 manual sections, 10 correlated questions; original PDF not verified",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": {"preset": args.model, "model_id": preset["model_id"], "query_prefix": preset["query_prefix"], "passage_prefix": preset["passage_prefix"]},
        "implementation": "normalized sentence embeddings + dot product (cosine); BM25/Overlap imported unchanged from step02",
        "environment": {"python": platform.python_version(), "sentence_transformers": __import__("sentence_transformers").__version__, "numpy": np.__version__, "device_requested": args.device or "auto"},
        "corpus": "mini_corpus_step02.json",
        "gold": "mini10_gold_step02.json",
        "top_k": args.top_k,
        "summary": summarize(rows, top_k=args.top_k),
        "cases": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n결과 저장: {args.out}")


if __name__ == "__main__":
    run_cli()
