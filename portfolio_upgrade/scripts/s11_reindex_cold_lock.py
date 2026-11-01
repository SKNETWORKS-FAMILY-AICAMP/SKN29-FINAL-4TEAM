"""S11: source-verified, RAG-only cold-lock page indexing and 53-vs-55 search ablation.

Run in Windows CMD from the *repository root*:
    python portfolio_upgrade\\scripts\\s11_reindex_cold_lock.py --check
    python portfolio_upgrade\\scripts\\s11_reindex_cold_lock.py --write
    python portfolio_upgrade\\scripts\\s11_reindex_cold_lock.py --retrieve --write

No training, no Dev/Holdout, no Gold injection. --retrieve uses offline CPU BGE-M3,
not the team's production pgvector. PDF files never enter the output index.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl'
MANIFEST = ROOT / 'portfolio_upgrade/data/s11_index/cold_lock_pages_verified_v1.json'
PATCH = ROOT / 'portfolio_upgrade/data/s11_index/cold_lock_addendum_v1.jsonl'
EXTENDED = ROOT / 'portfolio_upgrade/data/s11_index/cold_lock_candidate_55_v1.jsonl'
PREVIEW = ROOT / 'portfolio_upgrade/experiments/m2_training_readiness/s09_train_retrieval_preview.jsonl'
EXACT_AUDIT = ROOT / 'portfolio_upgrade/experiments/s11_readiness/s11_child_citation_audit.json'
OUT = ROOT / 'portfolio_upgrade/experiments/s11_readiness'
SOURCE_SHA = 'b4ba15c045d7c4eaf1e4cf90dff83ec9fa2c236f9cfcdad85467a42f1921eb78'
PREVIEW_SHA = '3a91e5343907926cc4c834b086916f0cd6fcf7ab467cb8ec62f490e7b4ee6f94'
MODEL_CODE_TO_NEW_CHILD = {
    'WPUIAC425SNW': 'CHILD-WPUIAC425SNW-P027-COLD-LOCK-UNLOCK-001',
    'WPUIAC606SNW': 'CHILD-WPUIAC606SNW-P024-COLD-LOCK-UNLOCK-001',
}
P1_IDS = {
    'SYN-IAC425-101': MODEL_CODE_TO_NEW_CHILD['WPUIAC425SNW'],
    'SYN-IAC606-101': MODEL_CODE_TO_NEW_CHILD['WPUIAC606SNW'],
}


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding='utf-8-sig').splitlines() if l.strip()]


def jsonl(rows: list[dict]) -> str:
    return ''.join(json.dumps(x, ensure_ascii=False, sort_keys=True) + '\n' for x in rows)


def freeze_output(path: Path, content: str) -> None:
    """Do not overwrite experiment artifacts if content differs."""
    if path.is_file() and path.read_text(encoding='utf-8') != content:
        raise FileExistsError(f'서로 다른 파일이 이미 존재해 덮어쓰지 않습니다: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8', newline='\n')


def check_corpus(rows: list[dict], raw_sha: str) -> dict[str,dict]:
    if raw_sha != SOURCE_SHA:
        raise ValueError('53청크 원본 SHA-256 불일치; 이전 파일을 변경하거나 다른 판본입니다')
    if len(rows) != 53:
        raise ValueError(f'원본 53청크 예상, 실제 {len(rows)}')
    seen = {}
    for c in rows:
        cid = c.get('child_id')
        if not cid or cid in seen: raise ValueError(f'원본 child ID 중복/누락: {cid}')
        for field, expected in [('record_type','child'),('retrieval_role','SEARCH_CANDIDATE'),
                                ('verification_status','TEXT_AND_VISUAL_VERIFIED'),
                                ('allowed_use','RAG_HANDOFF_ONLY')]:
            if c.get(field) != expected:
                raise ValueError(f'{cid}: {field} 정책 불일치')
        seen[cid] = c
    for model, expected_id in MODEL_CODE_TO_NEW_CHILD.items():
        related = [c for c in rows if c['exact_sales_code'] == model and 'COLD-LOCK' in c['child_id']]
        if len(related) != 1 or expected_id in seen:
            raise ValueError(f'{model}: 기존 잠금 요약 청크 또는 신규 ID에 충돌')
    return seen


def verify_source_pdf(manifest: dict, paths: dict[str,Path]) -> None:
    """Optional independent page-level check when the exact PDFs are locally available."""
    if not paths: return
    if set(paths) != set(MODEL_CODE_TO_NEW_CHILD):
        raise ValueError('PDF 확인을 요청하면 425·606 경로를 모두 지정하세요')
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError('PDF 직접 검증 시 pymupdf 설치 필요: python -m pip install pymupdf') from exc
    for item in manifest['records']:
        model = item['model_code']
        pdf = paths[model]
        if not pdf.is_file(): raise FileNotFoundError(pdf)
        if sha_file(pdf).lower() != item['source_pdf_sha256'].lower():
            raise ValueError(f'{model}: 제조사 PDF 원본 해시 불일치')
        doc = fitz.open(pdf)
        page = item['page_number']
        if len(doc) != item['pdf_pages']:
            raise ValueError(f'{model}: PDF 페이지 수가 다름')
        text = doc[page-1].get_text(sort=True)
        for anchor in item['observed_pdf_anchors']:
            if anchor not in text:
                raise ValueError(f'{model} p.{page}: 원문 앵커 없음: {anchor}')
        if model == 'WPUIAC425SNW':
            if '[물] 버튼' not in text: raise ValueError('425의 완료 버튼 근거 미검출')
        elif model == 'WPUIAC606SNW':
            if '출수/출빙' not in text: raise ValueError('606의 완료 버튼 근거 미검출')
        # PyMuPDF output order can depend on versions. Treat this check as provenance
        # reporting; the *PDF byte hash* + semantic anchors are the hard gate.
        here = sha_bytes(text.encode('utf-8'))
        expected = item['page_text_sha256_pymupdf_sorted']
        print(f'[S11] PDF VERIFY | {model} p.{page} / original SHA OK / sorted page text SHA match={here==expected}')


def build_addendum(corpus: list[dict], manifest: dict) -> list[dict]:
    if (manifest.get('status') != 'RAG_REINDEX_PREVIEW_ONLY_NO_SFT'
            or manifest.get('original_53_index_sha256') != SOURCE_SHA
            or manifest.get('s09_snapshot_sha256') != PREVIEW_SHA):
        raise ValueError('추가 청크 출처 계약 또는 원본 해시 불일치')
    if len(manifest.get('records', [])) != 2: raise ValueError('검수된 신규 페이지는 2개여야 합니다')
    originals = {c['exact_sales_code']:c for c in corpus if c['child_id'].endswith('COLD-LOCK-001')}
    result=[]
    for p in manifest['records']:
        model = p['model_code']
        if model not in MODEL_CODE_TO_NEW_CHILD or model not in originals:
            raise ValueError(f'허용되지 않는 제품: {model}')
        if p.get('approved_for_training') is not False:
            raise ValueError('공식 매뉴얼 유래 텍스트의 SFT 학습 승인은 불가능합니다')
        if p.get('status') != 'SOURCE_TEXT_AND_VISUAL_VERIFIED_RAG_PREVIEW_ONLY':
            raise ValueError('PDF 사전검수 상태가 잘못됐습니다')
        if p.get('page_number') != (27 if model=='WPUIAC425SNW' else 24):
            raise ValueError('PDF 출처 페이지 불일치')
        if p.get('source_pdf_sha256','').lower() != originals[model]['source_file_sha256'].lower():
            raise ValueError('기존 검증판과 PDF SHA-256이 다릅니다')
        body = p['text'].strip()
        if not all(t in body for t in ['[설정]', '3초', '[냉수]', '7초']):
            raise ValueError(f'{model}: 냉수 잠금 절차 필수 설명 누락')
        if model == 'WPUIAC425SNW':
            if '[물]' not in body or '출수/출빙' in body: raise ValueError('425 전용 완료 버튼 오류')
        else:
            if '출수/출빙' not in body or '[물]' in body: raise ValueError('606 전용 완료 버튼 오류')
        old = originals[model]
        child = dict(old)  # reuse verified product/policy/lineage fields
        page = p['page_number']
        child.update({
            'child_id': MODEL_CODE_TO_NEW_CHILD[model],
            'child_text': body,
            'child_text_sha256': sha_bytes(body.encode('utf-8')).upper(),
            'page_id': f"{old['document_id']}-P{page:03d}",
            'page_refs': [page],
            'parent_id': f'PARENT-S11-{model}-P{page:03d}',
            'parent_text_sha256': p['page_text_sha256_pymupdf_sorted'].upper(),
            'section_title': '잠금 기능 설정/해제',
            'safe_actions': [body],
            'consultation_conditions': [],
            'source_page_text_sha256': p['page_text_sha256_pymupdf_sorted'].upper(),
            'source_span': {
                'type': 'MANUAL_PARAPHRASE_VISUAL_AND_TEXT_VERIFIED',
                'row_label': '잠금 해제',
                'start_anchor': '잠금 해제',
                'end_anchor': '설정이 완료됩니다.',
                'note': '원문 PDF의 단계와 버튼명을 충실히 요약. 53청크 기존 ID 변경 없음',
            },
            'source_variant_id': f'S11-LOCK-UNLOCK-P{page:03d}-001',
            'generated_at': '2026-11-01',
            'retrieval_role': 'SEARCH_CANDIDATE',
            'verification_status': 'TEXT_AND_VISUAL_VERIFIED',
            'allowed_use': 'RAG_HANDOFF_ONLY',
            's11_training_ready': False,
            's11_source_license_approved_for_training': False,
            's11_source_pdf_page_text_sha256_method': 'PyMuPDF_get_text_sort_true',
            's11_review_scope': 'OFFLINE_RAG_PREVIEW_NOT_DEPLOYMENT',
        })
        if child['evidence_group_id'] != old['evidence_group_id']:
            raise ValueError('기존 Gold 그룹 ID 유지에 실패했습니다')
        result.append(child)
    if len({x['child_id'] for x in result})!=2:
        raise ValueError('새로운 child ID 중복')
    return sorted(result,key=lambda x:x['child_id'])


def check_extended(corpus: list[dict], added: list[dict]) -> list[dict]:
    joined = corpus + added  # original order retained; do not mutate corpus
    if len(joined)!=55 or len({c['child_id'] for c in joined})!=55:
        raise ValueError('확장 55청크/유일 ID 무결성 실패')
    if joined[:53]!=corpus: raise ValueError('기존 53청크가 변경됐습니다')
    if {c['child_id'] for c in joined[53:]}!=set(MODEL_CODE_TO_NEW_CHILD.values()):
        raise ValueError('새 페이지 2건 이외 변경 불가')
    for c in added:
        if c['allowed_use']!='RAG_HANDOFF_ONLY' or c['s11_training_ready']:
            raise ValueError('학습 금지 위반')
    return joined


def validate_frozen_train(rows: list[dict], actual_hash: str) -> list[dict]:
    if actual_hash != PREVIEW_SHA: raise ValueError('S09 고정 Train 입력 SHA-256 다름')
    if len(rows)!=26 or len({r['example_id'] for r in rows})!=26:
        raise ValueError('고정 Train 26건 수/ID 불일치')
    for r in rows:
        if r.get('status')!='PREVIEW_NOT_TRAIN_READY':raise ValueError('S09 파일 상태 불일치')
        if r.get('audit_only',{}).get('split')!='train' or r['audit_only'].get('training_ready') is not False:
            raise ValueError('Dev/Holdout 사용 또는 학습 승인 플래그 오류')
        ms=r.get('messages')
        if [m.get('role') for m in ms]!=['system','user','assistant']:
            raise ValueError('S09 메시지 형식 불일치')
        user=json.loads(ms[1]['content'])
        if any(k in user for k in ('target','gold_evidence_ids','audit_only','expected_action')):
            raise ValueError('검색 입력에 Gold/정답 혼입')
        if not user.get('customer_message') or not user.get('product_code'):
            raise ValueError('질문/제품 코드 누락')
    return rows


def comparison_rows(rows: list[dict], old_ranked: list[list[dict]], new_ranked: list[list[dict]],
                    fixed_audit: dict | None) -> tuple[list[dict],dict]:
    results=[]
    prior = {r['example_id']:r for r in (fixed_audit or {}).get('case_checks',[])}
    drift=[]
    for item,old,new in zip(rows,old_ranked,new_ranked,strict=True):
        case=item['example_id']
        user=json.loads(item['messages'][1]['content'])
        old_ids=[c['chunk_id'] for c in old]
        new_ids=[c['chunk_id'] for c in new]
        if case in prior and old_ids!=prior[case]['exact_child_ids']:
            drift.append(case)
        model=user['product_code']
        new_lock_id=MODEL_CODE_TO_NEW_CHILD.get(model)
        lock_rank=next((i+1 for i,cid in enumerate(new_ids) if cid==new_lock_id),None) if new_lock_id else None
        gold=set(item['audit_only'].get('gold_evidence_ids') or [])
        old_gold={c['evidence_group_id'] for c in old}
        new_gold={c['evidence_group_id'] for c in new}
        res={
            'example_id':case,'source_scenario_id':item['audit_only']['source_scenario_id'],
            'product_code':model,'baseline_53_child_ids':old_ids,
            'candidate_55_child_ids':new_ids,
            'baseline_53_gold_any_FOR_AUDIT_ONLY':bool(gold&old_gold),
            'candidate_55_gold_any_FOR_AUDIT_ONLY':bool(gold&new_gold),
            'baseline_53_all_gold_FOR_AUDIT_ONLY':gold.issubset(old_gold),
            'candidate_55_all_gold_FOR_AUDIT_ONLY':gold.issubset(new_gold),
            'new_lock_detail_top5':lock_rank is not None,
            'new_lock_detail_rank':lock_rank,
            'baseline_53_match_frozen_child_snapshot':(case not in drift) if case in prior else None,
            'training_ready':False,
        }
        results.append(res)
    p1=[r for r in results if r['source_scenario_id'] in P1_IDS]
    summary={
        'status':'S11_BGE_INDEX_ABLATION_NOT_SFT_OR_PRODUCTION',
        'total_train_rows':len(rows),'source_scenarios':len({x['source_scenario_id'] for x in results}),
        'baseline_index_children':53,'candidate_index_children':55,
        'frozen_previous_snapshot_available':bool(prior),
        'baseline_53_drift_count':len(drift),
        'baseline_53_drift_examples':drift,
        'baseline_gold_any_count':sum(x['baseline_53_gold_any_FOR_AUDIT_ONLY'] for x in results),
        'candidate_gold_any_count':sum(x['candidate_55_gold_any_FOR_AUDIT_ONLY'] for x in results),
        'baseline_all_gold_count':sum(x['baseline_53_all_gold_FOR_AUDIT_ONLY'] for x in results),
        'candidate_all_gold_count':sum(x['candidate_55_all_gold_FOR_AUDIT_ONLY'] for x in results),
        'cold_lock_p1_4_rows':len(p1),
        'new_lock_detail_top5_count':sum(x['new_lock_detail_top5'] for x in p1),
        'new_lock_detail_not_in_top5':[x['example_id'] for x in p1 if not x['new_lock_detail_top5']],
        'change_in_produced_child_ids_count':sum(x['baseline_53_child_ids']!=x['candidate_55_child_ids'] for x in results),
        'training_ready':False,'manual_based_data_use_authorized_for_sft':False,
        'notes':[
            '53와 55는 같은 BGE-M3 임베딩 실행의 결과를 재랭킹. 신규 청크는 제품 필터/유사도 임계값을 똑같이 적용.',
            'Cold-lock 4행의 새 페이지 근거 Top-5 진입은 답변 개선이나 학습 승인을 의미하지 않음.',
            '53행 검색 결과가 이전 S09 스냅샷과 다르면 drift를 표시하며 이전 기록과 동등한 실측으로 주장하지 않음.',
            'Gold는 검색/임베딩 전 입력에 넣지 않고 순위 확정 후 지표 계산에만 사용.',
            'Dev/Holdout/학습/운영 DB/LLM 추론 사용 없음.',
        ]
    }
    return results,summary


def retrieve_compare(corpus: list[dict], extended: list[dict], rows: list[dict], fixed_audit: dict | None) -> tuple[list[dict],dict]:
    try:
        from s05_offline_bge_rag import make_embeddings, rank_for_case, MODEL_ID, MODEL_REVISION, TOP_K, SCORE_THRESHOLD
        import numpy as np
    except ImportError as e:
        raise RuntimeError('CPU BGE-M3 비교에 sentence-transformers, numpy 또는 S05 스크립트 필요') from e
    ordered=sorted(extended,key=lambda x:x['child_id'])
    questions=[json.loads(row['messages'][1]['content'])['customer_message'] for row in rows]
    print('[S11] BGE-M3 CPU 실험 시작 | 55청크 / Train 26질문 / 모델 다운로드 가능 / GPU·API 비용 없음',flush=True)
    dv,qv=make_embeddings(ordered,questions,device='cpu',batch_size=4)
    base_indices=[i for i,x in enumerate(ordered) if x['child_id'] not in MODEL_CODE_TO_NEW_CHILD.values()]
    if len(base_indices)!=53:raise ValueError('기존 후보 53개 분리 실패')
    baseline=[ordered[i] for i in base_indices]
    basevec=np.asarray(dv)[base_indices]
    base_ranks=[];new_ranks=[]
    for i,r in enumerate(rows):
        model=json.loads(r['messages'][1]['content'])['product_code']
        old=rank_for_case(baseline,basevec,qv[i],model_code=model)
        new=rank_for_case(ordered,dv,qv[i],model_code=model)
        base_ranks.append(old);new_ranks.append(new)
        print(f"[S11] 비교 {i+1}/{len(rows)} | {r['example_id']} | 53={len(old)} / 55={len(new)}",flush=True)
    details,summary=comparison_rows(rows,base_ranks,new_ranks,fixed_audit)
    summary.update({'model':MODEL_ID,'model_revision':MODEL_REVISION,'top_k':TOP_K,'min_similarity':SCORE_THRESHOLD,
                    'base_index_sha256':sha_file(SOURCE),'extended_index_sha256':sha_bytes(jsonl(extended).encode('utf-8')),
                    'train_snapshot_sha256':sha_file(PREVIEW)})
    return details,summary


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true',help='원본 해시·55청크 사전검사 (기본)')
    p.add_argument('--write',action='store_true',help='기존 53을 보존한 별도 55청크 인덱스 저장')
    p.add_argument('--retrieve',action='store_true',help='BGE-M3 CPU 53 vs 55 비교 (최초 모델 다운로드 가능)')
    p.add_argument('--pdf-425',type=Path,help='선택: IAC425 원본 PDF 해시 및 27쪽 직접 검증')
    p.add_argument('--pdf-606',type=Path,help='선택: IAC606 원본 PDF 해시 및 24쪽 직접 검증')
    a=p.parse_args(argv)
    if bool(a.pdf_425)!=bool(a.pdf_606):
        raise ValueError('PDF 직접 검증을 하려면 두 파일 경로 모두 제공')
    for path in [SOURCE,MANIFEST]:
        if not path.is_file():raise FileNotFoundError(f'필수 파일 없음: {path} (프로젝트 루트 및 ZIP 추출 위치 확인)')
    old=read_jsonl(SOURCE)
    check_corpus(old,sha_file(SOURCE))
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    paths={'WPUIAC425SNW':a.pdf_425,'WPUIAC606SNW':a.pdf_606} if a.pdf_425 else {}
    verify_source_pdf(manifest,paths)
    added=build_addendum(old,manifest)
    extended=check_extended(old,added)
    print('[S11] INDEX CHECK PASS | 기존 53개 불변 + PDF 검수 기반 2개 = 55개',flush=True)
    print('[S11] IAC425 p.27 [물] / IAC606 p.24 출수/출빙 | 두 모델 완료 버튼 구분',flush=True)
    print('[S11] ALL RAG_HANDOFF_ONLY | NO SFT approval, NO Dev/Holdout, NO Gold ranking',flush=True)
    if a.write:
        freeze_output(PATCH,jsonl(added))
        freeze_output(EXTENDED,jsonl(extended))
        meta={'status':'SOURCE_VERIFIED_INDEX_PREVIEW_NOT_TRAIN_READY','source_index_sha256':sha_file(SOURCE),
              'patch_sha256':sha_file(PATCH),'extended_index_sha256':sha_file(EXTENDED),
              'original_index_size':53,'new_index_size':55,'added_child_ids':[x['child_id'] for x in added],
              'source_pdf_provenance':[{k:p[k] for k in ('model_code','page_number','source_pdf_sha256','page_text_sha256_pymupdf_sorted')} for p in manifest['records']],
              'verified_pdf_files_at_user_runtime':bool(paths),'training_ready':False,
              'notes':'PDF 페이지 내용은 준비 과정에서 문자·이미지로 검수. 공식 매뉴얼의 학습 이용 범위는 미확정.'}
        freeze_output(OUT/'s11_cold_lock_index_audit.json',json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
        print('[S11] INDEX WRITE PASS | '+str(EXTENDED.relative_to(ROOT)),flush=True)
    if a.retrieve:
        if not PREVIEW.is_file():raise FileNotFoundError(f'고정 Train 검색 입력 없음: {PREVIEW}')
        rows=validate_frozen_train(read_jsonl(PREVIEW),sha_file(PREVIEW))
        prior=None
        if EXACT_AUDIT.is_file():
            prior=json.loads(EXACT_AUDIT.read_text(encoding='utf-8'))
            sha=(prior.get('source_sha256') or {})
            if sha.get('source_child_chunks')!=SOURCE_SHA or sha.get('s09_preview')!=PREVIEW_SHA:
                raise ValueError('S11 고정 child 원본 해시 불일치')
        details,summary=retrieve_compare(old,extended,rows,prior)
        if a.write:
            freeze_output(OUT/'s11_cold_lock_retrieval_compare.json',json.dumps({'summary':summary,'cases':details},ensure_ascii=False,indent=2)+'\n')
        else:
            print('[S11] NOTE: --write 생략됨. 비교 결과는 저장되지 않음')
        print(f"[S11] RETRIEVAL COMPARISON PASS | 새 냉수 잠금 근거 Top-5 {summary['new_lock_detail_top5_count']}/4 | baseline drift {summary['baseline_53_drift_count']}",flush=True)
        print(f"[S11] 53→55 all-Gold {summary['baseline_all_gold_count']}/26 → {summary['candidate_all_gold_count']}/26 (그룹 단위·학습 정확도 아님)")
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (FileNotFoundError,ValueError,FileExistsError,KeyError,TypeError,RuntimeError) as e:
        print('[S11] ERROR:',e,file=sys.stderr)
        raise SystemExit(1)
