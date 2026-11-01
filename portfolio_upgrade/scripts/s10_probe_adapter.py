"""S10: reload the LoRA adapter and compare with BASE on separate toy prompts.

Windows/CPU preflight, zero downloads:
    python portfolio_upgrade/scripts/s10_probe_adapter.py --check
Run on same CUDA pod after training and before stopping it:
    python portfolio_upgrade/scripts/s10_probe_adapter.py --run --ack-cost

This is a pipeline smoke-test; never call toy action rate WaterBridge accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import nullcontext
import json
import hashlib
from pathlib import Path
import time

import s10_prepare_demo as demo
import s10_train_lora as train_module

ROOT = Path(__file__).resolve().parents[2]
OUT = train_module.OUT
PROBE_OUT = OUT / 'toy_probe_predictions.jsonl'
SUMMARY = OUT / 'toy_probe_summary.json'


def validate_local() -> tuple[dict, list[dict]]:
    cfg, _ = train_module.validate_local()
    records = train_module.read_jsonl(demo.PROBES)
    manifest = json.loads(demo.MANIFEST.read_text(encoding='utf-8'))
    if len(records) != 8 or manifest['probes_sha256'] != train_module.digest(demo.PROBES):
        raise ValueError('Toy probe set missing or changed unexpectedly.')
    if any(r['split'] != 'probe' or r['origin'] != 'FICTIONAL_ORIGINAL_DEMO' for r in records):
        raise ValueError('Only independent fictional toy probes are allowed.')
    if set(r['source_id'] for r in records) & set(r['source_id'] for r in train_module.read_jsonl(demo.TRAIN)):
        raise ValueError('Toy source case crossing train/probe split.')
    print('[S10] PROBE CHECK PASS | 8 separate fictional source cases | no real Dev/Holdout')
    if train_module.REPORT.is_file():
        report = json.loads(train_module.REPORT.read_text(encoding='utf-8'))
        if report.get('status') != 'TOY_LORA_TRAINED_NOT_WATERBRIDGE_EVALUATED':
            raise ValueError('Unexpected S10 training report state.')
        if report.get('train_sha256') != train_module.digest(demo.TRAIN):
            raise ValueError('Adapter training provenance does not match the toy dataset.')
        if report.get('revision') != cfg['model_revision']:
            raise ValueError('Training model revision mismatch.')
        print('[S10] TRAIN REPORT CHECK PASS | adapter training metadata found')
    else:
        print('[S10] No training report yet. This is normal before GPU S10.')
    print('[S10] No model download, CUDA request or model inference performed.')
    return cfg, records


def extract_generation_inputs(encoded):
    """Accept a tensor (Transformers 4) or a BatchEncoding (Transformers 5).

    Return (input_ids, attention_mask). In the old tensor-only case the mask
    is constructed by the caller. Avoid mixing tensors with mapping objects.
    """
    if hasattr(encoded, 'keys'):
        if 'input_ids' not in encoded:
            raise ValueError('Tokenizer BatchEncoding has no input_ids.')
        return encoded['input_ids'], encoded.get('attention_mask')
    return encoded, None


def run(cfg: dict, records: list[dict]) -> None:
    if not train_module.REPORT.is_file() or not train_module.ADAPTER.is_dir():
        raise FileNotFoundError('Train S10 toy adapter first; adapter + report not found.')
    if PROBE_OUT.exists() or SUMMARY.exists():
        raise FileExistsError('S10 toy probe outputs already exist. Avoid accidental repeat GPU charges.')
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import PeftModel
    except ImportError as exc:
        raise RuntimeError('Install compatible GPU torch/transformers/peft first.') from exc
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required for adapter comparison. CPU model inference not started.')
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    print('[S10] Loading original model + saved adapter |', cfg['base_model'], cfg['model_revision'], flush=True)
    tokenizer = AutoTokenizer.from_pretrained(cfg['base_model'], revision=cfg['model_revision'], trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base_model = AutoModelForCausalLM.from_pretrained(
        cfg['base_model'], revision=cfg['model_revision'], dtype=dtype, trust_remote_code=False
    ).eval().to('cuda')
    model = PeftModel.from_pretrained(base_model, str(train_module.ADAPTER), is_trainable=False).eval()
    end_id = tokenizer.convert_tokens_to_ids('<|im_end|>')
    results = []
    for i, rec in enumerate(records, 1):
        encoded = tokenizer.apply_chat_template(
            rec['prompt'], tokenize=True, add_generation_prompt=True,
            enable_thinking=False, return_tensors='pt',
        )
        prompt_ids, prompt_attention = extract_generation_inputs(encoded)
        prompt_ids = prompt_ids.to('cuda')
        attention_mask = (prompt_attention.to('cuda') if prompt_attention is not None
                          else torch.ones_like(prompt_ids))
        if prompt_ids.ndim != 2 or prompt_ids.shape[0] != 1 or attention_mask.shape != prompt_ids.shape:
            raise ValueError('Unexpected Qwen3 generation tensor shape or mask.')
        expected_action = json.loads(rec['completion'][0]['content'])['action']
        item = {'demo_id': rec['demo_id'], 'expected_action': expected_action,
                'origin': 'FICTIONAL_ORIGINAL_DEMO'}
        for condition in ('base', 'lora'):
            # One PeftModel object, with adapter temporarily disabled for BASE.
            context = model.disable_adapter() if condition == 'base' else nullcontext()
            start = time.monotonic()
            with context, torch.inference_mode():
                generated = model.generate(
                    input_ids=prompt_ids, attention_mask=attention_mask,
                    do_sample=False, max_new_tokens=192,
                    pad_token_id=tokenizer.pad_token_id, eos_token_id=end_id,
                )
            out = tokenizer.decode(generated[0, prompt_ids.shape[-1]:], skip_special_tokens=True).strip()
            try:
                obj = json.loads(out)
                error = None
            except (TypeError, json.JSONDecodeError) as exc:
                obj, error = None, str(exc)
            allowed = {'ANSWER', 'ASK', 'ESCALATE', 'EXPLAIN_UNSUPPORTED'}
            action = obj.get('action') if isinstance(obj, dict) else None
            schema_ok = bool(isinstance(obj, dict) and set(obj) == {
                'action','customer_message','cited_evidence_ids','missing_fields'
            } and action in allowed and isinstance(obj['customer_message'], str)
                             and isinstance(obj['cited_evidence_ids'], list)
                             and isinstance(obj['missing_fields'], list))
            item[condition] = {
                'raw_output': out, 'json_parse_error': error, 'schema_valid': schema_ok,
                'action': action, 'raw_action_match': action == expected_action,
                'seconds_generate': round(time.monotonic()-start,3),
                'output_tokens': int(generated.shape[-1]-prompt_ids.shape[-1]),
            }
        results.append(item)
        print(f"[S10] toy probe {i}/8 | {rec['demo_id']} | base={item['base']['action']} | lora={item['lora']['action']}",flush=True)
    PROBE_OUT.parent.mkdir(parents=True, exist_ok=True)
    PROBE_OUT.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in results),encoding='utf-8')
    summary = {
        'status': 'S10_TOY_PIPELINE_ONLY_NOT_WATERBRIDGE_EVALUATION',
        'model': cfg['base_model'], 'revision': cfg['model_revision'],
        'toy_probes': len(results), 'train_sha256': train_module.digest(demo.TRAIN),
        'probe_sha256': train_module.digest(demo.PROBES),
        'base_json_valid': sum(r['base']['json_parse_error'] is None for r in results),
        'lora_json_valid': sum(r['lora']['json_parse_error'] is None for r in results),
        'base_action_matches': sum(r['base']['raw_action_match'] for r in results),
        'lora_action_matches': sum(r['lora']['raw_action_match'] for r in results),
        'base_schema_valid': sum(r['base']['schema_valid'] for r in results),
        'lora_schema_valid': sum(r['lora']['schema_valid'] for r in results),
        'notes': ('The 8 fictional toy probes are a plumbing check. They are too small, '
                  'not real WaterBridge Dev/Holdout, and cannot establish a causal SFT benefit.'),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    print('[S10] ADAPTER RELOAD+COMPARE PASS | predictions:', PROBE_OUT,flush=True)
    print('[S10] TOY SUMMARY:', SUMMARY,flush=True)
    print('[S10] Before stopping/deleting GPU pod, copy the whole pilot folder (adapter+reports) to local persistent storage.',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--run', action='store_true')
    parser.add_argument('--ack-cost', action='store_true')
    ns = parser.parse_args()
    cfg, records = validate_local()
    if ns.run:
        if not ns.ack_cost:
            parser.error('GPU comparison requires --ack-cost')
        run(cfg, records)
