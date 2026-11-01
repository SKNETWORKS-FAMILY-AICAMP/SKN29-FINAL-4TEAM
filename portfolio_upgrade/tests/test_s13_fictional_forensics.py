"""Offline regression tests for S13: never download/load a model or touch GPU."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/s13_analyze_fictional_failures.py'
spec=importlib.util.spec_from_file_location('s13_script',SCRIPT)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class S13ForensicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=module.load_and_audit()

    def test_01_16_paired_distinct_rows(self):
        r=self.audit['details']
        self.assertEqual(len(r),16)
        self.assertEqual(len({x['case_id'] for x in r}),16)
        self.assertEqual({x['semantic_group_id'] for x in r}, {'F13','F14','F15','F16'})

    def test_02_official_metric_matches_s12(self):
        b=self.audit['metrics']['BASE']['official_s12']
        l=self.audit['metrics']['LORA']['official_s12']
        self.assertEqual(b['schema_valid'],11)
        self.assertEqual(l['schema_valid'],4)
        self.assertEqual(b['raw_action_match'],6)
        self.assertEqual(l['raw_action_match'],8)

    def test_03_shape_vs_business_rule_separate(self):
        b=self.audit['metrics']['BASE']['official_s12']
        l=self.audit['metrics']['LORA']['official_s12']
        self.assertEqual((b['fields_exact'],l['fields_exact']), (16,15))
        self.assertEqual((b['missing_contract_valid'],l['missing_contract_valid']), (11,4))

    def test_04_action_families(self):
        b=self.audit['metrics']['BASE']['by_gold_action']
        l=self.audit['metrics']['LORA']['by_gold_action']
        self.assertEqual([b[k]['raw_action_correct'] for k in ['ANSWER','ASK','ESCALATE','EXPLAIN_UNSUPPORTED']], [0,4,2,0])
        self.assertEqual([l[k]['raw_action_correct'] for k in ['ANSWER','ASK','ESCALATE','EXPLAIN_UNSUPPORTED']], [0,4,4,0])

    def test_05_ungated_citation_id_exactness(self):
        b=self.audit['metrics']['BASE']
        l=self.audit['metrics']['LORA']
        self.assertEqual((b['citation_exact_without_schema_gate'],l['citation_exact_without_schema_gate']),(8,11))
        self.assertEqual((b['official_s12']['citation_exact'],l['official_s12']['citation_exact']), (5,2))

    def test_06_question_echo_and_missing_fields(self):
        b=self.audit['metrics']['BASE']
        l=self.audit['metrics']['LORA']
        self.assertEqual((b['copied_input_question'],l['copied_input_question']),(16,8))
        self.assertEqual((b['nonask_nonempty_missing'],l['nonask_nonempty_missing']),(5,7))
        self.assertEqual((b['ask_empty_missing'],l['ask_empty_missing']),(0,4))
        self.assertEqual((b['markdown_fence_parse_failures'],l['markdown_fence_parse_failures']),(0,1))

    def test_07_invalid_json_not_dropped(self):
        rows=self.audit['details']
        l=[r['lora'] for r in rows]
        self.assertEqual(sum(x['json_object'] for x in l),15)
        self.assertEqual(sum(x['parse_fail_markdown_code_fence'] for x in l),1)
        self.assertEqual(sum(x['raw_action_match'] for x in l),8)

    def test_08_invalid_citation_and_missing_contract(self):
        target={'action':'ESCALATE','customer_message':'x', 'cited_evidence_ids':['A'], 'missing_fields':[]}
        e=module.evaluate_one('{"action":"ESCALATE","customer_message":"x","cited_evidence_ids":["UNKNOWN"],"missing_fields":[]}',
                              'original',{'A'},target)
        self.assertFalse(e['schema_valid'])
        self.assertFalse(e['citation_grounded'])
        e2=module.evaluate_one('{"action":"ESCALATE","customer_message":"x","cited_evidence_ids":["A"],"missing_fields":["foo"]}',
                               'original',{'A'},target)
        self.assertFalse(e2['schema_valid'])
        self.assertTrue(e2['citation_grounded'])
        self.assertFalse(e2['missing_contract_valid'])

    def test_09_write_no_override(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'audit'
            module.write_new(out,self.audit)
            self.assertTrue((out/'s13_audit.json').is_file())
            self.assertTrue((out/'s13_case_breakdown.csv').is_file())
            with self.assertRaises(FileExistsError):
                module.write_new(out,self.audit)

    def test_10_hash_mutation_detected(self):
        with tempfile.TemporaryDirectory() as td:
            dst=Path(td)
            for n in module.REQUIRED:
                (dst/n).write_bytes((module.INPUT/n).read_bytes())
            original=(dst/'s12_dev_comparison.json').read_bytes()
            (dst/'s12_dev_comparison.json').write_bytes(original.replace(b'"schema_valid": 4',b'"schema_valid": 5',1))
            with self.assertRaises(ValueError):
                module.load_and_audit(dst)


    def test_11_manifest_detects_metric_neutral_mutation(self):
        # Never modify bundled frozen S12 source data, even temporarily.
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            copied=out/'source_results'
            copied.mkdir()
            for n in module.REQUIRED:
                (copied/n).write_bytes((module.INPUT/n).read_bytes())
            man=out/'source_sha256_manifest.json'
            man.write_bytes(module.MANIFEST.read_bytes())
            pred=copied/'base_predictions.jsonl'
            pred.write_bytes(pred.read_bytes()+b'\n')  # metric-neutral mutation in the *copy*
            with patch.object(module,'INPUT',copied),patch.object(module,'MANIFEST',man):
                with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                    module.load_and_audit(copied)

if __name__=='__main__':
    unittest.main()
