"""S11 regression tests; no model/network/PDF/GPU required."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 's11_cold_lock_condition_gate.py'
spec=importlib.util.spec_from_file_location('s11_cold_gate',MODULE)
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

P='WPUIAC425SNW'
Q='냉수 버튼을 누르면 부저음과 잠금 표시가 깜빡입니다. 정수는 나옵니다.'
NEW=gate.LOCK_DETAIL_BY_PRODUCT[P]

class S11ColdGateTests(unittest.TestCase):
    def test_positive_uses_only_customer_text_and_product(self):
        self.assertEqual(gate.classify_lock_signal(Q,P),(True,'CLEAR_COLD_LOCK_INDICATOR'))

    def test_negative_already_unlocked(self):
        t='냉수 잠금은 해제했습니다. 2시간 기다려도 냉수가 미지근합니다.'
        self.assertEqual(gate.classify_lock_signal(t,P)[1],'ALREADY_UNLOCKED_OR_INDICATOR_ABSENT')

    def test_negative_missing_lock_indicator(self):
        t='냉수 버튼을 눌렀는데 잠금 표시는 없어요. 물이 덜 차갑습니다.'
        self.assertEqual(gate.classify_lock_signal(t,P)[1],'ALREADY_UNLOCKED_OR_INDICATOR_ABSENT')

    def test_negative_no_explicit_blink(self):
        t='냉수 버튼이 안 돼요. 잠금인지 모르겠어요.'
        self.assertEqual(gate.classify_lock_signal(t,P)[1],'NO_BLINKING_INDICATOR')

    def test_unresolved_unlock_not_false_marked_done(self):
        t='냉수 잠금 해제가 안 돼요. 냉수 버튼을 누르면 잠금 표시가 깜빡입니다.'
        self.assertTrue(gate.classify_lock_signal(t,P)[0])

    def test_safety_precedes_cold_lock(self):
        t='냉수 버튼을 누르면 잠금 표시가 깜빡이고 누수도 생겨요.'
        self.assertEqual(gate.classify_lock_signal(t,P)[1],'SAFETY_PRIORITY')

    def test_unrelated_ice_not_cold_unlock(self):
        t='얼음 버튼을 누르면 잠금 표시가 깜빡여요.'
        self.assertFalse(gate.classify_lock_signal(t,P)[0])

    def test_specific_child_only_and_no_refill(self):
        case={'product_code':P,'candidate_55_child_ids':[NEW, 'CHILD-A','CHILD-B','CHILD-C','CHILD-D']}
        kept,removed,reason=gate.filter_case(case,P,'잠금 표시는 없고 냉수만 미지근해요.')
        self.assertEqual(removed,[NEW]);self.assertEqual(kept,['CHILD-A','CHILD-B','CHILD-C','CHILD-D'])
        self.assertEqual(len(kept),4)
        self.assertEqual(case['candidate_55_child_ids'][0],NEW) # immutable original

    def test_cross_model_child_injection_rejected(self):
        other=gate.LOCK_DETAIL_BY_PRODUCT['WPUIAC606SNW']
        case={'product_code':P,'candidate_55_child_ids':[other,'CHILD-A','CHILD-B','CHILD-C','CHILD-D']}
        with self.assertRaisesRegex(ValueError,'다른 제품'):
            gate.filter_case(case,P,Q)

    def test_no_gold_in_router_and_audit_labels_only_downstream(self):
        case={'product_code':P,'candidate_55_child_ids':[NEW,'CHILD-A','CHILD-B','CHILD-C','CHILD-D'],
              'gold_evidence_ids':['OTHER'], 'source_scenario_id':'SCENARIO-WRONG'}
        self.assertIn(NEW,gate.filter_case(case,P,Q)[0])
        self.assertNotIn(NEW,gate.filter_case(case,P,'냉수 온도가 미지근해요')[0])

    def test_inconsistent_rank_flag_is_rejected(self):
        case={'product_code':P,'candidate_55_child_ids':[NEW,'CHILD-A','CHILD-B','CHILD-C','CHILD-D'],
              'new_lock_detail_top5':False,'new_lock_detail_rank':None}
        with self.assertRaisesRegex(ValueError,'존재 플래그'):
            gate.filter_case(case,P,Q)

    def test_missing_or_duplicate_candidates_fail_closed(self):
        with self.assertRaises(ValueError):
            gate.filter_case({'product_code':P,'candidate_55_child_ids':[NEW]*5},P,Q)

    def test_nonoverwriting_results(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'sample.json'
            gate.write_unchanged_or_new(path,'ok\n')
            gate.write_unchanged_or_new(path,'ok\n')
            with self.assertRaises(FileExistsError):gate.write_unchanged_or_new(path,'changed\n')

    def test_real_csv_output_can_be_reexecuted_idempotently(self):
        if not gate.COMPARE.is_file() or not gate.PREVIEW.is_file():
            self.skipTest('Frozen inputs unavailable')
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td, patch.object(gate,'OUT',Path(td)):
            self.assertEqual(gate.run(['--write']),0)
            self.assertEqual(gate.run(['--write']),0)
            path=Path(td)/'s11_cold_lock_gate_cases.csv'
            self.assertIn('LOCK_POSITIVE',path.read_text(encoding='utf-8'))

    def test_actual_snapshot_integration_when_available(self):
        # Tests in the user's repo require last step's compare + S09 frozen input.
        if not gate.COMPARE.is_file() or not gate.PREVIEW.is_file():
            self.skipTest('Frozen S11 comparison/S09 input unavailable; pure tests still run')
        cases,inputs,meta=gate.load_inputs(gate.COMPARE,gate.PREVIEW)
        sm,details=gate.evaluate_cases(cases,inputs,meta)
        self.assertEqual(len(details),26)
        self.assertEqual((sm['positive_detail_before'],sm['positive_detail_after']),(4,4))
        self.assertEqual((sm['negative_detail_before'],sm['negative_detail_after']),(6,0))
        self.assertEqual(sm['rows_modified'],6)
        self.assertEqual(sm['baseline_53_snapshot_drift_count_carried_from_previous_run'],6)
        self.assertFalse(sm['training_ready'])

if __name__=='__main__':unittest.main()
