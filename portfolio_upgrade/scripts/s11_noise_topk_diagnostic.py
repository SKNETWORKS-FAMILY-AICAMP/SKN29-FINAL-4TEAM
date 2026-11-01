"""S11: IAC606 complex-noise missing evidence — inspect rank versus Top-K.

Read-only TRAIN diagnostic. No manual-derived data are trained or distributed.

From Windows repository root:
    python portfolio_upgrade\\scripts\\s11_noise_topk_diagnostic.py --check
    python portfolio_upgrade\\scripts\\s11_noise_topk_diagnostic.py --retrieve --write

Model may download for --retrieve; CUDA and paid APIs are not used. This script
reuses the S05 pinned BGE-M3, normalized embeddings, product filter and 0.4
similarity threshold. Evaluation Gold is consulted ONLY after ranking.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
INDEX53 = ROOT / 'data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl'
SNAPSHOT = ROOT / 'portfolio_upgrade/experiments/m2_training_readiness/s09_train_retrieval_preview.jsonl'
PREVIOUS = ROOT / 'portfolio_upgrade/experiments/s11_readiness/s11_cold_lock_retrieval_compare.json'
OUT = ROOT / 'portfolio_upgrade/experiments/s11_readiness/s11_noise_topk_diagnostic.json'
EXPECTED_INDEX_SHA = 'b4ba15c045d7c4eaf1e4cf90dff83ec9fa2c236f9cfcdad85467a42f1921eb78'
EXPECTED_SNAPSHOT_SHA = '3a91e5343907926cc4c834b086916f0cd6fcf7ab467cb8ec62f490e7b4ee6f94'
NOISE_SOURCE = 'SYN-IAC606-104'
NOISE_REQUIRED_GROUPS = {
    'EVD-WPUIAC606SNW-ICE-MAKING-NOISE-001',
    'EVD-WPUIAC606SNW-DEFROST-NOISE-001',
}
K_VALUES = (5, 8, 10)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_lines(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding='utf-8-sig').splitlines() if ln.strip()]


def validate_data(index_path: Path = INDEX53, snapshot_path: Path = SNAPSHOT,
                  previous_path: Path = PREVIOUS) -> tuple[list[dict], list[dict], dict]:
    for path in (index_path, snapshot_path):
        if not path.is_file():
            raise FileNotFoundError(f'필수 파일 없음: {path}')
    if sha(index_path) != EXPECTED_INDEX_SHA or sha(snapshot_path) != EXPECTED_SNAPSHOT_SHA:
        raise ValueError('원본 53 청크 또는 S09 Train 스냅샷 SHA-256이 고정판과 다릅니다')
    chunks, rows = read_lines(index_path), read_lines(snapshot_path)
    if len(chunks) != 53 or len({c['child_id'] for c in chunks}) != 53:
        raise ValueError('기존 검색 인덱스는 중복 없는 53청크여야 합니다')
    for c in chunks:
        if any(c.get(k) != v for k, v in {
            'record_type': 'child', 'retrieval_role': 'SEARCH_CANDIDATE',
            'verification_status': 'TEXT_AND_VISUAL_VERIFIED',
            'allowed_use': 'RAG_HANDOFF_ONLY',
        }.items()):
            raise ValueError('검색 후보 계약 불일치: '+c['child_id'])
    if len(rows) != 26 or len({r['example_id'] for r in rows}) != 26:
        raise ValueError('고정 Train 26건의 ID 중복 또는 누락')
    if sum(r['audit_only']['source_scenario_id'] == NOISE_SOURCE for r in rows) != 2:
        raise ValueError('복합 소음 BASE/PAR1 두 건이 필요합니다')
    for r in rows:
        a=r.get('audit_only') or {}
        if a.get('split')!='train' or a.get('training_ready') is not False:
            raise ValueError('Train-only, NOT TRAIN READY 계약 위반')
        messages=r.get('messages', [])
        if [x.get('role') for x in messages] != ['system','user','assistant']:
            raise ValueError('기존 모델 입력 대화 형식 불일치')
        user=json.loads(messages[1]['content'])
        if not user.get('product_code') or not user.get('customer_message'):
            raise ValueError('제품·고객 발화 누락')
        if any(x in user for x in ('gold_evidence_ids','target','audit_only','expected_action','answer')):
            raise ValueError('모델 입력에 정답/Gold 포함')
    previous=None
    if previous_path.is_file():
        previous=json.loads(previous_path.read_text(encoding='utf-8-sig'))
        meta=previous.get('summary') or {}
        if (meta.get('base_index_sha256')!=EXPECTED_INDEX_SHA or
                meta.get('train_snapshot_sha256')!=EXPECTED_SNAPSHOT_SHA or
                meta.get('total_train_rows')!=26 or len(previous.get('cases',[]))!=26):
            raise ValueError('S11 기존 53↔55 비교 결과가 다른 버전입니다')
    return chunks, rows, previous


def model_input(row: dict) -> tuple[str,str]:
    """The embedder receives ONLY these values (never labels/Gold)."""
    u=json.loads(row['messages'][1]['content'])
    return u['product_code'], u['customer_message'].strip()


def ranked_for_model(chunks: list[dict], docvec, queryvec, product: str, threshold: float) -> list[dict]:
    """All candidates sorted by cosine then child ID, without Top-K cutoff.

    threshold is retained per candidate so the analysis can distinguish rank
    outside Top-K from similarity below the S05 minimum.
    """
    import numpy as np
    relevant=[i for i,c in enumerate(chunks) if c['exact_sales_code']==product]
    if not relevant:
        return []
    scores=(np.asarray(docvec,dtype=np.float32)[relevant] @ np.asarray(queryvec,dtype=np.float32)).tolist()
    ranked=sorted(zip(relevant,scores),key=lambda e:(-e[1],chunks[e[0]]['child_id']))
    return [{'chunk_id':chunks[idx]['child_id'],'group_id':chunks[idx]['evidence_group_id'],
             'score':round(float(score),6),'passes_threshold':score>=threshold,
             'rank_unthresholded':rank}
            for rank,(idx,score) in enumerate(ranked,1)]


def evaluate_rankings(rows: list[dict], rankings: list[list[dict]], previous: dict|None,
                      *, model_id: str, revision: str, threshold: float) -> dict:
    if len(rows)!=26 or len(rankings)!=26:
        raise ValueError('모든 Train 26질문에 검색이 수행되어야 합니다')
    prev={c['example_id']:c for c in (previous or {}).get('cases',[])}
    details=[];drift=[]
    for row, all_rank in zip(rows,rankings,strict=True):
        case=row['example_id']
        product,_=model_input(row)
        eligible=[c for c in all_rank if c['passes_threshold']]
        top5=[c['chunk_id'] for c in eligible[:5]]
        if case in prev and top5!=prev[case]['baseline_53_child_ids']:
            drift.append(case)
        # Deliberately AFTER scores, sorting, product filtering and threshold.
        gold=set(row['audit_only'].get('gold_evidence_ids') or [])
        snapshots={}
        for k in K_VALUES:
            part=eligible[:k]
            hit={c['group_id'] for c in part}
            snapshots[str(k)]={
                'child_ids':[c['chunk_id'] for c in part],
                'candidate_count':len(part),
                'gold_any_FOR_AUDIT_ONLY':bool(hit & gold),
                'all_declared_gold_FOR_AUDIT_ONLY':gold.issubset(hit),
            }
        record={
            'example_id':case,'source_scenario_id':row['audit_only']['source_scenario_id'],
            'product_code':product, 'topk':snapshots,
            'baseline53_matches_previous_run':None if case not in prev else case not in drift,
        }
        if record['source_scenario_id']==NOISE_SOURCE:
            if product!='WPUIAC606SNW' or gold!=NOISE_REQUIRED_GROUPS:
                raise ValueError('IAC606 소음 원본의 제품/Gold 메타데이터가 달라졌습니다')
            record['noise_evidence_rank_FOR_AUDIT_ONLY']={}
            for gid in sorted(NOISE_REQUIRED_GROUPS):
                hits=[x for x in all_rank if x['group_id']==gid]
                record['noise_evidence_rank_FOR_AUDIT_ONLY'][gid]={
                    'rank_in_product_full_list':hits[0]['rank_unthresholded'] if hits else None,
                    'score':hits[0]['score'] if hits else None,
                    'passes_0_4':hits[0]['passes_threshold'] if hits else False,
                    'first_topk_presence':next((k for k in K_VALUES if any(x['group_id']==gid for x in eligible[:k])),None),
                }
        details.append(record)
    if sum(x['source_scenario_id']==NOISE_SOURCE for x in details)!=2:
        raise ValueError('소음 2건 누락')
    summaries={}
    for k in K_VALUES:
        entries=[x['topk'][str(k)] for x in details]
        summaries[str(k)]={
            'all_declared_gold_count':sum(e['all_declared_gold_FOR_AUDIT_ONLY'] for e in entries),
            'gold_any_count':sum(e['gold_any_FOR_AUDIT_ONLY'] for e in entries),
            'total_returned_children':sum(e['candidate_count'] for e in entries),
            'noise_two_rows_all_gold':sum(x['topk'][str(k)]['all_declared_gold_FOR_AUDIT_ONLY']
                                          for x in details if x['source_scenario_id']==NOISE_SOURCE),
        }
    return {'summary':{
        'status':'S11_NOISE_TOPK_TRAIN_DIAGNOSTIC_NOT_SFT_OR_PRODUCTION',
        'total_train_rows':26,'original_scenarios':13,'noise_probe_rows':2,
        'index_children':53, 'topk':list(K_VALUES), 'threshold':threshold,
        'model':model_id,'model_revision':revision,
        'source_sha256':{'index53':EXPECTED_INDEX_SHA,'train_s09':EXPECTED_SNAPSHOT_SHA},
        'metrics_by_k':summaries,
        'baseline53_drift_vs_previous_comparison_count':len(drift),
        'baseline53_drift_examples':drift,
        'training_ready':False,'manual_based_data_use_authorized_for_sft':False,
        'notes':[
            'The ranker receives ONLY customer text and exact product code; all Gold appears in AFTER-ranking audit only.',
            'TopK=8/10 expansion is a diagnostic, not a general retrieval or response improvement.',
            'Additional irrelevant documents and token costs may increase; no LLM was run to assess response quality.',
            'These 26 rows are in-sample Train variants from 6 groups, not independent evaluation.',
            'This query does NOT assess production pgvector, safety gates, Dev or Holdout.',
        ]},'cases':details}


def run(argv=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check',action='store_true',help='Verify source files and S05 baseline availability, no model download')
    ap.add_argument('--retrieve',action='store_true',help='Run BGE-M3 CPU embeddings and rank all product-matched child documents')
    ap.add_argument('--write',action='store_true',help='Persist summary; requires --retrieve')
    args=ap.parse_args(argv)
    if args.write and not args.retrieve:
        raise ValueError('--write 옵션은 --retrieve와 함께 사용하세요')
    chunks,rows,prev=validate_data()
    print(f'[S11] DATA CHECK PASS | original 53 chunks / Train-only {len(rows)} rows / 2 noise cases | previous={bool(prev)}')
    print('[S11] NO Gold ranking / NO LLM / NO Dev/Holdout / NO SFT permission / NO GPU')
    if not args.retrieve:
        return 0
    try:
        from s05_offline_bge_rag import make_embeddings,rank_for_case,passage_text,MODEL_ID,MODEL_REVISION,SCORE_THRESHOLD
    except ImportError as e:
        raise RuntimeError('S05 BGE-M3 검색기 코드 필요: portfolio_upgrade/scripts/s05_offline_bge_rag.py') from e
    ordered=sorted(chunks,key=lambda x:x['child_id'])
    queries=[model_input(x)[1] for x in rows]
    print('[S11] BGE-M3 CPU full-rank diagnostic | 53 chunks, 26 Train queries',flush=True)
    dv,qv=make_embeddings(ordered,queries,device='cpu',batch_size=4)
    rankings=[]
    for i,row in enumerate(rows):
        product,_=model_input(row)
        ranked=ranked_for_model(ordered,dv,qv[i],product,SCORE_THRESHOLD)
        # Guarantee faithful S05 baseline: Top-5 exactly same IDs and order.
        old=rank_for_case(ordered,dv,qv[i],model_code=product)
        top5=[x['chunk_id'] for x in ranked if x['passes_threshold']][:5]
        if top5 != [x['chunk_id'] for x in old]:
            raise ValueError('S05 rank_for_case 순위와 재계산 Top-5 불일치: '+row['example_id'])
        rankings.append(ranked)
        print(f"[S11] rank {i+1}/{len(rows)} | {row['example_id']} | eligible={sum(x['passes_threshold'] for x in ranked)}",flush=True)
    report=evaluate_rankings(rows,rankings,prev,model_id=MODEL_ID,revision=MODEL_REVISION,threshold=SCORE_THRESHOLD)
    if args.write:
        text=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
        OUT.parent.mkdir(parents=True,exist_ok=True)
        if OUT.exists() and OUT.read_text(encoding='utf-8')!=text:
            raise FileExistsError(f'기존 결과를 덮어쓰지 않습니다: {OUT}. 이전 파일을 따로 백업하세요.')
        OUT.write_text(text,encoding='utf-8',newline='\n')
        print('[S11] WRITE PASS | '+str(OUT.relative_to(ROOT)))
    met=report['summary']['metrics_by_k']
    print(f"[S11] NOISE TOPK PASS | all Gold noise 2 rows: Top5 {met['5']['noise_two_rows_all_gold']}/2 → Top8 {met['8']['noise_two_rows_all_gold']}/2 → Top10 {met['10']['noise_two_rows_all_gold']}/2")
    print(f"[S11] TRAIN ONLY | baseline drift vs preceding S11 run: {report['summary']['baseline53_drift_vs_previous_comparison_count']} | SFT ready: NO")
    return 0


if __name__=='__main__':
    try:raise SystemExit(run())
    except (ValueError,FileExistsError,FileNotFoundError,RuntimeError,KeyError,TypeError) as ex:
        print('[S11] ERROR:',ex,file=sys.stderr)
        raise SystemExit(1)
