"""CPU-only S11 cold-lock indexed-child regression tests. No PDF/GPU/API required."""
from __future__ import annotations
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

S = pathlib.Path(__file__).resolve().parents[1]/'scripts/s11_reindex_cold_lock.py'
spec=importlib.util.spec_from_file_location('s11_reindex_cold_lock',S)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
MANIFEST=pathlib.Path(__file__).resolve().parents[1]/'data/s11_index/cold_lock_pages_verified_v1.json'


def fixture_corpus():
    models=['WPUIAC425SNW','WPUIAC606SNW']
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    index={r['model_code']:r for r in manifest['records']}
    out=[]
    for k in models:
        p=index[k]
        page=43 if k=='WPUIAC425SNW' else 40
        out.append({
            'child_id':f'CHILD-{k}-P{page:03d}-COLD-LOCK-001',
            'exact_sales_code':k,
            'evidence_group_id':f'EVD-{k}-COLD-LOCK-001',
            'document_id':f"MAN-SKMAGIC-WPU-{p['family']}-{p['manual_revision'].replace('.','')}",
            'source_file_sha256':p['source_pdf_sha256'].upper(),
            'child_text':'냉수 잠금은 해당 페이지 참고',
            'section_title':'고장 신고 전 확인하기',
            'record_type':'child','retrieval_role':'SEARCH_CANDIDATE',
            'verification_status':'TEXT_AND_VISUAL_VERIFIED','allowed_use':'RAG_HANDOFF_ONLY'
        })
    # the other records simulate unrelated chunks, without making product claims
    for i in range(51):
        out.append({'child_id':f'CHILD-SIM-{i:03d}', 'exact_sales_code':'SIM-OTHER',
                    'record_type':'child','retrieval_role':'SEARCH_CANDIDATE',
                    'verification_status':'TEXT_AND_VISUAL_VERIFIED','allowed_use':'RAG_HANDOFF_ONLY'})
    return out,manifest


class S11ColdLockIndexTests(unittest.TestCase):
    def test_exactly_two_rag_only_pages_and_model_buttons(self):
        corpus,manifest=fixture_corpus()
        added=mod.build_addendum(corpus,manifest)
        self.assertEqual(len(added),2)
        self.assertTrue(all(c['allowed_use']=='RAG_HANDOFF_ONLY' for c in added))
        self.assertTrue(all(c['s11_training_ready'] is False for c in added))
        one={c['exact_sales_code']:c for c in added}
        self.assertEqual(one['WPUIAC425SNW']['page_refs'],[27])
        self.assertEqual(one['WPUIAC606SNW']['page_refs'],[24])
        self.assertIn('[물]',one['WPUIAC425SNW']['child_text'])
        self.assertNotIn('출수/출빙',one['WPUIAC425SNW']['child_text'])
        self.assertIn('출수/출빙',one['WPUIAC606SNW']['child_text'])
        self.assertNotIn('[물]',one['WPUIAC606SNW']['child_text'])
        self.assertEqual(one['WPUIAC425SNW']['evidence_group_id'],corpus[0]['evidence_group_id'])
        self.assertEqual(one['WPUIAC606SNW']['evidence_group_id'],corpus[1]['evidence_group_id'])

    def test_mixed_up_completion_button_is_rejected(self):
        corpus,manifest=fixture_corpus()
        manifest['records'][0]['text']=manifest['records'][0]['text'].replace('[물]','출수/출빙')
        with self.assertRaisesRegex(ValueError,'425 전용'):
            mod.build_addendum(corpus,manifest)

    def test_sft_permission_cannot_be_elevated_by_manifest(self):
        corpus,manifest=fixture_corpus()
        manifest['records'][0]['approved_for_training']=True
        with self.assertRaisesRegex(ValueError,'SFT 학습 승인'):
            mod.build_addendum(corpus,manifest)

    def test_source_sha_and_index_are_immutable(self):
        corpus,manifest=fixture_corpus()
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            mod.check_corpus(corpus,'0'*64)
        added=mod.build_addendum(corpus,manifest)
        old_ids=[x['child_id'] for x in corpus]
        joined=mod.check_extended(corpus,added)
        self.assertEqual(len(joined),55)
        self.assertEqual([x['child_id'] for x in joined[:53]],old_ids)
        self.assertEqual(len(set(x['child_id'] for x in joined)),55)

    def test_training_data_gold_is_excluded_from_search_queries(self):
        rows=[]
        for i in range(26):
            rows.append({'example_id':f'S07-SYN-SIM-{i:02d}',
                         'status':'PREVIEW_NOT_TRAIN_READY',
                         'messages':[{'role':'system','content':'a'},
                                     {'role':'user','content':json.dumps({'customer_message':'q','product_code':'SIM'})},
                                     {'role':'assistant','content':'{}'}],
                         'audit_only':{'split':'train','training_ready':False}})
        self.assertEqual(len(mod.validate_frozen_train(rows,mod.PREVIEW_SHA)),26)
        rows[1]['messages'][1]['content']=json.dumps({'customer_message':'q','product_code':'SIM','gold_evidence_ids':['ANSWER']})
        with self.assertRaisesRegex(ValueError,'Gold'):
            mod.validate_frozen_train(rows,mod.PREVIEW_SHA)
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            mod.validate_frozen_train(rows,'bad')

    def test_comparison_tracks_new_page_not_only_same_group_gold(self):
        rows=[];old=[];new=[]
        for src,code in [('SYN-IAC425-101','WPUIAC425SNW'),('SYN-IAC606-101','WPUIAC606SNW')]:
            for variant in ['BASE','PAR1']:
                eid=f'S07-{src}-{variant}'
                rows.append({'example_id':eid,'messages':[{}, {'content':json.dumps({'product_code':code})}],
                             'audit_only':{'source_scenario_id':src,'gold_evidence_ids':[f'EVD-{code}-COLD-LOCK-001']}})
                old.append([{'chunk_id':'old','evidence_group_id':f'EVD-{code}-COLD-LOCK-001'}])
                new.append([{'chunk_id':mod.MODEL_CODE_TO_NEW_CHILD[code], 'evidence_group_id':f'EVD-{code}-COLD-LOCK-001'}])
        details,s=mod.comparison_rows(rows,old,new,None)
        self.assertEqual(s['new_lock_detail_top5_count'],4)
        self.assertEqual(s['baseline_gold_any_count'],4)
        self.assertEqual(s['candidate_gold_any_count'],4)
        self.assertTrue(all(x['new_lock_detail_rank']==1 for x in details))
        self.assertFalse(s['training_ready'])

    def test_explicit_pdf_checks_require_both_files(self):
        _,manifest=fixture_corpus()
        with self.assertRaisesRegex(ValueError,'모두 지정'):
            mod.verify_source_pdf(manifest,{'WPUIAC425SNW':pathlib.Path('not-exist.pdf')})

    def test_outputs_refuse_conflicting_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'compare.json'
            mod.freeze_output(path,'AAA')
            mod.freeze_output(path,'AAA')
            with self.assertRaises(FileExistsError):mod.freeze_output(path,'BBB')
            self.assertEqual(path.read_text(),'AAA')


    def test_end_to_end_write_creates_55_without_touching_53(self):
        corpus,manifest=fixture_corpus()
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            orig=root/'data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl'
            orig.parent.mkdir(parents=True,exist_ok=True)
            orig.write_text(mod.jsonl(corpus),encoding='utf-8')
            orig_bytes=orig.read_bytes()
            source_sha=mod.sha_bytes(orig_bytes)
            manifest['original_53_index_sha256']=source_sha
            man=root/'portfolio_upgrade/data/s11_index/cold_lock_pages_verified_v1.json'
            man.parent.mkdir(parents=True,exist_ok=True)
            man.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
            patchf=root/'portfolio_upgrade/data/s11_index/cold_lock_addendum_v1.jsonl'
            extended=root/'portfolio_upgrade/data/s11_index/cold_lock_candidate_55_v1.jsonl'
            audit=root/'portfolio_upgrade/experiments/s11_readiness'
            with patch.object(mod,'ROOT',root),patch.object(mod,'SOURCE',orig),patch.object(mod,'SOURCE_SHA',source_sha),patch.object(mod,'MANIFEST',man),patch.object(mod,'PATCH',patchf),patch.object(mod,'EXTENDED',extended),patch.object(mod,'OUT',audit):
                self.assertEqual(mod.main(['--write']),0)
            self.assertEqual(orig.read_bytes(),orig_bytes)
            self.assertEqual(len(mod.read_jsonl(extended)),55)
            self.assertEqual(len(mod.read_jsonl(patchf)),2)
            self.assertFalse(json.loads((audit/'s11_cold_lock_index_audit.json').read_text(encoding='utf-8'))['training_ready'])

    def test_wrong_pdf_hash_cannot_create_record(self):
        corpus,manifest=fixture_corpus()
        manifest['records'][0]['source_pdf_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'PDF SHA-256'):
            mod.build_addendum(corpus,manifest)

if __name__=='__main__': unittest.main()
