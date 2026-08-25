from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.scripts.validate_gold_corpus_compatibility_v2 import (
    build_compatibility_report,
    main,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


class GoldCorpusCompatibilityV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.gold_path = root / "gold.jsonl"
        self.groups_path = root / "groups.jsonl"
        self.children_path = root / "children.jsonl"
        self.corpus_path = root / "corpus.jsonl"

        self.gold = [
            {
                "case_id": "RAGV2-GOLD-0001",
                "evaluation_status": "ACTIVE",
                "product_model_code": "MODEL-A",
                "expected_retrieval_outcome": "EVIDENCE",
                "expected_execution_path": "PGVECTOR_QUERY",
                "required_evidence_group_ids": ["EVD-MODELA-A-001"],
                "supporting_evidence_group_ids": ["EVD-MODELA-S-001"],
                "evidence_match_policy": "ANY",
            },
            {
                "case_id": "RAGV2-GOLD-0002",
                "evaluation_status": "ACTIVE",
                "product_model_code": "MODEL-A",
                "expected_retrieval_outcome": "NO_EVIDENCE",
                "expected_execution_path": "POLICY_BLOCK_UNVERIFIED_SOURCE",
                "required_evidence_group_ids": [],
                "supporting_evidence_group_ids": [],
                "evidence_match_policy": "NONE",
            },
            {
                "case_id": "RAGV2-GOLD-0040",
                "evaluation_status": "EXCLUDED",
                "product_model_code": "MODEL-A",
                "expected_retrieval_outcome": "EVIDENCE",
                "expected_execution_path": "PGVECTOR_QUERY",
                "required_evidence_group_ids": [],
                "supporting_evidence_group_ids": [],
                "evidence_match_policy": "ANY",
            },
        ]
        self.groups = [
            {
                "schema_version": "2.0.0-draft.1",
                "evidence_group_id": "EVD-MODELA-A-001",
                "topic_code": "TOPIC_A",
                "exact_sales_code": "MODEL-A",
                "document_id": "DOC-A",
                "page_refs": [4, 5],
                "child_ids": ["CHILD-A1", "CHILD-A2"],
                "source_variant_ids": ["VAR-A1", "VAR-A2"],
                "consultation_conditions": [],
                "mapping_action": "REUSE_EXISTING_GROUP",
                "supersedes_group_id": None,
                "activation_gates": ["CORPUS_V3_LINKED"],
            },
            {
                "schema_version": "2.0.0-draft.1",
                "evidence_group_id": "EVD-MODELA-S-001",
                "topic_code": "TOPIC_S",
                "exact_sales_code": "MODEL-A",
                "document_id": "DOC-A",
                "page_refs": [6],
                "child_ids": ["CHILD-S1"],
                "source_variant_ids": ["VAR-S1"],
                "consultation_conditions": [],
                "mapping_action": "REUSE_EXISTING_GROUP",
                "supersedes_group_id": None,
                "activation_gates": ["CORPUS_V3_LINKED"],
            },
        ]
        self.children = [
            self._child("CHILD-A1", "EVD-MODELA-A-001", "VAR-A1", [4]),
            self._child("CHILD-A2", "EVD-MODELA-A-001", "VAR-A2", [5]),
            self._child("CHILD-S1", "EVD-MODELA-S-001", "VAR-S1", [6]),
        ]
        self.corpus = [self._corpus(child) for child in self.children]

    def tearDown(self) -> None:
        self.directory.cleanup()

    @staticmethod
    def _child(
        child_id: str,
        group_id: str,
        variant_id: str,
        page_refs: list[int],
    ) -> dict[str, object]:
        return {
            "child_id": child_id,
            "evidence_group_id": group_id,
            "source_variant_id": variant_id,
            "exact_sales_code": "MODEL-A",
            "document_id": "DOC-A",
            "page_refs": page_refs,
            "record_type": "child",
            "retrieval_role": "SEARCH_CANDIDATE",
            "allowed_use": "RAG_HANDOFF_ONLY",
            "verification_status": "TEXT_AND_VISUAL_VERIFIED",
            "source_file_sha256": "A" * 64,
            "child_text_sha256": "B" * 64,
        }

    @staticmethod
    def _corpus(child: dict[str, object]) -> dict[str, object]:
        return {
            "chunk_id": child["child_id"],
            "source_record_id": child["child_id"],
            "evidence_unit_ids": [child["evidence_group_id"]],
            "source_variant_id": child["source_variant_id"],
            "exact_sales_code": child["exact_sales_code"],
            "document_id": child["document_id"],
            "page_refs": child["page_refs"],
            "record_type": "CHILD",
            "retrieval_role": "SEARCH_CANDIDATE",
            "allowed_use": "EXPERIMENT_ONLY",
            "source_verification_status": "TEXT_AND_VISUAL_VERIFIED",
            "source_file_sha256": child["source_file_sha256"],
            "text_sha256": child["child_text_sha256"],
        }

    def _report(
        self,
        *,
        gold: list[dict[str, object]] | None = None,
        groups: list[dict[str, object]] | None = None,
        children: list[dict[str, object]] | None = None,
        corpus: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        _write_jsonl(self.gold_path, self.gold if gold is None else gold)
        _write_jsonl(self.groups_path, self.groups if groups is None else groups)
        _write_jsonl(self.children_path, self.children if children is None else children)
        _write_jsonl(self.corpus_path, self.corpus if corpus is None else corpus)
        return build_compatibility_report(
            self.gold_path,
            self.groups_path,
            self.children_path,
            self.corpus_path,
        )

    @staticmethod
    def _codes(report: dict[str, object]) -> set[str]:
        return set(report["error_code_counts"])

    def test_passes_with_one_search_candidate_from_required_group(self) -> None:
        report = self._report()

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["counts"]["active_cases"], 2)
        self.assertEqual(report["counts"]["linked_required_groups"], 1)
        self.assertEqual(report["counts"]["linked_supporting_groups"], 1)
        self.assertEqual(report["counts"]["linked_evidence_groups"], 2)
        self.assertEqual(report["counts"]["linked_group_children"], 3)
        self.assertEqual(report["errors"], [])

    def test_unreferenced_registry_group_still_requires_child_corpus_link(self) -> None:
        groups = copy.deepcopy(self.groups)
        candidate_group = copy.deepcopy(groups[0])
        candidate_group.update({
            "evidence_group_id": "EVD-MODELA-CANDIDATE-001",
            "topic_code": "CANDIDATE",
            "page_refs": [7],
            "child_ids": ["CHILD-C1"],
            "source_variant_ids": ["VAR-C1"],
        })
        groups.append(candidate_group)
        children = copy.deepcopy(self.children)
        children.append(
            self._child(
                "CHILD-C1",
                "EVD-MODELA-CANDIDATE-001",
                "VAR-C1",
                [7],
            )
        )

        report = self._report(groups=groups, children=children)

        self.assertIn("GROUP_CHILD_CORPUS_LINK_MISSING", self._codes(report))
        self.assertEqual(report["counts"]["evidence_group_rows"], 3)
        self.assertEqual(report["counts"]["linked_evidence_groups"], 2)

    def test_orphan_child_cannot_point_to_an_unknown_group(self) -> None:
        children = copy.deepcopy(self.children)
        children.append(
            self._child("CHILD-ORPHAN", "EVD-MODELA-UNKNOWN-001", "VAR-O1", [7])
        )

        report = self._report(children=children)

        self.assertIn("CHILD_GROUP_NOT_FOUND", self._codes(report))

    def test_every_declared_group_child_must_link_to_corpus(self) -> None:
        report = self._report(corpus=self.corpus[:1] + self.corpus[2:])

        self.assertIn("GROUP_CHILD_CORPUS_LINK_MISSING", self._codes(report))
        self.assertEqual(report["counts"]["linked_group_children"], 2)

    def test_child_and_corpus_approval_metadata_are_fail_closed(self) -> None:
        children = copy.deepcopy(self.children)
        children[0]["allowed_use"] = "PUBLIC_RUNTIME"
        children[0]["verification_status"] = "TEXT_EXTRACTED"
        corpus = copy.deepcopy(self.corpus)
        corpus[0]["allowed_use"] = "RAG_HANDOFF_ONLY"
        corpus[0]["source_verification_status"] = "TEXT_EXTRACTED"

        report = self._report(children=children, corpus=corpus)

        self.assertTrue(
            {
                "CHILD_ALLOWED_USE_INVALID",
                "CHILD_VERIFICATION_STATUS_INVALID",
                "CORPUS_ALLOWED_USE_INVALID",
                "CORPUS_VERIFICATION_STATUS_INVALID",
            }.issubset(self._codes(report))
        )

    def test_child_text_hash_must_match_corpus_text_hash(self) -> None:
        corpus = copy.deepcopy(self.corpus)
        corpus[0]["text_sha256"] = "C" * 64

        report = self._report(corpus=corpus)

        self.assertIn("CORPUS_CHILD_TEXT_SHA256_MISMATCH", self._codes(report))

    def test_supporting_only_positive_and_no_evidence_groups_are_blocked(self) -> None:
        gold = copy.deepcopy(self.gold)
        gold[0]["required_evidence_group_ids"] = []
        gold[1]["required_evidence_group_ids"] = ["EVD-MODELA-A-001"]
        gold[1]["evidence_match_policy"] = "ANY"

        report = self._report(gold=gold)

        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            {
                "GOLD_SUPPORTING_ONLY_POSITIVE",
                "GOLD_NO_EVIDENCE_GROUPS_NOT_EMPTY",
                "GOLD_NO_EVIDENCE_MATCH_POLICY_INVALID",
            }.issubset(self._codes(report))
        )

    def test_consultation_condition_must_resolve_through_referenced_group(self) -> None:
        gold = copy.deepcopy(self.gold)
        gold[0]["consultation_condition_ids"] = ["COND-SYMPTOM-PERSISTS-001"]
        groups = copy.deepcopy(self.groups)
        groups[0]["consultation_conditions"] = [
            {
                "condition_id": "COND-SYMPTOM-PERSISTS-001",
                "trigger_type": "PERSISTENCE",
                "source_child_ids": ["CHILD-A1"],
                "source_page_refs": [4],
            }
        ]

        passed = self._report(gold=gold, groups=groups)
        groups[0]["consultation_conditions"] = []
        missing = self._report(gold=gold, groups=groups)

        self.assertEqual(passed["status"], "PASS")
        self.assertEqual(passed["counts"]["referenced_conditions"], 1)
        self.assertIn("GOLD_CONDITION_NOT_FOUND", self._codes(missing))

    def test_group_registry_rows_must_match_canonical_schema(self) -> None:
        missing_required = copy.deepcopy(self.groups)
        del missing_required[0]["schema_version"]
        unexpected_field = copy.deepcopy(self.groups)
        unexpected_field[0]["unreviewed_extension"] = True

        for groups in (missing_required, unexpected_field):
            with self.subTest(groups=groups):
                report = self._report(groups=groups)
                self.assertIn(
                    "GROUP_SCHEMA_VALIDATION_ERROR", self._codes(report)
                )

    def test_condition_pages_must_belong_to_selected_source_children(self) -> None:
        groups = copy.deepcopy(self.groups)
        groups[0]["consultation_conditions"] = [
            {
                "condition_id": "COND-SYMPTOM-PERSISTS-001",
                "trigger_type": "PERSISTENCE",
                "source_child_ids": ["CHILD-A1"],
                "source_page_refs": [5],
            }
        ]

        report = self._report(groups=groups)

        self.assertIn("GROUP_CONDITION_PAGE_LINEAGE_INVALID", self._codes(report))

    def test_group_product_and_child_variant_cardinality_are_exact(self) -> None:
        groups = copy.deepcopy(self.groups)
        groups[0]["exact_sales_code"] = "MODEL-B"
        groups[0]["source_variant_ids"] = ["VAR-A1"]

        report = self._report(groups=groups)

        self.assertTrue(
            {
                "GOLD_GROUP_PRODUCT_MISMATCH",
                "GROUP_CHILD_VARIANT_CARDINALITY_MISMATCH",
                "CHILD_PRODUCT_LINEAGE_MISMATCH",
                "CHILD_SOURCE_VARIANT_LINEAGE_MISMATCH",
                "GROUP_CHILD_SOURCE_VARIANT_COVERAGE_MISMATCH",
            }.issubset(self._codes(report))
        )

    def test_gold_cannot_require_or_support_a_forbidden_group_source(self) -> None:
        forbidden_document = copy.deepcopy(self.gold)
        forbidden_document[0]["forbidden_document_ids"] = ["DOC-A"]
        forbidden_model = copy.deepcopy(self.gold)
        forbidden_model[0]["forbidden_model_codes"] = ["MODEL-A"]

        cases = (
            (forbidden_document, "GOLD_GROUP_DOCUMENT_FORBIDDEN"),
            (forbidden_model, "GOLD_GROUP_MODEL_FORBIDDEN"),
        )
        for gold, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                report = self._report(gold=gold)
                self.assertIn(expected_code, self._codes(report))

    def test_child_group_product_document_and_page_lineage_are_checked(self) -> None:
        children = copy.deepcopy(self.children)
        children[0]["evidence_group_id"] = "EVD-OTHER"
        children[0]["exact_sales_code"] = "MODEL-B"
        children[0]["document_id"] = "DOC-B"
        children[0]["page_refs"] = [99]

        report = self._report(children=children)

        self.assertTrue(
            {
                "CHILD_GROUP_LINEAGE_MISMATCH",
                "CHILD_PRODUCT_LINEAGE_MISMATCH",
                "CHILD_DOCUMENT_LINEAGE_MISMATCH",
                "CHILD_PAGE_LINEAGE_MISMATCH",
            }.issubset(self._codes(report))
        )

    def test_undeclared_child_pointing_to_referenced_group_is_blocked(self) -> None:
        children = copy.deepcopy(self.children)
        children.append(
            self._child("CHILD-A3", "EVD-MODELA-A-001", "VAR-A3", [4])
        )

        report = self._report(children=children)

        self.assertIn("GROUP_UNDECLARED_CHILD_REFERENCE", self._codes(report))

    def test_parent_or_preservation_cannot_satisfy_required_group(self) -> None:
        for record_type in ("PARENT", "PRESERVATION"):
            with self.subTest(record_type=record_type):
                corpus = copy.deepcopy(self.corpus)
                corpus[0]["record_type"] = record_type
                corpus[1]["record_type"] = record_type

                report = self._report(corpus=corpus)

                self.assertIn(
                    "CORPUS_NON_CHILD_CANNOT_SATISFY_GROUP", self._codes(report)
                )
                self.assertIn(
                    "REQUIRED_GROUP_SEARCH_CANDIDATE_MISSING", self._codes(report)
                )

    def test_corpus_requires_exact_child_group_product_document_page_lineage(self) -> None:
        corpus = copy.deepcopy(self.corpus)
        for row in corpus[:2]:
            row["evidence_unit_ids"] = ["EVD-OTHER"]
            row["exact_sales_code"] = "MODEL-B"
            row["document_id"] = "DOC-B"
            row["page_refs"] = [99]

        report = self._report(corpus=corpus)

        self.assertTrue(
            {
                "CORPUS_GROUP_LINK_MISSING",
                "CORPUS_PRODUCT_LINEAGE_MISMATCH",
                "CORPUS_DOCUMENT_LINEAGE_MISMATCH",
                "CORPUS_PAGE_LINEAGE_MISMATCH",
                "REQUIRED_GROUP_SEARCH_CANDIDATE_MISSING",
            }.issubset(self._codes(report))
        )

    def test_referenced_group_cannot_be_attached_to_unregistered_corpus_record(self) -> None:
        corpus = copy.deepcopy(self.corpus)
        corpus.append(
            {
                **copy.deepcopy(corpus[0]),
                "chunk_id": "SOURCE-PAGE-A",
                "source_record_id": "SOURCE-PAGE-A",
                "record_type": "SOURCE_PAGE",
            }
        )

        report = self._report(corpus=corpus)

        self.assertIn(
            "CORPUS_GROUP_ATTACHED_TO_UNREGISTERED_CHILD", self._codes(report)
        )

    def test_rejected_case_is_not_an_active_compatibility_input(self) -> None:
        gold = copy.deepcopy(self.gold)
        gold[0]["evaluation_status"] = "REJECTED"

        report = self._report(gold=gold)

        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["counts"]["active_cases"], 1)
        self.assertEqual(report["counts"]["referenced_required_groups"], 0)

    def test_duplicate_group_child_and_corpus_identifiers_are_blocked(self) -> None:
        groups = [*copy.deepcopy(self.groups), copy.deepcopy(self.groups[0])]
        children = [*copy.deepcopy(self.children), copy.deepcopy(self.children[0])]
        corpus = [*copy.deepcopy(self.corpus), copy.deepcopy(self.corpus[0])]

        report = self._report(groups=groups, children=children, corpus=corpus)

        self.assertTrue(
            {
                "DUPLICATE_EVIDENCE_GROUP_ID",
                "DUPLICATE_CHILD_ID",
                "DUPLICATE_CORPUS_CHUNK_ID",
                "DUPLICATE_CORPUS_SOURCE_RECORD_ID",
            }.issubset(self._codes(report))
        )

    def test_cli_prints_only_status_counts_and_error_codes(self) -> None:
        self._report()
        stdout = io.StringIO()
        argv = [
            "validate_gold_corpus_compatibility_v2.py",
            "--gold",
            str(self.gold_path),
            "--evidence-groups",
            str(self.groups_path),
            "--children",
            str(self.children_path),
            "--corpus",
            str(self.corpus_path),
        ]

        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as exit_context:
                main()

        self.assertEqual(exit_context.exception.code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(set(payload), {"status", "counts", "error_code_counts"})
        self.assertNotIn("EVD-MODELA-A-001", stdout.getvalue())
        self.assertNotIn(str(self.gold_path), stdout.getvalue())

    def test_cli_failure_uses_exit_one_without_identifier_or_path_values(self) -> None:
        corpus = copy.deepcopy(self.corpus)
        corpus[0]["record_type"] = "PRESERVATION"
        self._report(corpus=corpus)
        stdout = io.StringIO()
        argv = [
            "validate_gold_corpus_compatibility_v2.py",
            "--gold",
            str(self.gold_path),
            "--evidence-groups",
            str(self.groups_path),
            "--children",
            str(self.children_path),
            "--corpus",
            str(self.corpus_path),
        ]

        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as exit_context:
                main()

        self.assertEqual(exit_context.exception.code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "FAIL")
        self.assertIn(
            "CORPUS_NON_CHILD_CANNOT_SATISFY_GROUP",
            payload["error_code_counts"],
        )
        self.assertEqual(set(payload), {"status", "counts", "error_code_counts"})
        self.assertNotIn("EVD-MODELA-A-001", stdout.getvalue())
        self.assertNotIn("CHILD-A1", stdout.getvalue())
        self.assertNotIn(str(self.corpus_path), stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
