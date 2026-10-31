"""S07: S06 PDF-reviewed Train examples -> cautious synthetic draft (stdlib only).

Does NOT call an LLM, train a model, touch Dev/Holdout, or mark records training-ready.
Read-only preview by default. Use --write to create files; --overwrite to replace them.

From repo root (Windows CMD):
  python portfolio_upgrade\\scripts\\s07_prepare_pilot.py
  python portfolio_upgrade\\scripts\\s07_prepare_pilot.py --write
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'portfolio_upgrade/data/training/examples_pdf_reviewed_v1.jsonl'
DEST = ROOT / 'portfolio_upgrade/data/training'
REPORT_DIR = ROOT / 'portfolio_upgrade/experiments/s07_data'

# Each paraphrase preserves the same symptom, product, important time/negation facts
# and uncertainty. These are WRITER-GENERATED proposals, NOT PDF re-verified cases.
PARAPHRASES: dict[str, str] = {
    'SYN-IAC425-101': 'WPU-IAC425 냉수를 선택할 때 알림음이 들리고 잠금 표시가 깜빡여요. 정수는 정상적으로 나옵니다.',
    'SYN-IAC606-103': 'WPU-IAC606입니다. 상담에서 기다렸다가 다시 받아 보라고 했고 전원도 정상인데, 2시간이 지나도 냉수가 계속 미지근해요.',
    'SYN-IAC606-104': 'WPU-IAC606에서 밤에 물 흐르는 소리와 달그락거리는 소리, 공기가 빠지는 듯한 소리가 나요. 고장일까요?',
    'SYN-IAC425-106': 'WPU-IAC425인데 싱크대 조리수를 쓰는 동안에만 물줄기가 약해져요. 조리수를 끄면 다시 정상으로 나옵니다.',
    'SYN-IAC425-108': 'WPU-IAC425 물받이 바깥으로 물이 새서 바닥까지 퍼져요. 버튼을 누를 때마다 띵띵띵 소리도 계속 납니다.',
    'SYN-JAC104-028': 'WPU-JAC104에서 윙 소리가 나고 물 받을 때는 툭 소리, 가끔 물 흐르는 소리까지 들려요. 소리가 큰지는 모르겠습니다.',
    'SYN-IAC606-101': 'WPU-IAC606 냉수를 고르면 부저음과 함께 잠금 표시가 깜빡입니다. 정수는 잘 나오고 있어요.',
    'SYN-IAC606-107': 'WPU-IAC606 물받이 넘침은 아닌데 기기 밑으로 물이 번져요. 버튼을 누르면 계속 띵띵띵 소리가 납니다.',
    'SYN-JAC104-026': 'WPU-JAC104 냉수를 회의 중에 여러 명이 연속으로 많이 사용했더니 그 후부터 덜 차갑습니다. 전에는 정상이었어요.',
    'SYN-JAC104-027': 'WPU-JAC104 전원은 AC 220V로 정상이고 냉수 잠금도 풀었는데, 2시간 뒤 다시 받아도 물이 미지근합니다.',
    'SYN-IAC425-103': 'WPU-IAC425의 전원 220V도 정상이고 냉수 잠금은 해제했어요. 2시간 넘게 기다렸다가 다시 출수해도 미지근합니다.',
    'SYN-IAC425-102': 'WPU-IAC425를 쓰는데 가족들이 냉수를 계속 많이 받은 직후부터 물이 덜 차가워졌어요. 그 전엔 정상이었고 잠금 표시도 없어요.',
    'SYN-IAC606-102': 'WPU-IAC606에서 손님들이 냉수를 연달아 많이 사용한 직후 물이 평소보다 덜 차가워졌습니다. 이전엔 정상입니다.',
}


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f'필수 입력 파일이 없습니다: {path}')
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decide_bucket(x: dict) -> str:
    action = x['target']['action']
    q = x['input']['customer_message']
    if action == 'ESCALATE' and (('물' in q and '새' in q) or '누수' in q or '띵띵띵' in q):
        return 'safety_leak_full_review'
    if action == 'ESCALATE':
        return 'escalation_condition_full_review'
    if action == 'ASK':
        return 'ask_missing_conditions_review'
    return 'answer_condition_review'


def convert(x: dict, kind: str) -> dict:
    y = copy.deepcopy(x)
    source_id = x['provenance']['source_scenario_id']
    y['example_id'] = f'S07-{source_id}-' + ('BASE' if kind == 'source' else 'PAR1')
    if kind == 'paraphrase':
        y['input']['customer_message'] = PARAPHRASES[source_id]
        y['review']['status'] = 'needs_review'
        y['review']['assistant_message_reviewed'] = False  # same output but new customer wording
    y['s07'] = {
        'source_example_id': x['example_id'],
        'variant_kind': kind,
        'content_origin': 's06_pdf_reviewed' if kind == 'source' else 'controlled_manual_paraphrase_proposed',
        'risk_bucket': decide_bucket(x),
        'review_state': 'pending_s07_review',
        'condition_preservation': 'review_needed' if kind == 'paraphrase' else 'from_s06',
        'training_ready': False,
        'retrieval_evidence_supplied': bool(y['input'].get('evidence')),
        'source_use_approved_for_training': False,
    }
    return y


def generate() -> tuple[list[dict], list[dict], dict]:
    source = load_jsonl(INPUT)
    if len(source) != 15:
        raise ValueError(f'S06 입력 15건을 예상했지만 {len(source)}건입니다. 최신 파일을 확인하세요.')
    ids = [r['provenance']['source_scenario_id'] for r in source]
    if len(set(ids)) != len(ids):
        raise ValueError('중복된 S06 source_scenario_id가 있습니다.')
    if set(PARAPHRASES) - set(ids):
        raise ValueError(f'원본에 없는 패러프레이즈 ID: {set(PARAPHRASES)-set(ids)}')
    eligible, held = [], []
    for x in source:
        p, t, rev = x['provenance'], x['target'], x['review']
        if p.get('split') != 'train':
            raise ValueError(f'Train 이외의 분할이 포함됨: {p.get("source_scenario_id")}')
        if t.get('action') not in ('ANSWER', 'ASK', 'ESCALATE'):
            raise ValueError(f'허용 범위 밖 행동: {p.get("source_scenario_id")}')
        if not rev.get('pdf_reviewed') or not rev.get('pdf_hash_matched') or not t.get('assistant_message'):
            raise ValueError(f'PDF 검수/답변 누락: {p.get("source_scenario_id")}')
        if rev.get('training_ready'):
            raise ValueError('S07 자동 생성 단계에서 training_ready=true를 허용하지 않습니다.')
        if rev.get('action_label_review_status') == 'consistent_with_manual':
            eligible.append(x)
        else:
            held.append(x)
    if len(eligible) != 13 or len(held) != 2 or set(PARAPHRASES) != {x['provenance']['source_scenario_id'] for x in eligible}:
        raise ValueError('라벨 재검토 수 또는 안전한 변형 대상이 예상과 다릅니다. 자동 생성을 중단합니다.')

    draft = []
    for x in eligible:
        draft.append(convert(x, 'source'))
        draft.append(convert(x, 'paraphrase'))
    holdback = []
    for x in held:
        y = copy.deepcopy(x)
        y['s07'] = {
            'review_state': 'held_for_action_decision',
            'reason': 'ASK vs ANSWER 미확정 또는 근거 ID 부재',
            'training_ready': False,
        }
        holdback.append(y)
    report = {
        'status': 'PILOT_DRAFT_NOT_TRAIN_READY',
        's06_input_sha256': sha256(INPUT),
        'source_s06_count': len(source),
        'eligible_source_count': len(eligible),
        'label_holdback_count': len(holdback),
        'generated_paraphrase_count': len(eligible),
        'draft_rows': len(draft),
        'source_semantic_groups': len({x['provenance']['semantic_group_id'] for x in source}),
        'draft_semantic_groups': len({x['provenance']['semantic_group_id'] for x in draft}),
        'action_distribution': dict(sorted(Counter(x['target']['action'] for x in draft).items())),
        'held_ids': [x['provenance']['source_scenario_id'] for x in held],
        'safety_and_escalation_rows': sum(x['target']['action'] == 'ESCALATE' for x in draft),
        'need_manual_review': len(draft),
        'training_ready': 0,
        'leakage_policy': 'Only S06 train inputs. Same semantic_group_id preserved. Dev/Holdout never read.',
        'known_limitations': [
            '패러프레이즈는 작성자 생성 초안이며 PDF 재검수/의미 보존 검수 전임',
            '실제 검색 결과를 input.evidence에 아직 연결하지 않음',
            '공식 PDF/합성 데이터의 학습 용도 이용 범위 별도 검토 필요',
            '기초 사례 13건(6개 의미 그룹)의 표현 변형에 불과; 일반화 근거로 쓰지 않음',
            '버튼 명칭 불일치 사례 2건은 행동 라벨과 인덱스 근거 공백 문제로 보류',
            '모델 학습·평가·GPU 사용은 수행하지 않음',
        ],
    }
    return draft, holdback, report


def jsonl_bytes(rows: list[dict]) -> bytes:
    return ('\n'.join(json.dumps(z, ensure_ascii=False, sort_keys=True) for z in rows) + '\n').encode('utf-8')


def log_bytes(draft: list[dict], holdback: list[dict]) -> bytes:
    from io import StringIO
    fields = [
        'example_id', 'source_scenario_id', 'variant_kind', 'split', 'model_code', 'family_group',
        'action', 'risk_bucket', 'customer_question', 'manual_pages', 'source_issue',
        'semantic_same_as_source', 'required_actions_ok', 'forbidden_claims_ok',
        'model_scope_ok', 'evidence_supply_ok', 'rights_ok', 'review_decision', 'review_notes',
    ]
    s = StringIO(); w = csv.DictWriter(s, fieldnames=fields, lineterminator='\n');w.writeheader()
    for item in draft + holdback:
        p, a = item['provenance'], item['target']
        w.writerow({
            'example_id':item['example_id'], 'source_scenario_id':p['source_scenario_id'],
            'variant_kind':item.get('s07',{}).get('variant_kind','held_label'),
            'split':p['split'], 'model_code':item['input']['product_code'],
            'family_group':p['semantic_group_id'], 'action':a['action'],
            'risk_bucket':item.get('s07',{}).get('risk_bucket','label_holdback'),
            'customer_question':item['input']['customer_message'],
            'manual_pages':';'.join(map(str,p['manual_pages'])),
            'source_issue':p.get('source_issue',''),
            'review_decision':'HOLD_ACTION_LABEL' if item in holdback else 'PENDING',
            # Rest of review fields intentionally blank for manual review
        })
    return s.getvalue().encode('utf-8-sig')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true',help='생성물을 파일로 저장')
    parser.add_argument('--overwrite',action='store_true',help='기존 출력 파일 교체(명시적 지정만)')
    args = parser.parse_args()
    try:
        draft, holdback, report = generate()
        out = {
            DEST/'train_draft.jsonl':jsonl_bytes(draft),
            DEST/'s07_label_review_queue.jsonl':jsonl_bytes(holdback),
            DEST/'review_log.csv':log_bytes(draft, holdback),
            REPORT_DIR/'s07_build_report.json':(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'),
        }
        print('[S07] ' + ('파일 생성' if args.write else '읽기 전용 미리보기'))
        print('S06 15건 / 라벨 일치 13건 / 라벨 보류 2건')
        print('원본 13건 + 보수적 질문 재표현 13건 = 초안 26건')
        print('의미 그룹 6개 / 학습 준비 완료 0건 / 새 PDF 검수 완료 0건')
        for p in out:
            print('  '+str(p.relative_to(ROOT)))
        if not args.write:
            print('저장하려면 --write 옵션을 추가하세요.')
            return 0
        already=[str(p.relative_to(ROOT)) for p in out if p.exists()]
        if already and not args.overwrite:
            raise FileExistsError('기존 파일을 덮어쓰지 않음: '+', '.join(already)+' (교체하려면 --overwrite)')
        for p,b in out.items():
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        print('[S07] DRAFT WRITE PASS (검수용, 학습용 확정 아님)')
        return 0
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print('[S07] ERROR:',str(exc),file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
