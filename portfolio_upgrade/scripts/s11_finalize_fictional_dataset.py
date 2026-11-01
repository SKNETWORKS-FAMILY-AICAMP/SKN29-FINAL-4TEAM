"""S11 v2: apply a small, auditable patch to the original fictional draft.

RUN FROM REPOSITORY ROOT (no model, no GPU, no LLM):
  python portfolio_upgrade/scripts/s11_finalize_fictional_dataset.py --check
  python portfolio_upgrade/scripts/s11_finalize_fictional_dataset.py --write
  python portfolio_upgrade/scripts/s11_finalize_fictional_dataset.py --token-check

The v1 files are NEVER overwritten. v2 outputs are created in
portfolio_upgrade/data/s11_grounded/v2/. Review is AI pre-review, not human approval.
Dev probe inputs and evaluation-only targets are copied unchanged, NOT trained on.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "portfolio_upgrade/data/s11_grounded"
OUT = BASE / "v2"
MODEL = "Qwen/Qwen3-1.7B"
REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
BASE_SHA256 = {
    "s11_fictional_train_draft.jsonl": "c6e775bedafb73a7f0dbbb312bd93b760b77c5010eff082cc42638411a27be27",
    "s11_fictional_probe_inputs.jsonl": "7fc5401cec2f06e924ae540ed33a5a1fe306dc7084d877e705ace991167d9de3",
    "s11_fictional_probe_targets_EVAL_ONLY.jsonl": "c653562c677a6d46387c99dd915dd4066c9a4541b356a124c7f2736055be1ac7",
    "s11_fictional_scenario_manifest.csv": "dce8a65eba91b2d189d014501d62b3f05cac1de8b820c1c701fec5faac4eae6d",
}
ACTIONS = ("ANSWER", "ASK", "ESCALATE", "EXPLAIN_UNSUPPORTED")
EXPECTED_TARGET_FIELDS = {"action", "customer_message", "cited_evidence_ids", "missing_fields"}
EXPECTED_PROMPT_FIELDS = {"customer_message", "product_code", "known_conditions", "provided_evidence"}

# Change once per evidence ID across every case in a family; NEVER make a
# stable ID refer to different text for different customers.
EVIDENCE_REVISIONS = {
    "SIM-EVD-F03-d3b77308792d":
        "SIM-F03에서 흰 바람개비 표시는 저소음 풍량 모드다. 풍량을 한 단계 올리려면 바람 버튼을 짧게 한 번 누른다. 이미 버튼을 눌렀는데 표시가 유지된다면 버튼을 반복해서 누르기보다 현재 풍량 모드 표시가 바뀌었는지 먼저 확인한다.",
    "SIM-EVD-F05-070e6d307ac1":
        "SIM-C05에서 달 아이콘은 야간 표시 모드를 뜻한다. 야간 표시 해제는 디스플레이 버튼 한 번으로 시도할 수 있다. 이미 해당 버튼을 눌렀는데도 달 표시가 유지되면 자동 야간 표시 설정을 확인한다.",
    "SIM-EVD-F06-607494bf43a7":
        "SIM-W06 센서 케이스가 깨져 내부 전선이 노출되면 즉시 사용을 중단하고 전선이나 손상 부분을 만지지 않는다. 특히 주변이 젖었을 때는 장치를 직접 분리하거나 전선을 건드리지 말고 지원센터에 안전한 분리 및 점검을 요청한다.",
}

# Existing case IDs are preserved: we are revising facts, not creating new
# independent scenarios. Each supplied prior answer is an observed condition,
# never a gold label or a completed tool action invented by the model.
PRIOR_CONDITIONS = {
    "S11-F03-f2894b6a": ("fan_button_already_pressed", "바람 버튼을 한 번 눌렀지만 흰 바람개비 표시가 그대로입니다."),
    "S11-F05-c7b75a5a": ("display_button_already_pressed", "디스플레이 버튼을 한 번 눌렀지만 달 아이콘이 계속 켜져 있습니다."),
    "S11-F02-cb37b615": ("alarm_sound_enabled_checked", "알림음이 켜져 있다는 점은 이미 확인했습니다. 알림 모드는 아직 확인하지 못했습니다."),
    "S11-F07-108ed175": ("keypad_reconnected", "키패드는 다시 연결해 봤지만 특수키 입력 문제는 같습니다. 입력 레이아웃은 아직 확인하지 않았습니다."),
    "S11-F04-a410b564": ("charging_stopped", "외관이 부풀어 오른 뒤 충전과 재생은 이미 중단했고 장치를 만지지 않았습니다."),
    "S11-F06-ab234ab5": ("soil_wet_device_attached", "화분 흙이 젖어 있고 센서는 아직 꽂혀 있습니다. 노출된 전선에는 손대지 않았습니다."),
    "S11-F09-7d12d506": ("mop_attachment_present", "물걸레 부착물은 갖고 있지만 자동 세탁 기능은 확인되지 않았습니다."),
    "S11-F10-e6917a55": ("fingerprint_menu_checked", "화면 설정에서 지문 등록 메뉴를 찾아봤지만 보이지 않았습니다."),
}

# Three pre-review flags: F04 ANSWER (no-sound vs quiet-sound), F04 ESCALATE
# (missing do-not-touch), F06 ESCALATE (unsafe disconnect instruction).
QUESTION_REVISIONS = {
    "S11-F04-51940a59": "스피커 연결등이 청록색으로 고정됐고 음악 소리가 너무 작게 들려요. 어떤 상태인가요?",
}
ANSWER_REVISIONS = {
    "S11-F03-f2894b6a": "흰 바람개비는 저소음 풍량 모드 표시입니다. 바람 버튼은 이미 한 번 누르셨으니 같은 조작을 반복하기보다 현재 풍량 모드 표시가 바뀌었는지 확인해 주세요.",
    "S11-F05-c7b75a5a": "달 아이콘은 야간 표시 모드를 뜻합니다. 디스플레이 버튼을 이미 눌렀다면 같은 조작을 반복하기보다 자동 야간 표시 설정을 확인해 주세요.",
    "S11-F04-a410b564": "충전과 재생을 이미 중단하셨다면 다시 켜지 마세요. 배터리가 부풀어 오른 스피커를 만지거나 분해하지 말고 지원센터에 문의해 주세요.",
    "S11-F06-ab234ab5": "센서 사용을 중단하고, 젖은 상태에서 노출 전선이나 손상된 부분을 만지거나 센서를 직접 분리하지 마세요. 지원센터에 안전한 분리와 점검을 요청해 주세요.",
}

FIX_ISSUE_IDS = {"S11-F04-51940a59", "S11-F04-a410b564", "S11-F06-ab234ab5"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(value: object, *, indent: int | None = None) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent)


def load_jsonl(raw: bytes) -> list[dict]:
    return [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]


def jsonl(rows: list[dict]) -> str:
    return "".join(dump(row) + "\n" for row in rows)


def read_verified_source(base_dir: Path) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    raw = {}
    for name, expected in BASE_SHA256.items():
        p = base_dir / name
        if not p.is_file():
            raise FileNotFoundError(f"v1 원본 누락: {p} (S11 v1 --write 결과 필요)")
        b = p.read_bytes()
        got = sha(b)
        if got != expected:
            raise ValueError(f"v1 원본 SHA 불일치 / 원본 보존: {name} (expected {expected[:12]}, actual {got[:12]})")
        raw[name] = b
    train = load_jsonl(raw["s11_fictional_train_draft.jsonl"])
    probe = load_jsonl(raw["s11_fictional_probe_inputs.jsonl"])
    targets = load_jsonl(raw["s11_fictional_probe_targets_EVAL_ONLY.jsonl"])
    manifest = list(csv.DictReader(io.StringIO(raw["s11_fictional_scenario_manifest.csv"].decode("utf-8-sig"))))
    return train, probe, targets, manifest, {k: sha(v) for k, v in raw.items()}


def revise(train: list[dict]) -> tuple[list[dict], list[dict]]:
    changes = []
    evidence_hits = Counter()
    revised, found = [], set()
    for source in train:
        # Never mutate caller's source, even during a partial failure.
        row = json.loads(dump(source))
        cid = row["case_id"]
        prompt = json.loads(row["messages"][1]["content"])
        target = json.loads(row["messages"][2]["content"])
        before = {"question": prompt["customer_message"], "answer": target["customer_message"],
                  "known_conditions": list(prompt["known_conditions"])}
        for evidence in prompt["provided_evidence"]:
            eid = evidence["id"]
            if eid in EVIDENCE_REVISIONS:
                evidence["text"] = EVIDENCE_REVISIONS[eid]
                evidence_hits[eid] += 1
        if cid in QUESTION_REVISIONS:
            prompt["customer_message"] = QUESTION_REVISIONS[cid]
        if cid in PRIOR_CONDITIONS:
            qid, answer = PRIOR_CONDITIONS[cid]
            if prompt["known_conditions"]:
                raise ValueError(f"이미 선행 조건이 있는 사례는 덮어쓰지 않음: {cid}")
            prompt["known_conditions"] = [{"question_id": qid, "answer_text": answer}]
        if cid in ANSWER_REVISIONS:
            target["customer_message"] = ANSWER_REVISIONS[cid]
        if cid in FIX_ISSUE_IDS | set(PRIOR_CONDITIONS):
            found.add(cid)
            changes.append({"case_id": cid, "before": before,
                            "after": {"question": prompt["customer_message"],
                                      "answer": target["customer_message"],
                                      "known_conditions": prompt["known_conditions"]},
                            "original_review_flag_resolved_in_v2": cid in FIX_ISSUE_IDS})
        row["messages"][1]["content"] = dump(prompt)
        row["messages"][2]["content"] = dump(target)
        row["review_status"] = "AI_PRE_REVIEWED_HUMAN_APPROVAL_PENDING"
        row["training_ready_for_waterbridge"] = False
        row["s11_revision"] = "v2"
        row["fictional_engineering_sft_candidate"] = True
        revised.append(row)
    if found != FIX_ISSUE_IDS | set(PRIOR_CONDITIONS):
        raise ValueError(f"예상 사례 일부를 찾지 못함: {sorted((FIX_ISSUE_IDS | set(PRIOR_CONDITIONS)) - found)}")
    if set(evidence_hits) != set(EVIDENCE_REVISIONS):
        raise ValueError(f"가상 근거 수정 미적용: {sorted(set(EVIDENCE_REVISIONS)-set(evidence_hits))}")
    return revised, changes


def validate(train: list[dict], probe: list[dict], targets: list[dict], manifest: list[dict], changes: list[dict]) -> dict:
    if (len(train), len(probe), len(targets), len(manifest)) != (48, 16, 16, 64):
        raise ValueError("Train48/Probe16 구조 불일치")
    by_id = {x["case_id"]: x for x in train + probe}
    if len(by_id) != 64 or len({x["case_id"] for x in targets}) != 16:
        raise ValueError("case_id 누락 또는 중복")
    train_g = {x["semantic_group_id"] for x in train}
    dev_g = {x["semantic_group_id"] for x in probe}
    if len(train_g) != 12 or len(dev_g) != 4 or train_g & dev_g:
        raise ValueError("의미 그룹 Train/Probe 중복")
    if {x["case_id"] for x in probe} != {x["case_id"] for x in targets}:
        raise ValueError("Probe 입력·평가 정답 ID 불일치")
    actions = Counter()
    condition_rows = []
    evidence_text_by_id: dict[str,set[str]] = defaultdict(set)
    for row in train:
        prompt = json.loads(row["messages"][1]["content"])
        target = json.loads(row["messages"][2]["content"])
        if [m["role"] for m in row["messages"]] != ["system", "user", "assistant"]:
            raise ValueError(f"Train 메시지 순서 불일치: {row['case_id']}")
        if set(prompt) != EXPECTED_PROMPT_FIELDS or set(target) != EXPECTED_TARGET_FIELDS:
            raise ValueError(f"JSON 필드 계약 불일치: {row['case_id']}")
        if not re.fullmatch(r"SIM-[A-Z]\d\d", prompt["product_code"]):
            raise ValueError("실제 제품 코드 차단")
        if len(prompt["provided_evidence"]) != 2:
            raise ValueError("근거 2개 제약 위반")
        if target["action"] not in ACTIONS:
            raise ValueError("허용되지 않은 행동")
        actions[target["action"]] += 1
        if not isinstance(target["missing_fields"], list) or bool(target["missing_fields"]) != (target["action"] == "ASK"):
            raise ValueError("ASK missing_fields 또는 비ASK 필드 오류")
        if len(target["cited_evidence_ids"]) != 1:
            raise ValueError("단일 명시 인용 제약 위반")
        es = {e["id"]:e for e in prompt["provided_evidence"]}
        if len(es) != 2 or not set(target["cited_evidence_ids"]).issubset(es):
            raise ValueError("인용 ID가 입력 근거와 불일치")
        for eid, e in es.items():
            if not re.fullmatch(r"SIM-EVD-F\d\d-[0-9a-f]{12}", eid):
                raise ValueError("근거 ID 누출 형식")
            if e["source_kind"] != "ORIGINAL_FICTIONAL_POLICY":
                raise ValueError("외부 매뉴얼 근거가 섞임")
            evidence_text_by_id[eid].add(e["text"])
        conditions = prompt["known_conditions"]
        if conditions:
            condition_rows.append(row["case_id"])
            for c in conditions:
                if set(c) != {"question_id", "answer_text"} or not c["answer_text"].strip():
                    raise ValueError("previous_answers 계약 위반")
        for bad in ("SK매직", "WaterBridge", "WPU-IAC", "WPU-JAC", "WPUIAC", "WPUJAC"):
            if bad in dump(row):
                raise ValueError("비허가 원본 혼입")
        if row["review_status"] != "AI_PRE_REVIEWED_HUMAN_APPROVAL_PENDING" or row["training_ready_for_waterbridge"] is not False:
            raise ValueError("학습 승인 상태 오류")
        if "target_FOR_EVALUATION_ONLY" in row["messages"][1]["content"] or '"action"' in row["messages"][1]["content"]:
            raise ValueError("정답 행동 누출")
    if actions != Counter({a: 12 for a in ACTIONS}):
        raise ValueError(f"행동 분포 변경: {dict(actions)}")
    if len(condition_rows) != 8 or set(condition_rows) != set(PRIOR_CONDITIONS):
        raise ValueError("기존 조건 8행 누락")
    if any(len(texts) != 1 for texts in evidence_text_by_id.values()):
        bad = [k for k, texts in evidence_text_by_id.items() if len(texts)>1]
        raise ValueError(f"동일 근거 ID에 내용 불일치: {bad}")
    if len([r for r in changes if r["original_review_flag_resolved_in_v2"]]) != 3:
        raise ValueError("검수 대상 3건 수정 누락")
    if any(len(row["messages"]) != 2 for row in probe):
        raise ValueError("Probe에 정답 메시지가 혼입됨")
    return {"status":"S11_FICTIONAL_V2_AI_PRE_REVIEWED_NOT_REAL_WATERBRIDGE_APPROVED",
            "train_count":48, "probe_count":16, "train_groups":12, "probe_groups":4,
            "action_train_counts":dict(actions), "prior_condition_examples": len(condition_rows),
            "prior_condition_case_ids":sorted(condition_rows), "review_fixes":3,
            "unchanged_probe_targets":True, "same_id_same_evidence_text":True,
            "probe_role":"DEV_PROBE_ONLY_ALREADY_PRE_REVIEWED_NOT_BLIND_FINAL",
            "manual_based_data_use_authorized":False,
            "fictional_sft_engineering_pilot_eligible":True,
            "human_signed_off":False,
            "note":"This pre-review is an AI-authored content check. Toy pilot only, never claim real service efficacy."}


def render_cards(train: list[dict]) -> str:
    out = ["# S11 가상 데이터 v2 — 변경 사례 빠른 검수", "",
           "> **AI 사전 검수본. 인간 최종 검수 승인 아님.** 기존 F01~F16 / 64건은 유지; Train 48건 가운데 기존 확인사항 8건 반영; 기존 Probe 16건은 내용·정답 모두 변경하지 않음.",
           "> **가상 제품 규칙**으로 만든 자료이며 실제 SK매직 매뉴얼/고객 응대의 학습 승인이 아님.", ""]
    ids = FIX_ISSUE_IDS | set(PRIOR_CONDITIONS)
    for row in train:
        if row["case_id"] not in ids:
            continue
        u = json.loads(row["messages"][1]["content"])
        t = json.loads(row["messages"][2]["content"])
        out += [f"## {row['case_id']} — {t['action']}", "",
                f"**질문:** {u['customer_message']}", "",
                f"**이미 확인한 내용:** {dump(u['known_conditions'])}", "",
                "**모델에 제공하는 가상 근거:**", ""]
        for ev in u["provided_evidence"]:
            out.append(f"- `{ev['id']}` — {ev['text']}")
        out += ["", "**정답 JSON:**", "", "```json", dump(t,indent=2), "```", "",
                "- [ ] 원문 가상 규칙과 조건이 일치하는가?", "- [ ] 이미 한 행동을 무조건 반복하지 않았는가?",
                "- [ ] 부정·안전 조건과 답변이 충돌하지 않는가?", "- [ ] 인용 ID와 내용이 실제 주장을 지지하는가?", ""]
    return "\n".join(out)+"\n"


def build(base_dir: Path = BASE) -> tuple[dict[str,str], dict]:
    train, probe, targets, manifest, source_hashes = read_verified_source(base_dir)
    v2_train, changes = revise(train)
    summary = validate(v2_train, probe, targets, manifest, changes)
    summary["source_sha256"] = source_hashes
    outputs = {
        "s11_fictional_train_v2.jsonl": jsonl(v2_train),
        "s11_fictional_probe_inputs_v2.jsonl": jsonl(probe),
        "s11_fictional_probe_targets_EVAL_ONLY_v2.jsonl": jsonl(targets),
        "s11_fictional_v2_changes.json": dump({"changes":changes,"changed_source_evidence_ids":sorted(EVIDENCE_REVISIONS)},indent=2)+"\n",
        "s11_fictional_v2_review_cards.md": render_cards(v2_train),
    }
    summary["output_sha256"] = {k:sha(v.encode("utf-8")) for k,v in outputs.items()}
    outputs["s11_fictional_v2_summary.json"] = dump(summary,indent=2)+"\n"
    return outputs, summary


def _ids(value: object) -> list[int]:
    value = value["input_ids"] if hasattr(value,"keys") else value
    if not isinstance(value,list) or not all(isinstance(x,int) for x in value):
        raise TypeError("토크나이저 input_ids는 1차원 정수 리스트여야 함")
    return value


def token_check(outputs: dict[str,str], max_length: int = 768):
    try:
        from transformers import AutoTokenizer
    except ImportError as e:
        raise RuntimeError("--token-check 실행 시 transformers 설치가 필요합니다") from e
    tok = AutoTokenizer.from_pretrained(MODEL,revision=REVISION,trust_remote_code=False)
    train = [json.loads(s) for s in outputs["s11_fictional_train_v2.jsonl"].splitlines() if s]
    probe = [json.loads(s) for s in outputs["s11_fictional_probe_inputs_v2.jsonl"].splitlines() if s]
    lengths, a_lens, p_lens = [],[],[]
    for r in train:
        messages = r["messages"]
        p = _ids(tok.apply_chat_template(messages[:2],tokenize=True,add_generation_prompt=True,enable_thinking=False))
        a = tok.encode(messages[2]["content"] + "<|im_end|>",add_special_tokens=False)
        if not p or not a or len(p)+len(a)>max_length:
            raise ValueError(f"S11 v2 토큰 초과/빈 응답: {r['case_id']}: {len(p)}+{len(a)}")
        labels = [-100]*len(p)+a
        if any(v!=-100 for v in labels[:len(p)]) or not any(v!=-100 for v in labels[len(p):]):
            raise ValueError("완료 토큰 loss 마스킹 오류")
        lengths.append(len(labels)); a_lens.append(len(a))
    for r in probe:
        p = _ids(tok.apply_chat_template(r["messages"],tokenize=True,add_generation_prompt=True,enable_thinking=False))
        if not p or len(p)>max_length:
            raise ValueError("Probe 토큰 길이 초과")
        p_lens.append(len(p))
    return {"train_min":min(lengths),"train_max":max(lengths),"probe_max":max(p_lens),
            "assistant_token_min":min(a_lens),"max_length":max_length,"mask_ok":True}


def write_same_or_new(directory: Path, outputs: dict[str,str]) -> None:
    # Preflight *all* conflicts before writing anything to disk.
    for name,content in outputs.items():
        p=directory/name
        if p.exists() and p.read_bytes()!=content.encode("utf-8"):
            raise FileExistsError(f"서로 다른 내용의 v2 결과를 덮어쓰지 않음: {p}")
    directory.mkdir(parents=True,exist_ok=True)
    for name,content in outputs.items():
        p=directory/name
        if not p.exists():
            with p.open("x",encoding="utf-8",newline="\n") as f:
                f.write(content)


def main(argv: list[str] | None = None) -> int:
    ap=argparse.ArgumentParser()
    opt=ap.add_mutually_exclusive_group()
    opt.add_argument("--check",action="store_true")
    opt.add_argument("--write",action="store_true")
    opt.add_argument("--token-check",action="store_true")
    ns=ap.parse_args(argv)
    files,summary=build()
    print("[S11 v2] CONTENT CHECK PASS | 3 target issues resolved / 8 previous-condition examples")
    print("[S11 v2] SPLIT PASS | Train 48 / Dev probe 16 / groups 12+4 / actions 12 each")
    print("[S11 v2] SOURCE SHA PASS | original v1 untouched / evidence IDs consistent / no WaterBridge manuals")
    if ns.token_check:
        metrics=token_check(files)
        print("[S11 v2] TOKEN CHECK PASS | "+dump(metrics))
    if ns.write:
        write_same_or_new(OUT,files)
        print("[S11 v2] WRITE PASS | portfolio_upgrade/data/s11_grounded/v2/")
    else:
        print("[S11 v2] CHECK PASS (no file write / no model training)")
    print("[S11 v2] Fictional engineering candidate only; human review pending / real SFT approval: NO")
    return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except (ValueError,FileNotFoundError,FileExistsError,KeyError,AssertionError,RuntimeError,TypeError) as e:
        print("[S11 v2] ERROR: "+str(e),file=sys.stderr)
        raise SystemExit(1)
