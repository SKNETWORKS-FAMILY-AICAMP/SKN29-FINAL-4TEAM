"""S11: conservative post-retrieval gate for two *new* cold-lock UNLOCK child documents.

Train-only offline ablation. Does NOT rerun BGE, insert Gold, call a model,
change existing search files, train SFT, or alter WaterBridge production.

Windows CMD from repo root:
    python portfolio_upgrade\\scripts\\s11_cold_lock_condition_gate.py --check
    python portfolio_upgrade\\scripts\\s11_cold_lock_condition_gate.py --write
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
COMPARE = ROOT / 'portfolio_upgrade/experiments/s11_readiness/s11_cold_lock_retrieval_compare.json'
PREVIEW = ROOT / 'portfolio_upgrade/experiments/m2_training_readiness/s09_train_retrieval_preview.jsonl'
OUT = ROOT / 'portfolio_upgrade/experiments/s11_readiness'
EXPECTED_TRAIN_SHA = '3a91e5343907926cc4c834b086916f0cd6fcf7ab467cb8ec62f490e7b4ee6f94'
EXPECTED_INDEX_53_SHA = 'b4ba15c045d7c4eaf1e4cf90dff83ec9fa2c236f9cfcdad85467a42f1921eb78'
EXPECTED_INDEX_55_SHA = '1b56511bbcebb3c11bbb507dcd9546593cf49e139beeb4fdf114091a1ecc36b2'
LOCK_DETAIL_BY_PRODUCT = {
    'WPUIAC425SNW': 'CHILD-WPUIAC425SNW-P027-COLD-LOCK-UNLOCK-001',
    'WPUIAC606SNW': 'CHILD-WPUIAC606SNW-P024-COLD-LOCK-UNLOCK-001',
}
# Evaluation-only labels are in a separate section and NEVER used by the gate.
EVAL_LOCK_SOURCES = frozenset({'SYN-IAC425-101', 'SYN-IAC606-101'})
EVAL_NEGATIVE_SOURCES = frozenset({'SYN-IAC425-102', 'SYN-IAC425-103', 'SYN-IAC606-103'})



def compact(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError('질문은 문자열이어야 합니다')
    return re.sub(r'\s+', '', text).lower()


def classify_lock_signal(question: str, product_code: str) -> tuple[bool, str]:
    """ONLY raw customer text + product code; no Gold, IDs, manual labels, or symptoms.

    Deliberately conservative: without explicit cold-lock indicator, omit the
    new *detailed unlock instructions* but leave other retrieved child results.
    """
    if product_code not in LOCK_DETAIL_BY_PRODUCT:
        return False, 'NOT_SUPPORTED_INDEX_PRODUCT'
    s = compact(question)
    # A clear safety situation takes priority over control-button instructions.
    if any(term in s for term in ('누수', '감전', '스파크', '연기', '물이새', '물이샘', '물이고여')):
        return False, 'SAFETY_PRIORITY'
    if any(re.search(p, s) for p in (
        r'잠금표시(?:등)?(?:가|이|도|는)?(?:없|안뜨|안나|보이지않|꺼져)',
        r'잠금(?:이|을|은|도)?(?:이미)?해제(?:했|됐|완료|되어|된상태|한상태)',
        r'(?:이미|벌써)(?:냉수)?잠금(?:은|이|을)?해제',
    )):
        return False, 'ALREADY_UNLOCKED_OR_INDICATOR_ABSENT'
    if '냉수' not in s:
        return False, 'NO_COLD_WATER_SIGNAL'
    if '잠금' not in s:
        return False, 'NO_LOCK_INDICATOR'
    if not any(term in s for term in ('깜빡', '점멸', '번쩍')):
        return False, 'NO_BLINKING_INDICATOR'
    if not any(term in s for term in ('버튼', '선택', '고르', '누르', '누를', '누르면', '눌렀')):
        return False, 'NO_COLD_SELECTION_CONTEXT'
    return True, 'CLEAR_COLD_LOCK_INDICATOR'


def load_inputs(compare_path: Path, preview_path: Path) -> tuple[list[dict], dict, dict]:
    if not compare_path.is_file() or not preview_path.is_file():
        raise FileNotFoundError('S09 JSONL 또는 S11 53↔55 비교 JSON을 찾지 못했습니다. 프로젝트 루트/압축 경로 확인')
    actual_sha = hashlib.sha256(preview_path.read_bytes()).hexdigest()
    if actual_sha != EXPECTED_TRAIN_SHA:
        raise ValueError('S09 고정 Train 스냅샷 해시 불일치; 다른 입력으로 침묵 재평가 금지')
    comparison = json.loads(compare_path.read_text(encoding='utf-8-sig'))
    sm = comparison.get('summary') or {}
    expected = {
        'status':'S11_BGE_INDEX_ABLATION_NOT_SFT_OR_PRODUCTION',
        'total_train_rows':26, 'baseline_index_children':53, 'candidate_index_children':55,
        'base_index_sha256':EXPECTED_INDEX_53_SHA,
        'extended_index_sha256':EXPECTED_INDEX_55_SHA,
        'train_snapshot_sha256':EXPECTED_TRAIN_SHA,
        'training_ready':False, 'manual_based_data_use_authorized_for_sft':False,
    }
    for key, value in expected.items():
        if sm.get(key) != value:
            raise ValueError(f'S11 비교 계약 불일치: {key}={sm.get(key)!r}, expected={value!r}')
    cases = comparison.get('cases') or []
    if len(cases)!=26 or len({c.get('example_id') for c in cases})!=26:
        raise ValueError('S11 비교 케이스 26건 중복/누락')
    rows = [json.loads(line) for line in preview_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if len(rows)!=26 or len({r.get('example_id') for r in rows})!=26:
        raise ValueError('S09 Train-only 26행 중복/누락')
    inputs = {}
    for r in rows:
        if r.get('status')!='PREVIEW_NOT_TRAIN_READY' or r.get('audit_only', {}).get('split')!='train' or r['audit_only'].get('training_ready') is not False:
            raise ValueError('Dev/Holdout 또는 학습 승인 플래그 오염')
        ms = r.get('messages')
        if not isinstance(ms,list) or [m.get('role') for m in ms]!=['system','user','assistant']:
            raise ValueError('S09 메시지 구조 불일치')
        user = json.loads(ms[1]['content'])
        if any(k in user for k in ('gold_evidence_ids','target','answer','expected_action','audit_only')):
            raise ValueError('모델 입력에 정답/Gold 필드 혼입')
        if not isinstance(user.get('customer_message'),str) or not isinstance(user.get('product_code'),str):
            raise ValueError('고객 발화·제품 코드 누락')
        inputs[r['example_id']] = {'product':user['product_code'], 'question':user['customer_message'],
                                  'source_id':r['audit_only']['source_scenario_id']}
    if set(inputs)!={c['example_id'] for c in cases}:
        raise ValueError('S09 vs S11 케이스 ID 집합 불일치')
    return cases, inputs, {'comparison_sha256':hashlib.sha256(compare_path.read_bytes()).hexdigest(),
                           's09_train_sha256':actual_sha, 'summary':sm}


def filter_case(case: dict, product: str, question: str) -> tuple[list[str], list[str], str]:
    """Pure transformation of already-ranked Top-5 child IDs; no refill or rerank."""
    if case.get('product_code')!=product:
        raise ValueError('제품 코드가 S09와 비교 파일에서 다릅니다')
    original = case.get('candidate_55_child_ids')
    if not isinstance(original,list) or len(original)!=5 or len(set(original))!=5:
        raise ValueError('55개 인덱스의 고정 Top-5 청크가 잘못되었습니다')
    all_new=set(LOCK_DETAIL_BY_PRODUCT.values())
    for cid in original:
        if cid in all_new and cid!=LOCK_DETAIL_BY_PRODUCT.get(product):
            raise ValueError('다른 제품의 신규 잠금 청크 유입: '+cid)
    detail_id = LOCK_DETAIL_BY_PRODUCT.get(product)
    observed_rank = (original.index(detail_id) + 1) if detail_id in original else None
    if case.get('new_lock_detail_top5', observed_rank is not None) != (observed_rank is not None):
        raise ValueError('S11 이전 비교의 새 잠금 청크 존재 플래그와 ID가 불일치')
    if case.get('new_lock_detail_rank', observed_rank) != observed_rank:
        raise ValueError('S11 이전 비교의 새 잠금 청크 순위와 ID가 불일치')
    allowed, reason=classify_lock_signal(question,product)
    # Only remove the two newly indexed child IDs; preserve legacy documents.
    removed=[cid for cid in original if cid in all_new and not allowed]
    kept=[cid for cid in original if cid not in removed]
    if [cid for cid in kept if cid not in original]:
        raise AssertionError('원본 검색 외 ID 주입')
    return kept,removed,reason


def evaluate_cases(cases: list[dict], user_inputs: dict, source_meta: dict) -> tuple[dict, list[dict]]:
    """Audit only. Labels from a PRIOR HUMAN REVIEW, not the filter function."""
    report=[]
    for c in cases:
        id_=c['example_id']
        u=user_inputs[id_]
        product,question,source=u['product'],u['question'],u['source_id']
        if c.get('source_scenario_id')!=source or c.get('training_ready') is not False:
            raise ValueError('S09/S11 출처·학습 상태 불일치: '+id_)
        kept,removed,reason=filter_case(c,product,question)
        detail=LOCK_DETAIL_BY_PRODUCT.get(product)
        before=detail in c['candidate_55_child_ids'] if detail else False
        after=detail in kept if detail else False
        aud_label=('LOCK_POSITIVE' if source in EVAL_LOCK_SOURCES else
                   'KNOWN_NEGATIVE' if source in EVAL_NEGATIVE_SOURCES else 'OTHER_TRAIN')
        report.append({
            'example_id':id_, 'source_scenario_id':source,'model_code':product,
            'manual_audit_class_EVAL_ONLY':aud_label,
            'cold_lock_candidate_before':before,'cold_lock_candidate_after':after,
            'gate_reason':reason,
            'candidate_55_child_ids':list(c['candidate_55_child_ids']),
            'after_gate_child_ids':kept,
            'removed_child_ids':removed,
            'training_ready':False,
        })
    classes=Counter(x['manual_audit_class_EVAL_ONLY'] for x in report)
    if classes!=Counter({'LOCK_POSITIVE':4,'KNOWN_NEGATIVE':6,'OTHER_TRAIN':16}):
        raise ValueError(f'감사 그룹 구성 변경: {classes}')
    positives=[r for r in report if r['manual_audit_class_EVAL_ONLY']=='LOCK_POSITIVE']
    negatives=[r for r in report if r['manual_audit_class_EVAL_ONLY']=='KNOWN_NEGATIVE']
    pre_exposure=sum(r['cold_lock_candidate_before'] for r in report)
    post_exposure=sum(r['cold_lock_candidate_after'] for r in report)
    for r in report:
        if any(x not in r['candidate_55_child_ids'] for x in r['after_gate_child_ids']):
            raise AssertionError('검색 결과 이외의 청크가 삽입됨')
    summary={
        'status':'S11_POST_RETRIEVAL_GATE_TRAIN_DIAGNOSTIC_NOT_SFT_OR_PRODUCTION',
        'n_rows':len(report),'n_positive_train_rows':len(positives),
        'n_known_negative_train_rows':len(negatives),
        'positive_detail_before':sum(r['cold_lock_candidate_before'] for r in positives),
        'positive_detail_after':sum(r['cold_lock_candidate_after'] for r in positives),
        'negative_detail_before':sum(r['cold_lock_candidate_before'] for r in negatives),
        'negative_detail_after':sum(r['cold_lock_candidate_after'] for r in negatives),
        'all_rows_detail_before':pre_exposure,'all_rows_detail_after':post_exposure,
        'rows_modified':sum(bool(r['removed_child_ids']) for r in report),
        'remaining_candidates_by_row':dict(Counter(str(len(r['after_gate_child_ids'])) for r in report)),
        'baseline_53_snapshot_drift_count_carried_from_previous_run':source_meta['summary'].get('baseline_53_drift_count'),
        'source_sha256':{'s09_train':source_meta['s09_train_sha256'],
                         's11_55_compare':source_meta['comparison_sha256'],
                         's11_55_index':source_meta['summary'].get('extended_index_sha256')},
        'source_truth_access_in_router':False,
        'manual_based_data_use_authorized_for_sft':False,'training_ready':False,
        'limits':[
            'Gate uses raw customer_message + product_code only; test labels never influence selection.',
            'Same 10 Train examples informed the gate design: 4/4 and 6/6 are in-sample diagnostics, not generalization.',
            'Removes only NEW cold-lock unlock detail child IDs; the legacy COLD-LOCK summary may still rank for unrelated questions.',
            'No refill from ranks 6+ because the comparison JSON holds only Top-5; remaining list may have 4 entries.',
            'No rerank, GPU, PDF reread, LLM response generation, SFT, Dev/Holdout, or production deployment.',
            'Rules may reject legitimate paraphrases or miss negation/other safety conditions; independent review is required.',
            'The baseline search drift of 6 rows remains a separate reproducibility issue.',
        ]}
    return summary, report


def write_unchanged_or_new(path: Path, value: str) -> None:
    if path.is_file() and path.read_text(encoding='utf-8')!=value:
        raise FileExistsError('기존 파일 내용이 달라 덮어쓰지 않습니다: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value,encoding='utf-8',newline='\n')


def run(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true')
    p.add_argument('--write',action='store_true')
    a=p.parse_args(argv)
    cases, inputs, meta=load_inputs(COMPARE, PREVIEW)
    summary, cases_out=evaluate_cases(cases,inputs,meta)
    print(f"[S11] GATE CHECK PASS | {summary['n_rows']} Train | positive {summary['positive_detail_before']}/4 → {summary['positive_detail_after']}/4 | irrelevant {summary['negative_detail_before']}/6 → {summary['negative_detail_after']}/6")
    print(f"[S11] Modified {summary['rows_modified']} rows | no new retrieval / Gold-based filtering / GPU / SFT / Dev-Holdout")
    if a.write:
        out=OUT/'s11_cold_lock_gate_compare.json'
        body=json.dumps({'summary':summary,'cases':cases_out},ensure_ascii=False,indent=2)+'\n'
        write_unchanged_or_new(out,body)
        csvbuf=io.StringIO(newline='')
        writer=csv.DictWriter(csvbuf,lineterminator="\n",fieldnames=['example_id','manual_audit_class_EVAL_ONLY','cold_lock_candidate_before','cold_lock_candidate_after','gate_reason','removed_child_ids','remaining_count'])
        writer.writeheader()
        for r in cases_out:
            writer.writerow({'example_id':r['example_id'],'manual_audit_class_EVAL_ONLY':r['manual_audit_class_EVAL_ONLY'],
                             'cold_lock_candidate_before':r['cold_lock_candidate_before'],
                             'cold_lock_candidate_after':r['cold_lock_candidate_after'],
                             'gate_reason':r['gate_reason'],'removed_child_ids':';'.join(r['removed_child_ids']),
                             'remaining_count':len(r['after_gate_child_ids'])})
        write_unchanged_or_new(OUT/'s11_cold_lock_gate_cases.csv',csvbuf.getvalue())
        print('[S11] GATE WRITE PASS | '+str(out.relative_to(ROOT) if out.is_relative_to(ROOT) else out))
    else:
        print('[S11] CHECK ONLY — 저장하려면 --write')
    return 0

if __name__=='__main__':
    try:raise SystemExit(run())
    except (FileNotFoundError,ValueError,FileExistsError,TypeError,KeyError) as exc:
        print('[S11] ERROR: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
