from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from data.tools.rag_experiments.build_three_model_handoff import build
from data.tools.rag_experiments.qa_three_model_handoff import build_qa_report


REPO_ROOT = Path(__file__).resolve().parents[3]


class ThreeModelRagHandoffTests(unittest.TestCase):
    def test_canonical_handoff_passes_count_lineage_and_anchor_gates(self) -> None:
        report = build_qa_report(
            REPO_ROOT / "data/processed/structured/rag/expansion/rag_parent_pages_3model_v1.jsonl",
            REPO_ROOT / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl",
            REPO_ROOT / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl",
            REPO_ROOT / "data/config/rag/three_model_evaluation_cases.json",
        )
        self.assertEqual("PASS", report["status"])
        self.assertEqual(15, report["counts"]["parents"])
        self.assertEqual(53, report["counts"]["children"])
        self.assertEqual(43, report["counts"]["groups"])
        self.assertEqual(49, report["counts"]["cases"])

    def test_rebuild_is_byte_identical(self) -> None:
        canonical = [
            REPO_ROOT / "data/processed/structured/rag/expansion/rag_parent_pages_3model_v1.jsonl",
            REPO_ROOT / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl",
            REPO_ROOT / "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl",
            REPO_ROOT / "data/config/rag/three_model_evaluation_cases.json",
            REPO_ROOT / "data/processed/metadata/rag_three_model_handoff_manifest.json",
        ]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            generated = [root / path.name for path in canonical]
            build(*generated)
            for expected, actual in zip(canonical, generated, strict=True):
                self.assertEqual(expected.read_bytes(), actual.read_bytes(), expected.name)

    def test_positive_cases_forbid_the_other_two_supported_models(self) -> None:
        document = json.loads(
            (REPO_ROOT / "data/config/rag/three_model_evaluation_cases.json").read_text(encoding="utf-8")
        )
        positives = [row for row in document["cases"] if row["case_type"] == "POSITIVE"]
        self.assertEqual(43, len(positives))
        for case in positives:
            self.assertEqual(2, len(case["forbidden_model_codes"]), case["case_id"])


if __name__ == "__main__":
    unittest.main()
