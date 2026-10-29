"""S05: Dev-only OFFLINE BGE-M3 or safe-routed retrieval -> LLM vs Oracle.

This is NOT WaterBridge's public pgvector pipeline. The team's three-model
RAG_HANDOFF_ONLY candidates are indexed in memory solely for an offline test.
Only Dev cases are read. No Gold labels are used to rank or filter documents.

Windows CMD (repository root):
    python portfolio_upgrade\\scripts\\s05_offline_bge_rag.py --preview
    python portfolio_upgrade\\scripts\\s05_offline_bge_rag.py --retrieve
    python portfolio_upgrade\\scripts\\s05_offline_bge_rag.py --run --retrieval-file <printed-path> --max-cases 1
    python portfolio_upgrade\\scripts\\s05_offline_bge_rag.py --run --retrieval-file <printed-path>

The --retrieve step loads BAAI/bge-m3 using sentence-transformers; initial
model download may be large. --run calls the billable OpenAI API via the same
model/prompt/schema/auth code as s05_oracle_pilot.py; backend/.env is the
API key fallback. No files under ai/, backend/, or the S04 split are edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from s05_oracle_pilot import (
    CHUNK_FILE,
    SCENARIO_FILE,
    SYSTEM_PROMPT,
    call_openai,
    load_context,
    read_api_key,
    read_jsonl,
    sha256,
    user_prompt,
)

MODEL_ID = "BAAI/bge-m3"
# The exact revision configured in ai/configs/retrieval_policy.yaml
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
TOP_K = 5
SCORE_THRESHOLD = 0.4
OUT_SUBDIR = "portfolio_upgrade/experiments/s05_retrieval"
EXPECTED_CASES = 6


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_cases(root: Path):
    csv_path, dev, scenarios = load_context(root)
    chunks_path = root / CHUNK_FILE
    if not chunks_path.is_file():
        raise FileNotFoundError(f"검색 후보 청크 파일이 없습니다: {chunks_path}")
    raw_chunks = read_jsonl(chunks_path)
    candidates = []
    for c in raw_chunks:
        if (
            c.get("record_type") != "child"
            or c.get("retrieval_role") != "SEARCH_CANDIDATE"
            or c.get("verification_status") != "TEXT_AND_VISUAL_VERIFIED"
            or c.get("allowed_use") != "RAG_HANDOFF_ONLY"
        ):
            raise ValueError(f"후보 청크 검증/허용 범위 불일치: {c.get('child_id')}")
        for k in ("child_id", "child_text", "evidence_group_id", "exact_sales_code", "page_refs"):
            if not c.get(k):
                raise ValueError(f"청크 필수 필드 누락: {k} / {c.get('child_id')}")
        candidates.append(c)
    if len(candidates) != 53 or len(dev) != EXPECTED_CASES:
        raise ValueError(f"예상 후보 53개, Dev 6건과 다릅니다: 청크 {len(candidates)}, Dev {len(dev)}")
    ids = [c["child_id"] for c in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError("청크 식별자 중복")
    candidates.sort(key=lambda x: x["child_id"])
    digest = {
        "s04_csv_sha256": sha256(csv_path),
        "team_scenarios_sha256": sha256(root / SCENARIO_FILE),
        "team_children_sha256": sha256(chunks_path),
    }
    return dev, scenarios, candidates, digest


def passage_text(chunk: dict) -> str:
    # Metadata is NOT a Gold label. It is part of the indexed source record.
    return f"{chunk.get('section_title','')}\n{chunk['child_text']}".strip()


def retrieval_query(scenario: dict) -> str:
    # Keep exactly the customer's raw question. The LLM gets previous answers
    # separately in the identical (except evidence condition label) prompt.
    return scenario["request"]["raw_symptom"].strip()


def make_embeddings(candidates: list[dict], queries: list[str], *, device: str, batch_size: int):
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "BGE-M3 실험에는 numpy와 sentence-transformers가 필요합니다. "
            "ai/.venv에 설치된 파이썬을 사용하거나 python -m pip install sentence-transformers 를 실행하세요."
        ) from exc
    print(f"BGE-M3 모델 로드: {MODEL_ID} / revision={MODEL_REVISION[:12]}... / device={device}", flush=True)
    print("첫 실행은 모델 다운로드 때문에 시간이 걸릴 수 있습니다. API 비용은 발생하지 않습니다.", flush=True)
    model = SentenceTransformer(MODEL_ID, device=device, revision=MODEL_REVISION)
    docvec = np.asarray(model.encode(
        [passage_text(c) for c in candidates], normalize_embeddings=True,
        batch_size=batch_size, show_progress_bar=True,
    ), dtype=np.float32)
    qvec = np.asarray(model.encode(
        queries, normalize_embeddings=True, batch_size=batch_size, show_progress_bar=False,
    ), dtype=np.float32)
    if docvec.shape != (len(candidates), 1024) or qvec.shape != (len(queries), 1024):
        raise ValueError(f"BGE-M3 1024차원 크기 불일치: doc={docvec.shape} query={qvec.shape}")
    if not np.isfinite(docvec).all() or not np.isfinite(qvec).all():
        raise ValueError("NaN/Inf 임베딩 결과")
    return docvec, qvec


def rank_for_case(candidates: list[dict], docvec, qvec, *, model_code: str) -> list[dict]:
    """Per-model exact cosine ranking, 0.4 threshold, Top-5 CHILD candidates.

    This mirrors the *math and basic product/verification constraints* of
    pgvector, not its active DB index, gate/PII/structuring, or postfilters.
    """
    import numpy as np
    valid_ids = [i for i, c in enumerate(candidates) if c["exact_sales_code"] == model_code]
    if not valid_ids:
        return []
    queryvec = np.asarray(qvec, dtype=np.float32)
    scores = (docvec[valid_ids] @ queryvec).tolist()
    ranked = sorted(zip(valid_ids, scores), key=lambda x: (-x[1], candidates[x[0]]["child_id"]))
    out = []
    for i, score in ranked:
        if score < SCORE_THRESHOLD:
            continue
        c = candidates[i]
        out.append({
            "chunk_id": c["child_id"], "evidence_group_id": c["evidence_group_id"],
            "model_code": c["exact_sales_code"], "page_refs": c["page_refs"],
            "score": round(float(score), 6), "text": c["child_text"],
        })
        if len(out) >= TOP_K:
            break
    return out


def distinct_evidence(retrieved: list[dict]) -> list[dict]:
    """Collapse retrieved CHILD results into CITEABLE group IDs.

    Unlike Oracle (which gives all child texts of Gold groups), only the
    selected top-K child texts are provided; this is a normal RAG difference.
    """
    groups: dict[str, dict] = {}
    for c in retrieved:
        gid = c["evidence_group_id"]
        if gid not in groups:
            groups[gid] = {"id": gid, "page_refs": [], "parts": [], "chunk_ids": []}
        groups[gid]["page_refs"].extend(c["page_refs"])
        groups[gid]["parts"].append(c["text"])
        groups[gid]["chunk_ids"].append(c["chunk_id"])
    return [{
        "id": g["id"], "page_refs": list(dict.fromkeys(g["page_refs"])),
        "text": "\n".join(g["parts"]), "chunk_ids": g["chunk_ids"],
    } for g in groups.values()]


def gold_ids(row: dict) -> list[str]:
    # Must be called AFTER retrieval. Gold is never used as an embedding input.
    return [x for x in (row.get("suggested_gold_evidence_group_ids") or row.get("expected_evidence_group_ids") or "").split(";") if x]


def make_records(dev: list[dict], scenarios: dict, candidates: list[dict], digest: dict, docvec, queryvec) -> list[dict]:
    records = []
    for row, vec in zip(dev, queryvec, strict=True):
        case = scenarios[row["scenario_id"]]
        ranked = rank_for_case(candidates, docvec, vec, model_code=row["model_code"])
        evidence = distinct_evidence(ranked)
        expected_ids = gold_ids(row)
        seen = [e["id"] for e in evidence]
        hit = bool(set(expected_ids) & set(seen)) if expected_ids else None
        records.append({
            "case_id": row["scenario_id"],
            "condition": "OFFLINE_BGE_M3_THREE_MODEL_SEARCH_CANDIDATES",
            "retrieval_status": "FOUND_CANDIDATES" if evidence else "NO_MATCH",
            "model_code": row["model_code"],
            "query": retrieval_query(case),
            "ranked_chunks": ranked,
            "evidence": evidence,
            "gold_group_ids_FOR_EVALUATION_ONLY": expected_ids,
            "hit_at_5_when_gold_exists": hit,
            "retrieval_config": {
                "model": MODEL_ID, "revision": MODEL_REVISION, "top_k_chunks": TOP_K,
                "min_cosine_score": SCORE_THRESHOLD, "verified_candidates": len(candidates),
                "method": "offline normalized embeddings exact cosine, exact model filter",
                "caveat": "Not active pgvector/WaterBridge E2E; no runtime gates, query expansion, topic filter or scenario selector",
            },
            "input_sha256": digest,
        })
    return records


def save_records(root: Path, prefix: str, records: list[dict]):
    folder = root / OUT_SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{prefix}_{iso_now()}_{os.getpid()}.jsonl"
    with target.open("x", encoding="utf-8", newline="\n") as out:
        for r in records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    return target


def load_verified_retrieval_file(
    path: Path, dev: list[dict], scenarios: dict, candidates: list[dict],
    digest: dict, root: Path,
):
    """Read either original unfiltered search OR safe-routing output.

    Normalizes both formats so the SAME LLM prompt/client runs over the selected
    evidence. Gold labels are validated for reporting, never fed into the prompt.
    Does not contact the embedding model, PostgreSQL or OpenAI.
    """
    rows = read_jsonl(path)
    expected_ids = [r["scenario_id"] for r in dev]
    if len(rows) != len(dev) or [r.get("case_id") for r in rows] != expected_ids:
        raise ValueError("검색 결과의 6개 Dev 사례 ID/순서가 S04 Dev와 다릅니다.")

    kinds = {"SAFE_ROUTED" if "safe_routed" in r else "BASELINE" for r in rows}
    if len(kinds) != 1:
        raise ValueError("검색 파일에 기존/안전 라우팅 형식이 혼합돼 있습니다.")
    kind = kinds.pop()
    child_by_id = {c["child_id"]: c for c in candidates}
    groups = None
    if kind == "SAFE_ROUTED":
        from s05_safe_routing_guard import choose_model_candidates
        groups = {g["evidence_group_id"]: g for g in read_jsonl(
            root / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
        )}

    normalized = []
    for line, (rec, dev_row) in enumerate(zip(rows, dev, strict=True), start=1):
        case_id = dev_row["scenario_id"]
        if rec.get("input_sha256") != digest:
            raise ValueError(f"{case_id}: 검색 당시 데이터 SHA와 현재 데이터가 다릅니다.")
        if rec.get("model_code") != dev_row["model_code"]:
            raise ValueError(f"{case_id}: 모델 코드가 현재 Dev 입력과 다릅니다.")
        if rec.get("query") != retrieval_query(scenarios[case_id]):
            raise ValueError(f"{case_id}: 질문 원문이 현재 Dev 입력과 다릅니다.")
        expected_gold = sorted(gold_ids(dev_row))

        if kind == "SAFE_ROUTED":
            from s05_safe_routing_guard import NO_WATER
            config = rec.get("config") or {}
            if (config.get("embedding") != MODEL_ID or
                config.get("revision") != MODEL_REVISION or
                config.get("top_k") != TOP_K or
                config.get("threshold") != SCORE_THRESHOLD or
                config.get("offline_only") is not True):
                raise ValueError(f"{case_id}: BGE 검색 조건이 기존 실험과 다릅니다.")
            if sorted(rec.get("gold_ids_evaluation_only", [])) != expected_gold:
                raise ValueError(f"{case_id}: 정답 근거 집합이 현재 Dev CSV와 다릅니다.")
            approved, decision = choose_model_candidates(
                candidates, groups, query=rec["query"], model_code=rec["model_code"]
            )
            if rec.get("route") != decision.route:
                raise ValueError(f"{case_id}: 저장된 라우팅과 현재 질문 기반 규칙이 다릅니다.")
            ranked = rec["safe_routed"]["ranked"]
            evidence = rec["safe_routed"]["evidence"]
            actual_hit = rec["safe_routed"].get("hit_at_5")
            approved_ids = {c["child_id"] for c in approved}
            if decision.route != NO_WATER and ranked != rec["baseline"]["ranked"]:
                raise ValueError(f"{case_id}: 미필터 경로에서 검색 순위가 변경됐습니다.")
            strategy = "SAFE_ROUTING_BGE_M3"
        else:
            if rec.get("condition") != "OFFLINE_BGE_M3_THREE_MODEL_SEARCH_CANDIDATES":
                raise ValueError(f"{case_id}: 기존 BGE 검색 파일 형식이 아닙니다.")
            if sorted(rec.get("gold_group_ids_FOR_EVALUATION_ONLY", [])) != expected_gold:
                raise ValueError(f"{case_id}: Gold가 현재 Dev와 다릅니다.")
            ranked = rec["ranked_chunks"]
            evidence = rec["evidence"]
            actual_hit = rec["hit_at_5_when_gold_exists"]
            approved_ids = {c["child_id"] for c in candidates if c["exact_sales_code"] == rec["model_code"]}
            decision = None
            strategy = "UNFILTERED_BGE_M3"

        if len(ranked) > TOP_K or len({c["chunk_id"] for c in ranked}) != len(ranked):
            raise ValueError(f"{case_id}: 중복 청크 또는 Top-K 초과")
        if any(not isinstance(c.get("score"), (int,float)) or c["score"] < SCORE_THRESHOLD for c in ranked):
            raise ValueError(f"{case_id}: 유사도 임계값에 맞지 않는 청크가 있습니다.")
        if any(ranked[i]["score"] < ranked[i+1]["score"] for i in range(len(ranked)-1)):
            raise ValueError(f"{case_id}: 점수 내림차순이 아닙니다.")
        for c in ranked:
            child = child_by_id.get(c["chunk_id"])
            if (child is None or c["chunk_id"] not in approved_ids or
                c["model_code"] != rec["model_code"] or
                c["evidence_group_id"] != child["evidence_group_id"] or
                c["text"] != child["child_text"] or
                c["page_refs"] != child["page_refs"]):
                raise ValueError(f"{case_id}: 검색 결과가 공식 후보 청크와 일치하지 않습니다: {c.get('chunk_id')}")

        if evidence != distinct_evidence(ranked):
            raise ValueError(f"{case_id}: LLM에 주는 근거가 검색 청크에서 유도되지 않았습니다.")
        computed_hit = (bool(set(expected_gold) & {e["id"] for e in evidence})
                        if expected_gold else None)
        if actual_hit is not computed_hit:
            raise ValueError(f"{case_id}: 근거 Hit 값이 재계산 결과와 다릅니다.")
        normalized.append({
            "case_id": case_id, "condition": strategy, "query": rec["query"],
            "model_code": rec["model_code"], "ranked_chunks": ranked,
            "evidence": evidence, "hit_at_5_when_gold_exists": computed_hit,
            "route": rec.get("route") if kind == "SAFE_ROUTED" else None,
            "route_reason": rec.get("route_reason") if kind == "SAFE_ROUTED" else None,
        })
    return normalized


def execute_preview(root: Path, dev: list[dict], scenarios: dict, candidates: list[dict], digest: dict):
    counts = {model: sum(c["exact_sales_code"] == model for c in candidates)
              for model in sorted({c["exact_sales_code"] for c in candidates})}
    print(f"[S05 preview] Dev {len(dev)}건 | 오프라인 공식 후보 청크 {len(candidates)}개 | {counts}")
    for row in dev:
        q = retrieval_query(scenarios[row["scenario_id"]])
        print(f" - {row['scenario_id']} / {row['model_code']} / 질문: {q[:96]}")
    print("참고: S04 Gold/Oracle 행동라벨은 검색에 사용하지 않습니다. Holdout은 검색/응답/평가에 사용하지 않습니다.")
    print("--preview: 임베딩 모델·OpenAI 호출 없음, 파일 저장 없음")


def execute_retrieve(root: Path, dev: list[dict], scenarios: dict, candidates: list[dict], digest: dict, args):
    qs = [retrieval_query(scenarios[row["scenario_id"]]) for row in dev]
    vectors, qvectors = make_embeddings(candidates, qs, device=args.device, batch_size=args.batch_size)
    records = make_records(dev, scenarios, candidates, digest, vectors, qvectors)
    print("\n[S05 offline retrieval] 정답 근거 그룹 검색 Hit@5 (5건 양성만 평가)")
    hits = 0
    positive = 0
    for rec in records:
        if rec["hit_at_5_when_gold_exists"] is not None:
            positive += 1
            hits += int(rec["hit_at_5_when_gold_exists"])
        top = ", ".join(e["id"] for e in rec["evidence"][:3]) or "없음"
        x = rec["hit_at_5_when_gold_exists"]
        print(f"  {rec['case_id']}: {'HIT' if x else 'MISS' if x is False else 'NO_GOLD'} | {top}")
    path = save_records(root, "retrieval", records)
    print(f"Positive evidence hit: {hits}/{positive} (학습용 Dev 소표본)")
    print("NO_GOLD 1건은 검색 실패로 판정하지 않음. 실제 서비스에서는 JAC 얼음 문의를 정책 Gate가 별도로 차단함.")
    print(f"검색 결과 파일: {path}")
    print("다음: python portfolio_upgrade\\scripts\\s05_offline_bge_rag.py --run --retrieval-file 위_경로")


def execute_run(root: Path, dev: list[dict], scenarios: dict, candidates: list[dict], digest: dict, args):
    if args.retrieval_file is None:
        raise ValueError("--run에는 --retrieval-file 경로가 필요합니다. --retrieve 먼저 실행하세요.")
    retrieval = load_verified_retrieval_file(Path(args.retrieval_file), dev, scenarios, candidates, digest, root)
    to_run = list(zip(dev, retrieval, strict=True))[:args.max_cases]
    print(f"[S05] 오프라인 검색 근거 → 동일 LLM 응답 {len(to_run)}건 / model={args.model}")
    print("실제 OpenAI API 호출 (과금 가능); 공개 WaterBridge 서비스/pgvector E2E가 아닙니다.")
    key = read_api_key(root, args.env_file)
    prefix = "rag_safe" if retrieval[0]["condition"] == "SAFE_ROUTING_BGE_M3" else "rag"
    target = root / OUT_SUBDIR / f"{prefix}_{iso_now()}_{os.getpid()}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    correct = 0
    with target.open("x", encoding="utf-8", newline="\n") as f:
        for row, rec in to_run:
            start = time.perf_counter()
            evidence = rec["evidence"]
            # Original Oracle script's system prompt, model settings and JSON schema.
            # Only the supplied retrieved evidence and its description change.
            prompt = user_prompt(scenarios[row["scenario_id"]], evidence)
            prompt = prompt.replace("Oracle 제공", "오프라인 검색 결과")
            try:
                answer, metadata = call_openai(key, model=args.model, prompt=prompt)
                valid_ids = {e["id"] for e in evidence}
                invalid_ids = [i for i in answer["cited_evidence_ids"] if i not in valid_ids]
                action_match = answer["action"] == row["intended_oracle_action"]
                correct += int(action_match)
                entry = {
                    "case_id": row["scenario_id"],
                    "condition": ("OFFLINE_SAFE_ROUTED_EVIDENCE_LLM" if rec["condition"] == "SAFE_ROUTING_BGE_M3"
                                  else "OFFLINE_RETRIEVED_EVIDENCE_LLM"),
                    "retrieval_strategy": rec["condition"],
                    "route": rec["route"], "route_reason": rec["route_reason"],
                    "model_code": row["model_code"], "expected_action": row["intended_oracle_action"],
                    "retrieval_hit_at_5": rec["hit_at_5_when_gold_exists"],
                    "retrieved_chunk_ids": [x["chunk_id"] for x in rec["ranked_chunks"]],
                    "evidence_ids_given": [e["id"] for e in evidence],
                    "action_match": action_match, "invalid_cited_ids": invalid_ids,
                    "model_output": answer, "metadata": metadata,
                    "elapsed_seconds": round(time.perf_counter() - start,3),
                    "prompt_sha256": hashlib.sha256((SYSTEM_PROMPT + "\n" + prompt).encode("utf-8")).hexdigest(),
                    "input_sha256": digest,
                    "retrieval_file_sha256": sha256(Path(args.retrieval_file)),
                    "final_accuracy_review": "NOT_GRADED_HUMAN_REVIEW_REQUIRED",
                }
                evidence_mark = ('HIT' if rec['hit_at_5_when_gold_exists'] is True
                                 else 'MISS' if rec['hit_at_5_when_gold_exists'] is False
                                 else 'NO_GOLD')
                print(f"  {row['scenario_id']}: {answer['action']} / 기대 {row['intended_oracle_action']} / 근거 {evidence_mark} / invalid_ids={len(invalid_ids)}", flush=True)
                print(f"    답변: {answer['customer_message'][:240]}", flush=True)
            except Exception as exc:
                entry = {"case_id": row["scenario_id"], "condition":"OFFLINE_RETRIEVED_EVIDENCE_LLM",
                         "error": str(exc)[:700], "input_sha256": digest,
                         "final_accuracy_review": "NOT_GRADED_EXECUTION_ERROR"}
                print(f"  {row['scenario_id']}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
    print(f"\n결과 파일: {target}")
    print(f"행동 분류 일치(내용 안전성 검수 전): {correct}/{len(to_run)}")
    print("Oracle와 비교할 때: PDF 정답 근거를 못 찾았는지 vs 근거가 있어도 조치를 잘못 설명했는지 구분하세요.")
    print("**주의**: Oracle의 미지원 기능 사례는 매뉴얼 사양 페이지를 추가 제공받았으며, 이 오프라인 검색은 팀 후보 청크 53개만 사용합니다. 6번째 사례의 점수 비교는 동일 증거 조건이 아닙니다.")


def main():
    parser = argparse.ArgumentParser(description="S05 Offline BGE-M3 retrieval then OpenAI LLM (Dev only)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="자료 점검만 수행; 모델/API 실행 없음")
    mode.add_argument("--retrieve", action="store_true", help="BGE-M3 로컬 임베딩/검색만 수행; API 호출 없음")
    mode.add_argument("--run", action="store_true", help="저장된 검색 결과로 OpenAI 응답 생성 (과금 가능)")
    mode.add_argument("--verify-retrieval", action="store_true", help="검색 파일 검증만 수행 (API 호출 없음)")
    parser.add_argument("--retrieval-file", type=Path, default=None, help="--retrieve가 출력한 retrieval_...jsonl 파일")
    parser.add_argument("--max-cases", type=int, default=6, help="--run 호출 건수 (1~6)")
    parser.add_argument("--device", default="cpu", help="임베딩 모델 디바이스: cpu 또는 cuda")
    parser.add_argument("--batch-size", type=int, default=4, help="문서 임베딩 배치 크기(기본 4)")
    parser.add_argument("--model", default="gpt-4.1-mini", help="Oracle와 동일한 OpenAI API 모델")
    parser.add_argument("--env-file", default=None, help="OpenAI 키 파일, 기본 backend/.env")
    args = parser.parse_args()
    if not 1 <= args.max_cases <= 6 or args.batch_size < 1:
        parser.error("--max-cases는 1~6, --batch-size는 1 이상이어야 합니다")
    try:
        root = Path(__file__).resolve().parents[2]
        dev, scenarios, candidates, digest = load_cases(root)
        if args.preview:
            execute_preview(root, dev, scenarios, candidates, digest)
        elif args.retrieve:
            execute_retrieve(root, dev, scenarios, candidates, digest, args)
        elif args.verify_retrieval:
            if args.retrieval_file is None:
                raise ValueError("--verify-retrieval에는 --retrieval-file이 필요합니다.")
            results = load_verified_retrieval_file(
                args.retrieval_file, dev, scenarios, candidates, digest, root
            )
            print(f"[S05] Retrieval file: VERIFIED ({results[0]['condition']}, Dev {len(results)}건)")
            for item in results:
                mark = item["hit_at_5_when_gold_exists"]
                outcome = "HIT" if mark is True else "MISS" if mark is False else "NO_GOLD"
                print(f"  {item['case_id']}: {outcome}, {item['route'] or 'UNFILTERED'}, evidence={len(item['evidence'])}")
            print("입력·근거·SHA 검증 완료. OpenAI API 호출 없음. LLM 응답 평가 시 --run 사용.")
        else:
            execute_run(root, dev, scenarios, candidates, digest, args)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
