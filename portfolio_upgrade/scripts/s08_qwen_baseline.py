"""M2/S08: pin the base model revision, audit Dev inputs, optionally run a base-model baseline.

Repository root (Windows CMD):
    python portfolio_upgrade\\scripts\\s08_qwen_baseline.py --prepare

On CUDA-enabled Linux with torch / transformers / accelerate installed, after
copying the same checked files into the repo:
    python portfolio_upgrade/scripts/s08_qwen_baseline.py --run

Uses ONLY s08_dev_model_inputs.jsonl. Never reads Dev targets, Gold labels or
Holdout during inference. Does not train. Model weight download and GPU required
for --run. Output can include AI-generated text; review before using it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MODEL = "Qwen/Qwen3-1.7B"
REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "portfolio_upgrade/configs/eval_contract.yaml"
INPUTS = ROOT / "portfolio_upgrade/data/splits/s08_dev_model_inputs.jsonl"
TOKENIZER_REPORT = ROOT / "portfolio_upgrade/experiments/s09_model_preflight/tokenizer_report.json"
OUTPUT_DIR = ROOT / "portfolio_upgrade/experiments/s08_baseline"
SOURCE_RETRIEVAL = ROOT / "portfolio_upgrade/experiments/s05_retrieval/retrieval_20261029T152819Z_33220.jsonl"
ACTIONS = {"ANSWER", "ASK", "ESCALATE", "EXPLAIN_UNSUPPORTED"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_contract():
    if not CONTRACT.is_file():
        raise ValueError(f"평가 계약 파일 없음: {CONTRACT}")
    text = CONTRACT.read_text(encoding="utf-8-sig")
    lines = {}
    for ln in text.splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if ":" in ln:
            k, v = ln.split(":", 1)
            lines[k.strip()] = v.strip().strip('"\'')
    return text, lines


def load_checked_inputs() -> tuple[list[dict], str]:
    if not INPUTS.is_file():
        raise ValueError(f"Dev 입력 파일 없음: {INPUTS}")
    rows = [json.loads(line) for line in INPUTS.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(rows) != 6 or len({r.get("case_id") for r in rows}) != 6:
        raise ValueError("Dev 입력은 중복 없는 6건이어야 합니다.")
    if any(not r.get("case_id", "").startswith("SYN-") for r in rows):
        raise ValueError("인식할 수 없는 case_id가 포함됐습니다.")
    for rec in rows:
        case = rec["case_id"]
        ms = rec.get("messages")
        if not isinstance(ms, list) or [m.get("role") for m in ms] != ["system", "user"]:
            raise ValueError(f"{case}: system/user 구조가 아닙니다.")
        if any(not isinstance(m.get("content"), str) for m in ms):
            raise ValueError(f"{case}: 입력 메시지가 문자열이 아닙니다.")
        user = json.loads(ms[1]["content"])
        if any(x in user for x in ("expected_action", "gold_evidence_ids", "gold", "required_actions", "intended_oracle_action")):
            raise ValueError(f"{case}: 모델 입력에 정답이 섞였을 가능성")
        if any(x in rec for x in ("gold_evidence_ids", "expected_action", "intended_oracle_action", "target_output")):
            raise ValueError(f"{case}: 모델 입력 레코드에 정답 필드가 있습니다.")
        evidence = user.get("retrieved_evidence")
        if not isinstance(evidence, list):
            raise ValueError(f"{case}: retrieved_evidence가 리스트가 아닙니다.")
        IDs = [e.get("id") for e in evidence]
        if any(not isinstance(i, str) for i in IDs) or len(IDs) != len(set(IDs)):
            raise ValueError(f"{case}: 근거 ID 중복/누락")
        if set(IDs) != set(rec.get("visible_citation_ids", [])):
            raise ValueError(f"{case}: visible_citation_ids 불일치")
        if not user.get("product_code") or not user.get("customer_message"):
            raise ValueError(f"{case}: 모델 코드/문의 누락")
    return rows, sha(INPUTS)


def verify_preflight(require_pinned: bool):
    contract_text, contract = read_contract()
    rows, input_sha = load_checked_inputs()
    if contract.get("pilot_model") != MODEL:
        raise ValueError("평가 계약의 기반 모델이 바뀌었습니다.")
    if contract.get("dev_cases") != "6" or contract.get("holdout_use") != "FINAL_ONLY_DO_NOT_TUNE":
        raise ValueError("Dev/Holdout 계약이 달라졌습니다.")
    if contract.get("matched_input_for_base_and_sft") != "true":
        raise ValueError("학습 전후 동일 입력 규칙이 비활성화됐습니다.")
    if contract.get("thinking_mode") != "disabled":
        raise ValueError("thinking_mode 계약이 달라졌습니다.")
    if require_pinned and contract.get("model_revision") != REVISION:
        raise ValueError("모델 버전이 고정되지 않았습니다. 먼저 --prepare를 실행하세요.")
    if TOKENIZER_REPORT.is_file():
        report = json.loads(TOKENIZER_REPORT.read_text(encoding="utf-8-sig"))
        if report.get("status") != "TOKENIZER_CHECK_PASSED" or report.get("model_revision") != REVISION:
            raise ValueError("토크나이저 점검에 사용한 모델 버전과 일치하지 않습니다.")
        if report.get("candidate_model") != MODEL:
            raise ValueError("토크나이저 점검에 사용한 기반 모델이 다릅니다.")
    else:
        raise ValueError(f"S09 tokenizer_report.json을 찾을 수 없습니다: {TOKENIZER_REPORT}")
    # This will verify the retrieval snapshot when available locally. Some users
    # copy only Dev model input to remote GPU; the digest is still recorded below.
    if SOURCE_RETRIEVAL.is_file() and contract.get("retrieval_file_sha256") != sha(SOURCE_RETRIEVAL):
        raise ValueError("검색 결과 파일 SHA-256이 평가 계약과 다릅니다.")
    print(f"[S08] Dev {len(rows)}건, 입력 SHA-256 {input_sha}")
    print(f"[S08] 검색 결과 제공된 근거 수: {[len(r['visible_citation_ids']) for r in rows]}")
    print("[S08] Gold/Dev 정답 필드는 모델 입력에 없음 (구조 점검)")
    return contract_text, contract, rows, input_sha


def prepare():
    original, contract, rows, digest = verify_preflight(require_pinned=False)
    old = contract.get("model_revision")
    if old == REVISION:
        print("[S08] 모델 리비전이 이미 고정되어 있습니다.")
    elif old == "TO_BE_PINNED_S09":
        new = re.sub(r"(?m)^model_revision:\s*TO_BE_PINNED_S09\s*$", f"model_revision: {REVISION}", original)
        if new == original:
            raise ValueError("model_revision 변경 대상이 없습니다.")
        CONTRACT.write_text(new.rstrip("\n") + "\n", encoding="utf-8")
        print("[S08] 모델 리비전 고정 완료: " + REVISION)
    else:
        raise ValueError(f"모델 리비전이 예상과 다릅니다. 자동 변경하지 않습니다: {old}")
    verify_preflight(require_pinned=True)
    print("[S08] PREPARE PASS — 학습 전 기준선은 여전히 미측정, 학습 데이터 미승인")


def extract_json(text: str):
    # Never fabricate or repair an invalid output. Preserve the actual model text.
    try:
        return json.loads(text.strip()), None
    except (json.JSONDecodeError, TypeError) as exc:
        return None, str(exc)


def run(max_new_tokens: int):
    _, contract, data, digest = verify_preflight(require_pinned=True)
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
    except ImportError as exc:
        raise ValueError("GPU 환경에 torch, transformers, accelerate를 설치해야 합니다.") from exc
    if not torch.cuda.is_available():
        raise ValueError("GPU(CUDA)가 감지되지 않았습니다. 현재 PC의 CPU 모드에서 전체 모델 다운로드/추론을 시작하지 않습니다.")
    if max_new_tokens < 64 or max_new_tokens > 1024:
        raise ValueError("max_new_tokens는 64~1024 범위여야 합니다.")
    print(f"[S08] GPU: {torch.cuda.get_device_name(0)} | Qwen3 원본 모델 다운로드/추론 시작", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION, trust_remote_code=False)
    torch_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=REVISION, torch_dtype=torch_dtype, device_map="auto", trust_remote_code=False
    ).eval()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUTPUT_DIR / f"base_qwen3_1p7b_{stamp}_{os.getpid()}.jsonl"
    meta = out.with_suffix(".metadata.json")
    metadata = {
        "status": "STARTED", "model": MODEL, "revision": REVISION,
        "dev_input_sha256": digest, "eval_contract_sha256": sha(CONTRACT),
        "retrieval_file_sha256": contract.get("retrieval_file_sha256"),
        "thinking_mode": "disabled", "decoding": {"do_sample": False, "max_new_tokens": max_new_tokens},
        "gpu": torch.cuda.get_device_name(0), "output_file": str(out),
        "count_expected": len(data), "count_finished": 0,
    }
    meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    actions, parse_failures, citation_errors = Counter(), 0, 0
    with out.open("x", encoding="utf-8", newline="\n") as f:
        for i, rec in enumerate(data, 1):
            prompt = tokenizer.apply_chat_template(
                rec["messages"], tokenize=True, add_generation_prompt=True,
                enable_thinking=False, return_tensors="pt",
            ).to(model.device)
            t0 = time.perf_counter()
            with torch.inference_mode():
                generated = model.generate(
                    input_ids=prompt, max_new_tokens=max_new_tokens, do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            elapsed = time.perf_counter() - t0
            text = tokenizer.decode(generated[0, prompt.shape[-1]:], skip_special_tokens=True)
            obj, json_error = extract_json(text)
            if json_error is not None:parse_failures += 1
            action = obj.get("action") if isinstance(obj, dict) else None
            citations = obj.get("cited_evidence_ids") if isinstance(obj, dict) else None
            if isinstance(citations, list):
                invalid_citations = [x for x in citations if x not in rec["visible_citation_ids"]]
            else:
                invalid_citations = ["NON_LIST"] if obj is not None else []
            if invalid_citations:citation_errors += 1
            actions[action or "PARSE_ERROR"] += 1
            result = {
                "case_id": rec["case_id"], "model": MODEL, "model_revision": REVISION,
                "input_sha256": digest, "output_text": text, "parsed_json": obj,
                "json_parse_error": json_error, "output_action_is_allowed": action in ACTIONS,
                "invalid_citation_ids": invalid_citations, "seconds_model_generate": round(elapsed, 3),
                "prompt_tokens": int(prompt.shape[-1]),
                "output_tokens": int(generated.shape[-1] - prompt.shape[-1]),
                "no_gold_used": True,
            }
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            metadata["count_finished"] = i
            meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[S08] {i}/{len(data)} {rec['case_id']} {elapsed:.1f}초 | action={action or 'PARSE_ERROR'}", flush=True)
    metadata.update({"status": "BASELINE_GENERATED_NOT_HUMAN_GRADED", "action_counts": dict(actions),
                     "json_parse_failures": parse_failures, "citation_format_errors": citation_errors})
    meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[S08] 학습 전 모델 원시 응답 6건 생성 완료:", out)
    print("[S08] 행동 정답률/필수 조치/안전성은 미채점 — 별도 정답 비교 및 사람 검수 필요")


def main():
    parser = argparse.ArgumentParser(description="Qwen3-1.7B S08 평가 계약 및 Dev 기반선")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--prepare", action="store_true", help="로컬 환경: 버전 고정 + 정답 누출/입력 무결성 점검, 모델 다운로드 없음")
    g.add_argument("--check", action="store_true", help="입력·리비전·계약 재검증")
    g.add_argument("--run", action="store_true", help="GPU 환경: 모델 다운로드 및 Dev 6건 추론, 과금 가능")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    a = parser.parse_args()
    try:
        if a.prepare:prepare()
        elif a.check: verify_preflight(require_pinned=True); print("[S08] CHECK PASS")
        else:run(a.max_new_tokens)
    except (ValueError, RuntimeError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("[S08] ERROR:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
