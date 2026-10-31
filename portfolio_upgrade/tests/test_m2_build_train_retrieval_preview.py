"""No network/GPU; run: python -m unittest portfolio_upgrade/tests/test_m2_build_train_retrieval_preview.py -v"""
from __future__ import annotations
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPT_DIR))
import m2_build_train_retrieval_preview as m2


class TrainingPreviewTests(unittest.TestCase):
    def setUp(self):
        self.policy = {"system_prompt": "응대 정책", "model_revision": "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"}
        self.row = {
            "example_id": "S07-TEST-BASE",
            "input": {"product_code": "ABC1", "customer_message": "냉수 잠금 표시가 깜빡입니다.",
                      "known_conditions": {"previous_answers": [], "selected_symptoms": ["냉수 잠금"]}},
            "provenance": {"split": "train", "source_scenario_id": "SYN-TEST", "semantic_group_id": "group-A",
                           "gold_evidence_ids": ["GOLD-1"]},
            "target": {"action": "ANSWER", "assistant_message": "잠금 상태를 확인해주세요.", "missing_fields": []},
        }
        self.ranked = [{"model_code": "ABC1", "evidence_group_id": "GOLD-1", "page_refs": [10], "text": "잠금 해제 안내"},
                       {"model_code": "ABC1", "evidence_group_id": "OTHER-1", "page_refs": [20], "text": "관련 없는 근거"}]

    def test_gold_not_leaked_into_model_input_or_system_prompt(self):
        rec=m2.pack_record(self.row,self.ranked,self.policy)
        self.assertEqual(rec['status'],'PREVIEW_NOT_TRAIN_READY')
        self.assertFalse(rec['audit_only']['training_ready'])
        self.assertEqual(rec['messages'][2]['role'],'assistant')
        self.assertEqual(json.loads(rec['messages'][2]['content'])['cited_evidence_ids'],['GOLD-1'])
        payload=json.loads(rec['messages'][1]['content'])
        self.assertEqual(sorted(payload.keys()), sorted(['customer_message','previous_answers','product_code','retrieved_evidence','selected_symptoms']))
        self.assertNotIn('gold_evidence_ids',payload)
        self.assertNotIn('source_scenario_id',payload)
        self.assertNotIn('action',payload)

    def test_missing_gold_does_not_make_training_ready(self):
        rec=m2.pack_record(self.row,self.ranked[1:],self.policy)
        self.assertFalse(rec['audit_only']['gold_in_retrieved'])
        self.assertIn('GOLD_NOT_RETRIEVED',rec['audit_only']['requires_followup'])
        self.assertEqual(json.loads(rec['messages'][2]['content'])['cited_evidence_ids'],[])
        self.assertFalse(rec['audit_only']['data_use_authorized_for_sft'])

    def test_duplicate_child_group_collapses_without_losing_text(self):
        a=self.ranked[0]
        r=m2.pack_record(self.row,[a,{**a,'text':'2번째 단락','page_refs':[11]}],self.policy)
        evidence=json.loads(r['messages'][1]['content'])['retrieved_evidence']
        self.assertEqual(len(evidence),1)
        self.assertEqual(evidence[0]['page_refs'],[10,11])
        self.assertIn('2번째 단락',evidence[0]['text'])

    def test_dev_row_rejected(self):
        row=copy.deepcopy(self.row)
        row['provenance']['split']='dev'
        with self.assertRaisesRegex(ValueError,'Dev/Holdout'):
            m2.pack_record(row,self.ranked,self.policy)

    def test_cross_product_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError,'제품'):
            m2.pack_record(self.row,[{**self.ranked[0],'model_code':'XYZ'}],self.policy)

    def test_original_contract_prompt_digest_is_fixed(self):
        path=Path(__file__).resolve().parents[1]/'configs'/'m2_training_input_contract.json'
        contract=json.loads(path.read_text(encoding='utf-8'))
        sha=hashlib.sha256(contract['system_prompt'].encode()).hexdigest()
        self.assertEqual(sha,contract['system_prompt_sha256'])
        self.assertEqual(sha,'48231b33236b0d5791ab5de0525bb0fc5801442abaa24c547d6e46f9fa7ed1c5')
        self.assertFalse(contract['data_use_authorized_for_sft'])


if __name__=='__main__':unittest.main()
