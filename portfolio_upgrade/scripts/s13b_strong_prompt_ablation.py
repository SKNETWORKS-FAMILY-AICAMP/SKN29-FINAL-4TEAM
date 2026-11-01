"""S13b: 2x2 controlled prompt-vs-frozen-LoRA DEV comparison (fictional evidence ONLY).

Run on existing S12 workspace. S12 training is NEVER rerun.

Windows/no GPU:
    python portfolio_upgrade/scripts/s13b_strong_prompt_ablation.py --check
    python -m unittest discover -s portfolio_upgrade/tests -p 'test_s13b_strong_prompt_ablation.py' -v
RunPod with original S12 adapter/predictions retained (billable inference ONLY):
    python portfolio_upgrade/scripts/s13b_strong_prompt_ablation.py --run --ack-cost
If BASE P1 predictions already saved and LoRA generation failed:
    python portfolio_upgrade/scripts/s13b_strong_prompt_ablation.py --resume --ack-cost
Scoring existing predictions (CPU only):
    python portfolio_upgrade/scripts/s13b_strong_prompt_ablation.py --score-only
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import s12_run_fictional_pilot as s12

ROOT = s12.ROOT
PROMPT_FILE = ROOT / 'portfolio_upgrade/configs/s13b_strong_prompt_v1.txt'
OUT = ROOT / 'portfolio_upgrade/experiments/s13b_strong_prompt_v1'
OLD_BASE = 'base_predictions.jsonl'
OLD_LORA = 'lora_predictions.jsonl'
NEW_BASE = 'base_strong_predictions.jsonl'
NEW_LORA = 'lora_strong_predictions.jsonl'
MANIFEST = 's13b_run_manifest.json'
COMPARE = 's13b_2x2_dev_comparison.json'
REPORT = 's13b_human_review_EVAL_ONLY.csv'
EXPECTED_OLD_METRICS = {
    'baseline': {'json_object': 16, 'schema_valid': 11, 'raw_action_match': 6, 'citation_exact': 5},
    'adapter': {'json_object': 15, 'schema_valid': 4, 'raw_action_match': 8, 'citation_exact': 2},
}


def read_prompt() -> str:
    p = PROMPT_FILE.read_text(encoding='utf-8').strip()
    if not p or ('customer_message' not in p or 'missing_fields' not in p or
                 'EXPLAIN_UNSUPPORTED' not in p):
        raise ValueError('Strong prompt output/action contract incomplete.')
    forbidden = ('SIM-B13', 'SIM-M14', 'SIM-Q15', 'SIM-V16',
                 'tracking_mode', 'mounting_type', 'slat_control_mode', 'microphone_source',
                 'S11-F13-', 'S11-F14-', 'S11-F15-', 'S11-F16-')
    if any(t in p for t in forbidden):
        raise ValueError('Strong prompt contains DEV-only product/target-specific tokens.')
    return p


def adapt_inputs(probe: list[dict], strong_prompt: str) -> list[dict]:
    """Only system prompt changes. Product, question, evidence and known conditions stay frozen."""
    modified = copy.deepcopy(probe)
    for original, candidate in zip(probe, modified):
        assert candidate['messages'][0]['role'] == 'system'
        if [m['role'] for m in candidate['messages']] != ['system', 'user']:
            raise ValueError('Probe must contain only system and user messages.')
        candidate['messages'][0]['content'] = strong_prompt
        if candidate['messages'][1] != original['messages'][1]:
            raise ValueError('DEV user input / simulated evidence changed.')
        if (candidate['case_id'], candidate['semantic_group_id']) != (original['case_id'], original['semantic_group_id']):
            raise ValueError('DEV case metadata changed.')
    return modified


def preflight(require_s12_results: bool = False) -> tuple[dict, list[dict], str]:
    cfg, _train, probe, _summary = s12.validate_local()
    prompt = read_prompt()
    adapted = adapt_inputs(probe, prompt)
    if adapted == probe:
        raise ValueError('P1 has not changed the S12 prompt.')
    if {r['case_id'] for r in adapted} != {r['case_id'] for r in probe}:
        raise ValueError('DEV cases changed.')
    if require_s12_results:
        check_s12_saved(cfg, probe)
    print(f'[S13b] PREFLIGHT PASS | DEV={len(probe)}, P1 is system-only; SHA={hashlib.sha256(prompt.encode()).hexdigest()[:12]}...')
    print('[S13b] NO TRAINING | P0 is frozen S12; P1 runs BASE and saved LoRA with identical simulated evidence')
    print('[S13b] FICTIONAL DEV ONLY | No live WaterBridge retrieval, no blind holdout, no human efficacy score')
    return cfg, probe, prompt


def check_s12_saved(cfg: dict, probe: list[dict]) -> dict[str, Path]:
    old = s12.paths(cfg)['out']
    files = {k: old / k for k in [OLD_BASE, OLD_LORA, 'train_report.json', 's12_dev_comparison.json']}
    missing = [str(v) for v in files.values() if not v.is_file()]
    if missing:
        raise FileNotFoundError('Required frozen S12 results missing; restore your S12 backup first: ' + ', '.join(missing))
    report = json.loads(files['train_report.json'].read_text(encoding='utf-8'))
    if (report.get('model') != cfg['base_model'] or
        report.get('revision') != cfg['model_revision'] or
        report.get('train_sha256') != s12.sha256(s12.paths(cfg)['train_file']) or
        report.get('actual_global_step') != 12):
        raise ValueError('Saved adapter report does not match frozen S12 training.')
    comparison = json.loads(files['s12_dev_comparison.json'].read_text(encoding='utf-8'))
    if comparison.get('n_dev_probe') != 16 or comparison.get('status') != 'S12_FICTIONAL_DEV_ABLATION_NOT_WATERBRIDGE_ACCURACY':
        raise ValueError('Unexpected S12 frozen comparison source.')
    for side, met in [('baseline', comparison.get('baseline_metrics', {})), ('adapter', comparison.get('adapter_metrics', {}))]:
        for key, value in EXPECTED_OLD_METRICS[side].items():
            if met.get(key) != value:
                raise ValueError(f'Frozen S12 result changed: {side} {key}, expected {value}, got {met.get(key)}')
    paths = {**files, 'adapter': old / 'adapter'}
    if not (paths['adapter'] / 'adapter_config.json').is_file():
        raise FileNotFoundError('Saved adapter not found. Do NOT retrain; restore adapter/ from S12 backup.')
    adapter_cfg = json.loads((paths['adapter'] / 'adapter_config.json').read_text(encoding='utf-8'))
    model_ref = adapter_cfg.get('base_model_name_or_path')
    if model_ref not in [None, '', cfg['base_model']]:
        raise ValueError(f'LoRA adapter base_model_name_or_path mismatch: {model_ref}')
    existing_id = [r['case_id'] for r in probe]
    for k in [OLD_BASE, OLD_LORA]:
        rows = s12.jsonl(files[k])
        if len(rows) != 16 or [r['case_id'] for r in rows] != existing_id:
            raise ValueError(f'Frozen S12 predictions out of order/duplicate: {k}')
    return paths


def make_manifest(cfg: dict, prompt: str, sources: dict[str, Path]) -> dict:
    return {
        'status': 'S13B_P1_INFERENCE_ONLY_NOT_PRODUCTION',
        'frozen_s12_config_sha256': s12.sha256(s12.CONFIG),
        'frozen_dev_sha256': s12.sha256(s12.paths(cfg)['probe_input_file']),
        'base_model': cfg['base_model'], 'revision': cfg['model_revision'],
        'strong_prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'strong_prompt_file_sha256': s12.sha256(PROMPT_FILE),
        'decoder': 'greedy', 'max_new_tokens': cfg['max_new_tokens'],
        'frozen_source_sha256': {k: s12.sha256(v) for k, v in sources.items() if k != 'adapter'},
        'frozen_adapter_config_sha256': s12.sha256(sources['adapter'] / 'adapter_config.json'),
        'human_review_pending': True,
        'sft_training_performed_here': False,
        'curated_simulated_evidence_not_real_rag': True,
    }


def manifest_check(cfg: dict, prompt: str, sources: dict[str, Path]) -> None:
    current = make_manifest(cfg, prompt, sources)
    prior = json.loads((OUT / MANIFEST).read_text(encoding='utf-8'))
    if prior != current:
        raise ValueError('S13b source/prompt/adapter manifest drift; cannot resume or score.')


def require_gpu() -> None:
    s12.require_cuda()


def verify_prompt_length(tokenizer: Any, inputs: list[dict], max_new_tokens: int) -> None:
    lengths = [len(s12.token_ids(tokenizer, row['messages'])) for row in inputs]
    if max(lengths) + max_new_tokens > 2048:
        raise ValueError(f'Strong prompt+response budget too long: max prompt {max(lengths)} + {max_new_tokens}')
    print(f'[S13b] TOKEN BUDGET PASS | P1 prompts {min(lengths)}..{max(lengths)}; response <= {max_new_tokens}; budget 2048')


def run(cfg: dict, probe: list[dict], prompt: str, resume: bool = False) -> None:
    sources = check_s12_saved(cfg, probe)
    if resume:
        if not OUT.is_dir() or not (OUT / NEW_BASE).is_file() or (OUT / NEW_LORA).exists():
            raise ValueError('Resume allowed only when P1 BASE saved and P1 LoRA not yet saved.')
        manifest_check(cfg, prompt, sources)
        old_saved = s12.jsonl(OUT / NEW_BASE)
        if [r['case_id'] for r in old_saved] != [r['case_id'] for r in probe]:
            raise ValueError('Partial run P1 BASE IDs mismatch.')
    else:
        if OUT.exists():
            raise FileExistsError('S13b experiment folder already exists; never overwrite results: ' + str(OUT))
    require_gpu()
    from peft import PeftModel
    input_rows = adapt_inputs(probe, prompt)
    base_model, tokenizer, _ = s12._load_model_and_tokenizer(cfg)
    verify_prompt_length(tokenizer, input_rows, cfg['max_new_tokens'])
    if not resume:
        print('[S13b] P1 BASE generate 16 DEV, no training...', flush=True)
        base_predictions = s12.predict(base_model, tokenizer, input_rows, cfg, 'P1-BASE')
        # Save the baseline immediately so the user does not need to re-run it if adapter loading fails.
        s12.to_jsonl(OUT / NEW_BASE, base_predictions)
        s12.to_json(OUT / MANIFEST, make_manifest(cfg, prompt, sources))
    else:
        print('[S13b] Reusing saved P1 BASE, only P1 LoRA inference...', flush=True)
    model_with_adapter = PeftModel.from_pretrained(base_model, sources['adapter'], is_trainable=False).eval()
    print('[S13b] P1 LoRA generate same 16 DEV, frozen adapter...', flush=True)
    lora_predictions = s12.predict(model_with_adapter, tokenizer, input_rows, cfg, 'P1-LORA')
    s12.to_jsonl(OUT / NEW_LORA, lora_predictions)
    make_scores(cfg, probe, prompt, sources, write=True)
    print('[S13b] INFERENCE ONLY PASS | Stop GPU and back up folder before deleting Pod.')


def eval_extra(predictions: list[dict], probe: list[dict], targets: list[dict]) -> dict:
    expected = {r['case_id']: r['target_FOR_EVALUATION_ONLY'] for r in targets}
    visible = {r['case_id']: json.loads(r['messages'][1]['content']) for r in probe}
    exact_citations, echoes, useful_message, wrong_fields = 0, 0, 0, 0
    per_action: dict[str, dict[str, int]] = {a: {'correct': 0, 'total': 0} for a in sorted(s12.ACTIONS)}
    for row in predictions:
        cid = row['case_id']
        try:
            obj = json.loads(row['raw_output'])
        except (json.JSONDecodeError, TypeError):
            obj = None
        gold = expected[cid]
        u = visible[cid]
        act = obj.get('action') if isinstance(obj, dict) else None
        per_action[gold['action']]['total'] += 1
        per_action[gold['action']]['correct'] += int(act == gold['action'])
        if isinstance(obj, dict):
            cited = obj.get('cited_evidence_ids')
            if isinstance(cited, list) and all(isinstance(x, str) for x in cited) and len(cited) == len(set(cited)) and set(cited) == set(gold['cited_evidence_ids']):
                exact_citations += 1
            msg = obj.get('customer_message')
            if isinstance(msg, str):
                echoes += (msg.strip() == u['customer_message'].strip())
                useful_message += bool(msg.strip()) and (msg.strip() != u['customer_message'].strip())
            missing = obj.get('missing_fields')
            if isinstance(missing, list) and all(isinstance(x, str) for x in missing):
                wrong_fields += (set(missing) != set(gold['missing_fields']))
    return {
        'citation_id_exact_not_schema_gated': exact_citations,
        'question_echo_count': echoes,
        'non_echo_message_count_NOT_SEMANTIC_SCORE': useful_message,
        'missing_fields_not_exact_count_DIAGNOSTIC': wrong_fields,
        'action_by_gold': per_action,
    }


def build_review_rows(predictions: dict[str,list[dict]], probe: list[dict], targets: list[dict]) -> list[dict]:
    p_map = {name: {x['case_id']: x for x in rows} for name, rows in predictions.items()}
    g_map = {r['case_id']: r['target_FOR_EVALUATION_ONLY'] for r in targets}
    items = []
    for row in probe:
        cid = row['case_id']; user = json.loads(row['messages'][1]['content'])
        item = {'case_id': cid, 'group': row['semantic_group_id'], 'customer_input': user['customer_message'],
                'expected_action_EVAL_ONLY': g_map[cid]['action'],
                'gold_response_EVAL_ONLY': g_map[cid]['customer_message'],
                'gold_missing_fields_EVAL_ONLY': json.dumps(g_map[cid]['missing_fields'],ensure_ascii=False),
                'gold_citation_EVAL_ONLY': json.dumps(g_map[cid]['cited_evidence_ids'],ensure_ascii=False)}
        for name in ['BASE_P0','LORA_P0','BASE_P1','LORA_P1']:
            item[name] = p_map[name][cid]['raw_output']
        item['human_action_correctness'] = ''
        item['human_instruction_correctness'] = ''
        item['human_safety_check'] = ''
        item['reviewer_notes'] = ''
        items.append(item)
    return items


def make_scores(cfg: dict, probe: list[dict], prompt: str, sources: dict[str,Path], write: bool) -> dict:
    manifest_check(cfg, prompt, sources)
    source_predictions = {
        'BASE_P0': s12.jsonl(sources[OLD_BASE]),
        'LORA_P0': s12.jsonl(sources[OLD_LORA]),
        'BASE_P1': s12.jsonl(OUT / NEW_BASE),
        'LORA_P1': s12.jsonl(OUT / NEW_LORA),
    }
    targets = s12.jsonl(s12.paths(cfg)['probe_target_file'])  # OFFLINE scoring ONLY
    expected_ids = [row['case_id'] for row in probe]
    if any([row['case_id'] for row in ps] != expected_ids for ps in source_predictions.values()):
        raise ValueError('Four conditions do not have identical 16 ordered DEV IDs.')
    scored = {name: s12.evaluate_predictions(rows, probe, targets) for name, rows in source_predictions.items()}
    old = json.loads(sources['s12_dev_comparison.json'].read_text(encoding='utf-8'))
    if scored['BASE_P0']['metrics'] != old['baseline_metrics'] or scored['LORA_P0']['metrics'] != old['adapter_metrics']:
        raise ValueError('P0 re-score does not reproduce frozen S12!')
    extras = {name: eval_extra(rows, probe, targets) for name, rows in source_predictions.items()}
    metrics = {name: {**scored[name]['metrics'], **extras[name]} for name in source_predictions}
    def diff(a:str,b:str):
        return {k: metrics[b][k] - metrics[a][k] for k in scored[a]['metrics']}
    out = {
        'status': 'S13B_FICTIONAL_DEV_2X2_NO_RAG_NO_BLIND',
        'n_probe': len(probe),
        'conditions': {'BASE_P0':'original Qwen + S12 system prompt', 'LORA_P0':'S12 frozen LoRA + S12 system prompt',
                       'BASE_P1':'original Qwen + P1 strong prompt', 'LORA_P1':'S12 frozen LoRA + same P1 strong prompt'},
        'metrics': metrics,
        'contrasts': {'effect_of_lora_at_P0':diff('BASE_P0','LORA_P0'),
                      'effect_of_lora_at_P1':diff('BASE_P1','LORA_P1'),
                      'effect_of_prompt_on_BASE':diff('BASE_P0','BASE_P1'),
                      'effect_of_prompt_on_LORA':diff('LORA_P0','LORA_P1')},
        'run_manifest_sha256': s12.sha256(OUT/MANIFEST),
        'customer_answer_semantics_human_review_pending': True,
        'original_s12_results_preserved': True,
        'notes': [
            'P0 results are FROZEN S12, P1 results are new inference; same model revision and curated DEV evidence.',
            'Provided evidence is invented and curated, NOT real WaterBridge BGE-M3 retrieval.',
            'Dev cases have already been read/reviewed; NOT blind generalization.',
            'citation_id_exact_not_schema_gated measures exact reference IDs only, not soundness of answer text.',
            'missing_fields exact string matching on unseen fictional families may not measure semantic equivalence.',
            'This protocol does not test new independent examples; no model selection claim from this alone.',
        ],
    }
    if write:
        s12.to_json(OUT / COMPARE,out)
        rows = build_review_rows(source_predictions,probe,targets)
        p = OUT / REPORT
        if p.exists():
            raise FileExistsError('Review file already exists, refusing overwrite: '+str(p))
        with p.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader();writer.writerows(rows)
    print('[S13b] 2x2 DEV RESULTS |',json.dumps({k:{'schema_valid':v['schema_valid'],'raw_action_match':v['raw_action_match'],'question_echo_count':v['question_echo_count'],'citation_id_exact_not_schema_gated':v['citation_id_exact_not_schema_gated']} for k,v in metrics.items()},ensure_ascii=False))
    print('[S13b] DEV only. No RAG retrieval, no human semantic correctness measure.')
    return out


def score_only(cfg: dict, probe: list[dict], prompt: str) -> None:
    sources = check_s12_saved(cfg, probe)
    if not (OUT / NEW_BASE).is_file() or not (OUT / NEW_LORA).is_file():
        raise FileNotFoundError('Two strong-prompt predictions do not exist; cannot score yet.')
    report = make_scores(cfg, probe, prompt, sources, write=False)
    print(json.dumps(report['contrasts'],ensure_ascii=False,indent=2))
    print('[S13b] SCORE-ONLY PASS | no files written / no GPU')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check',action='store_true')
    group.add_argument('--run',action='store_true')
    group.add_argument('--resume',action='store_true')
    group.add_argument('--score-only',action='store_true')
    parser.add_argument('--ack-cost', action='store_true')
    args = parser.parse_args()
    cfg, probe, prompt = preflight(require_s12_results=(args.run or args.resume or args.score_only))
    if args.check:
        if not s12.paths(cfg)['out'].exists():
            print('[S13b] NOTE: S12 adapter/result folder absent here. Restore its backup on RunPod for --run.')
        print('[S13b] CHECK PASS | zero GPU, model download, and file writes')
    elif args.score_only:
        score_only(cfg, probe, prompt)
    else:
        if not args.ack_cost:
            parser.error('--run/--resume requires --ack-cost; GPU inference is billable, training is not performed.')
        run(cfg,probe,prompt,resume=args.resume)

if __name__=='__main__':
    main()
