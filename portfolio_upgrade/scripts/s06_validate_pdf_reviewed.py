r"""Validate S06 PDF-reviewed *candidate* JSONL (no PDF/network dependency).

From repository root:
    python portfolio_upgrade\scripts\s06_validate_pdf_reviewed.py

It checks data/label integrity and status, not the truth of manufacturer PDF facts.
"""
from pathlib import Path
from collections import Counter
import json, hashlib, sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'training'
ORIGINAL = DATA / 'examples_v0.jsonl'
REVIEWED = DATA / 'examples_pdf_reviewed_v1.jsonl'
MANUAL_SHA = {
    'WPUIAC425SNW': '97C027CE75BEC40386307C867DD3983513CB70FAC687F2D2DB6F1167EC9CAEC8',
    'WPUIAC606SNW': 'A062C0DD5C2ED17BC3734215C3106DCC82AB69346CF546BDDD9EDD328EA49572',
    'WPUJAC104DWH': '0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C',
}
EXPECTED_LABEL_REVIEW = {'SYN-IAC425-110', 'SYN-IAC606-110'}


def read_jsonl(p: Path):
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]


def validate():
    original = read_jsonl(ORIGINAL)
    reviewed = read_jsonl(REVIEWED)
    assert len(original) == len(reviewed) == 15, '15 records required'
    old = {x['example_id']: x for x in original}
    new = {x['example_id']: x for x in reviewed}
    assert len(old) == len(new) == 15 and set(old) == set(new), 'IDs changed or duplicated'
    flags = set()
    for key, x in new.items():
        y = old[key]
        assert x['input'] == y['input'], f'input altered {key}'
        assert x['provenance']['source_scenario_id'] == y['provenance']['source_scenario_id']
        assert x['provenance']['split'] == 'train'
        assert x['provenance']['semantic_group_id'] == y['provenance']['semantic_group_id']
        assert x['provenance']['gold_evidence_ids'] == y['provenance']['gold_evidence_ids']
        assert x['target']['action'] == y['target']['action'], f'action silently changed {key}'
        assert x['target']['required_actions'] == y['target']['required_actions'], f'official action altered {key}'
        assert x['target']['missing_fields'] == y['target']['missing_fields']
        assert x['target']['cited_evidence_ids'] is None, f'citation fabricated {key}'
        assert x['target']['assistant_message'] and x['target']['forbidden_claims']
        assert x['provenance']['manual_sha256'] == MANUAL_SHA[x['input']['product_code']]
        assert x['provenance']['manual_pdf_source']['sha256_verified'] == MANUAL_SHA[x['input']['product_code']]
        assert x['review']['pdf_reviewed'] and x['review']['pdf_hash_matched']
        assert x['review']['training_ready'] is False, f'premature training_ready {key}'
        if x['review']['status'] == 'needs_review':
            flags.add(x['provenance']['source_scenario_id'])
        else:
            assert x['review']['status'] == 'verified'
        pages = {p['page'] for p in x['provenance']['manual_pdf_source']['page_evidence']}
        assert pages == set(x['provenance']['manual_pages']), f'manual pages changed {key}'
    assert flags == EXPECTED_LABEL_REVIEW, flags
    print('[S06 PDF reviewed] VALIDATION PASS')
    print('Samples:', len(new), 'PDF checked:', sum(x['review']['pdf_reviewed'] for x in reviewed))
    print('Labels consistent:', len(new) - len(flags), 'label review:', len(flags))
    print('Train:', sum(x['provenance']['split'] == 'train' for x in reviewed),
          'training-ready:', sum(x['review']['training_ready'] for x in reviewed))
    print('Original action distribution:', dict(Counter(x['target']['action'] for x in reviewed)))

if __name__ == '__main__':
    try:
        validate()
    except Exception as e:
        print('S06 VALIDATION FAILED:', e, file=sys.stderr)
        raise SystemExit(1)
