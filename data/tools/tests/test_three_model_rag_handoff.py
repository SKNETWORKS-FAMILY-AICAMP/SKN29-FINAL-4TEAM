from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from data.tools.rag_experiments.build_three_model_handoff import build
from data.tools.rag_experiments.qa_three_model_handoff import build_qa_report


REPO_ROOT = Path(__file__).resolve().parents[3]


class ThreeModelRagHandoffTests(unittest.TestCase):
    @staticmethod
    def _canonical_children() -> list[dict[str, object]]:
        path = (
            REPO_ROOT
            / "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
        )
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

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
        self.assertEqual(50, report["counts"]["cases"])
        self.assertEqual(7, report["counts"]["negative_cases"])

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

    def test_acceptance_uses_one_verified_variant_per_expected_group(self) -> None:
        document = json.loads(
            (REPO_ROOT / "data/config/rag/three_model_evaluation_cases.json").read_text(encoding="utf-8")
        )
        acceptance = document["retrieval_acceptance"]
        self.assertEqual("RAG-EVAL-GROUP-TOP5-001", acceptance["positive_rule_id"])
        self.assertEqual(
            "AT_LEAST_ONE_VERIFIED_VARIANT_PER_EXPECTED_GROUP",
            acceptance["positive_match_mode"],
        )
        self.assertEqual(5, acceptance["positive_top_k"])
        self.assertEqual(
            "TEXT_AND_VISUAL_VERIFIED",
            acceptance["required_variant_verification_status"],
        )

    def test_unregistered_model_negative_case_is_preserved(self) -> None:
        document = json.loads(
            (REPO_ROOT / "data/config/rag/three_model_evaluation_cases.json").read_text(encoding="utf-8")
        )
        negatives = [row for row in document["cases"] if row["case_type"] == "NEGATIVE"]
        self.assertEqual(7, len(negatives))
        case = next(row for row in negatives if row["case_id"] == "RAG3-NEG-007")
        self.assertEqual("WPUIAC999ZZZ", case["exact_sales_code"])
        self.assertEqual("UNREGISTERED_EXACT_SALES_CODE", case["negative_reason"])
        self.assertTrue(case["expected_no_evidence"])

    def test_page_references_are_not_split_across_safe_actions(self) -> None:
        children = {row["child_id"]: row for row in self._canonical_children()}
        expected = {
            "CHILD-WPUIAC425SNW-P045-NO-ICE-001": (
                "방열팬 덮개 막힘 (먼지에 의한 막힘) - 청소하기 페이지 확인 후 "
                "방열팬 덮개를 청소해 주세요 (청소하기 p.41 참고)."
            ),
            "CHILD-WPUIAC606SNW-P040-NOISE-VENTILATION-001": (
                "방열팬 덮개 막힘 (먼지에 의한 막힘) - 청소하기 페이지 확인 후 "
                "방열팬 덮개를 청소해 주세요 (청소하기 p.36 참고)."
            ),
            "CHILD-WPUIAC606SNW-P042-NO-ICE-001": (
                "방열팬 덮개 막힘 (먼지에 의한 막힘) - 청소하기 페이지 확인 후 "
                "방열팬 덮개를 청소해 주세요 (청소하기 p.36 참고)."
            ),
        }
        for child_id, action in expected.items():
            self.assertIn(action, children[child_id]["safe_actions"], child_id)
            self.assertFalse(
                any(item.endswith(" p.") for item in children[child_id]["safe_actions"]),
                child_id,
            )

        for child_id in (
            "CHILD-WPUIAC425SNW-P045-NO-ICE-001",
            "CHILD-WPUIAC606SNW-P042-NO-ICE-001",
        ):
            self.assertIn(
                "배수 호스가 꺾이거나 수돗물이 얼진 않았는지 확인해 주세요.",
                children[child_id]["safe_actions"],
                child_id,
            )

        for child in children.values():
            for action in child["safe_actions"]:
                self.assertFalse(
                    action.startswith("(") and " p." in action,
                    child["child_id"],
                )


if __name__ == "__main__":
    unittest.main()
