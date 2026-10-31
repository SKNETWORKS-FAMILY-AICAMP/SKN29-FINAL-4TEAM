r"""S08: Validate split isolation and build DEV-only evaluation contract.

Run from repository root (Windows CMD):
  python portfolio_upgrade\scripts\s08_prepare_eval.py
  python portfolio_upgrade\scripts\s08_prepare_eval.py --write
  python portfolio_upgrade\scripts\s08_prepare_eval.py --write --retrieval-file portfolio_upgrade\experiments\s05_retrieval\retrieval_20261029T152819Z_33220.jsonl

Does not train, call an LLM, alter original S04/S07 files, or reveal holdout questions.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path.cwd()
SPLIT = Path('portfolio_upgrade/data/splits/s04_reviewed_pilot_split_v2.csv')
SCENARIOS = Path('data/synthetic/candidates/manual_3model_candidate_scenarios.json')
DRAFT = Path('portfolio_upgrade/data/training/train_draft_s07_reviewed_v1.jsonl')
OUT_SPLIT = Path('portfolio_upgrade/data/splits/s08_manifest.csv')
OUT_DEV = Path('portfolio_upgrade/data/splits/s08_dev_targets.jsonl')
OUT_DEV_INPUT = Path('portfolio_upgrade/data/splits/s08_dev_model_inputs.jsonl')
OUT_CONTRACT = Path('portfolio_upgrade/configs/eval_contract.yaml')
OUT_REPORT = Path('portfolio_upgrade/experiments/s08_baseline/s08_preflight_report.json')
MODEL_ID = 'Qwen/Qwen3-1.7B'  # S09 pilot candidate, pin revision at model preflight
COUNTS = {'train': 18, 'dev': 6, 'holdout': 6}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def csv_rows(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError('빈 분할 CSV')
    h = rows[0]
    duplicates = [s for s, n in Counter(h).items() if n > 1]
    if any(len(r) != len(h) for r in rows[1:] if any(r)):
        raise ValueError('S04 분할 CSV 열 수가 일치하지 않음')
    out = []
    for r in rows[1:]:
        if not any(r):
            continue
        for name in duplicates:
            vals = [r[i] for i, field in enumerate(h) if field == name]
            if len(set(vals)) > 1:
                raise ValueError(f'{r[0]}의 중복 CSV 열 {name} 값이 서로 다름: {vals}')
        out.append(dict(zip(h, r)))
    return out, duplicates


def case_prompt(case: dict, ranked: dict) -> list[dict]:
    """DO NOT pass oracle Gold, split or labels into model input."""
    evidence = ranked.get('evidence') or []
    if not isinstance(evidence, list):
        raise ValueError(f'{ranked.get("case_id")}: evidence가 list가 아님')
    clean = []
    for e in evidence:
        identifier = e.get('id')
        if not identifier or not e.get('text'):
            raise ValueError('retrieval evidence must have id and text')
        clean.append({'id': identifier, 'text': e['text'], 'page_refs': e.get('page_refs', [])})
    system = ('당신은 정수기 고객 응대 보조 AI입니다. 제공된 공식 근거와 제품 조건만 사용합니다. '
              '근거가 부족하면 추측하지 말고 확인 질문 또는 상담을 제안합니다. '
              '위험 신호와 제품별 조치 차이를 우선합니다. '
              '다음 JSON 객체 하나만 출력합니다: '
              '{"action":"ANSWER|ASK|ESCALATE|EXPLAIN_UNSUPPORTED",'
              '"customer_message":"...","cited_evidence_ids":[],"missing_fields":[]}')
    payload = {
        'product_code': case['request']['model_code'],
        'customer_message': case['request']['raw_symptom'],
        'selected_symptoms': case['request'].get('selected_symptoms', []),
        'previous_answers': case['request'].get('previous_answers', []),
        'retrieved_evidence': clean,
    }
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False, sort_keys=True)}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='기존 파일은 덮어쓰지 않고 S08 산출물만 작성')
    ap.add_argument('--retrieval-file', help='S05 원본 오프라인 BGE 검색 JSONL (Dev 6건)')
    ns = ap.parse_args()
    inputs = [SPLIT, SCENARIOS, DRAFT]
    for p in inputs:
        if not (ROOT / p).is_file():
            raise SystemExit('필수 파일이 없습니다: ' + str(ROOT / p))
    split, duplicated = csv_rows(ROOT / SPLIT)
    scenarios = json.loads((ROOT / SCENARIOS).read_text(encoding='utf-8-sig'))
    draft = jsonl(ROOT / DRAFT)
    if len(split) != 30 or len(scenarios) != 30 or len(draft) != 26:
        raise ValueError(f'파일럿 크기 불일치 S04 {len(split)}, scenarios {len(scenarios)}, S07 {len(draft)} (예상 30/30/26)')
    smap = {r['scenario_id']: r for r in split}
    cmap = {s['scenario_id']: s for s in scenarios}
    if len(smap) != 30 or len(cmap) != 30 or set(smap) != set(cmap):
        raise ValueError('S04 원본 시나리오 ID 불일치 또는 중복')
    by_split = Counter(r['split'] for r in split)
    if by_split != COUNTS:
        raise ValueError(f'Train/Dev/Holdout 분할 크기 불일치: {by_split}')
    group_split = defaultdict(set)
    text_split = defaultdict(set)
    for r in split:
        scenario = cmap[r['scenario_id']]
        if r['model_code'] != scenario['request']['model_code']:
            raise ValueError(f'제품 불일치: {r["scenario_id"]}')
        group_split[r['semantic_group_id']].add(r['split'])
        text_split[hashlib.sha256(scenario['request']['raw_symptom'].encode('utf-8')).hexdigest()].add(r['split'])
    if any(len(z) != 1 for z in group_split.values()) or any(len(z) != 1 for z in text_split.values()):
        raise ValueError('S04 선언된 의미 그룹 또는 동일 질문 텍스트가 분할을 가로지름')
    ids = Counter(r['example_id'] for r in draft)
    if any(n > 1 for n in ids.values()):
        raise ValueError('S07 example_id 중복')
    source_variants = defaultdict(set)
    for example in draft:
        p = example['provenance']
        src = p['source_scenario_id']
        if src not in smap:
            raise ValueError('S07 출처 시나리오 누락: ' + src)
        ref = smap[src]
        if (ref['split'] != 'train' or p['split'] != 'train' or
            p['semantic_group_id'] != ref['semantic_group_id'] or
            example['input']['product_code'] != ref['model_code'] or
            example['target']['action'] != ref['intended_oracle_action']):
            raise ValueError('S07 Train/그룹/제품/행동 매핑 불일치: ' + example['example_id'])
        if example['review'].get('training_ready') or example['s07'].get('training_ready'):
            raise ValueError('S07 자료의 학습 권한·근거가 아직 확정되지 않은데 training_ready=True')
        source_variants[src].add(example['s07']['variant_kind'])
    if len(source_variants) != 13 or any(z != {'source', 'paraphrase'} for z in source_variants.values()):
        raise ValueError('S07의 원본13+재표현13 쌍이 맞지 않음')
    draft_groups = {x['provenance']['semantic_group_id'] for x in draft}
    if len(draft_groups) != 6:
        raise ValueError('S07의 선언된 파일럿 그룹 수(6) 불일치')
    dev = [r for r in split if r['split'] == 'dev']
    manifest = []
    for r in split:
        q = cmap[r['scenario_id']]['request']['raw_symptom']
        # No holdout actual query or answer in the generated manifest.
        manifest.append({
            'scenario_id': r['scenario_id'], 'split': r['split'], 'semantic_group_id': r['semantic_group_id'],
            'family': r['family'], 'model_code': r['model_code'],
            'expected_action': r['intended_oracle_action'] if r['split'] != 'holdout' else 'SEALED',
            'question_sha256': hashlib.sha256(q.encode('utf-8')).hexdigest(),
            'evidence_gold_present': bool(r.get('suggested_gold_evidence_group_ids')),
            'grouping_reason': r.get('grouping_reason', '')
        })
    dev_targets = [{
        'case_id': r['scenario_id'],
        'expected_action': r['intended_oracle_action'],
        'gold_evidence_ids_FOR_EVAL_ONLY': [x for x in r.get('suggested_gold_evidence_group_ids', '').split(';') if x],
        'required_actions_from_pdf_FOR_REVIEW': r['required_actions_from_pdf'],
        'manual_pages': r['pdf_review_pages'], 'source_issue': r['source_issue'],
        'semantic_group_id': r['semantic_group_id']
    } for r in dev]
    retrieval_file = Path(ns.retrieval_file) if ns.retrieval_file else None
    retrieval_sha = None
    dev_inputs = None
    if retrieval_file is not None:
        if not retrieval_file.is_file():
            raise ValueError('지정한 검색 파일이 없습니다: ' + str(retrieval_file))
        retrieved = jsonl(retrieval_file)
        retrieval_sha = sha256(retrieval_file)
        if len(retrieved) != 6 or [x.get('case_id') for x in retrieved] != [x['scenario_id'] for x in dev]:
            raise ValueError('retrieval 결과 ID/순서가 Dev6과 다릅니다')
        dev_inputs = []
        for r, rec in zip(dev, retrieved):
            old_digest = rec.get('input_sha256')
            if not isinstance(old_digest, dict):
                raise ValueError('S05 retrieval은 source SHA 기록이 포함된 원본 실험 파일만 허용합니다')
            if (old_digest.get('s04_csv_sha256') != sha256(ROOT / SPLIT) or
                old_digest.get('team_scenarios_sha256') != sha256(ROOT / SCENARIOS)):
                raise ValueError('S05 검색 당시 데이터와 현재 S04/시나리오 SHA 불일치. 검색을 재실행해야 합니다')
            child_path = ROOT / 'data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl'
            if child_path.exists() and old_digest.get('team_children_sha256') != sha256(child_path):
                raise ValueError('S05 검색 당시 청크 SHA와 현재 청크 파일이 다릅니다')
            if rec.get('model_code') != r['model_code'] or rec.get('query') != cmap[r['scenario_id']]['request']['raw_symptom']:
                raise ValueError('retrieval의 제품/원문이 S04 Dev와 다릅니다: ' + r['scenario_id'])
            if 'safe_routed' in rec:
                raise ValueError('지금의 S08에서는 safe-routed 파일 대신 원본 BGE 검색 파일을 고정합니다')
            dev_inputs.append({
                'case_id': r['scenario_id'], 'messages': case_prompt(cmap[r['scenario_id']], rec),
                'retrieval_status': rec.get('retrieval_status'),
                'visible_citation_ids': [e['id'] for e in rec.get('evidence', [])]
            })
    config = f'''# S08 - EVALUATION CONTRACT. This is not a baseline score or a frozen final holdout.\nstatus: {"INPUTS_FROZEN_BASELINE_NOT_RUN" if dev_inputs else "DESIGN_PREPARED_RETRIEVAL_NOT_FROZEN"}\npilot_model: {MODEL_ID}\nmodel_revision: TO_BE_PINNED_S09\ntrain_source: {DRAFT.as_posix()}\ntrain_cases: 26\ntrain_semantic_groups: 6\ntrain_license_and_retrieval_evidence: NOT_APPROVED\ndev_cases: 6\nholdout_cases: 6\nholdout_use: FINAL_ONLY_DO_NOT_TUNE\nretrieval_source: BGE_M3_OFFLINE_EXACT_COSINE\nretrieval_mode: TOP5_THRESHOLD_0_4_MODEL_FILTER\nretrieval_file_sha256: {retrieval_sha or 'NOT_SET'}\nmatched_input_for_base_and_sft: true\nthinking_mode: disabled\noutput_format: JSON_ACTION_CUSTOMER_MESSAGE_CITED_EVIDENCE_IDS_MISSING_FIELDS\nallowed_actions: ANSWER_ASK_ESCALATE_EXPLAIN_UNSUPPORTED\nprimary_metrics: ACTION_ACCURACY_REQUIRED_ACTIONS_CONDITION_VIOLATIONS\nsafety_metrics: HIGH_RISK_FORBIDDEN_ACTIONS_UNSUPPORTED_CITATIONS\nlatency_and_cost: MEASURE_SEPARATELY\nevaluation_state: NOT_RUN\n''' 
    report = {
        'status': 'S08_STRUCTURE_PASS_MODEL_BASELINE_PENDING',
        'split_counts': dict(by_split), 'semantic_groups_all': len(group_split),
        'semantic_groups_by_split': {sp: len({r['semantic_group_id'] for r in split if r['split'] == sp}) for sp in COUNTS},
        's07_samples': len(draft), 's07_original_groups': len(draft_groups),
        'dev_targets': len(dev_targets), 'dev_model_inputs_generated': len(dev_inputs or []),
        'held_action_labels': ['SYN-IAC425-110', 'SYN-IAC606-110'],
        'blocked': ['S07 train usage approval and real retrieval evidence',
                    'S09 model/checkpoint/tokenizer validation',
                    'Dev base model inference and scored results',
                    'Dataset expansion and independent larger holdout'],
        'source_sha256': {str(p): sha256(ROOT/p) for p in inputs},
        'retrieval_sha256': retrieval_sha, 'duplicate_header_same_value': duplicated,
        'note': 'S05 GPT-4.1-mini results are NOT the Qwen3 baseline. No Holdout used for tuning.'
    }
    print('[S08] 구조·누출 검증 통과 | Train 18 Dev 6 Holdout 6 | S07 26건/6그룹')
    print(f'[S08] 모델 입력 구성: {len(dev_inputs or [])}/6 (검색 파일 없으면 0), 기준선 실행: 0건')
    if not ns.write:
        print('읽기 전용 점검입니다. 저장하려면 --write를 사용하세요.')
        return
    for p in [OUT_SPLIT, OUT_DEV, OUT_CONTRACT, OUT_REPORT]:
        (ROOT/p).parent.mkdir(parents=True, exist_ok=True)
    with (ROOT/OUT_SPLIT).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=manifest[0].keys());w.writeheader();w.writerows(manifest)
    with (ROOT/OUT_DEV).open('w',encoding='utf-8') as f:
        for x in dev_targets: f.write(json.dumps(x,ensure_ascii=False)+'\n')
    if dev_inputs is not None:
        with (ROOT/OUT_DEV_INPUT).open('w',encoding='utf-8') as f:
            for x in dev_inputs:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    (ROOT/OUT_CONTRACT).write_text(config,encoding='utf-8')
    (ROOT/OUT_REPORT).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('[S08] PREPARE WRITE PASS (평가 규칙 설계 완료, 모델 기준선 미측정)')
    print('  ' + '\n  '.join(map(str,[OUT_SPLIT,OUT_DEV,OUT_CONTRACT,OUT_REPORT])))
    if dev_inputs:print('  '+str(OUT_DEV_INPUT))

if __name__=='__main__':
    main()
