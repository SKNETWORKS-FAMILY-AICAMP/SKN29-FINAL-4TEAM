"""CPU regression tests for S13b; never downloads a model or touches GPU."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import s12_run_fictional_pilot as s12
import s13b_strong_prompt_ablation as s13b


class StrongPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.train, cls.probe, cls.summary = s12.validate_local()
        cls.prompt = s13b.read_prompt()

    def test_01_preflight_source_sha_and_group_split(self):
        cfg, probe, prompt = s13b.preflight()
        self.assertEqual(len(probe),16)
        self.assertEqual(cfg['model_revision'], s12.EXPECTED_REV)
        self.assertEqual(prompt,self.prompt)

    def test_02_strong_prompt_has_contract_and_no_dev_gold_leak(self):
        self.assertIn('customer_message',self.prompt)
        self.assertIn('missing_fields',self.prompt)
        self.assertIn('EXPLAIN_UNSUPPORTED',self.prompt)
        for s in ['S11-F13','SIM-B13','SIM-M14','SIM-Q15','SIM-V16','tracking_mode','mounting_type','slat_control_mode','microphone_source']:
            self.assertNotIn(s,self.prompt)

    def test_03_exactly_one_message_changes(self):
        copyprobe=s13b.adapt_inputs(self.probe,self.prompt)
        self.assertEqual(len(copyprobe),len(self.probe))
        for a,b in zip(self.probe,copyprobe):
            self.assertEqual(a['messages'][1],b['messages'][1])
            self.assertNotEqual(a['messages'][0],b['messages'][0])
            self.assertEqual(b['messages'][0]['content'],self.prompt)

    def test_04_no_mutation_of_frozen_probe(self):
        snap=copy.deepcopy(self.probe)
        s13b.adapt_inputs(self.probe,self.prompt)
        self.assertEqual(self.probe,snap)

    def test_05_new_probe_rejects_assistant_role(self):
        rows=copy.deepcopy(self.probe)
        rows[0]['messages'].append({'role':'assistant','content':'leak'})
        with self.assertRaises(ValueError): s13b.adapt_inputs(rows,self.prompt)

    def test_06_prompt_rejects_gold_specific_strings(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'strong.txt'
            p.write_text(self.prompt+'\ntracking_mode',encoding='utf8')
            with patch.object(s13b,'PROMPT_FILE',p):
                with self.assertRaises(ValueError): s13b.read_prompt()

    def test_07_eval_extra_cites_only_correct_id_and_detects_echo(self):
        probes=self.probe[:2]
        targets={x['case_id']:x for x in s12.jsonl(s12.paths(self.cfg)['probe_target_file'])}
        examples=[]
        for row in probes:
            gold=targets[row['case_id']]['target_FOR_EVALUATION_ONLY']
            user=json.loads(row['messages'][1]['content'])
            pred={**gold,'customer_message':user['customer_message']}
            examples.append({'case_id':row['case_id'],'raw_output':json.dumps(pred,ensure_ascii=False)})
        out=s13b.eval_extra(examples,probes,[targets[x['case_id']] for x in probes])
        self.assertEqual(out['question_echo_count'],2)
        self.assertEqual(out['citation_id_exact_not_schema_gated'],2)
        self.assertEqual(out['non_echo_message_count_NOT_SEMANTIC_SCORE'],0)

    def test_08_eval_extra_invalid_json_counts_as_zero(self):
        row=self.probe[0]
        gold=next(x for x in s12.jsonl(s12.paths(self.cfg)['probe_target_file']) if x['case_id']==row['case_id'])
        out=s13b.eval_extra([{'case_id':row['case_id'],'raw_output':'```json\n{}\n```'}],[row],[gold])
        self.assertEqual(out['citation_id_exact_not_schema_gated'],0)
        self.assertEqual(out['question_echo_count'],0)

    def test_09_build_review_rows_original_cases(self):
        gold=s12.jsonl(s12.paths(self.cfg)['probe_target_file'])
        sample=[{'case_id':r['case_id'],'raw_output':'{}'} for r in self.probe]
        data=s13b.build_review_rows({k:sample for k in ('BASE_P0','LORA_P0','BASE_P1','LORA_P1')},self.probe,gold)
        self.assertEqual(len(data),16)
        self.assertEqual(data[0]['human_safety_check'],'')
        self.assertTrue(all('gold_response_EVAL_ONLY' in r for r in data))

    def test_10_manifest_records_source_hashes_and_training_false(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            adapter=d/'adapter';adapter.mkdir()
            (adapter/'adapter_config.json').write_text('{}',encoding='utf8')
            sources={'adapter':adapter,'dummy':d/'x.json'}
            sources['dummy'].write_text('{}',encoding='utf8')
            meta=s13b.make_manifest(self.cfg,self.prompt,sources)
            self.assertFalse(meta['sft_training_performed_here'])
            self.assertTrue(meta['curated_simulated_evidence_not_real_rag'])
            self.assertEqual(meta['frozen_dev_sha256'],s12.sha256(s12.paths(self.cfg)['probe_input_file']))

    def test_11_frozen_comparison_guard_rejects_incorrect_s12_values(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            old=d/'s12_old';old.mkdir()
            (old/'adapter').mkdir()
            (old/'adapter'/'adapter_config.json').write_text(json.dumps({'base_model_name_or_path':self.cfg['base_model']}),encoding='utf8')
            (old/'train_report.json').write_text(json.dumps({'model':self.cfg['base_model'],'revision':self.cfg['model_revision'],'train_sha256':s12.sha256(s12.paths(self.cfg)['train_file']),'actual_global_step':12}),encoding='utf8')
            (old/'s12_dev_comparison.json').write_text(json.dumps({'status':'S12_FICTIONAL_DEV_ABLATION_NOT_WATERBRIDGE_ACCURACY','n_dev_probe':16,'baseline_metrics':{'json_object':16,'schema_valid':11,'raw_action_match':6,'citation_exact':5},'adapter_metrics':{'json_object':15,'schema_valid':4,'raw_action_match':8,'citation_exact':3}}),encoding='utf8')
            for name in [s13b.OLD_BASE,s13b.OLD_LORA]:
                (old/name).write_text(''.join(json.dumps({'case_id':r['case_id']})+'\n' for r in self.probe),encoding='utf8')
            original_paths=s12.paths(self.cfg)
            with patch.object(s12,'paths',return_value={**original_paths,'out':old}):
                with self.assertRaisesRegex(ValueError,'Frozen S12 result changed'):
                    s13b.check_s12_saved(self.cfg,self.probe)

    def test_12_checkpoint_resume_disallows_fresh_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            (d/'z.json').write_text('{}',encoding='utf8')
            with self.assertRaises(FileExistsError):
                s12.to_json(d/'z.json', {'different': True})



if __name__=='__main__': unittest.main()
