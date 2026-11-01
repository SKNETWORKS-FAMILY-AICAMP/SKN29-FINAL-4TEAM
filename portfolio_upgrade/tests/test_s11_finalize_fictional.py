"""S11 v2 deterministic fictional dataset, no external models or customer data."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import s11_finalize_fictional_dataset as s


class S11V2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs, cls.summary = s.build()
        cls.train = [json.loads(x) for x in cls.outputs["s11_fictional_train_v2.jsonl"].splitlines()]
        cls.probes = [json.loads(x) for x in cls.outputs["s11_fictional_probe_inputs_v2.jsonl"].splitlines()]
        cls.by_id = {x["case_id"]:x for x in cls.train}

    def pair(self, cid):
        r = self.by_id[cid]
        return json.loads(r["messages"][1]["content"]), json.loads(r["messages"][2]["content"])

    def test_48_16_disjoint_groups_and_balanced_actions(self):
        self.assertEqual((len(self.train),len(self.probes)),(48,16))
        self.assertTrue({r["semantic_group_id"] for r in self.train}.isdisjoint({r["semantic_group_id"] for r in self.probes}))
        self.assertEqual(Counter(json.loads(r["messages"][2]["content"])["action"] for r in self.train),Counter({a:12 for a in s.ACTIONS}))

    def test_source_hash_matches_and_files_immutable(self):
        for n, h in s.BASE_SHA256.items():
            self.assertEqual(s.sha((s.BASE/n).read_bytes()),h)

    def test_v1_probe_inputs_and_gold_unchanged(self):
        p=s.BASE/"s11_fictional_probe_inputs.jsonl"
        t=s.BASE/"s11_fictional_probe_targets_EVAL_ONLY.jsonl"
        self.assertEqual(self.outputs["s11_fictional_probe_inputs_v2.jsonl"].encode("utf-8"),p.read_bytes())
        self.assertEqual(self.outputs["s11_fictional_probe_targets_EVAL_ONLY_v2.jsonl"].encode("utf-8"),t.read_bytes())
        self.assertTrue(all([m["role"] for m in row["messages"]]==["system","user"] for row in self.probes))

    def test_case_question_f04_now_matches_low_volume_policy(self):
        u,t=self.pair("S11-F04-51940a59")
        self.assertIn("너무 작게",u["customer_message"])
        self.assertNotIn("안 나와",u["customer_message"])
        relevant=next(e["text"] for e in u["provided_evidence"] if e["id"]==t["cited_evidence_ids"][0])
        self.assertIn("소리가 작으면",relevant)
        self.assertEqual(t["action"],"ANSWER")

    def test_case_f04_battery_escalate_safety(self):
        u,t=self.pair("S11-F04-a410b564")
        self.assertEqual(t["action"],"ESCALATE")
        self.assertIn("만지거나 분해하지",t["customer_message"])
        self.assertIn("충전과 재생",u["known_conditions"][0]["answer_text"])
        self.assertNotIn("충전을 중단해",t["customer_message"])

    def test_case_f06_wet_wire_does_not_order_disconnection(self):
        u,t=self.pair("S11-F06-ab234ab5")
        self.assertEqual(t["action"],"ESCALATE")
        self.assertIn("직접 분리하지",t["customer_message"])
        self.assertIn("젖어",u["known_conditions"][0]["answer_text"])
        relevant=next(e["text"] for e in u["provided_evidence"] if e["id"]==t["cited_evidence_ids"][0])
        self.assertIn("직접 분리",relevant)

    def test_known_conditions_eight_with_two_per_action(self):
        actions=Counter()
        for cid in s.PRIOR_CONDITIONS:
            u,t=self.pair(cid)
            self.assertEqual(len(u["known_conditions"]),1)
            self.assertTrue(u["known_conditions"][0]["answer_text"])
            actions[t["action"]]+=1
        self.assertEqual(actions,Counter({a:2 for a in s.ACTIONS}))

    def test_previously_completed_action_not_repeated_f03_f05(self):
        for cid, term in [("S11-F03-f2894b6a","바람 버튼"),("S11-F05-c7b75a5a","디스플레이 버튼")]:
            u,t=self.pair(cid)
            self.assertIn(term, u["known_conditions"][0]["answer_text"])
            self.assertIn("반복하기보다",t["customer_message"])

    def test_evidence_ids_map_to_same_text_in_all_train_prompts(self):
        mapping={}
        for row in self.train:
            u=json.loads(row["messages"][1]["content"])
            for e in u["provided_evidence"]:
                self.assertEqual(mapping.setdefault(e["id"],e["text"]), e["text"])
        self.assertEqual(len(mapping),48)

    def test_target_and_evidence_not_leaked_in_model_input(self):
        for row in self.train:
            u,t=self.pair(row["case_id"])
            self.assertEqual(set(u),s.EXPECTED_PROMPT_FIELDS)
            self.assertEqual(set(t),s.EXPECTED_TARGET_FIELDS)
            self.assertNotIn('"action"', row["messages"][1]["content"])
            self.assertTrue(set(t["cited_evidence_ids"]).issubset({e["id"] for e in u["provided_evidence"]}))
            self.assertFalse(row["training_ready_for_waterbridge"])

    def test_tampered_v1_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in s.BASE_SHA256:
                (root/name).write_bytes((s.BASE/name).read_bytes())
            p=root/"s11_fictional_train_draft.jsonl"
            p.write_bytes(p.read_bytes()+b"\n")
            with self.assertRaisesRegex(ValueError,"SHA"):
                s.read_verified_source(root)

    def test_write_idempotence_and_conflict_raises(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            s.write_same_or_new(root,self.outputs)
            before={p.name:p.read_bytes() for p in root.iterdir()}
            s.write_same_or_new(root,self.outputs)
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})
            (root/"s11_fictional_train_v2.jsonl").write_text("tamper",encoding="utf-8")
            with self.assertRaises(FileExistsError):
                s.write_same_or_new(root,self.outputs)

    def test_same_input_same_output_hashes(self):
        o2,m2=s.build()
        self.assertEqual(o2,self.outputs)
        self.assertEqual(m2["output_sha256"],self.summary["output_sha256"])

    def test_token_ids_flatten_works_list_and_batchencoding(self):
        self.assertEqual(s._ids([1,2,3]),[1,2,3])
        self.assertEqual(s._ids({"input_ids":[1,2]}),[1,2])
        with self.assertRaises(TypeError):
            s._ids({"input_ids":[[1,2]]})

    def test_mock_tokenizer_checks_all_examples_and_mask(self):
        class FakeTok:
            def apply_chat_template(self, messages, **kwargs):
                self_assert = kwargs.get("enable_thinking") is False
                if not self_assert: raise AssertionError('enable_thinking not disabled')
                return {"input_ids":[2,3,4]}
            def encode(self, text, add_special_tokens):
                return [5,6,7]
        mock=types.SimpleNamespace(AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a, **kw:FakeTok()))
        with patch.dict(sys.modules,{"transformers":mock}):
            r=s.token_check(self.outputs,max_length=768)
        self.assertEqual(r["train_max"],6)
        self.assertEqual(r["probe_max"],3)
        self.assertTrue(r["mask_ok"])

if __name__=='__main__':unittest.main()
