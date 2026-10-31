"""S08/B1: strong-prompt *untrained* Qwen3 baseline with frozen Dev retrieval inputs.

This is a second prompt condition, NOT SFT and NOT a final holdout evaluation.
Only the system prompt is changed relative to the S08/B0 run. The six original
user JSON messages and evidence snapshots are identical. The script NEVER
reads target labels, human grades, Train rows, or Holdout.

Local/CPU: python portfolio_upgrade/scripts/s08_strong_prompt_baseline.py --check
CUDA:      python portfolio_upgrade/scripts/s08_strong_prompt_baseline.py --run
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

# Reuse the exact model-loading, input checking and strict JSON parsing rules
# of B0. Keep this module in the same scripts/ directory as s08_qwen_baseline.py.
import s08_qwen_baseline as b0

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / 'portfolio_upgrade/experiments/s08_baseline'
BASE_INPUT_SHA = 'b52adfb98546eb9d0bc096038ee64bcb7d34bcf571ab16a0e97491943a6f17ee'
BASE_CONTRACT_SHA = 'db1b93f65c646cffda38dfb4789f8c5d209ba525eb03e58fd03c750635f424b1'
BASE_RETRIEVAL_SHA = '57836eee9203c9fbecfb37d2b4bbd90f5c7e673ad239c4d8657e453ee7c03913'

# General behavioral instructions; no Dev case text, case labels or Gold IDs.
# Changing this prompt is the ONLY experimental intervention in B1.
STRONG_SYSTEM_PROMPT = """당신은 정수기 고객지원 응대 보조 AI입니다. 고객 문의의 제품 코드, 이미 확인된 사항, 제공된 공식 근거를 구분해서 판단하세요.

판단 규칙 (우선순위 순):
1. 누수·전기 위험처럼 즉시 안전 대응이 필요한 증상은 일반 사용 방법을 먼저 안내하지 않습니다. 해당 제품의 관련 공식 근거에 맞는 안전 조치를 안내하고 ESCALATE를 선택합니다. 원인이나 수리 성공을 단정하지 않습니다.
2. 어느 물 종류에서 문제가 발생하는지, 필요한 조건을 이미 확인했는지 불명확하면 임의 진단·일괄 조치 대신 ASK를 선택합니다. 고객이 확인할 수 있는 핵심 질문만 구체적으로 제시합니다.
3. ANSWER는 질문과 직접 관련되고 제품 코드 및 적용 조건이 일치하는 공식 근거가 충분할 때만 선택합니다. 근거가 있더라도 다른 증상·제품·조건의 조치를 섞지 않습니다.
4. EXPLAIN_UNSUPPORTED는 제공된 신뢰 가능한 제품 기능 정보가 해당 기능의 미지원을 명시적으로 확인해 줄 때만 선택합니다. 검색에서 관련 문단을 찾지 못한 것만으로 기능이 없다고 단정하지 않습니다.
5. 제공된 관련 근거가 없거나 내용이 불충분하면 추측해서 조작법·원인·연락처를 만들지 않습니다. 정보 부족이면 ASK, 공식 확인이나 상담이 필요한 경우 ESCALATE를 선택합니다.
6. 인용은 답변 내용과 직접 관계가 있는 제공 근거 ID만 사용합니다. 인용할 관련 문서가 없으면 빈 리스트를 사용합니다. 관련 없는 문단을 인용해서 주장을 정당화하지 않습니다.
7. previous_answers에 이미 명시된 고객의 확인 결과나 조치를 무시하거나 고객이 하지 않은 행동을 완료했다고 주장하지 않습니다.

출력은 다른 문구, 설명, 코드블록, 마크다운 없이 유효한 JSON 객체 하나만 작성하세요. 다음 네 필드를 모두 정확히 포함하세요.
{
  "action": "ANSWER 또는 ASK 또는 ESCALATE 또는 EXPLAIN_UNSUPPORTED",
  "customer_message": "고객에게 보일 한국어 안내 또는 추가 질문",
  "cited_evidence_ids": [],
  "missing_fields": []
}
- action에는 위 네 라벨 중 하나만 사용합니다.
- cited_evidence_ids는 제공된 공식 근거 ID의 문자열 리스트이며, 없는 ID를 생성하면 안 됩니다.
- missing_fields는 ASK 시 추가 확인해야 할 항목명의 문자열 리스트입니다. 불필요하면 []입니다.
- customer_message는 정중하고 간결하게 작성하고, 근거가 없는 정밀 조작·수치·연락처를 넣지 않습니다.
- JSON을 출력한 뒤 어떤 문자도 추가하지 않습니다."""


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_b1_messages(original_messages: list[dict]) -> list[dict]:
    """Only replace the system message. Never mutate the frozen records."""
    if len(original_messages) != 2 or [m.get('role') for m in original_messages] != ['system', 'user']:
        raise ValueError('B0 Dev 입력 system/user 구조가 아닙니다.')
    if STRONG_SYSTEM_PROMPT == original_messages[0]['content']:
        raise ValueError('B0/B1 시스템 프롬프트가 같습니다.')
    return [
        {'role': 'system', 'content': STRONG_SYSTEM_PROMPT},
        {'role': 'user', 'content': original_messages[1]['content']},
    ]


def verify() -> tuple[list[dict], str, str]:
    _, contract, records, digest = b0.verify_preflight(require_pinned=True)
    if digest != BASE_INPUT_SHA:
        raise ValueError(f'B0 대비 Dev 입력이 변경됐습니다: {digest}')
    if b0.sha(b0.CONTRACT) != BASE_CONTRACT_SHA:
        raise ValueError('B0 대비 eval_contract.yaml 바이트가 변경됐습니다. 파일을 원본으로 되돌리고 다시 확인하세요.')
    if contract['retrieval_file_sha256'] != BASE_RETRIEVAL_SHA:
        raise ValueError('B0 대비 검색 근거 원시파일 SHA 기록이 바뀌었습니다.')
    if b0.MODEL != 'Qwen/Qwen3-1.7B' or b0.REVISION != '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e':
        raise ValueError('B0와 모델/리비전이 다릅니다.')
    for rec in records:
        p = build_b1_messages(rec['messages'])
        if p[1] != rec['messages'][1] or p[0]['role'] != 'system':
            raise ValueError(f"{rec['case_id']}: 사용자 내용이나 근거가 바뀌었습니다.")
    prompt_sha = sha256_bytes(STRONG_SYSTEM_PROMPT.encode('utf-8'))
    print(f'[S08/B1] 같은 Dev {len(records)}건 / 원본 입력 SHA {digest[:12]}...')
    print(f'[S08/B1] B0 대비 변경 변수: 시스템 프롬프트만 (B1 SHA {prompt_sha[:12]}...)')
    print('[S08/B1] 정답(Gold)과 Holdout은 추론에 사용하지 않습니다.')
    return records, digest, prompt_sha


def validate_schema(obj: object) -> bool:
    if not isinstance(obj, dict) or set(obj) != {'action','customer_message','cited_evidence_ids','missing_fields'}:
        return False
    if not isinstance(obj['action'], str) or obj['action'] not in b0.ACTIONS or not isinstance(obj['customer_message'], str) or not obj['customer_message'].strip():
        return False
    if not isinstance(obj['cited_evidence_ids'], list) or not all(isinstance(x,str) for x in obj['cited_evidence_ids']):
        return False
    if not isinstance(obj['missing_fields'], list) or not all(isinstance(x,str) for x in obj['missing_fields']):
        return False
    return True


def run(max_new_tokens: int) -> None:
    rows, digest, prompt_sha = verify()
    if max_new_tokens != 512:
        raise ValueError('B0 비교 조건을 고정해야 하므로 max_new_tokens는 512여야 합니다.')
    try:
        import torch
        import transformers
        from transformers import AutoTokenizer, AutoModelForCausalLM
    except ImportError as exc:
        raise ValueError('GPU 환경에 torch, transformers, accelerate가 필요합니다.') from exc
    if not torch.cuda.is_available():
        raise ValueError('CUDA가 감지되지 않습니다. GPU 환경에서 실행하세요.')
    print(f'[S08/B1] GPU: {torch.cuda.get_device_name(0)} / B1 모델 추론 시작', flush=True)
    tokenizer = AutoTokenizer.from_pretrained(b0.MODEL, revision=b0.REVISION, trust_remote_code=False)
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        b0.MODEL, revision=b0.REVISION, torch_dtype=dtype, device_map='auto', trust_remote_code=False
    ).eval()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = OUTPUT_DIR / f'strong_qwen3_1p7b_{stamp}_{os.getpid()}.jsonl'
    meta = out.with_suffix('.metadata.json')
    metadata = {
        'status': 'STARTED', 'condition': 'B1_STRONG_PROMPT_NO_SFT',
        'model': b0.MODEL, 'revision': b0.REVISION,
        'dev_input_sha256': digest,
        'eval_contract_sha256': BASE_CONTRACT_SHA,
        'retrieval_file_sha256': BASE_RETRIEVAL_SHA,
        'system_prompt_sha256': prompt_sha,
        'system_prompt': STRONG_SYSTEM_PROMPT,
        'difference_from_B0': 'SYSTEM_PROMPT_ONLY',
        'thinking_mode': 'disabled',
        'decoding': {'do_sample': False, 'max_new_tokens': max_new_tokens},
        'gpu': torch.cuda.get_device_name(0),
        'torch_version': torch.__version__, 'transformers_version': transformers.__version__,
        'dtype': str(dtype), 'output_file': str(out),
        'count_expected': len(rows), 'count_finished': 0,
    }
    meta.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    actions: Counter[str] = Counter()
    parse_failures = schema_failures = citation_errors = 0
    with out.open('x',encoding='utf-8',newline='\n') as f:
        for i, rec in enumerate(rows, 1):
            messages = build_b1_messages(rec['messages'])
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
                enable_thinking=False, return_tensors='pt'
            ).to(model.device)
            start = time.perf_counter()
            with torch.inference_mode():
                generated = model.generate(
                    input_ids=prompt, max_new_tokens=max_new_tokens, do_sample=False,
                    pad_token_id=tokenizer.eos_token_id
                )
            elapsed = time.perf_counter() - start
            text = tokenizer.decode(generated[0, prompt.shape[-1]:], skip_special_tokens=True)
            obj, error = b0.extract_json(text)
            ok = validate_schema(obj)
            if error: parse_failures += 1
            if not ok: schema_failures += 1
            action = obj.get('action') if isinstance(obj,dict) else None
            citations = obj.get('cited_evidence_ids') if isinstance(obj,dict) else None
            bad_ids = [x for x in citations if x not in rec['visible_citation_ids']] if isinstance(citations,list) else (['NON_LIST'] if obj is not None else [])
            if bad_ids: citation_errors += 1
            actions[action or 'PARSE_ERROR'] += 1
            result = {
                'case_id': rec['case_id'], 'condition': 'B1_STRONG_PROMPT_NO_SFT',
                'model': b0.MODEL, 'model_revision': b0.REVISION,
                'input_sha256': digest, 'system_prompt_sha256': prompt_sha,
                'output_text': text, 'parsed_json': obj, 'json_parse_error': error,
                'schema_valid': ok, 'output_action_is_allowed': isinstance(action,str) and action in b0.ACTIONS,
                'invalid_citation_ids': bad_ids,
                'seconds_model_generate': round(elapsed,3),
                'prompt_tokens': int(prompt.shape[-1]),
                'output_tokens': int(generated.shape[-1]-prompt.shape[-1]),
                'no_gold_used': True,
            }
            f.write(json.dumps(result,ensure_ascii=False)+'\n')
            f.flush()
            metadata['count_finished'] = i
            meta.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(f"[S08/B1] {i}/{len(rows)} {rec['case_id']} {elapsed:.1f}초 | action={action or 'PARSE_ERROR'} | schema={ok}",flush=True)
    metadata.update({
        'status': 'B1_GENERATED_NOT_HUMAN_GRADED', 'action_counts': dict(actions),
        'json_parse_failures': parse_failures, 'schema_failures': schema_failures,
        'citation_format_errors': citation_errors
    })
    meta.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('[S08/B1] 원시 결과 저장:',out)
    print('[S08/B1] 정답 행동·안전성은 아직 사람 검수 전입니다. 원본 출력 그대로 보존하세요.')


def main() -> int:
    p = argparse.ArgumentParser(description='S08 B1 강한 프롬프트 기준선 (학습 없음)')
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true', help='CPU에서 B0 입력/계약 무결성 검증')
    group.add_argument('--run', action='store_true', help='CUDA GPU에서 B1 기준선 실행')
    p.add_argument('--max-new-tokens',type=int,default=512)
    args=p.parse_args()
    try:
        if args.check: verify()
        else: run(args.max_new_tokens)
    except (ValueError,RuntimeError,OSError,KeyError,json.JSONDecodeError) as exc:
        print('[S08/B1] ERROR:',exc,file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
