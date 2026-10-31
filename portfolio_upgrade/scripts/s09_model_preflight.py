r"""S09: Model/tokenizer training-format checks without any model training.

  python portfolio_upgrade\scripts\s09_model_preflight.py
  python portfolio_upgrade\scripts\s09_model_preflight.py --tokenizer-check --write

--tokenizer-check downloads Qwen3-1.7B TOKENIZER only (not model weights). Optional transformers dependency.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

ROOT = Path.cwd()
MODEL = 'Qwen/Qwen3-1.7B'
DATA = ROOT / 'portfolio_upgrade/data/training/train_draft_s07_reviewed_v1.jsonl'
OUT = ROOT / 'portfolio_upgrade/experiments/s09_model_preflight/tokenizer_report.json'
MAX_LENGTH_PILOT = 1536


def load_jsonl(p):
    return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def preview_messages(x):
    # Fact summaries are from S06 manual review, NOT the actual RAG retrieval input.
    facts = x['provenance'].get('manual_pdf_source', {}).get('page_evidence', [])
    fact_preview = [{'page': p['page'], 'summary': p['fact_summary']} for p in facts]
    question = {
        'product_code': x['input']['product_code'], 'customer_message': x['input']['customer_message'],
        'known_conditions': x['input'].get('known_conditions', {}),
        'official_fact_summaries_FOR_TOKENIZATION_PREVIEW_ONLY': fact_preview,
    }
    system = ('정수기 고객 응대 보조 AI. 공식 근거와 적용 조건만 사용합니다. '
              '추측하지 않고 답변/추가질문/상담연결을 판단하며 JSON 객체만 출력합니다.')
    return [{'role':'system','content':system},{'role':'user','content':json.dumps(question,ensure_ascii=False)}]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--tokenizer-check',action='store_true',help='HF tokenizer를 다운로드/사용해 20건 토큰 길이 점검')
    ap.add_argument('--write',action='store_true',help='결과 JSON 기록')
    ns=ap.parse_args()
    if not DATA.exists():
        raise SystemExit('S07 검수본이 없습니다: '+str(DATA))
    data=load_jsonl(DATA)
    if len(data)!=26:
        raise ValueError('예상 S07 26건이 아닙니다: '+str(len(data)))
    # Select up to 20 examples with unique IDs; this is preflight, not model inference.
    sample=data[:20]
    ready=sum(bool(x['review'].get('training_ready')) for x in data)
    result={
        'status':'MODEL_SELECTED_TOKENIZER_NOT_RUN' if not ns.tokenizer_check else 'TOKENIZER_CHECK_PASSED',
        'candidate_model':MODEL, 'model_card_license':'Apache-2.0',
        'model_license_reference':'https://huggingface.co/Qwen/Qwen3-1.7B',
        'owner_manual_training_rights':'NOT_CONFIRMED',
        'S07_draft_count':len(data), 'S07_training_ready':ready,
        'tokenizer_check_sample_count':len(sample) if ns.tokenizer_check else 0,
        'training_performed':False, 'baseline_measured':False,
        'training_config_state':'DRAFT_NOT_EXECUTED',
        'data_sha256':hashlib.sha256(DATA.read_bytes()).hexdigest(),
        'pilot_max_length':MAX_LENGTH_PILOT,
        'chat_template_enable_thinking':False,
        'notes':['Qwen3 text-only candidate; stable same-base comparison required',
                 'Actual training needs independent permission/usage review for manual-derived materials',
                 'SFT model input must use the same frozen retrieved evidence as baseline',
                 'No model weights downloaded by this preflight']
    }
    if ns.tokenizer_check:
        try:
            from transformers import AutoTokenizer
        except ImportError as e:
            raise SystemExit('transformers 설치 후 실행: python -m pip install -U transformers') from e
        revision = None
        try:
            from huggingface_hub import HfApi
            info=HfApi().model_info(MODEL)
            revision=info.sha
            result['model_revision']=revision
            result['model_license_runtime']=getattr(info,'card_data',None).license if getattr(info,'card_data',None) else None
        except Exception as e:
            result['revision_warning']=str(e)
        tok=AutoTokenizer.from_pretrained(MODEL,trust_remote_code=False,**({'revision':revision} if revision else {}))
        lengths=[]
        for item in sample:
            messages=preview_messages(item)
            # Hard-disable thinking; avoid training on hidden reasoning tokens.
            text=tok.apply_chat_template(messages,add_generation_prompt=True,tokenize=False,enable_thinking=False)
            target=json.dumps({'action':item['target']['action'],'customer_message':item['target']['assistant_message']},ensure_ascii=False)
            total=len(tok.encode(text+target,add_special_tokens=False))
            lengths.append({'example_id':item['example_id'],'tokens_estimate':total,
                            'over_max_length':total>MAX_LENGTH_PILOT})
        result['tokenizer_class']=type(tok).__name__
        result['token_lengths']=lengths
        result['min_tokens']=min(x['tokens_estimate'] for x in lengths)
        result['median_tokens']=median(x['tokens_estimate'] for x in lengths)
        result['max_tokens']=max(x['tokens_estimate'] for x in lengths)
        if any(x['over_max_length'] for x in lengths):
            result['status']='TOKENIZER_CHECK_PASSED_WITH_TRUNCATION_WARNING'
    try:
        import torch
        result['torch_version']=torch.__version__
        result['cuda_available']=torch.cuda.is_available()
        if result['cuda_available']:
            result['cuda_device']=torch.cuda.get_device_name(0)
            result['cuda_vram_gb']=round(torch.cuda.get_device_properties(0).total_memory/(1024**3),2)
    except ImportError:
        result['torch_available']=False
        result['cuda_available']=False
    print('[S09] 후보 모델:',MODEL,'| 모델 카드 라이선스: Apache-2.0')
    print('[S09] S07 데이터:',len(data),'| 학습 승인:',ready,'| 실제 학습: 미실행')
    if ns.tokenizer_check:
        print(f'[S09] 토크나이저 점검 {len(sample)}건, 토큰 최소/중앙/최대: {result["min_tokens"]}/{result["median_tokens"]}/{result["max_tokens"]}')
    else:
        print('[S09] tokenizer 점검 전. --tokenizer-check 필요 (네트워크 다운로드)')
    if not ns.write:
        print('미리보기입니다. 결과 저장은 --write 옵션 사용')
    else:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('[S09] 기록:',OUT.relative_to(ROOT))

if __name__=='__main__':main()
