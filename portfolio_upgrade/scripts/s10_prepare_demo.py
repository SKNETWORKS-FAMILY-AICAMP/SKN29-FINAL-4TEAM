"""S10: generate audited, *entirely fictional* LoRA smoke-test data.

Runs on Windows/CPU with Python stdlib only, no GPU, no API charges.
From repository root:
    python portfolio_upgrade/scripts/s10_prepare_demo.py --check
    python portfolio_upgrade/scripts/s10_prepare_demo.py --write
Only writes portfolio_upgrade/data/s10_demo/. Never reads WaterBridge manuals.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'portfolio_upgrade/data/s10_demo'
SOURCE = DIR / 's10_toy_source.json'
TRAIN = DIR / 's10_toy_train.jsonl'
PROBES = DIR / 's10_toy_probes.jsonl'
MANIFEST = DIR / 's10_toy_manifest.json'
ACTIONS = {'ANSWER', 'ASK', 'ESCALATE', 'EXPLAIN_UNSUPPORTED'}
SYSTEM_PROMPT = (
    '당신은 가상의 실습용 장치 SIM-P100 및 SIM-P200 전담 고객지원 AI입니다. '
    '실제 제품이나 SK매직의 정책을 안내하는 서비스가 아닙니다. '
    '고객 발화, 정확한 제품 코드, 제공된 가상 규칙만 보고 결정합니다. '
    '가능한 행동은 ANSWER, ASK, ESCALATE, EXPLAIN_UNSUPPORTED입니다. '
    '위험 상황이면 ESCALATE를 선택하고, 정보가 부족하면 ASK를 선택합니다. '
    '가상 규칙에 기능 미지원이 명시되어야만 EXPLAIN_UNSUPPORTED를 선택합니다. '
    '관련 근거 ID만 인용하세요. 반드시 action, customer_message, '
    'cited_evidence_ids, missing_fields 네 키를 포함한 JSON 객체 하나만 출력하세요.'
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def to_record(row: dict, question: str, variant: str) -> dict:
    rid = row['id']
    evidence_id = 'SIM-EVD-' + rid
    user = {
        'product_code': row['product_code'],
        'customer_question': question,
        'retrieved_evidence': [{'evidence_id': evidence_id, 'text': row['evidence_text']}],
    }
    answer = {
        'action': row['action'],
        'customer_message': row['answer'],
        'cited_evidence_ids': [evidence_id],
        'missing_fields': row['missing_fields'],
    }
    return {
        'demo_id': 'S10-' + rid + ('-ORIG' if variant == 'original' else '-PARA'),
        'source_id': rid,
        'variant': variant,
        'split': row['split'],
        'origin': 'FICTIONAL_ORIGINAL_DEMO',
        'prompt': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': json_line(user)},
        ],
        'completion': [{'role': 'assistant', 'content': json_line(answer)}],
    }


def build() -> tuple[list[dict], list[dict]]:
    source = json.loads(SOURCE.read_text(encoding='utf-8'))
    if source.get('scope') != 'FICTIONAL_ORIGINAL_DEMO_NOT_REAL_PRODUCT':
        raise ValueError('S10 source scope mismatch: real manual training is blocked.')
    rows = source['rows']
    if len(rows) != 28 or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Expected 28 distinct fictional source cases.')
    if any(r['action'] not in ACTIONS for r in rows):
        raise ValueError('Unknown action label.')
    if any(r['product_code'] not in {'SIM-P100', 'SIM-P200'} for r in rows):
        raise ValueError('Non-fictional product code. This package must never use WaterBridge data.')
    if any(not r['question'] or not r['evidence_text'] or not r['answer'] for r in rows):
        raise ValueError('Empty question, evidence or target answer.')
    if any((r['action'] == 'ASK') != bool(r['missing_fields']) for r in rows):
        raise ValueError('ASK cases must carry missing_fields, other actions must not.')
    split_counts = Counter(r['split'] for r in rows)
    if split_counts != Counter({'train': 20, 'probe': 8}):
        raise ValueError('Expected train source 20 and independent toy probe source 8.')
    if Counter(r['action'] for r in rows if r['split'] == 'train') != Counter({a: 5 for a in ACTIONS}):
        raise ValueError('Toy train labels must be balanced 5 per action.')
    if Counter(r['action'] for r in rows if r['split'] == 'probe') != Counter({a: 2 for a in ACTIONS}):
        raise ValueError('Toy probe labels must be balanced 2 per action.')
    train, probes = [], []
    for row in rows:
        if row['split'] == 'train':
            if not row['paraphrase'] or row['paraphrase'] == row['question']:
                raise ValueError('Each toy train source needs a distinct paraphrase.')
            train.extend([to_record(row, row['question'], 'original'), to_record(row, row['paraphrase'], 'paraphrase')])
        else:
            if row['paraphrase'] is not None:
                raise ValueError('Toy probe paraphrase should not exist.')
            probes.append(to_record(row, row['question'], 'original'))
    if len(train) != 40 or len(probes) != 8:
        raise ValueError('Expected toy train 40, toy probes 8.')
    assert not set(r['source_id'] for r in train) & set(r['source_id'] for r in probes)
    assert len({r['prompt'][1]['content'] for r in train + probes}) == 48
    return train, probes


def content(rows: list[dict]) -> bytes:
    return (''.join(json_line(r) + '\n' for r in rows)).encode('utf-8')


def run(write: bool) -> None:
    train, probes = build()
    tbytes, pbytes = content(train), content(probes)
    manifest = {
        'status': 'FICTIONAL_SMOKE_TEST_ONLY',
        'train_rows': len(train), 'train_source_cases': 20,
        'toy_probe_rows': len(probes), 'toy_probe_source_cases': 8,
        'source_sha256': sha256(SOURCE.read_bytes()),
        'train_sha256': sha256(tbytes), 'probes_sha256': sha256(pbytes),
        'eval_waterbridge_dev_or_holdout_used': False,
        'training_on_real_manual_prohibited': True,
    }
    if write:
        DIR.mkdir(parents=True, exist_ok=True)
        TRAIN.write_bytes(tbytes)
        PROBES.write_bytes(pbytes)
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('[S10] TOY WRITE PASS | Train=40 (20 originals + 20 paraphrases), probe=8')
    else:
        for path, expected in [(TRAIN, tbytes), (PROBES, pbytes)]:
            if path.is_file() and path.read_bytes() != expected:
                raise ValueError(f'S10 toy output differs from source: {path}. Do not train until reconciled.')
        if MANIFEST.is_file():
            stored = json.loads(MANIFEST.read_text(encoding='utf-8'))
            if stored != manifest:
                raise ValueError('S10 manifest hash mismatch.')
        print('[S10] TOY CHECK PASS | 28 original scenarios / 40 train rows / 8 distinct probe rows')
    print('[S10] Fictional data only. No model training, no WaterBridge manuals, no GPU.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    args = parser.parse_args()
    run(write=args.write)
