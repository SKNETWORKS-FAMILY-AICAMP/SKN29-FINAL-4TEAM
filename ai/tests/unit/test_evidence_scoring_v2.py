from __future__ import annotations

import unittest

from ai.evaluation.evidence_scoring_v2 import (
    LEGACY_SCORING_CONTRACT_VERSION,
    SCORING_CONTRACT_VERSION,
    score_evidence_case_v2,
    score_gold_case,
    score_legacy_gold_case_v1,
)


MODEL = "WPUJAC104DWH"
OTHER_MODEL = "WPUIAC425SNW"


def group(group_id: str, *child_ids: str, model: str = MODEL) -> dict[str, object]:
    return {
        "evidence_group_id": group_id,
        "child_ids": list(child_ids),
        "exact_sales_code": model,
    }


GROUPS = [
    group("EVD-A", "CHILD-A1", "CHILD-A2"),
    group("EVD-B", "CHILD-B1"),
    group("EVD-SUPPORT", "CHILD-S1"),
]


def corpus_row(
    child_id: str,
    *,
    model: str = MODEL,
    retrieval_role: str = "SEARCH_CANDIDATE",
    allowed_use: str = "EXPERIMENT_ONLY",
    verification_status: str = "TEXT_AND_VISUAL_VERIFIED",
    record_type: str = "CHILD",
    document_id: str = "DOC-A",
) -> dict[str, object]:
    return {
        "chunk_id": f"CORPUS-{child_id}",
        "source_record_id": child_id,
        "record_type": record_type,
        "document_id": document_id,
        "exact_sales_code": model,
        "retrieval_role": retrieval_role,
        "allowed_use": allowed_use,
        "source_verification_status": verification_status,
    }


def evidence_case(
    *,
    required: list[str] | None = None,
    supporting: list[str] | None = None,
    policy: str = "ANY",
) -> dict[str, object]:
    return {
        "product_model_code": MODEL,
        "expected_retrieval_outcome": "EVIDENCE",
        "expected_execution_path": "PGVECTOR_QUERY",
        "required_evidence_group_ids": required or ["EVD-A"],
        "supporting_evidence_group_ids": supporting or [],
        "evidence_match_policy": policy,
        "forbidden_document_ids": [],
        "forbidden_model_codes": [OTHER_MODEL],
    }


def no_evidence_case(expected_path: str = "PGVECTOR_QUERY") -> dict[str, object]:
    return {
        "product_model_code": MODEL,
        "expected_retrieval_outcome": "NO_EVIDENCE",
        "expected_execution_path": expected_path,
        "required_evidence_group_ids": [],
        "supporting_evidence_group_ids": [],
        "evidence_match_policy": "NONE",
        "forbidden_document_ids": [],
        "forbidden_model_codes": [OTHER_MODEL],
    }


class EvidenceScoringV2Tests(unittest.TestCase):
    def test_shared_entrypoint_dispatches_v2_and_requires_registry(self) -> None:
        result = score_gold_case(
            evidence_case(),
            [corpus_row("CHILD-A1")],
            evidence_groups=GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertEqual(result["scoring_contract_version"], SCORING_CONTRACT_VERSION)
        self.assertTrue(result["passed"])
        with self.assertRaisesRegex(ValueError, "Registry"):
            score_gold_case(
                evidence_case(),
                [],
                actual_execution_path="PGVECTOR_QUERY",
                vector_query_count=1,
            )

    def test_same_group_variants_do_not_complete_all_twice(self) -> None:
        result = score_evidence_case_v2(
            evidence_case(required=["EVD-A", "EVD-B"], policy="ALL"),
            [corpus_row("CHILD-A1"), corpus_row("CHILD-A2")],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertEqual(result["scoring_contract_version"], SCORING_CONTRACT_VERSION)
        self.assertEqual(result["covered_required_group_ids"], ["EVD-A"])
        self.assertEqual(result["missing_required_group_ids"], ["EVD-B"])
        self.assertEqual(
            result["matched_variant_child_ids"], ["CHILD-A1", "CHILD-A2"]
        )
        self.assertEqual(result["recall_at_5"], 0.5)
        self.assertEqual(result["hit_at_5"], 0.0)
        self.assertIsNone(result["required_completion_rank"])
        self.assertFalse(result["passed"])

    def test_all_completion_ignores_supporting_and_duplicate_variant(self) -> None:
        result = score_evidence_case_v2(
            evidence_case(
                required=["EVD-A", "EVD-B"],
                supporting=["EVD-SUPPORT"],
                policy="ALL",
            ),
            [
                corpus_row("CHILD-S1"),
                corpus_row("CHILD-A1"),
                corpus_row("CHILD-A2"),
                corpus_row("CHILD-B1"),
            ],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertEqual(result["covered_supporting_group_ids"], ["EVD-SUPPORT"])
        self.assertEqual(result["hit_at_1"], 0.0)
        self.assertEqual(result["hit_at_3"], 0.0)
        self.assertEqual(result["hit_at_5"], 1.0)
        self.assertEqual(result["required_completion_rank"], 4)
        self.assertEqual(result["mrr"], 0.25)
        self.assertTrue(result["passed"])

    def test_supporting_only_is_diagnostic_and_does_not_pass(self) -> None:
        result = score_evidence_case_v2(
            evidence_case(supporting=["EVD-SUPPORT"]),
            [corpus_row("CHILD-S1")],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertEqual(result["covered_required_group_ids"], [])
        self.assertEqual(result["covered_supporting_group_ids"], ["EVD-SUPPORT"])
        self.assertFalse(result["semantic_passed"])
        self.assertFalse(result["passed"])

    def test_product_role_allowed_use_and_verification_are_top_k_gates(self) -> None:
        result = score_evidence_case_v2(
            evidence_case(),
            [
                corpus_row("CHILD-A1", model=OTHER_MODEL),
                corpus_row("CHILD-A1", retrieval_role="CONTEXT_ONLY"),
                corpus_row("CHILD-A1", allowed_use="RAG_HANDOFF_ONLY"),
                corpus_row("CHILD-A1", verification_status="TEXT_EXTRACTED"),
                corpus_row("CHILD-A2"),
            ],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertEqual(result["covered_required_group_ids"], ["EVD-A"])
        self.assertEqual(result["required_completion_rank"], 5)
        self.assertEqual(result["wrong_product_hit_count"], 1)
        self.assertEqual(result["non_search_candidate_hit_count"], 1)
        self.assertEqual(result["disallowed_use_hit_count"], 1)
        self.assertEqual(result["unverified_hit_count"], 1)
        self.assertEqual(result["invalid_top_k_hit_count"], 4)
        self.assertTrue(result["semantic_passed"])
        self.assertFalse(result["passed"])

    def test_parent_and_noncanonical_child_id_fallback_cannot_match(self) -> None:
        parent = corpus_row("CHILD-A1", record_type="PARENT")
        fallback = corpus_row("UNRELATED")
        fallback["chunk_id"] = "CHILD-A1"
        fallback["child_id"] = "CHILD-A1"

        result = score_evidence_case_v2(
            evidence_case(),
            [parent, fallback],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertEqual(result["covered_required_group_ids"], [])
        self.assertEqual(result["non_child_hit_count"], 1)
        self.assertEqual(result["invalid_top_k_hit_count"], 1)
        self.assertFalse(result["passed"])

    def test_forbidden_document_or_model_hit_fails_case(self) -> None:
        case = evidence_case()
        case["forbidden_document_ids"] = ["DOC-FORBIDDEN"]
        rows = [
            corpus_row("UNRELATED", document_id="DOC-FORBIDDEN"),
            corpus_row("CHILD-A1"),
        ]

        result = score_evidence_case_v2(
            case,
            rows,
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertTrue(result["semantic_passed"])
        self.assertEqual(result["forbidden_document_hit_count"], 1)
        self.assertEqual(result["forbidden_model_hit_count"], 0)
        self.assertFalse(result["passed"])

    def test_allowed_use_values_are_explicit_strings(self) -> None:
        handoff_row = corpus_row("CHILD-A1", allowed_use="RAG_HANDOFF_ONLY")
        default_result = score_evidence_case_v2(
            evidence_case(),
            [handoff_row],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )
        handoff_result = score_evidence_case_v2(
            evidence_case(),
            [handoff_row],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
            allowed_use_values={"RAG_HANDOFF_ONLY"},
        )

        self.assertFalse(default_result["passed"])
        self.assertTrue(handoff_result["passed"])

    def test_evidence_requires_pgvector_path_query_and_top_k_completion(self) -> None:
        rows = [corpus_row("UNRELATED") for _ in range(5)] + [corpus_row("CHILD-A1")]
        default_top_k = score_evidence_case_v2(
            evidence_case(),
            rows,
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )
        top_six = score_evidence_case_v2(
            evidence_case(),
            rows,
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
            evaluation_top_k=6,
        )
        no_query = score_evidence_case_v2(
            evidence_case(),
            [corpus_row("CHILD-A1")],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=0,
        )

        self.assertIsNone(default_top_k["required_completion_rank"])
        self.assertEqual(default_top_k["missing_required_group_ids"], ["EVD-A"])
        self.assertFalse(default_top_k["passed"])
        self.assertTrue(top_six["passed"])
        self.assertFalse(no_query["execution_contract_passed"])
        self.assertFalse(no_query["passed"])

    def test_corpus_absence_requires_query_and_empty_ranked_results(self) -> None:
        passed = score_evidence_case_v2(
            no_evidence_case(),
            [],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )
        no_query = score_evidence_case_v2(
            no_evidence_case(),
            [],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=0,
        )
        non_empty = score_evidence_case_v2(
            no_evidence_case(),
            [corpus_row("CHILD-A1")],
            GROUPS,
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertTrue(passed["no_evidence_success"])
        self.assertTrue(passed["passed"])
        for metric in ("hit_at_1", "hit_at_3", "hit_at_5", "recall_at_5", "mrr"):
            self.assertIsNone(passed[metric])
        self.assertFalse(no_query["passed"])
        self.assertFalse(non_empty["passed"])

    def test_policy_block_requires_exact_path_zero_queries_and_empty_results(self) -> None:
        case = no_evidence_case("POLICY_BLOCK_UNVERIFIED_SOURCE")
        passed = score_evidence_case_v2(
            case,
            [],
            GROUPS,
            actual_execution_path="POLICY_BLOCK_UNVERIFIED_SOURCE",
            vector_query_count=0,
        )
        wrong_reason = score_evidence_case_v2(
            case,
            [],
            GROUPS,
            actual_execution_path="POLICY_BLOCK_UNSUPPORTED_MODEL",
            vector_query_count=0,
        )
        queried = score_evidence_case_v2(
            case,
            [],
            GROUPS,
            actual_execution_path="POLICY_BLOCK_UNVERIFIED_SOURCE",
            vector_query_count=1,
        )

        self.assertTrue(passed["policy_block_success"])
        self.assertTrue(passed["passed"])
        self.assertFalse(wrong_reason["passed"])
        self.assertFalse(queried["passed"])

    def test_registry_rejects_child_owned_by_two_groups(self) -> None:
        duplicate_registry = [
            group("EVD-A", "SHARED"),
            group("EVD-B", "SHARED"),
        ]

        with self.assertRaisesRegex(ValueError, "둘 이상의 Evidence Group"):
            score_evidence_case_v2(
                evidence_case(),
                [],
                duplicate_registry,
                actual_execution_path="PGVECTOR_QUERY",
                vector_query_count=1,
            )

    def test_v2_rejects_missing_group_and_required_supporting_overlap(self) -> None:
        with self.assertRaisesRegex(ValueError, "Registry에 없는"):
            score_evidence_case_v2(
                evidence_case(required=["EVD-MISSING"]),
                [],
                GROUPS,
                actual_execution_path="PGVECTOR_QUERY",
                vector_query_count=1,
            )
        with self.assertRaisesRegex(ValueError, "중복될 수 없습니다"):
            score_evidence_case_v2(
                evidence_case(required=["EVD-A"], supporting=["EVD-A"]),
                [],
                GROUPS,
                actual_execution_path="PGVECTOR_QUERY",
                vector_query_count=1,
            )


class LegacyGoldV1AdapterTests(unittest.TestCase):
    @staticmethod
    def case(policy: str = "ANY", expected_no_evidence: bool = False) -> dict[str, object]:
        expected = [] if expected_no_evidence else [
            {
                "evidence_unit_id": "EVD-LEGACY-A",
                "document_id": "DOC-A",
                "page_refs": [5, 7],
            }
        ]
        return {
            "product_model_code": MODEL,
            "expected_evidence": expected,
            "expected_no_evidence": expected_no_evidence,
            "evidence_match_policy": policy,
        }

    @staticmethod
    def row(
        *,
        evidence_id: str = "EVD-LEGACY-A",
        document_id: str = "DOC-A",
        page: int = 5,
    ) -> dict[str, object]:
        return {
            "evidence_unit_ids": [evidence_id],
            "document_id": document_id,
            "page_refs": [page],
            "exact_sales_code": MODEL,
            # Deliberately TEXT_EXTRACTED: legacy adapter must not add v2 gate.
            "source_verification_status": "TEXT_EXTRACTED",
        }

    def test_legacy_requires_unit_document_and_page_overlap(self) -> None:
        matching = score_legacy_gold_case_v1(self.case(), [self.row()])
        wrong_document = score_legacy_gold_case_v1(
            self.case(), [self.row(document_id="DOC-B")]
        )
        wrong_page = score_legacy_gold_case_v1(self.case(), [self.row(page=6)])
        wrong_id = score_legacy_gold_case_v1(
            self.case(), [self.row(evidence_id="EVD-OTHER")]
        )

        self.assertEqual(
            matching["scoring_contract_version"], LEGACY_SCORING_CONTRACT_VERSION
        )
        self.assertTrue(
            {
                "evidence_match_policy",
                "required_evidence_unit_ids",
                "covered_evidence_unit_ids",
                "hit_at_1",
                "hit_at_3",
                "hit_at_5",
                "mrr",
                "ndcg_at_5",
                "first_matched_rank",
                "evidence_completion_rank",
                "first_relevant_rank",
                "wrong_product_hit_count",
                "no_evidence_retrieval_empty",
                "no_evidence_passed",
                "answerability_gate_passed",
            }.issubset(matching)
        )
        self.assertTrue(matching["passed"])
        self.assertEqual(matching["mrr"], 1.0)
        self.assertFalse(wrong_document["passed"])
        self.assertFalse(wrong_page["passed"])
        self.assertFalse(wrong_id["passed"])

    def test_shared_entrypoint_dispatches_legacy_without_v2_registry(self) -> None:
        result = score_gold_case(
            self.case(),
            [self.row()],
            actual_execution_path="PGVECTOR_QUERY",
            vector_query_count=1,
        )

        self.assertEqual(
            result["scoring_contract_version"], LEGACY_SCORING_CONTRACT_VERSION
        )
        self.assertTrue(result["passed"])

        ambiguous = {**self.case(), **evidence_case()}
        with self.assertRaisesRegex(ValueError, "함께 사용할 수 없습니다"):
            score_gold_case(
                ambiguous,
                [],
                evidence_groups=GROUPS,
                actual_execution_path="PGVECTOR_QUERY",
                vector_query_count=1,
            )

    def test_legacy_all_and_none_semantics_are_preserved(self) -> None:
        all_case = self.case(policy="ALL")
        all_case["expected_evidence"] = [
            *all_case["expected_evidence"],
            {
                "evidence_unit_id": "EVD-LEGACY-B",
                "document_id": "DOC-B",
                "page_refs": [8],
            },
        ]
        first_only = score_legacy_gold_case_v1(all_case, [self.row()])
        completed = score_legacy_gold_case_v1(
            all_case,
            [
                self.row(),
                self.row(
                    evidence_id="EVD-LEGACY-B", document_id="DOC-B", page=8
                ),
            ],
        )
        none_case = self.case(policy="NONE", expected_no_evidence=True)
        none_empty = score_legacy_gold_case_v1(none_case, [])
        none_non_empty = score_legacy_gold_case_v1(none_case, [self.row()])

        self.assertFalse(first_only["passed"])
        self.assertTrue(completed["passed"])
        self.assertEqual(completed["required_completion_rank"], 2)
        self.assertEqual(none_empty["mrr"], 0.0)
        self.assertEqual(none_empty["hit_at_5"], 0.0)
        self.assertTrue(none_empty["no_evidence_retrieval_empty"])
        self.assertTrue(none_empty["no_evidence_passed"])
        self.assertTrue(none_empty["passed"])
        self.assertFalse(none_non_empty["passed"])


if __name__ == "__main__":
    unittest.main()
