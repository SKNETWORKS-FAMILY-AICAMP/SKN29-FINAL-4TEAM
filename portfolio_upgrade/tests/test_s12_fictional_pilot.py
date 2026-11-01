"""Offline regression checks for the S12 pilot; intentionally do NOT run Qwen weights."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/s12_run_fictional_pilot.py'
spec = importlib.util.spec_from_file_location('s12_run_fictional_pilot', MODULE)
s12 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = s12
spec.loader.exec_module(s12)


class DummyTokenizer:
    def apply_chat_template(self, messages, **kw):
        if kw.get('tokenize') is not True or kw.get('enable_thinking') is not False:
            raise ValueError('Chat template not pinned to non-thinking')
        return [10, 11, 12]

    def encode(self, text, **kw):
        return [1, 2, 3, 4]


class S12PilotOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.train, cls.probe, cls.summary = s12.validate_local()
        cls.target_file = s12.paths(cls.cfg)['probe_target_file']
        cls.targets = s12.jsonl(cls.target_file)

    def _valid(self, action='ANSWER', ids=('SIM-EVD-F99-abc',), missing=()):
        return {'action':action,'customer_message':'안내합니다.',
                'cited_evidence_ids':list(ids),'missing_fields':list(missing)}

    def test_01_source_summary_hashes_verified(self):
        p=s12.paths(self.cfg)
        for tag in ('train_file','probe_input_file','probe_target_file'):
            self.assertEqual(s12.sha256(p[tag]),
                self.summary['output_sha256'][p[tag].name])

    def test_02_train_probe_group_disjoint(self):
        self.assertEqual(set(r['semantic_group_id'] for r in self.train),
                         {f'F{i:02d}' for i in range(1,13)})
        self.assertEqual(set(r['semantic_group_id'] for r in self.probe),
                         {f'F{i:02d}' for i in range(13,17)})

    def test_03_train_has_forty_eight_probe_sixteen(self):
        self.assertEqual((len(self.train),len(self.probe)),(48,16))

    def test_04_no_answer_or_target_in_probe(self):
        for r in self.probe:
            self.assertEqual([m['role'] for m in r['messages']],['system','user'])
            self.assertFalse('target' in r)
            u=json.loads(r['messages'][1]['content'])
            self.assertNotIn('action',u)
            self.assertNotIn('expected_action',u)

    def test_05_all_train_target_schema_grounded(self):
        for r in self.train:
            u=json.loads(r['messages'][1]['content'])
            gold=json.loads(r['messages'][2]['content'])
            ids={x['id'] for x in u['provided_evidence']}
            self.assertTrue(s12.validate_schema(gold,ids)['schema_valid'],r['case_id'])

    def test_06_schema_rejects_missing_field(self):
        t=self._valid();t.pop('missing_fields')
        self.assertFalse(s12.validate_schema(t,{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_07_schema_rejects_extra_field(self):
        t=self._valid();t['comments']='model note'
        self.assertFalse(s12.validate_schema(t,{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_08_schema_rejects_wrong_field_type(self):
        t=self._valid();t['cited_evidence_ids']='SIM-EVD-F99-abc'
        self.assertFalse(s12.validate_schema(t,{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_09_schema_rejects_unsupported_action(self):
        self.assertFalse(s12.validate_schema(self._valid('CHOOSE'),{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_09b_schema_rejects_nonstring_action_without_crashing(self):
        t=self._valid();t['action']=['ANSWER']
        self.assertFalse(s12.validate_schema(t,{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_10_schema_rejects_hallucinated_citation(self):
        self.assertFalse(s12.validate_schema(self._valid(ids=['SIM-EVD-F99-nope']),{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_11_schema_rejects_missing_citation(self):
        self.assertFalse(s12.validate_schema(self._valid(ids=[]),{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_12_schema_rejects_duplicate_citation(self):
        self.assertFalse(s12.validate_schema(self._valid(ids=['SIM-EVD-F99-abc']*2),{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_13_schema_rejects_ask_without_missing_field(self):
        self.assertFalse(s12.validate_schema(self._valid('ASK'),{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_14_schema_rejects_answer_with_missing_field(self):
        self.assertFalse(s12.validate_schema(self._valid('ANSWER',missing=['mode']),{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_15_schema_accepts_ask_with_missing_field(self):
        self.assertTrue(s12.validate_schema(self._valid('ASK',missing=['mode']),{'SIM-EVD-F99-abc'})['schema_valid'])

    def test_16_tokenize_train_masks_entire_prompt(self):
        x=s12.tokenize_train(DummyTokenizer(), self.train[:1],20)[0]
        self.assertEqual(x['input_ids'],[10,11,12,1,2,3,4])
        self.assertEqual(x['labels'],[-100,-100,-100,1,2,3,4])
        self.assertEqual(x['attention_mask'],[1]*7)

    def test_17_token_length_guard_rejects_truncation(self):
        with self.assertRaisesRegex(ValueError,'token length'):
            s12.tokenize_train(DummyTokenizer(),self.train[:1],6)

    def test_18_token_ids_support_transformers_batchencoding(self):
        class BatchTokenizer(DummyTokenizer):
            def apply_chat_template(self,messages,**kw):return {'input_ids':[[10,11,12]]}
        self.assertEqual(s12.token_ids(BatchTokenizer(),self.train[0]['messages'][:2]),[10,11,12])

    def test_19_actual_collator_preserves_loss_mask_padding(self):
        try:
            import torch
        except ImportError:
            self.skipTest('torch not installed for CPU collator test')
        xs=[{'input_ids':[10,11,12,13], 'labels':[-100,-100,12,13],'attention_mask':[1]*4},
            {'input_ids':[20,21],'labels':[-100,21],'attention_mask':[1]*2}]
        b=s12.collate_completion_only(xs,0)
        self.assertEqual(b['labels'].tolist(),[[-100,-100,12,13],[-100,21,-100,-100]])
        self.assertEqual(b['attention_mask'].tolist(),[[1]*4,[1,1,0,0]])

    def test_20_score_correct_predictions(self):
        p=self.probe[:2]; t=self.targets[:2]
        records=[{'case_id':r['case_id'],
                  'raw_output':json.dumps(t[i]['target_FOR_EVALUATION_ONLY'],ensure_ascii=False)}
                 for i,r in enumerate(p)]
        metrics=s12.evaluate_predictions(records,p,t)['metrics']
        self.assertEqual(metrics['schema_valid'],2)
        self.assertEqual(metrics['raw_action_match'],2)
        self.assertEqual(metrics['structured_target_match'],2)

    def test_21_score_invalid_json_is_zero_not_dropped(self):
        p=self.probe[:2];t=self.targets[:2]
        records=[{'case_id':p[0]['case_id'],'raw_output':'```json {fail} ```'},
                 {'case_id':p[1]['case_id'], 'raw_output':json.dumps(t[1]['target_FOR_EVALUATION_ONLY'],ensure_ascii=False)}]
        summary=s12.evaluate_predictions(records,p,t)
        self.assertEqual(summary['n'],2)
        self.assertEqual(summary['metrics']['structured_target_match'],1)
        self.assertIsNotNone(summary['cases'][0]['json_parse_error'])

    def test_22_unstructured_wrong_citation_not_counted_correct(self):
        p=self.probe[:1];t=self.targets[:1]
        d=dict(t[0]['target_FOR_EVALUATION_ONLY']);d['cited_evidence_ids']=['fake']
        item=s12.evaluate_predictions([{'case_id':p[0]['case_id'],'raw_output':json.dumps(d)}],p,t)
        self.assertEqual(item['metrics']['raw_action_match'],1)
        self.assertEqual(item['metrics']['strict_action_match'],0)
        self.assertEqual(item['metrics']['structured_target_match'],0)

    def test_23_wrong_action_with_valid_schema_separate(self):
        p=self.probe[:1];t=self.targets[:1]
        d=dict(t[0]['target_FOR_EVALUATION_ONLY']);d['action']='EXPLAIN_UNSUPPORTED'
        item=s12.evaluate_predictions([{'case_id':p[0]['case_id'],'raw_output':json.dumps(d)}],p,t)
        self.assertEqual(item['metrics']['schema_valid'],1)
        self.assertEqual(item['metrics']['raw_action_match'],0)

    def test_24_case_mismatch_rejected_before_score(self):
        with self.assertRaisesRegex(ValueError,'Crossed/missing'):
            s12.evaluate_predictions([{'case_id':'fake','raw_output':'{}'}],self.probe[:1],self.targets[:1])

    def test_25_batchencoding_tensor_extraction(self):
        class Mapping(dict):pass
        ids,mask=s12.extract_generation_ids(Mapping(input_ids='a',attention_mask='b'))
        self.assertEqual((ids,mask),('a','b'))
        self.assertEqual(s12.extract_generation_ids('tensor'),('tensor',None))

    def test_26_atomic_json_rejects_existing_no_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'p.json'
            s12.to_json(p,{'one':1})
            with self.assertRaises(FileExistsError):s12.to_json(p,{'two':2})
            self.assertEqual(json.loads(p.read_text()),{'one':1})

    def test_27_atomic_jsonl_rejects_existing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'p.jsonl'
            s12.to_jsonl(p,[{'one':1}])
            with self.assertRaises(FileExistsError):s12.to_jsonl(p,[{'two':2}])
            self.assertEqual(s12.jsonl(p),[{'one':1}])

    def test_28_hash_mismatch_stops_before_gpu(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            shutil.copytree(s12.ROOT/'portfolio_upgrade/data/s11_grounded/v2',
                            root/'portfolio_upgrade/data/s11_grounded/v2')
            (root/'portfolio_upgrade/configs').mkdir(parents=True)
            cfgpath=root/'portfolio_upgrade/configs/s12_fictional_pilot.json'
            shutil.copyfile(s12.CONFIG,cfgpath)
            tr=root/'portfolio_upgrade/data/s11_grounded/v2/s11_fictional_train_v2.jsonl'
            tr.write_bytes(tr.read_bytes() + b'\n')
            with patch.object(s12,'ROOT',root),patch.object(s12,'CONFIG',cfgpath):
                with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                    s12.validate_local()

    def test_29_config_real_manual_claim_stops(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=json.loads(s12.CONFIG.read_text())
            cfg['manual_data_training_authorized']=True
            p=Path(td)/'p.json';p.write_text(json.dumps(cfg))
            with patch.object(s12,'CONFIG',p):
                with self.assertRaisesRegex(ValueError,'safety boundary'):
                    s12.validate_local()

    def test_30_all_training_messages_are_fictional_and_unique(self):
        self.assertEqual(len({r['case_id'] for r in self.train}),48)
        for r in self.train:
            self.assertTrue(json.loads(r['messages'][1]['content'])['product_code'].startswith('SIM-'))
            self.assertFalse(r['training_ready_for_waterbridge'])


if __name__=='__main__':unittest.main()
