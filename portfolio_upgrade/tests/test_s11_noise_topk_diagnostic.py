import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 's11_noise_topk_diagnostic.py'
spec=importlib.util.spec_from_file_location('s11_noise_topk_diagnostic',PATH)
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def row(case, src, gold=None):
    if gold is None:gold=['G1']
    return {'example_id':case,'audit_only':{'split':'train','training_ready':False,
            'source_scenario_id':src,'gold_evidence_ids':gold},
            'messages':[{'role':'system','content':'x'},
                        {'role':'user','content':json.dumps({'product_code':('WPUIAC606SNW' if src == s.NOISE_SOURCE else 'P'),'customer_message':'질문'})},
                        {'role':'assistant','content':json.dumps({'action':'ASK'})}]}


class NoiseTopKTests(unittest.TestCase):
    def test_customer_query_is_input_without_gold(self):
        self.assertEqual(s.model_input(row('R','X',['TOP_SECRET'])),('P','질문'))

    def test_ranking_cosine_and_stable_tie_break(self):
        try:import numpy as np
        except ImportError:self.skipTest('numpy optional for --check; required for --retrieve')
        chunks=[{'child_id':'B','exact_sales_code':'P','evidence_group_id':'G2'},
                {'child_id':'A','exact_sales_code':'P','evidence_group_id':'G1'},
                {'child_id':'C','exact_sales_code':'OTHER','evidence_group_id':'G3'}]
        ranks=s.ranked_for_model(chunks,np.array([[0.8,0.6],[0.8,0.6],[1,0]],dtype='float32'),
                                 np.array([1,0],dtype='float32'),'P',0.4)
        self.assertEqual([x['chunk_id'] for x in ranks],['A','B'])
        self.assertEqual([x['rank_unthresholded'] for x in ranks],[1,2])

    def test_threshold_is_separate_from_rank(self):
        try:import numpy as np
        except ImportError:self.skipTest('numpy not installed')
        chunks=[{'child_id':'A','exact_sales_code':'P','evidence_group_id':'G1'},
                {'child_id':'B','exact_sales_code':'P','evidence_group_id':'G2'}]
        ranks=s.ranked_for_model(chunks,np.array([[.7,0],[.3,0]],dtype='float32'),
                                 np.array([1,0],dtype='float32'),'P',0.4)
        self.assertTrue(ranks[0]['passes_threshold']);self.assertFalse(ranks[1]['passes_threshold'])
        self.assertEqual(ranks[1]['rank_unthresholded'],2)

    def test_noisy_case_all_gold_at_top8_only(self):
        rows=[row(f'X{i}','OTHER',['G1']) for i in range(24)] + [
            row('NOISE-BASE',s.NOISE_SOURCE,sorted(s.NOISE_REQUIRED_GROUPS)),
            row('NOISE-PAR',s.NOISE_SOURCE,sorted(s.NOISE_REQUIRED_GROUPS))]
        def build(needed_last):
            g=['G1','G1','G1','G1','G1','G1','G1','G1']
            g[0]='EVD-WPUIAC606SNW-ICE-MAKING-NOISE-001'
            g[needed_last]='EVD-WPUIAC606SNW-DEFROST-NOISE-001'
            return [{'chunk_id':f'C{i}','group_id':x,'score':0.6,'passes_threshold':True,
                     'rank_unthresholded':i+1} for i,x in enumerate(g)]
        rankings=[[{'chunk_id':'C1','group_id':'G1','score':0.7,
                   'passes_threshold':True,'rank_unthresholded':1}] for _ in range(24)]+[build(6),build(2)]
        report=s.evaluate_rankings(rows,rankings,None,model_id='test',revision='rev',threshold=.4)
        self.assertEqual(report['summary']['metrics_by_k']['5']['noise_two_rows_all_gold'],1)
        self.assertEqual(report['summary']['metrics_by_k']['8']['noise_two_rows_all_gold'],2)
        self.assertFalse(report['summary']['training_ready'])

    def test_drift_is_exposed_not_suppressed(self):
        rows=[row(f'R{i}','OTHER',['G1']) for i in range(24)]+[
            row('N1',s.NOISE_SOURCE,sorted(s.NOISE_REQUIRED_GROUPS)),
            row('N2',s.NOISE_SOURCE,sorted(s.NOISE_REQUIRED_GROUPS))]
        ranks=[[{'chunk_id':'A','group_id':'G1','score':0.6,'passes_threshold':True,'rank_unthresholded':1}]
               for _ in range(24)] + [
            [{'chunk_id':'A','group_id':'EVD-WPUIAC606SNW-ICE-MAKING-NOISE-001',
              'score':0.7,'passes_threshold':True,'rank_unthresholded':1},
             {'chunk_id':'B','group_id':'EVD-WPUIAC606SNW-DEFROST-NOISE-001',
              'score':0.6,'passes_threshold':True,'rank_unthresholded':2}]
            for _ in range(2)]
        prev={'cases':[{'example_id':'R0','baseline_53_child_ids':['OTHER']} ]}
        report=s.evaluate_rankings(rows,ranks,prev,model_id='test',revision='rev',threshold=.4)
        self.assertEqual(report['summary']['baseline53_drift_vs_previous_comparison_count'],1)

    def _mock_input_files(self, tmp: Path):
        chunks=[{'child_id':f'CHILD-{i:03}', 'record_type':'child',
                 'retrieval_role':'SEARCH_CANDIDATE', 'verification_status':'TEXT_AND_VISUAL_VERIFIED',
                 'allowed_use':'RAG_HANDOFF_ONLY'} for i in range(53)]
        records=[row(f'R{i}','OTHER') for i in range(24)]+[
            row('N1',s.NOISE_SOURCE,sorted(s.NOISE_REQUIRED_GROUPS)),
            row('N2',s.NOISE_SOURCE,sorted(s.NOISE_REQUIRED_GROUPS))]
        idx=tmp/'index.jsonl'; snap=tmp/'snapshot.jsonl';prev=tmp/'missing.json'
        idx.write_text(''.join(json.dumps(x)+'\n' for x in chunks),encoding='utf-8')
        snap.write_text(''.join(json.dumps(x)+'\n' for x in records),encoding='utf-8')
        return idx,snap,prev

    def test_source_sha_guard(self):
        with tempfile.TemporaryDirectory() as td:
            a,b,c=self._mock_input_files(Path(td))
            with self.assertRaises(ValueError):s.validate_data(a,b,c)

    def test_non_train_case_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a,b,c=self._mock_input_files(Path(td))
            records=[json.loads(x) for x in b.read_text().splitlines()]
            records[0]['audit_only']['split']='dev'
            b.write_text(''.join(json.dumps(x)+'\n' for x in records))
            def fake_sha(path):
                return s.EXPECTED_INDEX_SHA if path==a else s.EXPECTED_SNAPSHOT_SHA
            with patch.object(s,'sha',side_effect=fake_sha):
                with self.assertRaises(ValueError):s.validate_data(a,b,c)

    def test_invalid_write_without_retrieval(self):
        with self.assertRaises(ValueError):s.run(['--write'])


if __name__=='__main__':unittest.main()
