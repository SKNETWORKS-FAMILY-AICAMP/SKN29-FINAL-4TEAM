"""S11 child-citation audit regressions; self-contained CPU tests."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/'scripts/s11_child_citation_preview.py'
spec=importlib.util.spec_from_file_location('s11_child_citation_preview',PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def chunk(cid,text,page=5,gid='EVD-SIM-LEAK',model='SIM-P1'):
    return {'child_id':cid,'child_text':text,'page_refs':[page],
        'evidence_group_id':gid,'exact_sales_code':model,'allowed_use':'RAG_HANDOFF_ONLY',
        'record_type':'child','retrieval_role':'SEARCH_CANDIDATE','verification_status':'TEXT_AND_VISUAL_VERIFIED'}

def make_row(group_text,group_pages=[5,7]):
    user={'customer_message':'가상 문의','product_code':'SIM-P1','previous_answers':[],
        'retrieved_evidence':[{'id':'EVD-SIM-LEAK','page_refs':group_pages,'text':group_text}]}
    return {'example_id':'S07-SYN-SIM-001-BASE','status':'PREVIEW_NOT_TRAIN_READY',
        'messages':[{'role':'system','content':'가상 규칙'},
            {'role':'user','content':json.dumps(user,ensure_ascii=False)},
            {'role':'assistant','content':json.dumps({'action':'ANSWER','customer_message':'가상 안내',
                'cited_evidence_ids':['EVD-SIM-LEAK'],'missing_fields':[]})}],
        'audit_only':{'split':'train','training_ready':False,'data_use_authorized_for_sft':False,
            'source_scenario_id':'SYN-SIM-001','semantic_group_id':'sim-sg1',
            'gold_evidence_ids':['EVD-SIM-LEAK']}}

class ChildCitationTests(unittest.TestCase):
    def setUp(self):
        self.a=chunk('CHILD-SIM-LEAK-5','물받이 확인',5)
        self.b=chunk('CHILD-SIM-LEAK-7','안전 조치',7)
    def test_exact_decomposition_handles_internal_newlines(self):
        x=chunk('CHILD-X','한 줄\n두 줄')
        y=chunk('CHILD-Y','다음 줄')
        got=mod.recover_children(x['child_text']+'\n'+y['child_text'],[y,x])
        self.assertEqual([a['child_id'] for a in got],['CHILD-X','CHILD-Y'])
    def test_missing_evidence_fails_closed(self):
        with self.assertRaises(ValueError):mod.recover_children('조작법은 버튼 3초',[self.a,self.b])
    def test_ambiguous_evidence_fails_closed(self):
        a=chunk('CHILD-A','동일 문장');b=chunk('CHILD-B','동일 문장')
        with self.assertRaises(ValueError):mod.recover_children('동일 문장',[a,b])
    def test_child_ids_and_assistant_removed(self):
        row=make_row('물받이 확인\n안전 조치')
        exact,sibling,audit=mod.make_pair(row,{'EVD-SIM-LEAK':[self.a,self.b]}, expected_count=None)
        self.assertEqual(exact['visible_citation_ids'],['CHILD-SIM-LEAK-5','CHILD-SIM-LEAK-7'])
        self.assertEqual([m['role'] for m in exact['messages']],['system','user'])
        self.assertFalse(exact['audit_only']['training_ready'])
        self.assertFalse(exact['audit_only']['source_use_approved_for_training'])
        user=json.loads(exact['messages'][1]['content'])
        self.assertTrue(all(x['id'].startswith('CHILD-') for x in user['retrieved_evidence']))
        self.assertNotIn('gold_evidence_ids',exact['messages'][1]['content'])
        self.assertNotIn('reviewed_target_NOT_FOR_SFT',exact['messages'][1]['content'])
    def test_group_expansion_does_not_use_gold(self):
        row=make_row('물받이 확인',[5]);a,b,s=mod.make_pair(row,{'EVD-SIM-LEAK':[self.a,self.b]}, expected_count=None)
        self.assertEqual(a['visible_citation_ids'],['CHILD-SIM-LEAK-5'])
        self.assertEqual(len(b['visible_citation_ids']),2)
        self.assertEqual(b['audit_only']['added_siblings_count'],1)
        clone=copy.deepcopy(row);clone['audit_only']['gold_evidence_ids']=[]
        clone['messages'][2]['content']=json.dumps({'action':'ANSWER','customer_message':'가상','cited_evidence_ids':[],'missing_fields':[]})
        a2,b2,s2=mod.make_pair(clone,{'EVD-SIM-LEAK':[self.a,self.b]},expected_count=None)
        self.assertEqual(a['visible_citation_ids'],a2['visible_citation_ids'])
        self.assertEqual(b['visible_citation_ids'],b2['visible_citation_ids'])
    def test_wrong_product_rejected(self):
        row=make_row('물받이 확인',[5]);bad=copy.deepcopy(self.a);bad['exact_sales_code']='OTHER'
        with self.assertRaises(ValueError):mod.make_pair(row,{'EVD-SIM-LEAK':[bad]},expected_count=None)
    def test_wrong_split_or_training_approval_rejected(self):
        row=make_row('물받이 확인',[5]);row['audit_only']['training_ready']=True
        with self.assertRaises(ValueError):mod.make_pair(row,{'EVD-SIM-LEAK':[self.a]},expected_count=None)
    def test_bad_citation_group_not_silently_approved(self):
        row=make_row('물받이 확인',[5]);lab=json.loads(row['messages'][2]['content']);lab['cited_evidence_ids']=['EVD-SIM-OTHER'];row['messages'][2]['content']=json.dumps(lab)
        with self.assertRaises(ValueError):mod.make_pair(row,{'EVD-SIM-LEAK':[self.a]},expected_count=None)
    def test_full_26_case_pipeline_is_preview_only(self):
        corpus=[chunk(f'CHILD-SIM-G{i:02d}',f'가상 확인 문단 {i}',
                      page=i+1,gid=f'EVD-SIM-G{i:02d}') for i in range(53)]
        sources=['SYN-IAC425-101','SYN-IAC606-101','SYN-IAC425-108','SYN-IAC606-104']+[f'SYN-SIM-{i:03d}' for i in range(9)]
        rows=[]
        for source in sources:
            for suffix in ['BASE','PAR1']:
                row=make_row('가상 확인 문단 0',[1])
                row['example_id']=f'S07-{source}-{suffix}'
                row['audit_only']['source_scenario_id']=source
                u=json.loads(row['messages'][1]['content'])
                u['retrieved_evidence']=[{'id':f'EVD-SIM-G{i:02d}',
                     'page_refs':[i+1], 'text':f'가상 확인 문단 {i}'} for i in range(5)]
                row['messages'][1]['content']=json.dumps(u,ensure_ascii=False)
                row['audit_only']['gold_evidence_ids']=['EVD-SIM-G00']
                row['messages'][2]['content']=json.dumps({'action':'ANSWER','customer_message':'가상 안내',
                  'cited_evidence_ids':['EVD-SIM-G00'],'missing_fields':[]})
                rows.append(row)
        exact,expanded,summary=mod.review(rows,corpus,{'test':'synthetic'})
        self.assertEqual(len(exact),26)
        self.assertEqual(len(expanded),26)
        self.assertEqual(summary['exact_child_instances'],130)
        self.assertEqual(summary['sibling_child_instances_added'],0)
        self.assertEqual(summary['at_least_one_legacy_gold_group_present'],26)
        self.assertEqual(len(summary['p1_eight_rows']),8)
        self.assertTrue(all(len(x['messages'])==2 for x in exact+expanded))

    def test_source_constraints_checked(self):
        chunks=[chunk(f'CHILD-SIM-{i}','x'+str(i)) for i in range(53)];chunks[0]['allowed_use']='TRAIN'
        with self.assertRaises(ValueError):mod.prepare_index(chunks)

if __name__=='__main__':unittest.main()
