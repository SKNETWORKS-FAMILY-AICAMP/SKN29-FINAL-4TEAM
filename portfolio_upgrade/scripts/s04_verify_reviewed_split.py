"""S04 pilot split / reviewed gold validation (read-only, Python stdlib).

Run at SKN29-FINAL-4TEAM repository root:
    python portfolio_upgrade\\scripts\\s04_verify_reviewed_split.py

It validates consistency against TEAM candidate data and the reviewed CSV; it does
NOT execute a model, verify PDFs that are not present locally, or certify a blind holdout.
"""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path.cwd()
SPLIT = ROOT / 'portfolio_upgrade/data/splits/s04_reviewed_pilot_split_v2.csv'
FIXES = ROOT / 'portfolio_upgrade/data/splits/s04_gold_label_fixes_v2.json'
SCENARIOS = ROOT / 'data/synthetic/candidates/manual_3model_candidate_scenarios.json'
EVIDENCE = ROOT / 'data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl'
CHUNKS = ROOT / 'data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl'
COUNTS = {'train':18,'dev':6,'holdout':6}
EXPECTED_PDF_SHAS={
    'WPUJAC104DWH':'0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C',
    'WPUJCC104D':'0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C',
    'WPUIAC425SNW':'97C027CE75BEC40386307C867DD3983513CB70FAC687F2D2DB6F1167EC9CAEC8',
    'WPUIAC606SNW':'A062C0DD5C2ED17BC3734215C3106DCC82AB69346CF546BDDD9EDD328EA49572'
}
SEMANTIC_LINKS=[
 ('SYN-IAC425-101','SYN-IAC606-101'),
 ('SYN-IAC425-107','SYN-IAC606-106'),
 ('SYN-IAC425-109','SYN-IAC606-108'),
 ('SYN-JAC104-031','SYN-IAC425-109'),
 ('SYN-JAC104-026','SYN-IAC425-102'),
 ('SYN-JAC104-027','SYN-IAC425-103'),
 ('SYN-JAC104-025','SYN-IAC425-105'),
 # NOTE: JAC104 leak differs in mandatory electric plug step; intentionally
 # separate from IAC family leak, not proof of total policy independence.
]


def jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def main():
    required=[SPLIT,FIXES,SCENARIOS,EVIDENCE,CHUNKS]
    missing=[str(p) for p in required if not p.exists()]
    if missing:raise ValueError('Missing required input files: '+', '.join(missing))
    with SPLIT.open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
    cases=json.loads(SCENARIOS.read_text(encoding='utf-8'))
    fixes=json.loads(FIXES.read_text(encoding='utf-8'))
    evidence=jsonl(EVIDENCE);chunks=jsonl(CHUNKS)
    if len(records)!=30 or len(cases)!=30:raise ValueError('30 cases required for pilot split')
    R={r['scenario_id']:r for r in records}
    S={s['scenario_id']:s for s in cases}
    assert len(R)==len(S)==30 and set(R)==set(S),'IDs differ between reviewed CSV and team source'
    assert Counter(r['split'] for r in records)==COUNTS,'split counts must be 18/6/6'
    assert all(r['review_status'].startswith('PDF_REVIEWED') for r in records)
    group_splits=defaultdict(set)
    for r in records:
        group_splits[r['semantic_group_id']].add(r['split'])
        assert r['group_id']==r['semantic_group_id'],'group_id is not semantic group id'
        assert r['model_code']==S[r['scenario_id']]['product']['exact_sales_code'],'product changed'
        assert r['pdf_sha256_verified']==EXPECTED_PDF_SHAS[r['model_code']],'source PDF SHA conflict'
        orig=S[r['scenario_id']]['retrieval_expectation']['expected_evidence_group_ids']
        assert r['expected_evidence_group_ids']==';'.join(orig),'team evidence ID silently modified'
        assert r['handoff_gold_present']==('YES' if orig else 'NO')
        assert r['required_actions_from_pdf'].strip(), 'missing reviewed answer'
        assert r['pdf_review_pages'].strip(), 'missing page citation'
    bad=[gid for gid,x in group_splits.items() if len(x)!=1]
    assert not bad, f'semantic group leakage {bad}'
    for a,b in SEMANTIC_LINKS:
        assert R[a]['split']==R[b]['split'] and R[a]['semantic_group_id']==R[b]['semantic_group_id'],f'Semantic leakage {a} {b}'
    G={e['evidence_group_id']:e for e in evidence}
    C={c['child_id']:c for c in chunks}
    assert len(G)==len(evidence) and len(C)==len(chunks)
    group_owners=defaultdict(set)
    text_owners=defaultdict(set)
    for r in records:
        s=S[r['scenario_id']];sid=r['scenario_id']
        for gid in s['retrieval_expectation']['expected_evidence_group_ids']:
            g=G[gid]
            assert g['exact_sales_code']==r['model_code'],f'Wrong model for {sid} {gid}'
            group_owners[gid].add(r['split'])
            for cid in g['child_ids']:
                c=C[cid]
                assert c['exact_sales_code']==r['model_code']
                assert c['evidence_group_id']==gid
                digest=hashlib.sha256(c['child_text'].encode('utf-8')).hexdigest().upper()
                assert digest==c['child_text_sha256'].upper(),f'Invalid text SHA: {cid}'
                text_owners[digest].add(r['split'])
    assert all(len(x)==1 for x in group_owners.values()), 'same evidence_group_id crossed splits'
    assert all(len(x)==1 for x in text_owners.values()),'same official chunk text crossed splits'
    for id in ['SYN-JAC104-031','SYN-IAC425-109','SYN-IAC606-108']:
        assert '음용 금지' in R[id]['required_actions_from_pdf'],'do-not-drink safety rule missing'
    assert R['SYN-IAC425-104']['suggested_gold_evidence_group_ids']=='EVD-WPUIAC425SNW-ICE-MAKING-NOISE-001'
    fixed={f['scenario_id'] for f in fixes['fixes']}
    flagged={r['scenario_id'] for r in records if r['source_issue'] not in ('NONE','SCENARIO_CONDITION','WORKFLOW_NOT_PROVEN')}
    assert fixed==flagged,'gold correction entries must match CSV source_issue flags'
    for item in fixes['fixes']:
        r=R[item['scenario_id']]
        assert item['required_actions_from_pdf']==r['required_actions_from_pdf']
        assert ';'.join(item['suggested_gold_evidence_group_ids'])==r['suggested_gold_evidence_group_ids']
    negatives={r['scenario_id'] for r in records if r['handoff_gold_present']=='NO'}
    assert len(negatives)==5
    safety={r['scenario_id'] for r in records if r['family'] in ('LEAK','HOT_WATER_STOPPED','INSTANT_HOT_WATER_SAFETY')}
    for spl in COUNTS:
        assert safety.intersection(r['scenario_id'] for r in records if r['split']==spl),f'{spl} has no safety case'
    for spl in ('dev','holdout'):
        assert negatives.intersection(r['scenario_id'] for r in records if r['split']==spl),f'{spl} has no policy case'
    print('[S04] Reviewed PILOT dataset validation: PASS')
    print('Cases:',len(records),'semantic groups:',len(group_splits))
    for sp in COUNTS:
        subset=[r for r in records if r['split']==sp]
        print(f"  {sp:<7} {len(subset)} | positive {sum(r['handoff_gold_present']=='YES' for r in subset)} | no index evidence {sum(r['handoff_gold_present']=='NO' for r in subset)} | danger {sum(r['scenario_id'] in safety for r in subset)}")
    print('No exact-evidence/text or declared semantic group crossing split: PASS')
    print('Manual PDF content SHA recorded: values validated against supplied inventory; this verifier does not open PDFs.')
    print('PDF-reviewed cases:',len(records),'label/source fixes PROPOSED:',len(fixed),'not applied to team source')
    print('WARNING: This holdout is a PILOT, not a statistically reliable blind final test.')


if __name__=='__main__':
    try:main()
    except (ValueError, AssertionError, KeyError, OSError, json.JSONDecodeError) as e:
        print('ERROR:',e,file=sys.stderr)
        raise SystemExit(1)
