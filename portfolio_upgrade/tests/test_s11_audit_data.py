"""S11 offline audit guardrails. No CUDA, model downloads, network, data training."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "portfolio_upgrade/scripts/s11_audit_data.py"
spec = importlib.util.spec_from_file_location("s11_audit_data", SCRIPT)
s11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s11)


class S11AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training_path = ROOT / s11.TRAIN_REL
        cls.preview_path = ROOT / s11.PREVIEW_REL
        cls.review_path = ROOT / s11.REVIEW_REL
        for path in (cls.training_path, cls.preview_path, cls.review_path):
            if not path.is_file():
                raise unittest.SkipTest(f"S11 audit tests require previous S07/S09 artifacts: {path}")
        cls.train = s11.read_jsonl(cls.training_path)
        cls.preview = s11.read_jsonl(cls.preview_path)
        cls.review = json.loads(cls.review_path.read_text(encoding="utf-8-sig"))
        cls.hashes = {
            "s07_train":s11.sha256(cls.training_path),
            "s09_preview":s11.sha256(cls.preview_path),
            "m2_review":s11.sha256(cls.review_path),
        }

    def baseline(self, train=None, preview=None, review=None):
        return s11.verify_and_summarize(
            self.train if train is None else train,
            self.preview if preview is None else preview,
            self.review if review is None else review,
            self.hashes,
        )

    def test_baseline_counts_and_no_training_approval(self):
        report, queue = self.baseline()
        self.assertEqual((report["n_train_rows"],report["original_scenarios"],report["semantic_groups"]),(26,13,6))
        self.assertEqual(len(queue),13)
        self.assertEqual(report["training_ready_count"],0)
        self.assertEqual(report["source_use_approved_count"],0)
        self.assertEqual(report["retrieval"]["all_declared_gold_top5"],25)

    def test_fourth_action_absent_from_unapproved_train(self):
        report, _ = self.baseline()
        self.assertEqual(report["action_rows"],{
            "ANSWER":12,"ASK":4,"ESCALATE":10,"EXPLAIN_UNSUPPORTED":0,
        })

    def test_train_dev_holdout_leak_is_rejected(self):
        modified=json.loads(json.dumps(self.train,ensure_ascii=False))
        modified[0]["provenance"]["split"]="dev"
        with self.assertRaisesRegex(ValueError,"train"):
            self.baseline(train=modified)

    def test_training_permission_change_requires_new_review(self):
        modified=json.loads(json.dumps(self.train,ensure_ascii=False))
        modified[0]["s07"]["source_use_approved_for_training"]=True
        with self.assertRaisesRegex(ValueError,"사용 승인"):
            self.baseline(train=modified)

    def test_gold_in_model_input_is_rejected(self):
        modified=json.loads(json.dumps(self.preview,ensure_ascii=False))
        modified[0]["messages"][1]["content"] += " gold_evidence_ids"
        with self.assertRaisesRegex(ValueError,"Gold"):
            self.baseline(preview=modified)

    def test_changed_preview_sha_is_rejected(self):
        hashes=dict(self.hashes)
        hashes["s09_preview"]="a"*64
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            s11.verify_and_summarize(self.train,self.preview,self.review,hashes)

    def test_p1_queue_is_exactly_four_original_scenarios(self):
        _,queue=self.baseline()
        cases={r["scenario_id"] for r in queue if r["priority"] == "P1"}
        self.assertEqual(cases,{
            "SYN-IAC425-101","SYN-IAC425-108","SYN-IAC606-101","SYN-IAC606-104",
        })

    def test_write_only_derivatives_not_source_files(self):
        with tempfile.TemporaryDirectory(prefix="s11_") as temp:
            t=Path(temp)
            for rel,source in ((s11.TRAIN_REL,self.training_path), (s11.PREVIEW_REL,self.preview_path), (s11.REVIEW_REL,self.review_path)):
                dest=t/rel
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,dest)
            hashes_before={r:s11.sha256(t/r) for r in (s11.TRAIN_REL,s11.PREVIEW_REL,s11.REVIEW_REL)}
            summary,queue=s11.audit(t)
            out=t/s11.OUT_REL
            out.mkdir(parents=True,exist_ok=True)
            (out/"s11_audit_summary.json").write_text(json.dumps(summary,ensure_ascii=False),encoding="utf-8")
            (out/"s11_case_queue.csv").write_text("scenario_id\n"+"\n".join(x["scenario_id"] for x in queue),encoding="utf-8")
            self.assertEqual(hashes_before,{r:s11.sha256(t/r) for r in hashes_before})

if __name__=="__main__":
    unittest.main()
