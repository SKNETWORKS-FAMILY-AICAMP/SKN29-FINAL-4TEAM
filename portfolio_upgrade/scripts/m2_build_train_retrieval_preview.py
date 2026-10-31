"""Build an auditable *TRAIN-ONLY* RAG/SFT data preview. Never starts SFT.

Run from repository root (Windows CMD):
  python portfolio_upgrade\\scripts\\m2_build_train_retrieval_preview.py --check
  python portfolio_upgrade\\scripts\\m2_build_train_retrieval_preview.py --retrieve --write

S05 BGE-M3 full-corpus ranking is reused for train examples. Gold IDs are
read ONLY after retrieval for audit / candidate citations, never for ranking.
All outputs remain NOT_TRAIN_READY regardless of apparent correctness.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "portfolio_upgrade/data/training/train_draft_s07_reviewed_v1.jsonl"
CHUNKS = ROOT / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
CONTRACT = ROOT / "portfolio_upgrade/configs/m2_training_input_contract.json"
OUTDIR = ROOT / "portfolio_upgrade/experiments/m2_training_readiness"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(s) for s in path.read_text(encoding="utf-8-sig").splitlines() if s.strip()]


def get_data() -> tuple[list[dict], list[dict], dict]:
    for f in (DATA, CHUNKS, CONTRACT):
        if not f.is_file():
            raise FileNotFoundError(f"필수 파일 없음: {f} (저장소 루트 확인)")
    rows, chunks = load_jsonl(DATA), load_jsonl(CHUNKS)
    policy = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if len(rows) != 26:
        raise ValueError(f"S07 검수본 26건 예상, 실제 {len(rows)}")
    if len(chunks) != 53:
        raise ValueError(f"S05와 같은 후보 청크 53개 예상, 실제 {len(chunks)}")
    ids = [r.get("example_id") for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("example_id 중복")
    source_ids = [r["provenance"]["source_scenario_id"] for r in rows]
    if len(set(source_ids)) != 13:
        raise ValueError("원본 시나리오 13건이 아닙니다")
    groups = {r["provenance"]["semantic_group_id"] for r in rows}
    if len(groups) != 6:
        raise ValueError("서로 다른 의미 그룹 6개가 아닙니다")
    variants = Counter(r["s07"]["variant_kind"] for r in rows)
    if variants != Counter({"source": 13, "paraphrase": 13}):
        raise ValueError(f"원본/재표현의 수가 예상과 다릅니다: {variants}")
    if any(r["provenance"].get("split") != "train" for r in rows):
        raise ValueError("Train 외 사례가 포함되어 있습니다. 중단합니다.")
    if any(r["review"].get("action_label_review_status") != "consistent_with_manual" for r in rows):
        raise ValueError("행동 라벨 미확정 사례가 포함되어 있습니다.")
    if any(r["target"].get("action") not in {"ANSWER", "ASK", "ESCALATE"} for r in rows):
        raise ValueError("허용되지 않은 원본 행동 라벨이 포함되어 있습니다")
    if any(not r["target"].get("assistant_message") for r in rows):
        raise ValueError("검수된 고객 안내 문장이 비어 있습니다.")
    by_child = {c.get("child_id"): c for c in chunks}
    if len(by_child) != len(chunks) or None in by_child:
        raise ValueError("child_id 중복/누락")
    for c in chunks:
        if (c.get("record_type") != "child" or c.get("retrieval_role") != "SEARCH_CANDIDATE"
                or c.get("verification_status") != "TEXT_AND_VISUAL_VERIFIED"
                or c.get("allowed_use") != "RAG_HANDOFF_ONLY"):
            raise ValueError(f"후보 청크 계약 불일치: {c.get('child_id')}")
    if policy.get("status") != "PREVIEW_ONLY_NOT_TRAIN_READY":
        raise ValueError("preview-only 계약이 변경됐습니다. 실행 중단")
    if policy.get("data_use_authorized_for_sft") is not False:
        raise ValueError("학습 데이터 이용 승인은 별도 절차입니다. 자동 승인 금지")
    if policy.get("model_revision") != "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e":
        raise ValueError("Qwen3 버전이 기존 기준선과 다릅니다")
    if hashlib.sha256(policy["system_prompt"].encode("utf-8")).hexdigest() != policy["system_prompt_sha256"]:
        raise ValueError("고정된 B1 시스템 프롬프트가 변경됐습니다")
    return rows, chunks, policy


def pack_record(row: dict, ranked: list[dict], policy: dict) -> dict:
    """Create *suggested* train record. Provided ranked documents must come from retrieval, not Gold."""
    if row["provenance"]["split"] != "train":
        raise ValueError("Dev/Holdout은 학습 데이터로 변환할 수 없습니다")
    model_code = row["input"]["product_code"]
    for c in ranked:
        if c.get("model_code") != model_code:
            raise ValueError("서로 다른 제품 근거가 섞였습니다")
    evidence = []
    for c in ranked:
        group_id = c.get("evidence_group_id")
        if not group_id:
            raise ValueError("검색 근거 그룹 ID 누락")
        # Collapse duplicate child chunks to groups as S05 does.
        existing = next((e for e in evidence if e["id"] == group_id), None)
        if existing:
            existing["text"] += "\n" + c["text"]
            existing["page_refs"] = list(dict.fromkeys(existing["page_refs"] + c["page_refs"]))
        else:
            evidence.append({"id": group_id, "page_refs": c["page_refs"], "text": c["text"]})
    visible = {e["id"] for e in evidence}
    gold = set(row["provenance"].get("gold_evidence_ids") or [])
    # Candidate citation is not yet a confirmed safe citation; will require human check.
    citation_candidates = sorted(gold & visible)
    found_gold = bool(citation_candidates)
    user_payload = {
        "customer_message": row["input"]["customer_message"],
        "previous_answers": row["input"].get("known_conditions", {}).get("previous_answers", []),
        "product_code": model_code,
        "retrieved_evidence": evidence,
        "selected_symptoms": row["input"].get("known_conditions", {}).get("selected_symptoms", []),
    }
    target = {
        "action": row["target"]["action"],
        "customer_message": row["target"]["assistant_message"],
        "cited_evidence_ids": citation_candidates,
        "missing_fields": row["target"].get("missing_fields") or [],
    }
    # Review fields remain OUTSIDE of the LLM input messages.
    return {
        "example_id": row["example_id"],
        "status": "PREVIEW_NOT_TRAIN_READY",
        "messages": [
            {"role": "system", "content": policy["system_prompt"]},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
            {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)},
        ],
        "audit_only": {
            "source_scenario_id": row["provenance"]["source_scenario_id"],
            "split": "train", "semantic_group_id": row["provenance"]["semantic_group_id"],
            "gold_evidence_ids": sorted(gold),
            "retrieved_evidence_group_ids": sorted(visible),
            "gold_in_retrieved": found_gold,
            "citation_candidates_require_human_review": True,
            "model_input_evidence_origin": "S05_BGE_M3_TRAIN_RETRIEVAL_NOT_GOLD_ORACLE",
            "data_use_authorized_for_sft": False,
            "training_ready": False,
            "requires_followup": (["GOLD_NOT_RETRIEVED"] if not found_gold else []) + [
                "DATA_USE_PERMISSION_UNCONFIRMED", "CITATION_AND_SAFETY_REVIEW_PENDING",
                "RETRIEVAL_CONTEXT_TOKEN_LENGTH_NOT_CHECKED",
            ],
        },
    }


def run_retrieval(rows: list[dict], chunks: list[dict], device: str):
    # Existing S05 code implements the exact same BGE-M3 cosine ranking, model filter,
    # top-5 and threshold. Gold never participates in this path.
    from s05_offline_bge_rag import make_embeddings, rank_for_case, passage_text
    candidates = sorted(chunks, key=lambda c: c["child_id"])
    queries = [r["input"]["customer_message"].strip() for r in rows]
    print(f"[M2] Train-only BGE-M3 검색 시작 | {len(candidates)} 청크, {len(queries)} 질문, device={device}", flush=True)
    docvec, qvec = make_embeddings(candidates, queries, device=device, batch_size=4)
    ranked_lists = []
    for i, r in enumerate(rows):
        ranked = rank_for_case(candidates, docvec, qvec[i], model_code=r["input"]["product_code"])
        ranked_lists.append(ranked)
        print(f"[M2] 검색 {i+1}/{len(rows)} | {r['example_id']} | 청크 {len(ranked)}", flush=True)
    return ranked_lists


def run(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="local read-only status; no model download")
    p.add_argument("--retrieve", action="store_true", help="BGE-M3 inference on train only; downloads/loads retriever")
    p.add_argument("--write", action="store_true", help="write preview and audit, never final training dataset")
    p.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    a = p.parse_args(argv)
    if a.write and not a.retrieve:
        p.error("--write는 --retrieve와 함께 사용하세요")
    if not a.check and not a.retrieve:
        p.error("--check 또는 --retrieve를 선택하세요")
    rows, chunks, policy = get_data()
    print("[M2] 구조 검증 통과 | S07 26건 / 원본 13건 / 의미 그룹 6개 / Train-only")
    print("[M2] 학습 이용 승인: NO | 검색 근거 입력: 아직 안 붙임 | Training-ready: 0")
    if a.check and not a.retrieve:
        print("[M2] CHECK PASS (구조 점검만 수행, 학습 승인 아님)")
        return 0
    if a.write and any((OUTDIR / name).exists() for name in (
        "s09_train_retrieval_preview.jsonl", "s09_train_retrieval_audit.json"
    )):
        raise FileExistsError("결과 파일이 이미 있습니다. 중복 검색을 시작하기 전에 기존 결과를 별도 보관하세요.")
    ranked = run_retrieval(rows, chunks, device=a.device)
    records = [pack_record(r, found, policy) for r, found in zip(rows, ranked, strict=True)]
    fail = [r["example_id"] for r in records if not r["audit_only"]["gold_in_retrieved"]]
    prompt_digest = hashlib.sha256(policy["system_prompt"].encode()).hexdigest()
    stats = {
        "status": "PREVIEW_NOT_TRAIN_READY",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(records), "base_and_paraphrase": {"source": 13, "paraphrase": 13},
        "semantic_groups": 6, "holdout_used": False, "dev_used": False,
        "gold_not_found_count": len(fail), "gold_not_found_examples": fail,
        "no_model_training_performed": True,
        "source_sha256": {"train_reviewed": digest(DATA), "source_chunks": digest(CHUNKS), "input_contract": digest(CONTRACT)},
        "eval_reference": policy["frozen_dev_input_sha256"],
        "system_prompt_sha256": prompt_digest,
        "data_use_authorized_for_sft": False,
        "model_input_evidence": "BGE-M3 retrieved, not Gold oracle",
        "next": "Manually review relevance/citations, confirm permitted training source/use, count tokens with full context, extend independent train scenarios before actual SFT",
    }
    print(f"[M2] 검색 근거 연결: {len(records)}/{len(rows)} | Top-5 내 Gold 없는 예시: {len(fail)} | 학습 승인: 0")
    if a.write:
        OUTDIR.mkdir(parents=True, exist_ok=True)
        out = OUTDIR / "s09_train_retrieval_preview.jsonl"
        audit = OUTDIR / "s09_train_retrieval_audit.json"
        if out.exists() or audit.exists():
            raise FileExistsError("기존 결과가 있습니다. 실험 원본 보호를 위해 덮어쓰지 않습니다. 기존 파일을 별도 보관한 후 실행하세요.")
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        audit.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[M2] PREVIEW WRITE PASS | {out.relative_to(ROOT)} | {audit.relative_to(ROOT)}")
    else:
        print("[M2] 읽기 전용 검색 미리보기. 저장하려면 --write 추가")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (ValueError, FileNotFoundError, FileExistsError, KeyError, ImportError) as e:
        print(f"[M2] ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
