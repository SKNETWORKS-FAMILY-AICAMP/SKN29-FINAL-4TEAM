"""S05: DEV-only Oracle-evidence LLM pilot (not WaterBridge live RAG).

Run from repo root:
  python portfolio_upgrade/scripts/s05_oracle_pilot.py --preview
  python portfolio_upgrade/scripts/s05_oracle_pilot.py --run --max-cases 1
  python portfolio_upgrade/scripts/s05_oracle_pilot.py --run

No non-stdlib dependencies. --run makes billable API calls via OPENAI_API_KEY.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MODEL = "gpt-4.1-mini"
SPLIT_FILE = "portfolio_upgrade/data/splits/s04_reviewed_pilot_split_v2.csv"
SCENARIO_FILE = "data/synthetic/candidates/manual_3model_candidate_scenarios.json"
GROUP_FILE = "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
CHUNK_FILE = "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
JAC_PAGES_FILE = "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl"

SYSTEM_PROMPT = """너는 공식 정수기 사용설명서에만 근거해 응대하는 고객지원 실험용 AI다.
상대의 현재 증상, 이미 시행한 조치, 제품 모델을 구분하라.
- 제품 모델과 제공된 공식 근거에 부합하는 내용만 말한다. 특정 고장 원인을 추측으로 확정하지 않는다.
- 안전 위험(예: 제품 내부 누수)이 있으면 ESCALATE로 분류하고 해당 공식 근거의 즉시 조치와 상담 연결을 안내한다.
- 필수 원인/조건이 불분명해 안내가 달라질 수 있으면 ASK로 분류해 가장 필요한 점을 되묻는다. 조건부 조치는 그 조건을 붙여서만 말한다.
- 공식 문서의 조치만으로 충분하고 안전하게 답할 수 있으면 ANSWER로 분류한다.
- 특정 제품에 없는 기능이라는 근거가 있으면 EXPLAIN_UNSUPPORTED로 분류하고 없는 조작법을 만들어내지 않는다.
- 근거가 불충분하면 안전한 확인 질문 또는 상담 연결을 선택한다. 없는 내용을 만들어내지 않는다.
- 중요 안전 조치(누수 시 밸브/전원/상담, 음용 금지 등)는 근거에 있을 경우 빠뜨리지 않는다.
- cited_evidence_ids에는 제공된 근거 식별자만 넣는다. 사용하지 않은 근거는 인용하지 않는다.
- 실제 수리·상담 예약이나 고객 기록 변경을 수행하지 않는다.
응답은 지정된 JSON 스키마만 따른다."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["ANSWER", "ASK", "ESCALATE", "EXPLAIN_UNSUPPORTED"]},
        "customer_message": {"type": "string"},
        "cited_evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["action", "customer_message", "cited_evidence_ids"],
    "additionalProperties": False,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_context(root: Path):
    csv_path = root / SPLIT_FILE
    if not csv_path.is_file():
        raise FileNotFoundError(f"S04 검수 CSV가 없습니다: {csv_path}\nZIP의 data/splits 파일을 해당 경로에 넣어 주세요.")
    rows = read_csv(csv_path)
    dev = [r for r in rows if r.get("split", "").strip().lower() == "dev"]
    if len(rows) != 30 or len(dev) != 6:
        raise ValueError(f"파일럿 분할 예상 30건/Dev 6건과 다름: {len(rows)}/{len(dev)}")
    if any(r.get("review_status", "").startswith("UNREVIEWED") for r in dev):
        raise ValueError("Dev에 PDF 미검토 사례가 있습니다.")
    scen_path = root / SCENARIO_FILE
    if not scen_path.is_file():
        raise FileNotFoundError(f"팀 원본 합성 시나리오가 없습니다: {scen_path}")
    scenarios = {r["scenario_id"]: r for r in json.loads(scen_path.read_text(encoding="utf-8"))}
    dev.sort(key=lambda r: r["scenario_id"])
    if any(r["scenario_id"] not in scenarios for r in dev):
        raise ValueError("원본 시나리오에서 Dev 사례 ID를 찾을 수 없습니다.")
    return csv_path, dev, scenarios


def evidence_for(root: Path, row: dict) -> list[dict]:
    groups = {g["evidence_group_id"]: g for g in read_jsonl(root / GROUP_FILE)}
    chunks = {c["child_id"]: c for c in read_jsonl(root / CHUNK_FILE)}
    gold_ids = [x for x in row.get("suggested_gold_evidence_group_ids", "").split(";") if x]
    if not gold_ids:
        gold_ids = [x for x in row.get("expected_evidence_group_ids", "").split(";") if x]
    evidence = []
    for gid in gold_ids:
        g = groups.get(gid)
        if not g:
            raise ValueError(f"근거 그룹을 찾을 수 없음: {gid}")
        if g["exact_sales_code"] != row["model_code"]:
            raise ValueError(f"다른 제품 근거가 연결됨: {gid}")
        selected_chunks = []
        for cid in g.get("child_ids", []):
            chunk = chunks.get(cid)
            if not chunk or chunk["exact_sales_code"] != row["model_code"]:
                raise ValueError(f"근거 청크/제품이 다름: {cid}")
            selected_chunks.append(chunk["child_text"])
        evidence.append({"id": gid, "page_refs": g.get("page_refs", []), "text": "\n".join(selected_chunks)})

    # No indexed child for unsupported JAC104 ice function. Official *manual*
    # has model-specific controls/specifications, so the Oracle may use those pages.
    if not evidence and row["scenario_id"] == "SYN-JAC104-033":
        pages = {int(p["page"]): p for p in read_jsonl(root / JAC_PAGES_FILE)}
        for number in (12, 40):
            page = pages[number]
            if page["exact_sales_code"] != row["model_code"]:
                raise ValueError("원본 페이지에 지정된 모델이 서로 다릅니다.")
            evidence.append({
                "id": f"MANUAL-{row['model_code']}-P{number:03d}",
                "page_refs": [number],
                "text": page["text"][:3200],
            })
    if not evidence:
        raise ValueError(f"Oracle용 근거가 없는 Dev 사례입니다: {row['scenario_id']}")
    return evidence


def user_prompt(scenario: dict, evidence: list[dict]) -> str:
    document_text = "\n\n".join(
        f"[근거 ID: {e['id']} / 설명서 쪽: {','.join(map(str,e['page_refs']))}]\n{e['text']}"
        for e in evidence
    )
    return (
        f"제품 코드: {scenario['product']['exact_sales_code']}\n"
        f"고객 문의: {scenario['request']['raw_symptom']}\n"
        f"고객이 이미 답한 정보: {json.dumps(scenario['request'].get('previous_answers', []), ensure_ascii=False)}\n\n"
        f"공식 근거 자료 (Oracle 제공, 평가 정답/행동 라벨은 모델에 공개하지 않음):\n{document_text}"
    )


def read_api_key(root: Path, envfile: str | None) -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    candidates = [Path(envfile)] if envfile else [root / "backend/.env"]
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"^\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*(.*)$", line)
            if m:
                val = m.group(1).strip().strip('"\'')
                if val and not val.startswith("#"):
                    return val
    raise RuntimeError("OPENAI_API_KEY 환경변수나 backend/.env를 찾을 수 없습니다. 키를 채팅에 올리지 마세요.")


def call_openai(api_key: str, *, model: str, prompt: str) -> tuple[dict, dict]:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "temperature": 0,
        "max_completion_tokens": 550,
        "store": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "waterbridge_s05_response", "strict": True, "schema": OUTPUT_SCHEMA},
        },
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {body}") from exc
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError(f"모델 응답에 JSON 본문이 없습니다: finish_reason={data.get('choices',[{}])[0].get('finish_reason')}")
    answer = json.loads(content)
    if (answer.get("action") not in OUTPUT_SCHEMA["properties"]["action"]["enum"]
            or not isinstance(answer.get("customer_message"), str)
            or not isinstance(answer.get("cited_evidence_ids"), list)):
        raise ValueError("모델 응답이 예상 JSON 스키마와 다릅니다.")
    return answer, {"model": data.get("model"), "usage": data.get("usage", {}), "finish_reason": data["choices"][0].get("finish_reason")}


def run(args) -> None:
    root = Path(__file__).resolve().parents[2]
    csv_path, rows, scenarios = load_context(root)
    rows = rows[:args.max_cases]
    print(f"[S05] DEV-only Oracle pilot | {len(rows)} of 6 cases | model={args.model}")
    print("주의: 실제 WaterBridge DB·검색·서비스 E2E 실행이 아닙니다.")
    samples = []
    for row in rows:
        evidence = evidence_for(root, row)
        prompt = user_prompt(scenarios[row["scenario_id"]], evidence)
        samples.append((row, evidence, prompt))
        print(f"- {row['scenario_id']}: gold={row['intended_oracle_action']}, evidence={','.join(x['id'] for x in evidence)}, chars={len(prompt)}")
    if args.preview:
        print("[PREVIEW] 네트워크/API 호출 및 파일 저장 없음. 실행하려면 --run 지정.")
        return
    key = read_api_key(root, args.env_file)
    output_dir = root / "portfolio_upgrade" / "experiments" / "s05_oracle"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"oracle_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{os.getpid()}.jsonl"
    total = 0
    print("\n실제 API 호출 시작. 각 응답은 즉시 JSONL에 저장됩니다.")
    with filename.open("x", encoding="utf-8", newline="\n") as f:
        for row, evidence, prompt in samples:
            start = time.perf_counter()
            try:
                ans, metadata = call_openai(key, model=args.model, prompt=prompt)
                seen_ids = [e["id"] for e in evidence]
                invalid_ids = [id for id in ans["cited_evidence_ids"] if id not in seen_ids]
                action_match = ans["action"] == row["intended_oracle_action"]
                entry = {
                    "case_id": row["scenario_id"], "condition": "ORACLE_MANUAL_EVIDENCE",
                    "model_code": row["model_code"], "expected_action": row["intended_oracle_action"],
                    "required_actions_for_human_review": row["required_actions_from_pdf"],
                    "evidence_ids_given": seen_ids,
                    "action_match": action_match, "invalid_cited_ids": invalid_ids,
                    "model_output": ans, "metadata": metadata,
                    "elapsed_seconds": round(time.perf_counter() - start, 3),
                    "prompt_sha256": hashlib.sha256((SYSTEM_PROMPT + "\n" + prompt).encode("utf-8")).hexdigest(),
                    "input_csv_sha256": sha256(csv_path),
                    "final_accuracy_review": "NOT_GRADED_HUMAN_REVIEW_REQUIRED",
                }
                total += int(action_match)
                print(f"  {row['scenario_id']}: {ans['action']} (기대 {row['intended_oracle_action']}) / 행동 {'일치' if action_match else '불일치'} / citations {'확인' if not invalid_ids else '오류'}")
                print(f"    답변: {ans['customer_message'][:310]}")
            except Exception as exc:
                entry = {
                    "case_id": row["scenario_id"], "condition": "ORACLE_MANUAL_EVIDENCE",
                    "error": str(exc)[:600], "final_accuracy_review": "NOT_GRADED_EXECUTION_ERROR",
                    "input_csv_sha256": sha256(csv_path),
                }
                print(f"  {row['scenario_id']}: ERROR: {str(exc)[:210]}", file=sys.stderr)
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
    print(f"\n완료: {filename}")
    print(f"행동 라벨 일치(참고용): {total}/{len(samples)}; 실제 응답 정확도는 사람 검수 전까지 미확정.")
    print("실험 끝: 이번 스크립트는 Oracle만 실행했습니다. 다음에는 동일 질문의 실제 검색 근거 실험이 필요합니다.")


def main():
    parser = argparse.ArgumentParser(description="WaterBridge S05 DEV-only Oracle-evidence pilot")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="근거 연결만 확인 (API 호출 0회)")
    mode.add_argument("--run", action="store_true", help="실제 OpenAI API 호출 (비용 발생 가능)")
    parser.add_argument("--max-cases", type=int, default=6)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--env-file", default=None, help="환경변수가 설정되지 않았을 때 OPENAI_API_KEY를 읽을 파일 (기본: backend/.env)")
    args = parser.parse_args()
    if not 1 <= args.max_cases <= 6:
        parser.error("--max-cases는 1~6만 허용합니다.")
    try:
        run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
