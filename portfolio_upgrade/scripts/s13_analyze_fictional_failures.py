"""S13 forensic read-only audit of S12 fictional Dev model outputs.

No GPU, model loading, prompts, training, dataset changes, web, or SFT.
Gold data is loaded for evaluation only, NEVER for generation or training.

Usage from repository root:
  python portfolio_upgrade/scripts/s13_analyze_fictional_failures.py --check
  python portfolio_upgrade/scripts/s13_analyze_fictional_failures.py --write

--write emits into a NEW separate verification folder, never overwrites
frozen source files or committed report. Existing verification outputs abort.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / 'portfolio_upgrade/experiments/s13_fictional_error_analysis'
INPUT = EXPERIMENT / 'source_results'
MANIFEST = EXPERIMENT / 'source_sha256_manifest.json'
REQUIRED = (
    'base_predictions.jsonl', 'lora_predictions.jsonl',
    's12_dev_comparison.json', 'train_report.json',
    's11_fictional_probe_inputs_v2.jsonl',
    's11_fictional_probe_targets_EVAL_ONLY_v2.jsonl',
)
ACTIONS = {'ANSWER', 'ASK', 'ESCALATE', 'EXPLAIN_UNSUPPORTED'}
FIELDS = {'action', 'customer_message', 'cited_evidence_ids', 'missing_fields'}
METRICS = (
    'json_object', 'fields_exact', 'field_types_valid', 'schema_valid',
    'citation_grounded', 'missing_contract_valid', 'raw_action_match',
    'strict_action_match', 'citation_exact', 'missing_fields_exact',
    'structured_target_match',
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_raw(raw: str):
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except (ValueError, TypeError):
        return None


def evaluate_one(raw: str, question: str, provided: set[str], gold: dict) -> dict:
    obj = parse_raw(raw)
    parsed = isinstance(obj, dict)
    keys = bool(parsed and set(obj) == FIELDS)
    types = bool(keys and isinstance(obj.get('action'), str) and obj['action'] in ACTIONS and
                 isinstance(obj.get('customer_message'), str) and obj['customer_message'].strip() and
                 isinstance(obj.get('cited_evidence_ids'), list) and
                 all(isinstance(x,str) for x in obj['cited_evidence_ids']) and
                 isinstance(obj.get('missing_fields'), list) and
                 all(isinstance(x,str) for x in obj['missing_fields']))
    cites = list(obj['cited_evidence_ids']) if types else []
    missing = list(obj['missing_fields']) if types else []
    grounded = bool(types and cites and len(cites) == len(set(cites)) and set(cites)<=provided)
    missing_contract = bool(types and len(missing)==len(set(missing)) and
                            (bool(missing) if obj['action']=='ASK' else not missing))
    schema = bool(types and grounded and missing_contract)
    action = obj.get('action') if parsed else None
    action_match = action == gold['action']
    exact_citations_unconditional = bool(types and set(cites)==set(gold['cited_evidence_ids']) and
                                     len(cites)==len(set(cites)))
    missing_exact_unconditional = bool(types and set(missing)==set(gold['missing_fields']) and
                                   len(missing)==len(set(missing)))
    return {
        'json_object': parsed,
        'fields_exact': keys,
        'field_types_valid': types,
        'schema_valid': schema,
        'citation_grounded': grounded,
        'missing_contract_valid': missing_contract,
        'raw_action_match': action_match,
        'strict_action_match': bool(schema and action_match),
        'citation_exact': bool(schema and exact_citations_unconditional),
        'missing_fields_exact': bool(schema and missing_exact_unconditional),
        'structured_target_match': bool(schema and action_match and exact_citations_unconditional and missing_exact_unconditional),
        # Diagnostic-only additions, NOT part of the official scoring contract.
        'citation_exact_without_schema_gate': exact_citations_unconditional,
        'missing_exact_without_schema_gate': missing_exact_unconditional,
        'copied_input_question': bool(types and obj['customer_message']==question),
        'output_text_equals_gold': bool(types and obj['customer_message']==gold['customer_message']),
        'predicted_action': action,
        'provided_citations': cites,
        'missing_field_values': missing,
        'excess_citations': sorted(set(cites) - set(gold['cited_evidence_ids'])),
        'missing_gold_citations': sorted(set(gold['cited_evidence_ids']) - set(cites)),
        'parse_fail_markdown_code_fence': bool(not parsed and raw.lstrip().startswith('```')),
        'nonask_nonempty_missing': bool(types and action != 'ASK' and missing),
        'ask_empty_missing': bool(types and action == 'ASK' and not missing),
    }


def load_and_audit(folder: Path = INPUT) -> dict:
    for n in REQUIRED:
        if not (folder/n).is_file():
            raise FileNotFoundError(f'Missing frozen S13 input: {folder/n}')
    if folder == INPUT:
        if not MANIFEST.is_file():
            raise FileNotFoundError(f'Missing S13 frozen manifest: {MANIFEST}')
        frozen = json.loads(MANIFEST.read_text(encoding='utf-8'))
        for name in REQUIRED:
            if frozen.get(name) != sha(folder/name):
                raise ValueError(f'Frozen S13 input SHA mismatch: {name}')
    records = {
        'BASE': read_jsonl(folder/'base_predictions.jsonl'),
        'LORA': read_jsonl(folder/'lora_predictions.jsonl'),
    }
    probes = read_jsonl(folder/'s11_fictional_probe_inputs_v2.jsonl')
    targets = read_jsonl(folder/'s11_fictional_probe_targets_EVAL_ONLY_v2.jsonl')
    official=json.loads((folder/'s12_dev_comparison.json').read_text(encoding='utf-8'))
    train=json.loads((folder/'train_report.json').read_text(encoding='utf-8'))
    if len(probes)!=16 or len(targets)!=16 or any(len(v)!=16 for v in records.values()):
        raise ValueError('All frozen S12 Dev inputs, targets and predictions must be exactly 16.')
    if len({x['case_id'] for x in probes})!=16 or len({x['case_id'] for x in targets})!=16:
        raise ValueError('Duplicate DEV case IDs.')
    expected={p['case_id']:p['target_FOR_EVALUATION_ONLY'] for p in targets}
    if {x['case_id'] for x in probes} != set(expected):
        raise ValueError('Probe/target mismatch.')
    for key, pred in records.items():
        if len({x['case_id'] for x in pred})!=16 or {x['case_id'] for x in pred} != set(expected):
            raise ValueError(f'Prediction case IDs inconsistent: {key}')
        if any('assistant' in [m['role'] for m in p['messages']] for p in probes):
            raise ValueError('Probe leaked an assistant target.')
    if train['train_count'] != 48 or train['dev_count_not_trained'] != 16 or train['max_steps'] != 12:
        raise ValueError('Unexpected training report identity.')
    audit={'status':'S13_FICTIONAL_DEV_FORENSICS_OFFLINE_NOT_FINAL_OR_WATERBRIDGE',
           'source_sha256':{n:sha(folder/n) for n in REQUIRED},
           'metrics':{}, 'details':[], 'caveats':[
               'DEV 16 examples were AI-reviewed and are not blind final evaluation.',
               'All product rules and answers were fictitious; no real WaterBridge performance.',
               'No real retrieval (BGE-M3 or pgvector), no GPU, no inference, and no learning in this S13 audit.',
               'citation_exact_without_schema_gate is an additional ID-only diagnostic; semantic justification not established.',
               'customer_message_exact_target is a literal comparison only, not a semantic rating.',
           ]}
    metric_rows={}
    for key,items in records.items():
        predictions={x['case_id']:x for x in items}
        rows=[]
        for p in probes:
            cid=p['case_id']
            inp=json.loads(p['messages'][1]['content'])
            gold=expected[cid]
            if p.get('semantic_group_id') not in ('F13','F14','F15','F16'):
                raise ValueError('Unexpected DEV family: '+p['semantic_group_id'])
            if predictions[cid]['semantic_group_id']!=p['semantic_group_id']:
                raise ValueError('Prediction family mismatch: '+cid)
            provided={e['id'] for e in inp['provided_evidence']}
            if len(provided)!=2 or not set(gold['cited_evidence_ids']) <= provided:
                raise ValueError('Inconsistent curated evidence/gold: '+cid)
            r=evaluate_one(predictions[cid]['raw_output'],inp['customer_message'],provided,gold)
            r.update({'model':key,'case_id':cid,'semantic_group_id':p['semantic_group_id'],
                      'expected_action':gold['action'],'expected_citations':gold['cited_evidence_ids'],
                      'expected_missing_fields':gold['missing_fields'],
                      'input_question':inp['customer_message'],
                      'output_text': parse_raw(predictions[cid]['raw_output']).get('customer_message','') if parse_raw(predictions[cid]['raw_output']) else '',
                      'generation_tokens':predictions[cid]['generated_tokens']})
            rows.append(r)
        m={name:sum(bool(x[name]) for x in rows) for name in METRICS}
        if m != official[('baseline_metrics' if key=='BASE' else 'adapter_metrics')]:
            raise ValueError(f'S13 disagrees with S12 official {key} metrics: {m}')
        audit['metrics'][key]={
            'official_s12':m,
            'predicted_action_histogram':dict(Counter(str(x['predicted_action']) for x in rows)),
            'by_gold_action':{name:{'count':sum(x['expected_action']==name for x in rows),
                                     'raw_action_correct':sum(x['expected_action']==name and x['raw_action_match'] for x in rows),
                                     'schema_valid':sum(x['expected_action']==name and x['schema_valid'] for x in rows),
                                     'strict_action_correct':sum(x['expected_action']==name and x['strict_action_match'] for x in rows)}
                              for name in sorted(ACTIONS)},
            'citation_exact_without_schema_gate':sum(x['citation_exact_without_schema_gate'] for x in rows),
            'all_provided_citation_ids_valid':sum(x['citation_grounded'] for x in rows),
            'missing_fields_exact_without_schema_gate':sum(x['missing_exact_without_schema_gate'] for x in rows),
            'copied_input_question':sum(x['copied_input_question'] for x in rows),
            'output_text_equals_gold_literal':sum(x['output_text_equals_gold'] for x in rows),
            'nonask_nonempty_missing':sum(x['nonask_nonempty_missing'] for x in rows),
            'ask_empty_missing':sum(x['ask_empty_missing'] for x in rows),
            'markdown_fence_parse_failures':sum(x['parse_fail_markdown_code_fence'] for x in rows),
        }
        metric_rows[key]=rows
    if any(metric_rows['BASE'][i]['case_id']!=metric_rows['LORA'][i]['case_id'] for i in range(16)):
        raise ValueError('Paired ordering mismatch.')
    audit['details']=[{'case_id':x['case_id'],'semantic_group_id':x['semantic_group_id'],
                       'expected_action':x['expected_action'],
                       'base':x,'lora':metric_rows['LORA'][i]}
                      for i,x in enumerate(metric_rows['BASE'])]
    if official['adapter_minus_baseline'] != {k:audit['metrics']['LORA']['official_s12'][k] - audit['metrics']['BASE']['official_s12'][k] for k in METRICS}:
        raise ValueError('Official S12 difference mismatch')
    return audit


def flat_rows(audit: dict) -> list[dict]:
    cols=[]
    for row in audit['details']:
        b=row['base']; l=row['lora']
        cols.append({
            'case_id':row['case_id'],'group':row['semantic_group_id'],
            'gold_action':row['expected_action'],
            'base_action':b['predicted_action'] or '(UNPARSEABLE)',
            'lora_action':l['predicted_action'] or '(UNPARSEABLE)',
            'base_schema_valid':int(b['schema_valid']),
            'lora_schema_valid':int(l['schema_valid']),
            'base_citation_exact_ID_only':int(b['citation_exact_without_schema_gate']),
            'lora_citation_exact_ID_only':int(l['citation_exact_without_schema_gate']),
            'base_missing_contract_valid':int(b['missing_contract_valid']),
            'lora_missing_contract_valid':int(l['missing_contract_valid']),
            'base_question_echo':int(b['copied_input_question']),
            'lora_question_echo':int(l['copied_input_question']),
            'base_missing_fields':json.dumps(b['missing_field_values'],ensure_ascii=False),
            'lora_missing_fields':json.dumps(l['missing_field_values'],ensure_ascii=False),
            'gold_missing_fields':json.dumps(b['expected_missing_fields'],ensure_ascii=False),
            'lora_parse_fenced':int(l['parse_fail_markdown_code_fence']),
        })
    return cols


def write_new(base:Path,audit:dict)->None:
    if base.exists():
        raise FileExistsError('Refusing to replace an existing audit output: '+str(base))
    base.mkdir(parents=True,exist_ok=False)
    out=base/'s13_audit.json'
    out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    rows=flat_rows(audit)
    with (base/'s13_case_breakdown.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    opts=ap.add_mutually_exclusive_group(required=True)
    opts.add_argument('--check',action='store_true')
    opts.add_argument('--write',action='store_true')
    ap.add_argument('--out-dir',type=Path,default=EXPERIMENT/'recomputed')
    ns=ap.parse_args()
    audit=load_and_audit()
    bm=audit['metrics']['BASE']; lm=audit['metrics']['LORA']
    print('[S13] CHECK PASS | 16 paired DEV examples, S12 frozen metrics exactly reproduced')
    print('[S13] FORM vs CONTRACT | JSON objects: BASE={}/16 LORA={}/16; business-contract schema: BASE={}/16 LORA={}/16'.format(
           bm['official_s12']['json_object'],lm['official_s12']['json_object'],
           bm['official_s12']['schema_valid'],lm['official_s12']['schema_valid']))
    print('[S13] ACTION by Gold | '+', '.join(f'{a}: BASE {bm["by_gold_action"][a]["raw_action_correct"]}/4, LORA {lm["by_gold_action"][a]["raw_action_correct"]}/4' for a in ['ANSWER','ASK','ESCALATE','EXPLAIN_UNSUPPORTED']))
    print('[S13] CITATION ID EXACT (not gated on schema) | BASE={}/16, LORA={}/16'.format(
           bm['citation_exact_without_schema_gate'],lm['citation_exact_without_schema_gate']))
    print('[S13] QUESTION ECHO (parsed JSON) | BASE={}/16 LORA={}/16'.format(bm['copied_input_question'],lm['copied_input_question']))
    print('[S13] Non-ASK with nonempty missing_fields | BASE={} LORA={} | ASK with empty missing_fields: BASE={} LORA={}'.format(
           bm['nonask_nonempty_missing'],lm['nonask_nonempty_missing'],bm['ask_empty_missing'],lm['ask_empty_missing']))
    print('[S13] DEV-only, fictional, no GPU, no SFT / no real WaterBridge evaluation')
    if ns.write:
        write_new(ns.out_dir,audit)
        print('[S13] WRITE PASS | '+str(ns.out_dir))

if __name__=='__main__':
    main()
