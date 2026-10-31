r"""S08: Read frozen DEV labels and measure basic model-output checks.

  python portfolio_upgrade\scripts\s08_score_dev.py --predictions YOUR_OUTPUT.jsonl

Predictions JSONL: {"case_id":"SYN-...", "action":"ASK", "customer_message":"...", "cited_evidence_ids":[]}
Only categorical action and citation-ID membership are automated. Required-action coverage/safety requires manual PDF review.
"""
from __future__ import annotations
import argparse, json, csv
from pathlib import Path
from collections import Counter

ROOT=Path.cwd()
TARGETS=ROOT/'portfolio_upgrade/data/splits/s08_dev_targets.jsonl'
INPUTS=ROOT/'portfolio_upgrade/data/splits/s08_dev_model_inputs.jsonl'
OUT=ROOT/'portfolio_upgrade/experiments/s08_baseline/s08_score.json'
REVIEW=ROOT/'portfolio_upgrade/experiments/s08_baseline/s08_manual_review.csv'


def jlines(p):return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predictions',required=True);ap.add_argument('--write',action='store_true');ns=ap.parse_args()
    path=Path(ns.predictions)
    for p in [TARGETS,INPUTS,path]:
        if not p.exists():raise SystemExit('누락된 파일: '+str(p))
    gold=jlines(TARGETS);inputs=jlines(INPUTS);pred=jlines(path)
    gg={x['case_id']:x for x in gold};ii={x['case_id']:x for x in inputs};pp={x['case_id']:x for x in pred}
    if len(gg)!=6 or len(ii)!=6 or len(pp)!=6 or set(gg)!=set(ii) or set(ii)!=set(pp):
        raise ValueError('Dev 6개 ID 불일치/중복')
    rows=[]
    for id,g in gg.items():
        p=pp[id];x=ii[id]
        citations=p.get('cited_evidence_ids') or []
        valid = isinstance(citations,list) and set(citations).issubset(set(x['visible_citation_ids']))
        rows.append({'case_id':id,'expected_action':g['expected_action'],'actual_action':p.get('action',''),
                     'action_match':p.get('action')==g['expected_action'],
                     'citation_ids_valid_in_retrieved_input':valid,
                     'customer_message':p.get('customer_message',''),
                     'required_actions_from_pdf':g['required_actions_from_pdf_FOR_REVIEW'],
                     'manual_required_actions_check':'NOT_CHECKED',
                     'manual_safety_check':'NOT_CHECKED',
                     'manual_citation_relevance':'NOT_CHECKED'})
    summary={'total':6,'action_matches':sum(x['action_match'] for x in rows),
             'action_accuracy':sum(x['action_match'] for x in rows)/6,
             'citation_id_membership_pass':sum(x['citation_ids_valid_in_retrieved_input'] for x in rows),
             'manual_answer_quality':'NOT_EVALUATED',
             'warning':'valid citation ID != relevant citation or correct/safe advice; this is DEV only'}
    print('[S08] Dev 행동 정확도:',summary['action_matches'],'/6; 유효한 입력 ID만 인용한 사례:',summary['citation_id_membership_pass'],'/6')
    if ns.write:
        OUT.parent.mkdir(parents=True,exist_ok=True)
        OUT.write_text(json.dumps({'summary':summary,'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with REVIEW.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        print('[S08] 자동 점검 결과와 수동 검수용 CSV 저장')
    else:print('미리보기입니다. 저장하려면 --write')

if __name__=='__main__':main()
