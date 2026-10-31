"""Pure stdlib smoke tests for S08/S09 formatting guards."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
def load(name):
    spec=importlib.util.spec_from_file_location(name,SCRIPTS/(name+'.py'))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

class TestGuards(unittest.TestCase):
    def test_no_gold_in_prompt(self):
        m=load('s08_prepare_eval')
        messages=m.case_prompt({'request':{'model_code':'SAMPLE','raw_symptom':'냉수가 안 나와요','previous_answers':[]}},
              {'case_id':'test','evidence':[{'id':'REF1','text':'냉수 잠금 해제 확인','page_refs':[43]}],
               'gold_group_ids_FOR_EVALUATION_ONLY':['SECRET_GOLD']})
        rendered=json.dumps(messages,ensure_ascii=False)
        self.assertNotIn('SECRET_GOLD',rendered)
        self.assertIn('REF1',rendered)
        self.assertIn('냉수가 안 나와요',rendered)

    def test_csv_duplicate_header_conflict(self):
        m=load('s08_prepare_eval')
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'t.csv'
            p.write_text('scenario_id,manual_answerable,manual_answerable\nA,YES,NO\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'중복 CSV 열'):
                m.csv_rows(p)
            p.write_text('scenario_id,manual_answerable,manual_answerable\nA,YES,YES\n',encoding='utf-8')
            r,dup=m.csv_rows(p)
            self.assertEqual(len(r),1)
            self.assertEqual(dup,['manual_answerable'])

    def test_preview_marks_fact_summary_not_real_retrieval(self):
        m=load('s09_model_preflight')
        msg=m.preview_messages({'input':{'product_code':'TEST','customer_message':'TEST Q'},
                                'provenance':{'manual_pdf_source':{'page_evidence':[{'page':43,'fact_summary':'TEST FACT'}]}}})
        self.assertIn('FOR_TOKENIZATION_PREVIEW_ONLY',msg[-1]['content'])
        self.assertIn('TEST FACT',msg[-1]['content'])

if __name__=='__main__':unittest.main()
