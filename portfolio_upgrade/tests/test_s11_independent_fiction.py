"""S11 fictional candidate integrity; no model/GPU/network required."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/s11_build_independent_dataset.py"
spec = importlib.util.spec_from_file_location("s11_independent_fiction", SCRIPT)
s11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s11)


class S11IndependentDataTests(unittest.TestCase):
    def setUp(self):
        self.train, self.probes, self.targets, self.manifest = s11.make_all()

    def test_balanced_48_train_16_probe(self):
        summary = s11.validate_all(self.train, self.probes, self.targets, self.manifest)
        self.assertEqual((summary["train_rows"], summary["probe_rows"]), (48,16))
        self.assertEqual(summary["train_action_counts"], {a:12 for a in s11.ACTIONS})
        self.assertEqual(summary["probe_action_counts"], {a:4 for a in s11.ACTIONS})

    def test_family_level_split_not_only_exact_duplicate(self):
        t={x['semantic_group_id'] for x in self.train}
        p={x['semantic_group_id'] for x in self.probes}
        self.assertEqual(len(t),12)
        self.assertEqual(len(p),4)
        self.assertFalse(t & p)
        self.assertEqual(set(x['split'] for x in self.train), {'train'})
        self.assertEqual(set(x['split'] for x in self.probes), {'probe'})

    def test_probe_inputs_have_no_assistant_or_targets(self):
        for rec in self.probes:
            self.assertEqual([x['role'] for x in rec['messages']], ['system','user'])
            body=json.loads(rec['messages'][1]['content'])
            self.assertEqual(set(body),s11.PROMPT_ONLY_FIELDS)
            self.assertNotIn('expected_action', json.dumps(body))
            self.assertNotIn('cited_evidence_ids', json.dumps(body))
        self.assertEqual({x['case_id'] for x in self.probes}, {x['case_id'] for x in self.targets})

    def test_evidence_ids_do_not_expose_action_label(self):
        for row in self.train + self.probes:
            user=json.loads(row['messages'][1]['content'])
            for ev in user['provided_evidence']:
                self.assertRegex(ev['id'], r'^SIM-EVD-F\d\d-[a-f0-9]{12}$')
                self.assertNotRegex(ev['id'], r'-(A|Q|E|U)$')
        self.assertEqual(len({v['id'] for r in self.train+self.probes
            for v in json.loads(r['messages'][1]['content'])['provided_evidence']}),64)

    def test_all_targets_have_four_fields_correct_ids(self):
        s11.validate_all(self.train,self.probes,self.targets,self.manifest)
        for rec in self.train:
            target=json.loads(rec['messages'][2]['content'])
            evidence=json.loads(rec['messages'][1]['content'])['provided_evidence']
            self.assertEqual(set(target),s11.TARGET_KEYS)
            self.assertEqual(len(target['cited_evidence_ids']),1)
            self.assertIn(target['cited_evidence_ids'][0],{x['id'] for x in evidence})

    def test_all_questions_individually_authored_not_rephrasings(self):
        questions=[json.loads(x['messages'][1]['content'])['customer_message'] for x in self.train+self.probes]
        self.assertEqual(len(set(questions)),64)
        self.assertTrue(all(len(x)>15 for x in questions))

    def test_false_citation_rejected(self):
        train=deepcopy(self.train)
        data=json.loads(train[0]['messages'][2]['content'])
        data['cited_evidence_ids']=['SIM-EVD-UNKNOWN']
        train[0]['messages'][2]['content']=s11.json_dump(data)
        with self.assertRaises(AssertionError):
            s11.validate_all(train,self.probes,self.targets,self.manifest)

    def test_missing_fields_not_allowed_for_answer(self):
        train=deepcopy(self.train)
        target=json.loads(train[0]['messages'][2]['content'])
        target.pop('missing_fields')
        train[0]['messages'][2]['content']=s11.json_dump(target)
        with self.assertRaises(AssertionError):
            s11.validate_all(train,self.probes,self.targets,self.manifest)

    def test_ask_must_have_missing_field(self):
        train=deepcopy(self.train)
        ask=next(x for x in train if json.loads(x['messages'][2]['content'])['action']=='ASK')
        obj=json.loads(ask['messages'][2]['content']);obj['missing_fields']=[]
        ask['messages'][2]['content']=s11.json_dump(obj)
        with self.assertRaises(AssertionError):
            s11.validate_all(train,self.probes,self.targets,self.manifest)

    def test_real_waterbridge_products_rejected(self):
        train=deepcopy(self.train)
        user=json.loads(train[0]['messages'][1]['content']);user['product_code']='WPUIAC425SNW'
        train[0]['messages'][1]['content']=s11.json_dump(user)
        with self.assertRaises(AssertionError):
            s11.validate_all(train,self.probes,self.targets,self.manifest)

    def test_evaluation_family_leak_rejected(self):
        probes=deepcopy(self.probes)
        probes[0]['semantic_group_id']=self.train[0]['semantic_group_id']
        with self.assertRaises(AssertionError):
            s11.validate_all(self.train,probes,self.targets,self.manifest)

    def test_provenance_and_human_review_pending(self):
        for x in self.train+self.probes:
            self.assertFalse(x['training_ready_for_waterbridge'])
            self.assertEqual(x['review_status'],'MACHINE_CHECKED_HUMAN_REVIEW_PENDING')
            self.assertEqual(x['source_kind'],'ORIGINAL_FICTIONAL_POLICY')
            self.assertRegex(x['case_id'],r'^S11-F\d\d-[a-f0-9]{8}$')
        cards=s11.render_review_cards(self.train,self.probes,self.targets)
        self.assertEqual(cards.count('\n## S11-F'),64)

    def test_deterministic_files_and_sha_manifest(self):
        x, s = s11.build_files(); y,t=s11.build_files()
        self.assertEqual(x,y)
        for filename,digest in s['artifacts_sha256'].items():
            self.assertEqual(digest,s11.hashlib.sha256(x[filename].encode('utf8')).hexdigest())

    def test_write_existing_file_same_unchanged_and_conflict_stops(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sub'/'output.jsonl'
            self.assertEqual(s11.write_or_verify(p,'demo\n'),'WRITTEN')
            self.assertEqual(s11.write_or_verify(p,'demo\n'),'UNCHANGED')
            with self.assertRaises(FileExistsError):
                s11.write_or_verify(p,'other\n')
            self.assertEqual(p.read_text(),'demo\n')

    def test_tokenizer_flatten_4_and_5(self):
        self.assertEqual(s11._flat_token_ids([1,2,3]),[1,2,3])
        self.assertEqual(s11._flat_token_ids({'input_ids':[1,2,3]}),[1,2,3])
        with self.assertRaises(TypeError):s11._flat_token_ids({'input_ids':[[1,2,3]]})

    def test_optional_token_checker_mock_transformers5(self):
        class Tok:
            def apply_chat_template(self,msgs,**kwargs):
                return {'input_ids':list(range(100+len(msgs)))}
            def encode(self,text,**kwargs):return list(range(25))
        fake=types.SimpleNamespace(AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a,**kw:Tok()))
        with patch.dict('sys.modules',{'transformers':fake}):
            report=s11.run_token_check(self.train,self.probes,max_length=768)
        self.assertTrue(report['masked_prompt'])
        self.assertEqual(report['train_max'],127)
        self.assertEqual(report['probe_max'],102)


if __name__ == '__main__':
    unittest.main()
