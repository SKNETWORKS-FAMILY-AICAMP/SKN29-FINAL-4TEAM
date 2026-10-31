r"""Run Qwen3 base DEV-only inference on the frozen S08 retrieval inputs via a user-hosted OpenAI-compatible model endpoint.

Preview without calls:
  python portfolio_upgrade\scripts\s08_run_same_model_baseline.py --model Qwen/Qwen3-1.7B
Run on explicitly authorized local endpoint (vLLM on Linux/RunPod):
  python portfolio_upgrade\scripts\s08_run_same_model_baseline.py --model Qwen/Qwen3-1.7B --endpoint http://127.0.0.1:8000/v1/chat/completions --run

Requires a running model server; NO OpenAI public API is used. Model outputs are not validated human judgments.
"""
from __future__ import annotations
import argparse, json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path.cwd()
IN=ROOT/'portfolio_upgrade/data/splits/s08_dev_model_inputs.jsonl'
OUT=ROOT/'portfolio_upgrade/experiments/s08_baseline'


def parse_obj(raw):
    raw=raw.strip()
    if raw.startswith('```'):
        raw=re.sub(r'^```(?:json)?\s*','',raw);raw=re.sub(r'\s*```$','',raw)
    try:return json.loads(raw)
    except json.JSONDecodeError:return None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',default='Qwen/Qwen3-1.7B')
    ap.add_argument('--endpoint',default='http://127.0.0.1:8000/v1/chat/completions')
    ap.add_argument('--allow-remote',action='store_true',help='외부 서버로 질문·근거 전송을 명시적으로 허가')
    ap.add_argument('--run',action='store_true',help='서버에 실제 6회 요청')
    ns=ap.parse_args()
    if not IN.exists(): raise SystemExit('S08 dev inputs missing. Run s08_prepare_eval.py --write --retrieval-file ... first')
    rows=[json.loads(x) for x in IN.read_text(encoding='utf-8').splitlines() if x.strip()]
    if len(rows)!=6 or len({r['case_id'] for r in rows})!=6: raise ValueError('Dev6 입력 형식 오류')
    uri=urllib.parse.urlparse(ns.endpoint)
    if uri.scheme not in {'http','https'} or not uri.hostname:
        raise ValueError('올바른 http(s) endpoint를 명시해 주세요')
    if uri.hostname not in {'localhost','127.0.0.1','::1'} and not ns.allow_remote:
        raise ValueError('외부 모델 서버 전송은 --allow-remote 명시 후 가능합니다')
    if any(d in (uri.hostname or '').lower() for d in ('api.openai.com','api.anthropic.com')):
        raise ValueError('공정한 Qwen3 기반 모델 비교를 위해 상용 API 엔드포인트 사용을 제한합니다')
    if not ns.run:
        print('[S08] 미리보기: Dev 6건 / 기본 모델:', ns.model)
        print('모델 API 미호출. 실제 실행은 --run 지정 (서버 기동·비용 확인 필수)')
        return
    outputs=[]
    auth=os.getenv('VLLM_API_KEY','')
    for item in rows:
        payload={
            'model':ns.model,'messages':item['messages'], 'temperature':0.7, 'top_p':0.8,
            'max_tokens':350,'seed':42,
            # Supported by vLLM's OpenAI-compatible chat interface when its chat template supports it.
            'chat_template_kwargs': {'enable_thinking': False}
        }
        req=urllib.request.Request(ns.endpoint,
             data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
             headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+auth} if auth else {})},
             method='POST')
        t0=time.perf_counter()
        with urllib.request.urlopen(req,timeout=180) as res:
            data=json.loads(res.read().decode('utf-8'))
        elapsed=round(time.perf_counter()-t0,3)
        raw=data['choices'][0]['message']['content']
        value=parse_obj(raw)
        outputs.append({'case_id':item['case_id'],
                        'action':value.get('action') if isinstance(value,dict) else None,
                        'customer_message':value.get('customer_message') if isinstance(value,dict) else '',
                        'cited_evidence_ids':value.get('cited_evidence_ids') if isinstance(value,dict) else [],
                        'parse_ok':isinstance(value,dict), 'elapsed_seconds':elapsed,
                        'model_returned':data.get('model'), 'usage':data.get('usage'),
                        'raw_model_output':raw})
        print(item['case_id'],':',outputs[-1]['action'],'(',elapsed,'s)')
    OUT.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=OUT/f'base_qwen3_dev_{stamp}.jsonl'
    out.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in outputs),encoding='utf-8')
    print('Saved:',out)
    print('Next: python portfolio_upgrade\\scripts\\s08_score_dev.py --predictions "'+str(out)+'" --write')

if __name__=='__main__':main()
