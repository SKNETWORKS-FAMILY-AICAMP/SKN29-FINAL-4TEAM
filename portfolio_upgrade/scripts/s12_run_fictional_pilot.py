"""S12 fictional-domain LoRA engineering pilot (NO actual WaterBridge manuals).

Windows / CPU:
  python portfolio_upgrade/scripts/s12_run_fictional_pilot.py --check
  python portfolio_upgrade/scripts/s12_run_fictional_pilot.py --token-check
Cloud CUDA (billable):
  python portfolio_upgrade/scripts/s12_run_fictional_pilot.py --run --ack-cost
If evaluation crashes AFTER the adapter and train report were saved:
  python portfolio_upgrade/scripts/s12_run_fictional_pilot.py --compare-only --ack-cost

One command performs: frozen BASE dev-probe generation -> 12-step LoRA ->
checkpoint save -> fresh adapter reload -> same dev-probe generation -> scoring.
No model weights / GPU / internet in --check. Existing results never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'portfolio_upgrade/configs/s12_fictional_pilot.json'
ACTIONS = {'ANSWER', 'ASK', 'ESCALATE', 'EXPLAIN_UNSUPPORTED'}
FIELDS = {'action', 'customer_message', 'cited_evidence_ids', 'missing_fields'}
EXPECTED_MODEL = 'Qwen/Qwen3-1.7B'
EXPECTED_REV = '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def to_json(path: Path, data: Any) -> None:
    """No silent replacement of previous GPU experiments; write tmp then rename."""
    if path.exists():
        raise FileExistsError(f'Existing result, refusing overwrite: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    if tmp.exists():
        raise FileExistsError(f'Interrupted temporary result, review manually: {tmp}')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def to_jsonl(path: Path, data: list[dict]) -> None:
    if path.exists():
        raise FileExistsError(f'Existing predictions, refusing overwrite: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    if tmp.exists():
        raise FileExistsError(f'Interrupted temporary result, review manually: {tmp}')
    try:
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in data), encoding='utf-8')
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def paths(cfg: dict) -> dict[str, Path]:
    return {
        key: ROOT / cfg[key] for key in
        ('source_summary', 'train_file', 'probe_input_file', 'probe_target_file')
    } | {'out': ROOT / cfg['output_folder']}


def validate_schema(obj: Any, provided_ids: set[str]) -> dict:
    parsed = isinstance(obj, dict)
    fields_exact = parsed and set(obj) == FIELDS
    types_ok = bool(fields_exact and isinstance(obj.get('action'), str) and obj['action'] in ACTIONS and
                    isinstance(obj.get('customer_message'), str) and obj['customer_message'].strip() and
                    isinstance(obj.get('cited_evidence_ids'), list) and
                    all(isinstance(e, str) for e in obj['cited_evidence_ids']) and
                    isinstance(obj.get('missing_fields'), list) and
                    all(isinstance(e, str) for e in obj['missing_fields']))
    cites = (list(obj['cited_evidence_ids']) if types_ok else [])
    citation_grounded = bool(types_ok and cites and len(cites) == len(set(cites)) and set(cites) <= provided_ids)
    missing = (list(obj['missing_fields']) if types_ok else [])
    missing_contract = bool(types_ok and len(missing) == len(set(missing)) and
                            (bool(missing) if obj['action'] == 'ASK' else not missing))
    return {'json_object': parsed, 'fields_exact': bool(fields_exact),
            'field_types_valid': types_ok,
            'schema_valid': bool(types_ok and citation_grounded and missing_contract),
            'citation_grounded': citation_grounded, 'missing_contract_valid': missing_contract}


def validate_local() -> tuple[dict, list[dict], list[dict], dict]:
    if not CONFIG.is_file():
        raise FileNotFoundError(f'Missing S12 config: {CONFIG}')
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    if cfg.get('status') != 'S12_FICTIONAL_ENGINEERING_PILOT_ONLY':
        raise ValueError('S12 is allowed only for independent fictional engineering data.')
    if cfg.get('manual_data_training_authorized') is not False or cfg.get('production_claim_allowed') is not False:
        raise ValueError('S12 safety boundary removed: refuse to run.')
    if cfg.get('human_review_pending') is not True or cfg.get('probe_type') != 'DEV_ALREADY_AI_REVIEWED_NOT_BLIND':
        raise ValueError('S11 provenance or evaluation claim guard changed.')
    if cfg.get('gpu_ack_required') is not True or cfg.get('enable_thinking') is not False:
        raise ValueError('GPU approval or chat-template setting changed.')
    if cfg.get('base_model') != EXPECTED_MODEL or cfg.get('model_revision') != EXPECTED_REV:
        raise ValueError('Qwen3 model and revision must match S10, no silent base drift.')
    if cfg.get('decode') != 'greedy' or not 1 <= cfg.get('max_steps', -1) <= 12:
        raise ValueError('Generation and training budget must remain frozen.')
    if cfg.get('max_steps') != 12 or cfg.get('max_length') != 768 or not 64 <= cfg.get('max_new_tokens', -1) <= 256:
        raise ValueError('Pilot fixed train length / decoding bounds changed.')
    if cfg.get('per_device_train_batch_size') != 1 or cfg.get('gradient_accumulation_steps') != 4:
        raise ValueError('Pilot training schedule changed without new experiment ID.')
    if cfg.get('lora_target_modules') != ['q_proj', 'v_proj'] or cfg.get('prompt_loss_mask') != -100:
        raise ValueError('LoRA target or completion masking contract changed.')
    p = paths(cfg)
    summary = json.loads(p['source_summary'].read_text(encoding='utf-8'))
    if summary.get('status') != 'S11_FICTIONAL_V2_AI_PRE_REVIEWED_NOT_REAL_WATERBRIDGE_APPROVED':
        raise ValueError('Wrong S11 v2 source summary status.')
    if summary.get('fictional_sft_engineering_pilot_eligible') is not True or summary.get('human_signed_off') is not False:
        raise ValueError('S11 v2 pilot boundary changed unexpectedly.')
    if summary.get('manual_based_data_use_authorized') is not False:
        raise ValueError('Accidental manual training rights claim.')
    for tag, filename in (
        ('train_file', 's11_fictional_train_v2.jsonl'),
        ('probe_input_file', 's11_fictional_probe_inputs_v2.jsonl'),
        ('probe_target_file', 's11_fictional_probe_targets_EVAL_ONLY_v2.jsonl'),
    ):
        if p[tag].name != filename or 'data/s11_grounded/v2' not in p[tag].as_posix():
            raise ValueError(f'Unexpected data path: {p[tag]}')
        if sha256(p[tag]) != summary['output_sha256'][filename]:
            raise ValueError(f'S11 v2 SHA mismatch; do not train: {filename}')
    train = jsonl(p['train_file'])
    probe = jsonl(p['probe_input_file'])
    if len(train) != 48 or len(probe) != 16:
        raise ValueError('Expected Train 48 + DEV Probe 16, nothing else.')
    if len({r['case_id'] for r in train + probe}) != 64:
        raise ValueError('Duplicate case IDs between or within splits.')
    tg = {r['semantic_group_id'] for r in train}
    pg = {r['semantic_group_id'] for r in probe}
    if tg != {f'F{i:02d}' for i in range(1, 13)} or pg != {f'F{i:02d}' for i in range(13, 17)}:
        raise ValueError('Independent train/dev families changed or leaked.')
    counts = Counter()
    for row in train + probe:
        is_train = row['split'] == 'train'
        if is_train != (row in train):
            raise ValueError('Train/probe split label mismatch.')
        if row.get('source_kind') != 'ORIGINAL_FICTIONAL_POLICY' or row.get('training_ready_for_waterbridge') is not False:
            raise ValueError('Nonfictional source or real product claim in S12.')
        if row.get('evaluation_origin') != 'CURATED_SIMULATED_EVIDENCE_NOT_BGE_RETRIEVAL':
            raise ValueError('S12 is not a RAG retrieval performance experiment.')
        messages = row['messages']
        if [m['role'] for m in messages] != (['system', 'user', 'assistant'] if is_train else ['system', 'user']):
            raise ValueError(f'Assistant target leaked into probe or missing in train: {row["case_id"]}')
        user_input = json.loads(messages[1]['content'])
        if set(user_input) != {'customer_message', 'product_code', 'known_conditions', 'provided_evidence'}:
            raise ValueError('Unexpected visible user input fields.')
        code = user_input['product_code']
        if not isinstance(code, str) or not code.startswith('SIM-') or not isinstance(user_input['known_conditions'], list):
            raise ValueError('Real WaterBridge product or malformed conditions detected.')
        if not isinstance(user_input['customer_message'], str):
            raise ValueError('Invalid customer text')
        evidence = user_input['provided_evidence']
        if len(evidence) != 2 or any(set(e) != {'id', 'text', 'source_kind'} for e in evidence):
            raise ValueError('Curated evidence input changed.')
        ids = {e['id'] for e in evidence}
        if len(ids) != 2 or any(not x.startswith('SIM-EVD-') for x in ids):
            raise ValueError('Nonfictional or duplicate evidence ID.')
        if is_train:
            answer = json.loads(messages[2]['content'])
            result = validate_schema(answer, ids)
            if not result['schema_valid']:
                raise ValueError(f'Invalid training JSON contract in {row["case_id"]}: {result}')
            counts[answer['action']] += 1
        else:
            if set(row['visible_citation_ids']) != ids:
                raise ValueError('Probe visible citation IDs differ from provided evidence.')
    if {k: counts[k] for k in sorted(ACTIONS)} != {a: 12 for a in sorted(ACTIONS)}:
        raise ValueError('S12 training action balance altered.')
    # Read gold for OFFLINE validation only. Never forward this list to
    # tokenize_train(), predict() or SFTTrainer; those see separate inputs.
    eval_targets = jsonl(p['probe_target_file'])
    if len(eval_targets) != 16 or len({x['case_id'] for x in eval_targets}) != 16:
        raise ValueError('DEV target count/IDs changed.')
    by_id = {x['case_id']: x for x in eval_targets}
    action_counts = Counter()
    for row in probe:
        record = by_id.get(row['case_id'])
        if record is None or record.get('semantic_group_id') != row['semantic_group_id']:
            raise ValueError('DEV input/target case ID or group mismatch.')
        visible_ids = set(row['visible_citation_ids'])
        gold = record['target_FOR_EVALUATION_ONLY']
        if not validate_schema(gold, visible_ids)['schema_valid'] or gold['action'] != record['expected_action']:
            raise ValueError('Invalid DEV gold schema or action.')
        action_counts[gold['action']] += 1
    if any(action_counts[a] != 4 for a in ACTIONS):
        raise ValueError('Unbalanced development probe action labels.')
    print(f'[S12] PREFLIGHT PASS | Train={len(train)}, DEV probe={len(probe)}, groups={len(tg)}+{len(pg)}')
    print(f'[S12] SHA PASS | Train={sha256(p["train_file"])[:12]}... | Probe={sha256(p["probe_input_file"])[:12]}...')
    print('[S12] FICTION ONLY | S11 DEV probe is already AI-reviewed; no WaterBridge manuals or blind Holdout')
    return cfg, train, probe, summary


def token_ids(tokenizer, messages: list[dict]) -> list[int]:
    obj = tokenizer.apply_chat_template(messages, tokenize=True,
                                        add_generation_prompt=True, enable_thinking=False)
    ids = obj['input_ids'] if hasattr(obj, 'keys') else obj
    if isinstance(ids, list) and len(ids) == 1 and isinstance(ids[0], list):
        ids = ids[0]
    if not isinstance(ids, list) or not ids or any(not isinstance(t, int) for t in ids):
        raise TypeError('Expected flat prompt token ID list from Qwen3 chat template.')
    return ids


def tokenize_train(tokenizer, train: list[dict], max_length: int) -> list[dict]:
    outputs = []
    for row in train:
        prompt = token_ids(tokenizer, row['messages'][:2])
        target = tokenizer.encode(row['messages'][2]['content'] + '<|im_end|>', add_special_tokens=False)
        if not target or not all(isinstance(t, int) for t in target):
            raise ValueError('Empty/malformed assistant target tokens')
        if len(prompt) + len(target) > max_length:
            raise ValueError(f'S12 token length exceeds {max_length}: {row["case_id"]}: {len(prompt)}+{len(target)}')
        outputs.append({'input_ids': prompt + target,
                        'attention_mask': [1] * (len(prompt) + len(target)),
                        'labels': [-100] * len(prompt) + target})
    return outputs


def token_check(cfg: dict, train: list[dict], probe: list[dict]) -> None:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg['base_model'], revision=cfg['model_revision'], trust_remote_code=False)
    encoded = tokenize_train(tok, train, cfg['max_length'])
    lens = [len(x['input_ids']) for x in encoded]
    trg = [sum(t != -100 for t in x['labels']) for x in encoded]
    probe_lens = [len(token_ids(tok, r['messages'])) for r in probe]
    if max(probe_lens) + cfg['max_new_tokens'] > 1024:
        raise ValueError('Probe prompt + generation exceeds the 1024-token pilot budget')
    print(f'[S12] TOKEN PASS | train={min(lens)}..{max(lens)}/{cfg["max_length"]}; '
          f'completion min={min(trg)}; dev prompt max={max(probe_lens)}; '
          f'labels masked={all(-100 in x["labels"] for x in encoded)}')


def collate_completion_only(samples: list[dict], pad_token_id: int):
    """Do not let generic LM collators rebuild labels and erase prompt masking."""
    import torch
    maxlen = max(len(x['input_ids']) for x in samples)
    result = {'input_ids': [], 'attention_mask': [], 'labels': []}
    for x in samples:
        n = len(x['input_ids'])
        if not (len(x['labels']) == len(x['attention_mask']) == n):
            raise ValueError('S12 token/mask mismatch')
        pad = maxlen - n
        result['input_ids'].append(x['input_ids'] + [pad_token_id] * pad)
        result['attention_mask'].append(x['attention_mask'] + [0] * pad)
        result['labels'].append(x['labels'] + [-100] * pad)
    return {k: torch.tensor(v, dtype=torch.long) for k,v in result.items()}


def extract_generation_ids(encoded):
    """Support transformers 4/5: tensor or BatchEncoding returned by chat template."""
    if hasattr(encoded, 'keys'):
        if 'input_ids' not in encoded:
            raise ValueError('No input_ids in chat template encoding')
        return encoded['input_ids'], encoded.get('attention_mask')
    return encoded, None


def predict(model, tokenizer, probe: list[dict], cfg: dict, prefix: str) -> list[dict]:
    import torch
    model.eval()
    end_id = tokenizer.convert_tokens_to_ids('<|im_end|>')
    if not isinstance(end_id, int) or end_id < 0:
        raise ValueError('Missing Qwen3 <|im_end|> stop token.')
    results = []
    for i, r in enumerate(probe, 1):
        tensor = tokenizer.apply_chat_template(
            r['messages'], tokenize=True, add_generation_prompt=True,
            enable_thinking=False, return_tensors='pt')
        ids, attention = extract_generation_ids(tensor)
        ids = ids.to('cuda')
        attention = attention.to('cuda') if attention is not None else torch.ones_like(ids)
        if ids.ndim != 2 or ids.size(0) != 1 or attention.shape != ids.shape:
            raise ValueError('Unexpected tokenization output for generation')
        start = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(
                input_ids=ids, attention_mask=attention,
                do_sample=False, max_new_tokens=cfg['max_new_tokens'],
                eos_token_id=end_id, pad_token_id=tokenizer.pad_token_id,
            )
        raw = tokenizer.decode(generated[0, ids.size(1):], skip_special_tokens=True).strip()
        results.append({'case_id': r['case_id'], 'semantic_group_id': r['semantic_group_id'],
                        'raw_output': raw, 'generated_tokens': int(generated.size(1)-ids.size(1)),
                        'generation_seconds': round(time.monotonic()-start, 3)})
        print(f'[S12] {prefix} probe {i}/{len(probe)} | {r["case_id"]}', flush=True)
    return results


def evaluate_predictions(predictions: list[dict], probe: list[dict], targets: list[dict]) -> dict:
    if len(predictions) != len(probe) or len(targets) != len(probe):
        raise ValueError('Need one model prediction and one target for each DEV probe')
    ref = {r['case_id']: r for r in targets}
    pred = {r['case_id']: r for r in predictions}
    if len(ref) != len(probe) or len(pred) != len(probe):
        raise ValueError('Case ID duplication in targets or predictions')
    results = []
    for p in probe:
        k = p['case_id']
        if k not in pred or k not in ref or ref[k]['semantic_group_id'] != p['semantic_group_id']:
            raise ValueError(f'Crossed/missing probe row: {k}')
        u = json.loads(p['messages'][1]['content'])
        visible = {x['id'] for x in u['provided_evidence']}
        target = ref[k]['target_FOR_EVALUATION_ONLY']
        if not validate_schema(target, visible)['schema_valid']:
            raise ValueError(f'Invalid evaluation target: {k}')
        try:
            obj = json.loads(pred[k]['raw_output'])
            error = None
        except (json.JSONDecodeError, ValueError, TypeError) as ex:
            obj, error = None, str(ex)
        flags = validate_schema(obj, visible)
        action = obj.get('action') if isinstance(obj, dict) else None
        action_ok = action == target['action']
        strict_action_ok = bool(flags['schema_valid'] and action_ok)
        cite_ok = bool(flags['schema_valid'] and
                       set(obj['cited_evidence_ids']) == set(target['cited_evidence_ids']))
        missing_ok = bool(flags['schema_valid'] and
                          set(obj['missing_fields']) == set(target['missing_fields']))
        results.append({'case_id': k, 'expected_action': target['action'],
                        'predicted_action': action, 'json_parse_error': error,
                        **flags, 'raw_action_match': action_ok,
                        'strict_action_match': strict_action_ok,
                        'citation_exact': cite_ok, 'missing_fields_exact': missing_ok,
                        'structured_target_match': bool(strict_action_ok and cite_ok and missing_ok)})
    fields = ['json_object', 'fields_exact', 'field_types_valid', 'schema_valid',
              'citation_grounded', 'missing_contract_valid', 'raw_action_match',
              'strict_action_match', 'citation_exact', 'missing_fields_exact', 'structured_target_match']
    return {'n': len(results), 'metrics': {x: sum(r[x] for r in results) for x in fields},
            'cases': results,
            'disclaimer': 'DEV probe already AI-reviewed. Customer answer semantic correctness NOT scored; citation/missing-field comparison is structured exact match only.'}


def compare_results(baseline: dict, adapter: dict) -> dict:
    if baseline['n'] != 16 or adapter['n'] != 16:
        raise ValueError('S12 comparison needs the same 16 probes.')
    bm, am = baseline['metrics'], adapter['metrics']
    diff = {k: am[k] - bm[k] for k in bm}
    both = {r['case_id']: r for r in adapter['cases']}
    return {'status': 'S12_FICTIONAL_DEV_ABLATION_NOT_WATERBRIDGE_ACCURACY',
            'n_dev_probe': 16,
            'baseline_metrics': bm, 'adapter_metrics': am,
            'adapter_minus_baseline': diff,
            'changed_cases': [
                {'case_id': a['case_id'],
                 'base_action': a['predicted_action'],
                 'lora_action': both[a['case_id']]['predicted_action'],
                 'base_schema_ok': a['schema_valid'],
                 'lora_schema_ok': both[a['case_id']]['schema_valid']}
                for a in baseline['cases'] if a['predicted_action'] != both[a['case_id']]['predicted_action'] or
                a['schema_valid'] != both[a['case_id']]['schema_valid']
            ],
            'human_review_pending': True,
            'real_manual_sft_authorized': False,
            'blind_final_performance_measured': False,
            'customer_answer_semantics_measured': False,
            'notes': ['Gold loaded only for offline scoring after generation.',
                      'Same 16 fixed fictional DEV prompts, Qwen3 revision, greedy decoding and max_new_tokens for both.',
                      'Generations use curated simulated evidence, NOT actual BGE-M3 retrieval.',
                      'Do NOT use DEV results as proof of generalization or claim production performance.']}


def _collect_and_save_comparison(cfg: dict, probe: list[dict], output: Path) -> None:
    """Read gold targets only after both base and adapter predictions exist."""
    target = jsonl(paths(cfg)['probe_target_file'])
    original = jsonl(output / 'base_predictions.jsonl')
    tuned = jsonl(output / 'lora_predictions.jsonl')
    b = evaluate_predictions(original, probe, target)
    a = evaluate_predictions(tuned, probe, target)
    report = compare_results(b, a)
    to_json(output / 's12_dev_comparison.json', report)
    print('[S12] DEV SUMMARY | BASE:', json.dumps(b['metrics'], ensure_ascii=False), flush=True)
    print('[S12] DEV SUMMARY | LORA:', json.dumps(a['metrics'], ensure_ascii=False), flush=True)
    print('[S12] COMPARE PASS | fictional DEV only; no blind final or WaterBridge claims', flush=True)


def _load_model_and_tokenizer(cfg: dict):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(
        cfg['base_model'], revision=cfg['model_revision'], trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        cfg['base_model'], revision=cfg['model_revision'], dtype=dtype,
        trust_remote_code=False).to('cuda').eval()
    return model, tokenizer, dtype


def require_cuda():
    try:
        import torch
    except ImportError as ex:
        raise RuntimeError('Install CUDA PyTorch before GPU training; --check works without it.') from ex
    if not torch.cuda.is_available():
        raise RuntimeError('S12 --run requires CUDA; CPU model training is intentionally disabled.')
    print(f'[S12] GPU={torch.cuda.get_device_name(0)} | PyTorch={torch.__version__}', flush=True)
    return torch


def run_gpu(cfg: dict, train: list[dict], probe: list[dict]) -> None:
    out = paths(cfg)['out']
    if out.exists():
        raise FileExistsError(f'S12 experiment folder already exists. Never overwrite or bill twice: {out}')
    torch = require_cuda()
    try:
        import transformers, trl, peft, datasets, accelerate
        from datasets import Dataset
        from transformers import TrainingArguments
        from trl import SFTTrainer, SFTConfig
        from peft import get_peft_model, LoraConfig, PeftModel
    except ImportError as ex:
        raise RuntimeError('Install S10-compatible transformers, trl, peft, datasets, accelerate, safetensors first.') from ex
    seed = cfg['seed']
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.cuda.reset_peak_memory_stats()
    start = time.monotonic()
    model, tokenizer, dtype = _load_model_and_tokenizer(cfg)
    # Stage 1: REAL BASE outputs are frozen BEFORE introducing any LoRA adapter.
    print('[S12] 1/3 Base inference on untouched fictional DEV probe', flush=True)
    baseline = predict(model, tokenizer, probe, cfg, prefix='BASE')
    out.mkdir(parents=True, exist_ok=False)
    to_json(out / 'run_manifest.json', {
        'status': 'S12_FICTIONAL_DEV_BASELINE_FROZEN_BEFORE_TRAINING',
        'model': cfg['base_model'], 'revision': cfg['model_revision'],
        'data_sha256': {k: sha256(p) for k,p in paths(cfg).items() if k not in ('out',)},
        'config_sha256': sha256(CONFIG),
        'generation_config': {'decode': cfg['decode'], 'max_new_tokens': cfg['max_new_tokens'],
                              'enable_thinking': cfg['enable_thinking']},
        'training_configuration': {'max_steps': cfg['max_steps'], 'learning_rate': cfg['learning_rate'],
                                   'lora_r': cfg['lora_r'], 'lora_alpha': cfg['lora_alpha']},
    })
    to_jsonl(out / 'base_predictions.jsonl', baseline)
    # Stage 2: LoRA only, explicit -100 prompt mask. Never load probe targets for training.
    print('[S12] 2/3 Train LoRA on 48 fictional Train records (no probe targets)', flush=True)
    tokenized = tokenize_train(tokenizer, train, cfg['max_length'])
    target_lengths = [sum(t != -100 for t in x['labels']) for x in tokenized]
    model.config.use_cache = False
    lora = LoraConfig(task_type='CAUSAL_LM', r=cfg['lora_r'], lora_alpha=cfg['lora_alpha'],
                      lora_dropout=cfg['lora_dropout'], target_modules=cfg['lora_target_modules'], bias='none')
    model = get_peft_model(model, lora)
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in model.parameters())
    if not 0 < n_trainable < n_total:
        raise RuntimeError('LoRA did not freeze base model params; abort.')
    print(f'[S12] trainable/total={n_trainable:,}/{n_total:,} ({n_trainable/n_total:.3%})', flush=True)
    dataset = Dataset.from_list(tokenized)
    args = SFTConfig(
        output_dir=str(out / 'trainer_tmp'),
        max_steps=cfg['max_steps'], max_length=cfg['max_length'],
        per_device_train_batch_size=cfg['per_device_train_batch_size'],
        gradient_accumulation_steps=cfg['gradient_accumulation_steps'],
        learning_rate=cfg['learning_rate'],
        bf16=(dtype == torch.bfloat16), fp16=(dtype == torch.float16),
        packing=False, logging_steps=1, save_strategy='no', report_to='none',
        gradient_checkpointing=False, optim='adamw_torch',
        seed=seed, data_seed=seed,
        remove_unused_columns=False, disable_tqdm=False,
    )
    trainer = SFTTrainer(
        model=model, args=args, train_dataset=dataset,
        processing_class=tokenizer,
        data_collator=lambda rows: collate_completion_only(rows, tokenizer.pad_token_id),
    )
    # Check actual trainer batch matches our pretokenized prompt/completion mask.
    first = next(iter(trainer.get_train_dataloader()))
    if first['input_ids'].ndim != 2 or first['labels'].shape != first['input_ids'].shape:
        raise RuntimeError('SFTTrainer collator has broken token/label shape.')
    if int((first['labels'] != -100).sum()) <= 0 or int((first['labels'] == -100).sum()) <= 0:
        raise RuntimeError('SFTTrainer lost completion-only loss mask.')
    if torch.any((first['labels'] != -100) & (first['input_ids'] != first['labels'])):
        raise RuntimeError('SFTTrainer label/input alignment changed; abort before training.')
    trained = trainer.train()
    if not math.isfinite(trained.training_loss):
        raise RuntimeError('Nonfinite loss; do not trust the adapter.')
    adapter = out / 'adapter'
    if adapter.exists():
        raise FileExistsError('Adapter output already exists: ' + str(adapter))
    trainer.model.save_pretrained(adapter, safe_serialization=True)
    tokenizer.save_pretrained(adapter)
    if not (adapter / 'adapter_config.json').exists():
        raise RuntimeError('Adapter was not saved; check persistent storage before stopping GPU.')
    report = {
        'status': 'S12_FICTIONAL_TRAINED_NOT_PRODUCTION',
        'model': cfg['base_model'], 'revision': cfg['model_revision'],
        'train_sha256': sha256(paths(cfg)['train_file']),
        'train_count': len(train), 'dev_count_not_trained': len(probe),
        'max_steps': cfg['max_steps'], 'actual_global_step': trainer.state.global_step,
        'train_loss': trained.training_loss,
        'trainable': n_trainable, 'total': n_total,
        'target_token_min': min(target_lengths), 'target_token_max': max(target_lengths),
        'prompt_mask_verified': True,
        'seconds_to_training_and_save': round(time.monotonic()-start, 3),
        'peak_gpu_memory_allocated_gib': round(torch.cuda.max_memory_allocated()/(1024**3), 3),
        'gpu': torch.cuda.get_device_name(0), 'dtype': str(dtype),
        'logs': trainer.state.log_history,
        'versions': {'python':platform.python_version(),'torch':torch.__version__,
                     'transformers':transformers.__version__,'trl':trl.__version__,
                     'peft':peft.__version__,'datasets':datasets.__version__,
                     'accelerate':accelerate.__version__},
        'manual_data_training_authorized': False, 'production_quality_measured': False,
    }
    to_json(out / 'train_report.json', report)
    print('[S12] TRAIN+ADAPTER SAVED |', adapter, flush=True)
    # Fresh model & adapter reload, not the model object that just trained.
    del trainer, model, dataset, tokenized
    torch.cuda.empty_cache()
    print('[S12] 3/3 Fresh adapter reload, then same DEV prompts', flush=True)
    base2, tokenizer2, _ = _load_model_and_tokenizer(cfg)
    adapter_model = PeftModel.from_pretrained(base2, adapter, is_trainable=False).eval()
    tuned = predict(adapter_model, tokenizer2, probe, cfg, prefix='LORA')
    to_jsonl(out / 'lora_predictions.jsonl', tuned)
    _collect_and_save_comparison(cfg, probe, out)
    print('[S12] GPU peak GiB allocated:', round(torch.cuda.max_memory_allocated()/(1024**3), 3), flush=True)
    print('[S12] BACK UP adapter/ + train_report.json + predictions/*.jsonl + s12_dev_comparison.json BEFORE deleting GPU pod.',flush=True)


def compare_only(cfg: dict, probe: list[dict]):
    out = paths(cfg)['out']
    if not (out / 'run_manifest.json').is_file() or not (out / 'base_predictions.jsonl').is_file():
        raise FileNotFoundError('No frozen base predictions. Cannot compare.')
    if not (out / 'adapter' / 'adapter_config.json').is_file() or not (out / 'train_report.json').is_file():
        raise FileNotFoundError('No saved adapter/training report. Cannot run --compare-only.')
    if (out / 'lora_predictions.jsonl').exists() or (out / 's12_dev_comparison.json').exists():
        raise FileExistsError('LOra prediction or comparison already exists; do not overwrite/rebill.')
    manifest = json.loads((out/'run_manifest.json').read_text(encoding='utf-8'))
    report = json.loads((out/'train_report.json').read_text(encoding='utf-8'))
    if (manifest['config_sha256'] != sha256(CONFIG) or
        report['train_sha256'] != sha256(paths(cfg)['train_file']) or
        report['revision'] != cfg['model_revision'] or
        manifest['data_sha256']['probe_input_file'] != sha256(paths(cfg)['probe_input_file'])):
        raise ValueError('Training config/source changed. Refuse mismatched adapter comparison.')
    require_cuda()
    from peft import PeftModel
    model, tokenizer, _ = _load_model_and_tokenizer(cfg)
    model = PeftModel.from_pretrained(model, out/'adapter', is_trainable=False).eval()
    to_jsonl(out/'lora_predictions.jsonl', predict(model,tokenizer,probe,cfg,'LORA'))
    _collect_and_save_comparison(cfg,probe,out)


def show_existing(cfg: dict, probe: list[dict]):
    out = paths(cfg)['out']
    if not (out/'base_predictions.jsonl').is_file() or not (out/'lora_predictions.jsonl').is_file():
        raise FileNotFoundError('Model predictions not generated yet. Run GPU pilot first.')
    gold = jsonl(paths(cfg)['probe_target_file'])
    b = evaluate_predictions(jsonl(out/'base_predictions.jsonl'),probe,gold)
    a = evaluate_predictions(jsonl(out/'lora_predictions.jsonl'),probe,gold)
    print(json.dumps(compare_results(b,a),ensure_ascii=False,indent=2))
    print('[S12] SCORE ONLY: no GPU / no file writes; this is a recheck of EXISTING results.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mx = parser.add_mutually_exclusive_group(required=True)
    mx.add_argument('--check',action='store_true')
    mx.add_argument('--token-check',action='store_true')
    mx.add_argument('--run',action='store_true')
    mx.add_argument('--compare-only',action='store_true')
    mx.add_argument('--score-only',action='store_true')
    parser.add_argument('--ack-cost', action='store_true',
                        help='Explicit acknowledgement of billable CUDA GPU execution')
    ns=parser.parse_args()
    cfg,train,probe,_=validate_local()
    if ns.token_check: token_check(cfg,train,probe)
    if ns.run or ns.compare_only:
        if not ns.ack_cost:
            parser.error('GPU execution requires --ack-cost. No background GPU billing is initiated.')
        if ns.run: run_gpu(cfg,train,probe)
        else: compare_only(cfg,probe)
    if ns.score_only: show_existing(cfg,probe)
    if ns.check:
        print('[S12] CHECK PASS | no model download / GPU / file writes | ready for fictional S12 pilot after human review boundary is understood')
