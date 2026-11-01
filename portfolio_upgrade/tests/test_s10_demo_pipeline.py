"""CPU-only tests. Run: python -m unittest discover -s portfolio_upgrade/tests -p 'test_s10*.py' -v"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'portfolio_upgrade/scripts'))
import s10_prepare_demo as demo
import s10_train_lora as train
import s10_probe_adapter as probe


class FakeQwenTokenizer:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt, enable_thinking):
        assert len(messages) == 2 and tokenize and add_generation_prompt
        assert enable_thinking is False
        return [101, 102, 103, 104]

    def encode(self, completion, add_special_tokens):
        assert completion.endswith('<|im_end|>') and add_special_tokens is False
        return [201, 202, 203]


class FakeBatchEncodingTokenizer(FakeQwenTokenizer):
    """Regression stand-in for Transformers 5 apply_chat_template output."""

    def apply_chat_template(self, messages, tokenize, add_generation_prompt, enable_thinking):
        ids = super().apply_chat_template(messages, tokenize, add_generation_prompt, enable_thinking)
        return {'input_ids': ids, 'attention_mask': [1] * len(ids)}


class S10ToyUnitTests(unittest.TestCase):
    def test_40_train_8_probes_and_real_dataset_excluded(self):
        train_rows, probes = demo.build()
        self.assertEqual((len(train_rows),len(probes)), (40,8))
        self.assertTrue(all(r['origin']=='FICTIONAL_ORIGINAL_DEMO' for r in train_rows+probes))
        self.assertTrue(all(r['split']=='train' for r in train_rows))
        self.assertTrue(all(r['split']=='probe' for r in probes))
        self.assertFalse({r['source_id'] for r in train_rows} & {r['source_id'] for r in probes})
        self.assertEqual(Counter(json.loads(x['completion'][0]['content'])['action'] for x in train_rows),
                         Counter({a:10 for a in demo.ACTIONS}))
        self.assertEqual(Counter(json.loads(x['completion'][0]['content'])['action'] for x in probes),
                         Counter({a:2 for a in demo.ACTIONS}))

    def test_model_input_has_no_gold_answer(self):
        train_rows, probes = demo.build()
        for row in train_rows+probes:
            self.assertEqual([m['role'] for m in row['prompt']],['system','user'])
            self.assertEqual([m['role'] for m in row['completion']],['assistant'])
            user = json.loads(row['prompt'][1]['content'])
            target = json.loads(row['completion'][0]['content'])
            self.assertEqual(set(target),{'action','customer_message','cited_evidence_ids','missing_fields'})
            self.assertEqual(len(user['retrieved_evidence']),1)
            self.assertEqual(set(target['cited_evidence_ids']),{user['retrieved_evidence'][0]['evidence_id']})
            self.assertTrue(user['product_code'].startswith('SIM-'))
            self.assertNotIn('expected_action', row['prompt'][1]['content'])

    def test_prepare_idempotence_and_hash_manifest(self):
        demo.run(write=False)
        config, rows=train.validate_local()
        _, probes=probe.validate_local()
        self.assertEqual(len(rows),40)
        self.assertEqual(len(probes),8)
        self.assertEqual(config['max_steps'],10)
        self.assertFalse(config['manual_derived_sft_data_permitted'])
        self.assertEqual(json.loads(demo.MANIFEST.read_text(encoding='utf-8'))['train_sha256'],train.digest(demo.TRAIN))

    def test_token_loss_mask_only_completion(self):
        rows,_=demo.build()
        result=train.tokenize_examples(FakeQwenTokenizer(),rows[:1],768)[0]
        self.assertEqual(result['input_ids'],[101,102,103,104,201,202,203])
        self.assertEqual(result['attention_mask'],[1]*7)
        self.assertEqual(result['labels'],[-100,-100,-100,-100,201,202,203])

    def test_transformers5_batch_encoding_token_ids_and_loss_mask(self):
        rows, _ = demo.build()
        result = train.tokenize_examples(FakeBatchEncodingTokenizer(), rows[:1], 768)[0]
        self.assertEqual(result['input_ids'], [101, 102, 103, 104, 201, 202, 203])
        self.assertEqual(result['attention_mask'], [1] * 7)
        self.assertEqual(result['labels'], [-100, -100, -100, -100, 201, 202, 203])

    def test_transformers5_probe_generation_encoding_extraction(self):
        # Transformers 5 returns BatchEncoding; previously the probe code
        # treated it as a Tensor, causing torch.ones_like(BatchEncoding) failure.
        token_ids = [[100, 101, 102]]
        mask = [[1, 1, 1]]
        ids, attn = probe.extract_generation_inputs({'input_ids': token_ids, 'attention_mask': mask})
        self.assertIs(ids, token_ids)
        self.assertIs(attn, mask)
        with self.assertRaisesRegex(ValueError, 'no input_ids'):
            probe.extract_generation_inputs({'attention_mask': mask})

    def test_transformers4_probe_generation_tensor_extraction(self):
        old_tensor = object()
        ids, mask = probe.extract_generation_inputs(old_tensor)
        self.assertIs(ids, old_tensor)
        self.assertIsNone(mask)

    def test_too_short_max_length_stops_training_early(self):
        rows,_=demo.build()
        with self.assertRaises(ValueError):
            train.tokenize_examples(FakeQwenTokenizer(),rows[:1],6)

    def test_non_fictional_training_source_rejected(self):
        raw=json.loads(demo.SOURCE.read_text(encoding='utf-8'))
        raw['rows'][0]['product_code']='WPUIAC425SNW'
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'bad.json'
            source.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
            with patch.object(demo,'SOURCE',source):
                with self.assertRaisesRegex(ValueError,'Non-fictional product'):
                    demo.build()

    def test_source_split_protection(self):
        raw=json.loads(demo.SOURCE.read_text(encoding='utf-8'))
        raw['rows'][-1]['split']='train'
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'bad.json'
            source.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
            with patch.object(demo,'SOURCE',source):
                with self.assertRaisesRegex(ValueError,'train source 20'):
                    demo.build()


if __name__=='__main__':
    unittest.main()
