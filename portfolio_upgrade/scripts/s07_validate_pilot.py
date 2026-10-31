"""Read-only S07 draft validation: structure, provenance, exclusion, and invariants.

This does NOT certify paraphrase semantics, license, official PDF, or training readiness.
From repo root:
  python portfolio_upgrade\\scripts\\s07_validate_pilot.py
"""
from __future__ import annotations

import copy
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'portfolio_upgrade/data/training'
REPORT = ROOT / 'portfolio_upgrade/experiments/s07_data/s07_build_report.json'


def jsonl(path:Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def verify():
    source = jsonl(BASE/'examples_pdf_reviewed_v1.jsonl')
    draft = jsonl(BASE/'train_draft.jsonl')
    holdback = jsonl(BASE/'s07_label_review_queue.jsonl')
    report=json.loads(REPORT.read_text(encoding='utf-8'))
    with (BASE/'review_log.csv').open(encoding='utf-8-sig',newline='') as f:
        reviews=list(csv.DictReader(f))
    assert len(source)==15 and len(draft)==26 and len(holdback)==2 and len(reviews)==28, 'Unexpected row counts'
    source_by={r['provenance']['source_scenario_id']:r for r in source}
    assert len(source_by)==15, 'Duplicated S06 input IDs'
    assert len({r['example_id'] for r in draft+holdback})==28, 'Duplicated output IDs'
    assert set(r['provenance']['source_scenario_id'] for r in draft).isdisjoint(
        set(r['provenance']['source_scenario_id'] for r in holdback)), 'Held cases appeared in draft'
    assert all(r['provenance']['split']=='train' for r in draft+holdback), 'Dev/Holdout contamination'
    assert set(r['target']['action'] for r in draft)<=set(['ANSWER','ASK','ESCALATE']), 'Unexpected action'
    assert all(r['review']['training_ready'] is False for r in draft+holdback), 'Training gate bypassed'
    assert all(r['s07']['training_ready'] is False for r in draft+holdback), 'Training gate bypassed in S07'
    assert all(r['input'].get('evidence')==[] for r in draft+holdback), 'Evidence changed without evidence review'
    assert all(r['target'].get('cited_evidence_ids') is None for r in draft+holdback), 'Citations fabricated'
    counts=Counter(r['provenance']['source_scenario_id'] for r in draft)
    assert len(counts)==13 and all(n==2 for n in counts.values()), 'One original and one paraphrase per case required'
    variants=defaultdict(set)
    for r in draft:
        source_id=r['provenance']['source_scenario_id']; base=source_by[source_id]
        assert base['review']['action_label_review_status']=='consistent_with_manual',f'Label unresolved: {source_id}'
        assert r['target']==base['target'],f'Changed target unexpectedly: {source_id}'
        assert r['provenance']==base['provenance'],f'Changed provenance: {source_id}'
        assert r['input']['product_code']==base['input']['product_code'],f'Changed product: {source_id}'
        assert r['input']['known_conditions']==base['input']['known_conditions'],f'Changed known context: {source_id}'
        assert r['s07']['review_state']=='pending_s07_review'
        kind=r['s07']['variant_kind'];variants[source_id].add(kind)
        if kind=='source':
            assert r['input']['customer_message']==base['input']['customer_message']
            assert r['review']['status']==base['review']['status']
        elif kind=='paraphrase':
            assert r['input']['customer_message']!=base['input']['customer_message'],f'Same wording: {source_id}'
            assert r['review']['status']=='needs_review' and r['review']['assistant_message_reviewed'] is False
            assert len(r['input']['customer_message'])>10
        else:
            raise ValueError(f'Unknown variant: {kind}')
    assert all(v=={'source','paraphrase'} for v in variants.values())
    heldids=set()
    for r in holdback:
        sid=r['provenance']['source_scenario_id']; heldids.add(sid)
        assert source_by[sid]['review']['action_label_review_status']!='consistent_with_manual'
        assert r['s07']['review_state']=='held_for_action_decision'
        assert r['provenance']==source_by[sid]['provenance']
    assert heldids=={'SYN-IAC425-110','SYN-IAC606-110'}, 'Unexpected holdback IDs'
    assert report['draft_rows']==26 and report['label_holdback_count']==2
    assert report['training_ready']==0 and report['draft_semantic_groups']==6
    assert sum(r['review_decision']=='HOLD_ACTION_LABEL' for r in reviews)==2
    assert len({r['example_id'] for r in reviews})==28
    print('[S07] DRAFT VALIDATION PASS')
    print('Source: 15 | Draft: 26 (13 original + 13 paraphrases) | Held labels: 2')
    print('Actions:',dict(sorted(Counter(r['target']['action'] for r in draft).items())))
    print('Train-only:',len(draft),'| Distinct groups:',len({r['provenance']['semantic_group_id'] for r in draft}))
    print('Training-ready: 0 | PDF review of new paraphrases: NOT DONE')


if __name__ == '__main__':
    try:
        verify()
    except (AssertionError, ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as e:
        print('[S07] VALIDATION FAILED:',str(e),file=sys.stderr)
        raise SystemExit(1)
