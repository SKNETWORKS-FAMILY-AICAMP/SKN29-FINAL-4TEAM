"""S10: LoRA smoke-test on entirely fictional data, using Qwen3 and TRL.

Free local preflight (no extra libs required):
    python portfolio_upgrade/scripts/s10_train_lora.py --check
GPU-only, billable when cloud instance is running:
    python portfolio_upgrade/scripts/s10_train_lora.py --run --ack-cost

No WaterBridge data path is read. Does NOT push to any remote model hub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import time

import s10_prepare_demo as demo

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'portfolio_upgrade/configs/s10_smoke_config.json'
OUT = ROOT / 'portfolio_upgrade/experiments/s10_sft/pilot'
ADAPTER = OUT / 'adapter'
REPORT = OUT / 'training_report.json'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def validate_local() -> tuple[dict, list[dict]]:
    demo.run(write=False)
    if not CONFIG.is_file() or not demo.TRAIN.is_file() or not demo.MANIFEST.is_file():
        raise FileNotFoundError('Run s10_prepare_demo.py --write to create toy files.')
    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    manifest = json.loads(demo.MANIFEST.read_text(encoding='utf-8'))
    if cfg['status'] != 'DEMO_ONLY_NOT_WATERBRIDGE_TRAINING' or cfg['manual_derived_sft_data_permitted']:
        raise ValueError('Safety contract changed: WaterBridge training must remain disabled.')
    if cfg['training_data'] != 'portfolio_upgrade/data/s10_demo/s10_toy_train.jsonl':
        raise ValueError('Only the pinned fictional toy training file is accepted.')
    if cfg['base_model'] != 'Qwen/Qwen3-1.7B' or cfg['model_revision'] != '70d244cc86ccca08cf5af4e1e306ecf908b1ad5e':
        raise ValueError('Qwen3 model/revision unexpectedly changed.')
    if not cfg['runpod_cost_approval_required'] or not cfg['waterbridge_dev_holdout_excluded']:
        raise ValueError('Missing cost/data separation protections.')
    if cfg['max_steps'] > 10 or cfg['max_steps'] < 1 or cfg['max_length'] > 1024:
        raise ValueError('S10 smoke test training limits exceeded.')
    if manifest['train_sha256'] != digest(demo.TRAIN):
        raise ValueError('Toy train data hash mismatch.')
    rows = read_jsonl(demo.TRAIN)
    if len(rows) != 40 or len({r['demo_id'] for r in rows}) != 40:
        raise ValueError('Expected 40 unique toy training rows.')
    for row in rows:
        if row.get('split') != 'train' or row.get('origin') != 'FICTIONAL_ORIGINAL_DEMO':
            raise ValueError('Real manual/Dev/Holdout samples cannot enter S10.')
        if [m['role'] for m in row['prompt']] != ['system', 'user']:
            raise ValueError('Prompts must contain system and user, but no answer.')
        if len(row['completion']) != 1 or row['completion'][0]['role'] != 'assistant':
            raise ValueError('Expected assistant-only training target.')
        target = json.loads(row['completion'][0]['content'])
        if target['action'] not in demo.ACTIONS:
            raise ValueError('Unknown action in toy training targets.')
        data = json.loads(row['prompt'][1]['content'])
        if data['product_code'] not in ('SIM-P100','SIM-P200'):
            raise ValueError('Real product leaked into S10.')
        ids = {e['evidence_id'] for e in data['retrieved_evidence']}
        if not set(target['cited_evidence_ids']).issubset(ids):
            raise ValueError('Toy target cited an evidence ID not supplied in the prompt.')
    print(f"[S10] DATA CHECK PASS | 40 fictional train rows | sha={manifest['train_sha256'][:12]}...")
    print('[S10] NO model download, GPU, API, S07 training or real Dev/Holdout access.')
    return cfg, rows


def tokenize_examples(tokenizer, rows: list[dict], max_length: int) -> list[dict]:
    """Build input_ids and masks explicitly; -100 means no loss on prompt tokens."""
    packed = []
    for row in rows:
        prompt_output = tokenizer.apply_chat_template(
            row['prompt'], tokenize=True, add_generation_prompt=True, enable_thinking=False
        )
        # Transformers 4 may return list[int]; Transformers 5 returns BatchEncoding.
        # Always extract a flat list of token IDs before concatenating the target.
        prompt_ids = prompt_output['input_ids'] if hasattr(prompt_output, 'keys') else prompt_output
        if not isinstance(prompt_ids, list) or not all(isinstance(t, int) for t in prompt_ids):
            raise TypeError(f"Unexpected tokenizer output for {row['demo_id']}: expected a flat list of token IDs.")
        # Qwen3 chat turn ends with <|im_end|>; only the completion is supervised.
        completion = row['completion'][0]['content'] + '<|im_end|>'
        completion_ids = tokenizer.encode(completion, add_special_tokens=False)
        if not prompt_ids or not completion_ids:
            raise ValueError('Prompt/assistant target unexpectedly empty.')
        if len(prompt_ids) + len(completion_ids) > max_length:
            raise ValueError(f"Token length exceeded {max_length}: {row['demo_id']} "
                             f"({len(prompt_ids)}+{len(completion_ids)})")
        packed.append({
            'input_ids': prompt_ids + completion_ids,
            'attention_mask': [1] * (len(prompt_ids) + len(completion_ids)),
            'labels': [-100] * len(prompt_ids) + completion_ids,
        })
    return packed



def token_check(cfg: dict, rows: list[dict]) -> None:
    """No GPU; tokenizer download/cache use only. Catch length/mask errors early."""
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise RuntimeError('Install transformers for optional local --token-check first.') from exc
    print('[S10] Loading tokenizer only (CPU / may download weights-free tokenizer files).', flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        cfg['base_model'], revision=cfg['model_revision'], trust_remote_code=False
    )
    sequences = tokenize_examples(tokenizer, rows, cfg['max_length'])
    lengths = [len(r['input_ids']) for r in sequences]
    targets = [sum(x != -100 for x in r['labels']) for r in sequences]
    print('[S10] TOKEN CHECK PASS | max length:', max(lengths),
          '| assistant tokens min:', min(targets),
          '| prompt masked:', all(-100 in r['labels'] for r in sequences),flush=True)
    print('[S10] No GPU training or model weights loaded.', flush=True)


def train(cfg: dict, rows: list[dict]) -> None:
    if ADAPTER.exists() or REPORT.exists():
        raise FileExistsError('Existing S10 result detected. Do not overwrite / rebill: ' + str(OUT))
    try:
        import torch
        import transformers
        import trl
        import peft
        import datasets
        import accelerate
        from datasets import Dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTTrainer, SFTConfig
        from peft import LoraConfig
    except ImportError as exc:
        raise RuntimeError('Install compatible transformers/trl/peft/datasets/accelerate in the CUDA venv first.') from exc
    if not torch.cuda.is_available():
        raise RuntimeError('S10 --run needs CUDA. Stop; do not attempt expensive CPU model training.')
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    print('[S10] GPU:', torch.cuda.get_device_name(0), '| dtype:', dtype, flush=True)
    print('[S10] Pinned model revision:', cfg['model_revision'], flush=True)
    print('[S10] Download/load may have network traffic; no customer files will be used.', flush=True)
    torch.manual_seed(cfg['seed'])
    started = time.monotonic()
    tokenizer = AutoTokenizer.from_pretrained(
        cfg['base_model'], revision=cfg['model_revision'], trust_remote_code=False
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenized = tokenize_examples(tokenizer, rows, int(cfg['max_length']))
    lengths = [len(r['input_ids']) for r in tokenized]
    target_tokens = [sum(x != -100 for x in r['labels']) for r in tokenized]
    if min(target_tokens) <= 0:
        raise ValueError('No supervised assistant token in S10 train set.')
    print(f'[S10] Train tokens: min/median/max={min(lengths)}/{sorted(lengths)[len(lengths)//2]}/{max(lengths)}', flush=True)
    print(f'[S10] Completion-only label tokens: min={min(target_tokens)}, max={max(target_tokens)}', flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        cfg['base_model'], revision=cfg['model_revision'], dtype=dtype, trust_remote_code=False
    )
    model.config.use_cache = False  # Trainer + gradient computations
    train_set = Dataset.from_list(tokenized)
    lora = LoraConfig(
        task_type='CAUSAL_LM', r=cfg['lora_r'], lora_alpha=cfg['lora_alpha'],
        lora_dropout=cfg['lora_dropout'], target_modules=cfg['lora_target_modules'], bias='none'
    )
    args = SFTConfig(
        output_dir=str(OUT), max_steps=cfg['max_steps'], max_length=cfg['max_length'],
        per_device_train_batch_size=cfg['per_device_train_batch_size'],
        gradient_accumulation_steps=cfg['gradient_accumulation_steps'],
        learning_rate=cfg['learning_rate'],
        bf16=(dtype == torch.bfloat16), fp16=(dtype == torch.float16),
        packing=False, logging_steps=1, save_strategy='no', report_to='none',
        gradient_checkpointing=False, optim='adamw_torch',
        seed=cfg['seed'], data_seed=cfg['seed'],
        remove_unused_columns=False, disable_tqdm=False,
    )
    trainer = SFTTrainer(
        model=model, args=args, train_dataset=train_set,
        processing_class=tokenizer, peft_config=lora,
    )
    # TRL's pre-tokenized dataset accepts labels. Guard against accidental loss
    # over user/system tokens due to a version-specific collator behavior.
    batch = next(iter(trainer.get_train_dataloader()))
    if 'labels' not in batch or int((batch['labels'] == -100).sum().item()) == 0:
        raise RuntimeError('Completion-only loss mask was lost; abort before learning.')
    if int((batch['labels'] != -100).sum().item()) == 0:
        raise RuntimeError('All labels masked; no learning would happen.')
    n_trainable = sum(p.numel() for p in trainer.model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in trainer.model.parameters())
    if not 0 < n_trainable < n_total:
        raise RuntimeError('LoRA adapters were not the only trainable params.')
    print(f'[S10] trainable/total={n_trainable:,}/{n_total:,} ({n_trainable/n_total:.3%})', flush=True)
    torch.cuda.reset_peak_memory_stats()
    result = trainer.train()
    if not math.isfinite(result.training_loss):
        raise RuntimeError('Non-finite training loss! Adapter should not be used.')
    ADAPTER.mkdir(parents=True, exist_ok=False)
    trainer.model.save_pretrained(ADAPTER, safe_serialization=True)
    tokenizer.save_pretrained(ADAPTER)
    peak_gib = round(torch.cuda.max_memory_allocated() / (1024 ** 3), 3)
    report = {
        'status': 'TOY_LORA_TRAINED_NOT_WATERBRIDGE_EVALUATED',
        'model': cfg['base_model'], 'revision': cfg['model_revision'],
        'train_file': str(demo.TRAIN.relative_to(ROOT)),
        'train_sha256': digest(demo.TRAIN), 'training_examples': len(rows),
        'full_tokens_min_median_max': [min(lengths), sorted(lengths)[len(lengths)//2], max(lengths)],
        'target_tokens_min_max': [min(target_tokens), max(target_tokens)],
        'loss_mask_verified': True, 'trainable_params': n_trainable,
        'total_params': n_total, 'trainable_fraction': n_trainable / n_total,
        'train_loss': result.training_loss, 'max_steps': cfg['max_steps'],
        'seconds_train_and_load': round(time.monotonic()-started, 3),
        'peak_gpu_memory_gib_allocated': peak_gib,
        'gpu': torch.cuda.get_device_name(0), 'dtype': str(dtype),
        'versions': {'python': platform.python_version(), 'torch': torch.__version__,
                     'transformers': transformers.__version__, 'trl': trl.__version__,
                     'peft': peft.__version__, 'datasets': datasets.__version__,
                     'accelerate': accelerate.__version__},
        'logs': trainer.state.log_history,
        'adapter_dir': str(ADAPTER.relative_to(ROOT)),
        'customer_service_quality_conclusion': 'NOT_MEASURED',
    }
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
    print('[S10] TRAIN PASS | adapter:', ADAPTER, flush=True)
    print('[S10] REPORT:', REPORT, '| peak allocated GPU GiB:', peak_gib, flush=True)
    print('[S10] IMPORTANT: Before stopping ephemeral GPU, run s10_probe_adapter.py --run and copy artifacts off the pod.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--token-check', action='store_true')
    group.add_argument('--run', action='store_true')
    parser.add_argument('--ack-cost', action='store_true', help='Explicitly acknowledge cloud GPU costs')
    ns = parser.parse_args()
    cfg, rows = validate_local()
    if ns.token_check:
        token_check(cfg, rows)
    if ns.run:
        if not ns.ack_cost:
            parser.error('--run needs --ack-cost (you control cloud GPU expenses).')
        train(cfg, rows)
