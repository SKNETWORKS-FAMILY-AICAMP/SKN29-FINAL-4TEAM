"""Minimal, offline guardrail tests for the S08/B1 same-model prompt comparison."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import s08_strong_prompt_baseline as b1


class B1SafetyTests(unittest.TestCase):
    def test_exact_snapshot_pinned(self):
        rows, digest, prompt_sha = b1.verify()
        self.assertEqual(len(rows), 6)
        self.assertEqual(digest, b1.BASE_INPUT_SHA)
        self.assertEqual(len(prompt_sha), 64)

    def test_system_only_changes(self):
        rows, _, _ = b1.verify()
        for r in rows:
            before = r['messages']
            after = b1.build_b1_messages(before)
            self.assertEqual(after[1], before[1])
            self.assertNotEqual(after[0]['content'], before[0]['content'])
            self.assertEqual(before, r['messages'])

    def test_prompt_has_no_gold_or_case_specific_clues(self):
        prompt = b1.STRONG_SYSTEM_PROMPT
        for forbidden in ['SYN-', 'WPUJAC', 'IAC425', 'IAC606', '1544-1000', '1600-1661', 'JAC104-033']:
            self.assertNotIn(forbidden, prompt)

    def test_schema_validation(self):
        good = {'action':'ASK','customer_message':'추가 정보를 알려주세요.', 'cited_evidence_ids':[], 'missing_fields':['target_water_type']}
        self.assertTrue(b1.validate_schema(good))
        self.assertFalse(b1.validate_schema({**good, 'action':['ANSWER']}))
        self.assertFalse(b1.validate_schema({**good, 'cited_evidence_ids':['abc',3]}))
        self.assertFalse(b1.validate_schema({**good,'extra':'not allowed'}))

    def test_strict_json_no_auto_repair(self):
        value, error=b1.b0.extract_json('{"action":"ASK"}"')
        self.assertIsNone(value)
        self.assertTrue(error)


if __name__=='__main__':
    unittest.main(verbosity=2)
