"""S11: read-only input conversion to CHILD-level citations (no SFT, no BGE retraining).

Windows from repository root:
    python portfolio_upgrade\\scripts\\s11_child_citation_preview.py --check
    python portfolio_upgrade\\scripts\\s11_child_citation_preview.py --write

Reads existing frozen S09 *grouped* retrieval snapshot and source 53 child chunks.
The exact concatenated text for each retrieved group is decomposed back to
verified source child chunks; any mismatch/ambiguity causes a hard failure.
The original Top-5 search is NOT recomputed, and child global cosine ranks/scores
cannot be recovered from the grouped snapshot.

An optional ablation (ALL verified siblings of an already retrieved group) is
written separately from the exact baseline, and must not be treated as actual
BGE Top-5 results or as user-approved citations.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT/'data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl'
PREVIEW = ROOT/'portfolio_upgrade/experiments/m2_training_readiness/s09_train_retrieval_preview.jsonl'
OUT = ROOT/'portfolio_upgrade/experiments/s11_readiness'

SOURCE_STATUS = 'PREVIEW_NOT_TRAIN_READY'
NEW_STATUS = 'S11_CHILD_CITATION_PREVIEW_NOT_TRAIN_READY'
EVIDENCE_POLICY = 'RAG_HANDOFF_ONLY'
SPLITS = {'train'}
MODEL_MAP = {
    'SYN-IAC425-101': ('WPUIAC425SNW',27,'COLD-LOCK'),
    'SYN-IAC606-101': ('WPUIAC606SNW',24,'COLD-LOCK'),
    'SYN-IAC425-108': ('WPUIAC425SNW',5,'LEAK'),
    'SYN-IAC606-104': ('WPUIAC606SNW',41,'DEFROST-NOISE'),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_index(chunks: list[dict]) -> dict[str,list[dict]]:
    if len(chunks) != 53:
        raise ValueError(f'기존 검증 청크 53개 예상, 실제 {len(chunks)}; 원본 변경 여부 확인')
    children=set()
    by_group=defaultdict(list)
    for c in chunks:
        cid=c.get('child_id')
        if not cid or cid in children:
            raise ValueError(f'child ID 중복/누락: {cid}')
        children.add(cid)
        for key,val in [('record_type','child'),('retrieval_role','SEARCH_CANDIDATE'),
                        ('verification_status','TEXT_AND_VISUAL_VERIFIED'),('allowed_use',EVIDENCE_POLICY)]:
            if c.get(key)!=val:
                raise ValueError(f'{cid}: {key} 계약 오류')
        if not c.get('evidence_group_id') or not c.get('exact_sales_code') or not c.get('child_text'):
            raise ValueError(f'{cid}: 필수 본문/그룹/제품 메타데이터 누락')
        if not isinstance(c.get('page_refs'),list) or not c['page_refs']:
            raise ValueError(f'{cid}: 페이지 근거 누락')
        by_group[c['evidence_group_id']].append(c)
    for values in by_group.values():
        values.sort(key=lambda x:x['child_id'])
    return by_group


def recover_children(group_text: str, candidates: list[dict]) -> list[dict]:
    """Exact de-concatenation; never guess via substring or Gold ID.

    Each source child text may itself include newlines. Accept only a unique
    decomposition using full child_text strings separated by exactly one '\\n'.
    """
    solutions=[]
    def walk(rest: str, selected: list[dict], remaining: list[dict]):
        if not rest:
            solutions.append(selected)
            return
        for c in remaining:
            t=c['child_text']
            if rest==t or rest.startswith(t+'\n'):
                next_rest='' if rest==t else rest[len(t)+1:]
                walk(next_rest,selected+[c],[v for v in remaining if v['child_id']!=c['child_id']])
                if len(solutions)>1:
                    return
    walk(group_text,[],candidates)
    if len(solutions)!=1:
        raise ValueError(f'그룹 청크 복원 실패: 정확한 분해 {len(solutions)}개 (유일하게 1개 필요)')
    return solutions[0]


def view_piece(c: dict, origin: str) -> dict:
    return {
        'id':c['child_id'],
        'evidence_group_id':c['evidence_group_id'],
        'page_refs':c['page_refs'],
        'text':c['child_text'],
        'origin':origin,
    }


def make_pair(row: dict, index: dict[str,list[dict]], expected_count: int | None=5) -> tuple[dict,dict,dict]:
    eid=row['example_id']
    if row.get('status')!=SOURCE_STATUS:
        raise ValueError(f'{eid}: 원본 미리보기 상태가 달라짐')
    audit=row.get('audit_only') or {}
    if audit.get('split')!='train' or audit.get('training_ready') is not False or audit.get('data_use_authorized_for_sft') is not False:
        raise ValueError(f'{eid}: Train-only·학습 금지 계약 위반')
    ms=row.get('messages') or []
    if [m.get('role') for m in ms]!=['system','user','assistant']:
        raise ValueError(f'{eid}: S09 원본 입력 구조 변경')
    user=json.loads(ms[1]['content'])
    if 'gold_evidence_ids' in user or 'audit_only' in user or 'target' in user:
        raise ValueError(f'{eid}: 추론 입력에 정답 필드 누출')
    model=user.get('product_code')
    exact=[]
    sibling=[]
    recovered=[]
    seen=set()
    # Follow group order, then recovered order *within* each group. The global
    # child ranking is NOT recoverable from this grouped S09 snapshot.
    for group in user['retrieved_evidence']:
        gid=group['id']
        candidates=[c for c in index.get(gid,[]) if c['exact_sales_code']==model]
        if not candidates or len(candidates)!=len(index.get(gid,[])):
            raise ValueError(f'{eid}: {gid} / 원본 제품 교차 또는 없는 그룹')
        try:
            selected=recover_children(group['text'],candidates)
        except ValueError as exc:
            raise ValueError(f'{eid}: {gid}: {exc}') from exc
        pages=list(dict.fromkeys(p for c in selected for p in c['page_refs']))
        if pages!=group['page_refs']:
            raise ValueError(f'{eid}: {gid}: 원본 페이지와 청크 재구성이 불일치')
        recovered.extend(selected)
        for c in selected:
            if c['child_id'] in seen: raise ValueError(f'{eid}: 중복 검색 child')
            seen.add(c['child_id'])
            exact.append(view_piece(c,'S09_RETRIEVED_CHILD_EXACT'))
            sibling.append(view_piece(c,'S09_RETRIEVED_CHILD_EXACT'))
        for c in candidates:
            if c['child_id'] not in seen:
                sibling.append(view_piece(c,'GROUP_SIBLING_EXPANSION_NOT_RETRIEVED'))
                seen.add(c['child_id'])
    if expected_count is not None and len(exact)!=expected_count:
        raise ValueError(f'{eid}: 기존 S09 child 검색 {expected_count}건이 복원되지 않음 (복원 {len(exact)})')
    if len({c['id'] for c in exact})!=len(exact) or len({c['id'] for c in sibling})!=len(sibling):
        raise ValueError(f'{eid}: child ID 중복')
    legacy_answer=json.loads(ms[2]['content'])
    old_citations=legacy_answer.get('cited_evidence_ids') or []
    if any(not c.startswith('EVD-') for c in old_citations):
        raise ValueError(f'{eid}: 예상 밖의 기존 그룹 인용 ID')
    gold_groups=set(audit.get('gold_evidence_ids') or [])
    if any(c not in gold_groups for c in old_citations):
        raise ValueError(f'{eid}: 원본 인용과 Gold 그룹 불일치')
    baseline_ids={x['id'] for x in exact}
    if any(not x['id'].startswith('CHILD-') for x in exact+sibling):
        raise ValueError(f'{eid}: child ID 형식 오류')
    common_audit={
        'source_scenario_id':audit['source_scenario_id'],
        'semantic_group_id':audit['semantic_group_id'],
        'split':'train',
        'original_legacy_group_citations':old_citations,
        'gold_evidence_group_ids_FOR_AUDIT_ONLY':sorted(gold_groups),
        'candidate_child_ids_in_gold_groups_NOT_APPROVED': [x['id'] for x in exact if x['evidence_group_id'] in gold_groups],
        'expected_action_FOR_AUDIT_ONLY':legacy_answer.get('action'),
        'reviewed_target_NOT_FOR_SFT':legacy_answer,
        'training_ready':False,
        'source_use_approved_for_training':False,
        'citation_review_complete':False,
        'global_child_rank_recovered':False,
    }
    def create(visible, mode):
        payload={**user,'retrieved_evidence':visible}
        messages=[
            ms[0],
            {'role':'user','content':json.dumps(payload,ensure_ascii=False,sort_keys=True)}
        ]
        return {
            'example_id':eid,
            'status':NEW_STATUS,
            'mode':mode,
            'messages':messages, # no assistant! Cannot be fed to a trainer.
            'visible_citation_ids':[c['id'] for c in visible],
            'audit_only':{**common_audit,
                'retrieved_child_count_exact':len(exact),
                'added_siblings_count':sum(c['id'] not in baseline_ids for c in visible),
                'inference_only_no_assistant_target':True,
                'expansion_is_bge_top5':False if mode=='group_sibling_ablation' else None,
            },
        }
    return create(exact,'exact_child_snapshot'),create(sibling,'group_sibling_ablation'),{
        'example_id':eid,'source_scenario_id':audit['source_scenario_id'],
        'model_code':model,
        'exact_child_ids':[x['id'] for x in exact],
        'expanded_child_ids':[x['id'] for x in sibling],
        'added_child_ids':[x['id'] for x in sibling if x['id'] not in baseline_ids],
        'original_group_ids':[x['id'] for x in user['retrieved_evidence']],
        'gold_groups_FOR_AUDIT_ONLY':sorted(gold_groups),
        'original_group_gold_hit': bool(gold_groups.intersection(g['id'] for g in user['retrieved_evidence'])),
        'all_original_group_gold_present':gold_groups.issubset({g['id'] for g in user['retrieved_evidence']}),
    }


def p1_diagnostic(inventory:list[dict],checks:list[dict]) -> list[dict]:
    by_id={r['example_id']:r for r in checks}
    out=[]
    for source_id,(model,page,topic) in MODEL_MAP.items():
        qualified=[c['child_id'] for c in inventory if c['exact_sales_code']==model and page in c['page_refs'] and topic in c['child_id']]
        for v in ['BASE','PAR1']:
            eid='S07-'+source_id+'-'+v
            if eid not in by_id: raise ValueError(f'P1 사례 누락: {eid}')
            row=by_id[eid]
            out.append({
                'example_id':eid,
                'needed_topic':topic,'pdf_page_reported_from_prior_review':page,
                'matching_verified_child_ids_in_53_chunk_index':qualified,
                'in_exact_child_snapshot':bool(set(qualified).intersection(row['exact_child_ids'])),
                'in_group_expanded_snapshot':bool(set(qualified).intersection(row['expanded_child_ids'])),
                'action':('REINDEX_PDF_PAGE_AFTER_SOURCE_REVIEW' if not qualified else
                          'EVALUATE_RETRIEVAL_RECALL_NO_ORACLE_INJECTION' if not set(qualified).intersection(row['expanded_child_ids']) else
                          'REVIEW_CHILD_CITATION_AND_CONDITION'),
            })
    return out


def review(rows: list[dict],corpus:list[dict],sha:dict) -> tuple[list[dict],list[dict],dict]:
    if len(rows)!=26 or len({x.get('example_id') for x in rows})!=26:
        raise ValueError('기존 26행 검수 자료의 수가 다름')
    idx=prepare_index(corpus)
    originals=Counter()
    all_ex,all_sb,case_checks=[],[],[]
    variable=defaultdict(set)
    for row in rows:
        for e in json.loads(row['messages'][1]['content'])['retrieved_evidence']:
            variable[e['id']].add(e['text'])
        ex,sb,checks=make_pair(row,idx)
        originals[checks['source_scenario_id']]+=1
        all_ex.append(ex);all_sb.append(sb);case_checks.append(checks)
    if len(originals)!=13 or any(v!=2 for v in originals.values()):
        raise ValueError('13개 원본×2 변형 조건과 불일치')
    p1=p1_diagnostic(corpus,case_checks)
    all_groups=sum(len(x['original_group_ids']) for x in case_checks)
    base_count=sum(len(x['exact_child_ids']) for x in case_checks)
    expanded_count=sum(len(x['expanded_child_ids']) for x in case_checks)
    summary={
        'status':NEW_STATUS,
        'source_sha256':sha,
        'source_rows':len(rows),'source_scenarios':len(originals),'source_child_chunks':len(corpus),
        'retrieved_group_instances':all_groups,
        'exact_child_instances':base_count,
        'expanded_child_instances':expanded_count,
        'sibling_child_instances_added':expanded_count-base_count,
        'rows_with_expansion':sum(bool(x['added_child_ids']) for x in case_checks),
        'group_ids_with_variable_text_in_original_snapshot':{k:len(v) for k,v in sorted(variable.items()) if len(v)>1},
        'all_legacy_gold_groups_present_in_snapshot':sum(x['all_original_group_gold_present'] for x in case_checks),
        'at_least_one_legacy_gold_group_present':sum(x['original_group_gold_hit'] for x in case_checks),
        'p1_eight_rows':p1,
        'case_checks':case_checks,
        'disclaimers':[
            'Exact child snapshot reconstructs identities from frozen S09 text; embedding scores and global child ranks cannot be recovered.',
            'Group sibling is an ablation adding all verified children under retrieved group IDs; it is not a BGE Top-5 result.',
            'Expansion does not use Gold to select candidates. Gold remains audit-only.',
            'No original S07/S09 files modified; no Dev/Holdout/model/GPU/API/PDF loaded.',
            'All source chunks are RAG_HANDOFF_ONLY; training and redistribution use are not authorized by this audit.',
            'The assistant answer is deliberately absent from model inputs. Citeable child IDs still need claim-level human review.',
            'Index coverage and citation identity do not establish the correctness or safety of a customer answer.',
        ]
    }
    return all_ex,all_sb,summary


def main(argv=None):
    p=argparse.ArgumentParser()
    m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--check',action='store_true')
    m.add_argument('--write',action='store_true')
    args=p.parse_args(argv)
    for path in [CORPUS,PREVIEW]:
        if not path.is_file():raise FileNotFoundError(f'필수 원본 없음: {path}')
    old=read_jsonl(PREVIEW); children=read_jsonl(CORPUS)
    result=review(old,children,{'source_child_chunks':digest(CORPUS),'s09_preview':digest(PREVIEW)})
    ex,sb,s=result
    print(f"[S11] CHILD RECOVERY PASS | {s['source_rows']} rows / {s['retrieved_group_instances']} group entries / {s['exact_child_instances']} exact child references")
    print(f"[S11] SIBLING ABLATION | +{s['sibling_child_instances_added']} child references / {s['rows_with_expansion']} rows (not BGE ranking)")
    print(f"[S11] VARYING GROUP BODIES: {len(s['group_ids_with_variable_text_in_original_snapshot'])}")
    print(f"[S11] Gold group coverage unchanged: {s['at_least_one_legacy_gold_group_present']}/{len(old)} any | {s['all_legacy_gold_groups_present_in_snapshot']}/{len(old)} all")
    for d in s['p1_eight_rows']:
        print(f"[S11] P1 {d['example_id']} page {d['pdf_page_reported_from_prior_review']} | exact={d['in_exact_child_snapshot']} expanded={d['in_group_expanded_snapshot']} | {d['action']}")
    print('[S11] Not SFT, not verified customer answer, not model inference, no rights approval.')
    if args.write:
        OUT.mkdir(parents=True,exist_ok=True)
        targets=[
            (OUT/'s11_child_exact_inference_preview.jsonl', ''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in ex)),
            (OUT/'s11_group_sibling_ablation_preview.jsonl', ''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in sb)),
            (OUT/'s11_child_citation_audit.json',json.dumps(s,ensure_ascii=False,indent=2)+'\n'),
        ]
        for path,text in targets:
            if path.exists() and path.read_text(encoding='utf-8')!=text:
                raise FileExistsError(f'결과 파일이 이미 다른 내용으로 존재함. 원본 보존: {path}')
        for path,text in targets:path.write_text(text,encoding='utf-8')
        print('[S11] WRITE PASS | '+str(OUT.relative_to(ROOT))+' (3 files, no originals overwritten)')
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (FileNotFoundError,ValueError,KeyError,TypeError,FileExistsError) as exc:
        print('[S11] ERROR:',exc,file=sys.stderr)
        raise SystemExit(1)
