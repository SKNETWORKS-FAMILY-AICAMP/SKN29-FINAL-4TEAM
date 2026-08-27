from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ai.evaluation.file_integrity import file_sha256
from ai.scripts.run_full_corpus_baseline_v2 import (
    LOCAL_DENSE_QUERY,
    LOCAL_POLICY_SIMULATION,
    REPOSITORY_ROOT,
    build_preflight_report,
    run_baseline,
)


CORPUS_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/rag/experimental/full_corpus_chunks_v3.jsonl"
)
CHILDREN_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/rag/experimental/full_corpus_v3_children.jsonl"
)
HANDOFF_MANIFEST_PATH = (
    REPOSITORY_ROOT / "data/processed/metadata/full_corpus_v3_handoff_manifest.json"
)
REGISTRY_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/datasets/gold/full_corpus_v3_evidence_groups_gold_v2.jsonl"
)
REGISTRY_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/datasets/gold/full_corpus_v3_evidence_groups_gold_v2_manifest.json"
)
FALLBACK_REGISTRY_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/evidence/full_corpus_v3_evidence_groups.jsonl"
)
GOLD_SCHEMA_PATH = (
    REPOSITORY_ROOT / "ai/evaluation/schemas/gold_evaluation_case_v2.schema.json"
)

CHILD_ID = "CHILD-WPUJAC104DWH-P004-SPRAY-FIRE-PREVENTION-001"
SOURCE_PAGE_ID = "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P001"
PRESERVATION_ID = "PRESERVE-WPUJAC104DWH-P004-L001-L023"
GROUP_ID = "EVD-WPUJAC104DWH-SPRAY-FIRE-PREVENTION-001"


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _positive_case(
    case_id: str,
    query: str,
    *,
    evaluation_status: str = "ACTIVE",
) -> dict[str, object]:
    return {
        "schema_version": "2.0.0-draft.2",
        "case_id": case_id,
        "dataset_version": "2.0.0-draft.2",
        "evaluation_status": evaluation_status,
        "split": "DEV",
        "query_variant_type": "DIRECT",
        "query": query,
        "product_model_code": "WPUJAC104DWH",
        "expected_retrieval_outcome": "EVIDENCE",
        "expected_execution_path": "PGVECTOR_QUERY",
        "required_evidence_group_ids": [GROUP_ID],
        "supporting_evidence_group_ids": [],
        "evidence_match_policy": "ANY",
        "expected_risk_level": "general",
        "expected_usage_guidance_status": "NORMAL",
        "expected_consultation_requirement": "NONE",
        "consultation_basis_codes": ["NONE"],
        "consultation_condition_ids": [],
        "forbidden_document_ids": ["MAN-SKMAGIC-WPU-IAC425-REV02"],
        "forbidden_model_codes": ["WPUIAC425SNW"],
        "source_query_origin": "CURATED_VARIANT",
        "source_case_ids": [],
        "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
        "review_status": "UNREVIEWED_DRAFT",
        "reviewer_ids": [],
        "review_notes": "Runner 단위 검사용 Draft Case이며 공식 Metric으로 사용하지 않음",
    }


def _no_evidence_case(
    case_id: str,
    query: str,
    *,
    execution_path: str,
) -> dict[str, object]:
    policy_block = execution_path.startswith("POLICY_BLOCK_")
    return {
        "schema_version": "2.0.0-draft.2",
        "case_id": case_id,
        "dataset_version": "2.0.0-draft.2",
        "evaluation_status": "ACTIVE",
        "split": "TEST",
        "query_variant_type": "NO_EVIDENCE",
        "query": query,
        "product_model_code": "WPUJAC104DWH",
        "expected_retrieval_outcome": "NO_EVIDENCE",
        "expected_execution_path": execution_path,
        "required_evidence_group_ids": [],
        "supporting_evidence_group_ids": [],
        "evidence_match_policy": "NONE",
        "expected_risk_level": "caution",
        "expected_usage_guidance_status": "PENDING_CONSULTATION",
        "expected_consultation_requirement": "REQUIRED",
        "consultation_basis_codes": ["POLICY_BLOCK" if policy_block else "NO_EVIDENCE"],
        "consultation_condition_ids": [],
        "forbidden_document_ids": ["MAN-SKMAGIC-WPU-IAC425-REV02"],
        "forbidden_model_codes": ["WPUIAC425SNW"],
        "source_query_origin": "CURATED_NEGATIVE",
        "source_case_ids": [],
        "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
        "review_status": "UNREVIEWED_DRAFT",
        "reviewer_ids": [],
        "review_notes": "Runner 단위 검사용 Draft Case이며 공식 Metric으로 사용하지 않음",
    }


class DeterministicEmbeddingProvider:
    dimension = 1024

    def __init__(
        self,
        *,
        corpus_rows: list[dict[str, object]],
        query_target_by_text: dict[str, int],
    ) -> None:
        self._corpus_rows = corpus_rows
        self._query_target_by_text = query_target_by_text
        self.document_input_count = 0
        self.query_inputs: list[str] = []

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self.document_input_count += len(texts)
        if len(texts) != len(self._corpus_rows):
            raise AssertionError("Runner의 Eligible Corpus와 Embedding 입력이 달라짐")
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for index in range(len(texts)):
            vectors[index, index] = 1.0
        return vectors

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        self.query_inputs.extend(texts)
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for index, query in enumerate(texts):
            if query not in self._query_target_by_text:
                raise AssertionError(f"평가 대상이 아닌 Query가 임베딩됨: {query}")
            vectors[index, self._query_target_by_text[query]] = 1.0
        return vectors


class FullCorpusBaselineV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(
            dir=REPOSITORY_ROOT / "ai/tests/unit"
        )
        self.root = Path(self.directory.name)
        self.corpus_rows = _load_jsonl(CORPUS_PATH)
        self.index_by_chunk_id = {
            str(row["chunk_id"]): index for index, row in enumerate(self.corpus_rows)
        }
        self.cases = [
            _positive_case("RAGV2-GOLD-9001", "child probe"),
            _no_evidence_case(
                "RAGV2-GOLD-9002",
                "no evidence probe",
                execution_path="PGVECTOR_QUERY",
            ),
            _no_evidence_case(
                "RAGV2-GOLD-9003",
                "policy probe must not be embedded",
                execution_path="POLICY_BLOCK_UNVERIFIED_SOURCE",
            ),
            _positive_case("RAGV2-GOLD-9004", "source page probe"),
            _positive_case("RAGV2-GOLD-9005", "preservation probe"),
            _positive_case(
                "RAGV2-GOLD-9006",
                "excluded probe must not be embedded",
                evaluation_status="EXCLUDED",
            ),
        ]
        self.gold_path = self.root / "gold.jsonl"
        self.gold_manifest_path = self.root / "gold_manifest.json"
        _write_jsonl(self.gold_path, self.cases)
        _write_json(
            self.gold_manifest_path,
            {
                "dataset": {
                    "path": self.gold_path.as_posix(),
                    "records": len(self.cases),
                    "sha256": file_sha256(self.gold_path),
                }
            },
        )
        self.profile_path = self.root / "profile.json"
        self.output_directory = self.root / "output"
        self.profile = {
            "profile_id": "full_corpus_baseline_v2_unit",
            "profile_version": "2.0.0-draft.1",
            "dataset": {
                "path": self.gold_path.as_posix(),
                "manifest_path": self.gold_manifest_path.as_posix(),
                "schema_path": GOLD_SCHEMA_PATH.as_posix(),
                "splits": ["DEV", "TEST", "SAFETY"],
            },
            "evidence_groups": {
                "preferred_path": REGISTRY_PATH.as_posix(),
                "preferred_manifest_path": REGISTRY_MANIFEST_PATH.as_posix(),
                "fallback_path": FALLBACK_REGISTRY_PATH.as_posix(),
            },
            "children": {"path": CHILDREN_PATH.as_posix()},
            "corpus": {
                "path": CORPUS_PATH.as_posix(),
                "handoff_manifest_path": HANDOFF_MANIFEST_PATH.as_posix(),
            },
            "embedding": {
                "model": "BAAI/bge-m3",
                "revision": "5617a9f61b028005a4858fdac845db406aefb181",
                "dimension": 1024,
                "device": "cpu",
                "normalize_embeddings": True,
                "local_files_only": True,
            },
            "retrieval": {
                "engine": "numpy_dense_cosine_exact",
                "top_k": 5,
                "score_threshold": 0.4,
                "filter_mode": "EXACT_PRODUCT_FILTER",
                "vector_query_execution_path": LOCAL_DENSE_QUERY,
            },
            "output_directory": self.output_directory.as_posix(),
            "publication_limits": ["UNIT_TEST_DIAGNOSTIC_ONLY"],
        }
        _write_json(self.profile_path, self.profile)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _provider(self) -> DeterministicEmbeddingProvider:
        return DeterministicEmbeddingProvider(
            corpus_rows=self.corpus_rows,
            query_target_by_text={
                "child probe": self.index_by_chunk_id[CHILD_ID],
                "no evidence probe": 1023,
                "source page probe": self.index_by_chunk_id[SOURCE_PAGE_ID],
                "preservation probe": self.index_by_chunk_id[PRESERVATION_ID],
            },
        )

    def test_local_dense_run_preserves_semantic_and_execution_truth(self) -> None:
        provider = self._provider()

        manifest = run_baseline(
            self.profile_path,
            self.output_directory,
            embedding_provider=provider,
            allow_review_pending=True,
        )

        self.assertEqual(manifest["run_status"], "LOCAL_DENSE_DIAGNOSTIC_COMPLETE")
        self.assertFalse(manifest["official"])
        self.assertFalse(manifest["official_metrics_allowed"])
        self.assertIn(
            "POLICY_BLOCK_RUNTIME_NOT_EXECUTED",
            manifest["official_metrics_blockers"],
        )
        self.assertEqual(manifest["dataset"]["records"], 6)
        self.assertEqual(manifest["dataset"]["active_records"], 5)
        self.assertEqual(manifest["corpus"]["search_candidates"], 132)
        self.assertEqual(manifest["corpus"]["source_records"], 132)
        self.assertEqual(manifest["corpus"]["eligible_search_candidates"], 132)
        self.assertEqual(manifest["corpus"]["embedded_candidates"], 132)
        self.assertEqual(
            manifest["corpus"]["allowed_record_types"],
            ["CHILD", "PRESERVATION", "SOURCE_PAGE"],
        )
        self.assertEqual(
            manifest["corpus"]["record_type_counts"],
            {"CHILD": 37, "PRESERVATION": 10, "SOURCE_PAGE": 85},
        )
        self.assertEqual(provider.document_input_count, 132)
        self.assertCountEqual(
            provider.query_inputs,
            [
                "child probe",
                "no evidence probe",
                "source page probe",
                "preservation probe",
            ],
        )
        self.assertNotIn("policy probe must not be embedded", provider.query_inputs)
        self.assertNotIn("excluded probe must not be embedded", provider.query_inputs)

        results = {
            row["case_id"]: row
            for row in _load_jsonl(self.output_directory / "case_results.jsonl")
        }
        self.assertEqual(set(results), {f"RAGV2-GOLD-900{index}" for index in range(1, 6)})

        child = results["RAGV2-GOLD-9001"]
        self.assertEqual(child["actual_execution_path"], LOCAL_DENSE_QUERY)
        self.assertEqual(child["vector_query_count"], 1)
        self.assertEqual(child["ranked_results"][0]["chunk_id"], CHILD_ID)
        self.assertTrue(child["semantic_quality_passed"])
        self.assertTrue(child["metrics"]["semantic_passed"])
        self.assertFalse(child["metrics"]["execution_contract_passed"])
        self.assertFalse(child["metrics"]["passed"])

        no_evidence = results["RAGV2-GOLD-9002"]
        self.assertEqual(no_evidence["actual_execution_path"], LOCAL_DENSE_QUERY)
        self.assertEqual(no_evidence["vector_query_count"], 1)
        self.assertEqual(no_evidence["ranked_result_count"], 0)
        self.assertTrue(no_evidence["semantic_quality_passed"])
        self.assertFalse(no_evidence["metrics"]["execution_contract_passed"])
        self.assertFalse(no_evidence["metrics"]["no_evidence_success"])

        policy = results["RAGV2-GOLD-9003"]
        self.assertEqual(policy["actual_execution_path"], LOCAL_POLICY_SIMULATION)
        self.assertEqual(policy["vector_query_count"], 0)
        self.assertEqual(policy["ranked_result_count"], 0)
        self.assertEqual(policy["policy_block_status"], "NOT_RUN_RUNTIME_POLICY")
        self.assertFalse(policy["metrics"]["execution_contract_passed"])
        self.assertFalse(policy["metrics"]["policy_block_success"])
        self.assertFalse(policy["metrics"]["passed"])

        source_page = results["RAGV2-GOLD-9004"]
        self.assertEqual(source_page["ranked_results"][0]["record_type"], "SOURCE_PAGE")
        self.assertEqual(source_page["metrics"]["non_child_hit_count"], 1)
        self.assertEqual(source_page["metrics"]["invalid_top_k_hit_count"], 1)

        preservation = results["RAGV2-GOLD-9005"]
        self.assertEqual(
            preservation["ranked_results"][0]["record_type"], "PRESERVATION"
        )
        self.assertEqual(preservation["metrics"]["non_child_hit_count"], 1)
        self.assertEqual(preservation["metrics"]["unverified_hit_count"], 1)
        self.assertEqual(preservation["metrics"]["invalid_top_k_hit_count"], 1)

        performance = json.loads(
            (self.output_directory / "performance_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(performance["document_count"], 132)
        self.assertEqual(performance["source_corpus_record_count"], 132)
        self.assertEqual(performance["eligible_candidate_count"], 132)
        self.assertEqual(performance["embedded_candidate_count"], 132)
        self.assertEqual(performance["embedded_query_count"], 4)
        self.assertEqual(performance["policy_block_case_count"], 1)
        self.assertEqual(performance["active_case_count"], 5)

        retrieval_summary = json.loads(
            (self.output_directory / "retrieval_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertFalse(retrieval_summary["official"])
        self.assertEqual(
            retrieval_summary["semantic_metrics"]["invalid_top_k_hit_count"], 2
        )
        self.assertEqual(
            retrieval_summary["execution_contract"]["policy_block_runtime_status"],
            "NOT_RUN_RUNTIME_POLICY",
        )
        summary = retrieval_summary["summary"]
        self.assertEqual(summary["vector_query_count"], 4)
        self.assertEqual(summary["policy_block_case_count"], 1)
        self.assertEqual(summary["policy_block_passed_count"], 0)
        self.assertEqual(summary["non_child_hit_count"], 2)
        self.assertEqual(summary["unverified_hit_count"], 1)
        self.assertEqual(summary["invalid_top_k_hit_count"], 2)
        self.assertEqual(
            summary["actual_execution_path_counts"],
            {LOCAL_DENSE_QUERY: 4, LOCAL_POLICY_SIMULATION: 1},
        )
        self.assertTrue(
            {
                "preflight.json",
                "manifest.json",
                "case_results.jsonl",
                "retrieval_summary.json",
                "performance_summary.json",
            }.issubset(path.name for path in self.output_directory.iterdir())
        )

    def test_child_only_allowlist_embeds_only_eligible_candidates(self) -> None:
        profile = copy.deepcopy(self.profile)
        profile["profile_id"] = "full_corpus_baseline_v2_child_only_unit"
        profile["retrieval"]["allowed_record_types"] = ["CHILD"]
        profile_path = self.root / "child_only_profile.json"
        output_directory = self.root / "child_only_output"
        _write_json(profile_path, profile)

        child_rows = [
            row for row in self.corpus_rows if row["record_type"] == "CHILD"
        ]
        child_index_by_chunk_id = {
            str(row["chunk_id"]): index for index, row in enumerate(child_rows)
        }
        provider = DeterministicEmbeddingProvider(
            corpus_rows=child_rows,
            query_target_by_text={
                "child probe": child_index_by_chunk_id[CHILD_ID],
                "no evidence probe": 1023,
                "source page probe": 1023,
                "preservation probe": 1023,
            },
        )

        manifest = run_baseline(
            profile_path,
            output_directory,
            embedding_provider=provider,
            allow_review_pending=True,
        )

        self.assertEqual(provider.document_input_count, 37)
        self.assertEqual(manifest["corpus"]["source_records"], 132)
        self.assertEqual(manifest["corpus"]["source_search_candidates"], 132)
        self.assertEqual(manifest["corpus"]["eligible_search_candidates"], 37)
        self.assertEqual(manifest["corpus"]["embedded_candidates"], 37)
        self.assertEqual(manifest["corpus"]["allowed_record_types"], ["CHILD"])
        self.assertEqual(
            manifest["corpus"]["eligible_record_type_counts"], {"CHILD": 37}
        )

        preflight = json.loads(
            (output_directory / "preflight.json").read_text(encoding="utf-8")
        )
        self.assertEqual(preflight["counts"]["corpus_source_records"], 132)
        self.assertEqual(preflight["counts"]["corpus_eligible_candidates"], 37)
        self.assertEqual(
            preflight["counts"]["corpus_planned_embedded_candidates"], 37
        )
        self.assertEqual(
            preflight["retrieval_scope"]["mode"], "EXPLICIT_ALLOWLIST"
        )

        performance = json.loads(
            (output_directory / "performance_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(performance["document_count"], 37)
        self.assertEqual(performance["source_corpus_record_count"], 132)
        self.assertEqual(performance["eligible_candidate_count"], 37)
        self.assertEqual(performance["embedded_candidate_count"], 37)

        results = {
            row["case_id"]: row
            for row in _load_jsonl(output_directory / "case_results.jsonl")
        }
        self.assertEqual(
            results["RAGV2-GOLD-9001"]["ranked_results"][0]["record_type"],
            "CHILD",
        )
        self.assertEqual(results["RAGV2-GOLD-9004"]["ranked_result_count"], 0)
        self.assertEqual(results["RAGV2-GOLD-9005"]["ranked_result_count"], 0)
        self.assertEqual(
            sum(row["metrics"]["non_child_hit_count"] for row in results.values()),
            0,
        )

    def test_runtime_policy_and_query_expansion_are_executed_before_dense_search(
        self,
    ) -> None:
        cases = [
            _positive_case(
                "RAGV2-GOLD-9101",
                "정수기 물이 갑자기 졸졸 나와요.",
            ),
            _no_evidence_case(
                "RAGV2-GOLD-9102",
                "오늘 방문 예정인 기사님이 몇 시쯤 도착하나요?",
                execution_path="POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
            ),
        ]
        _write_jsonl(self.gold_path, cases)
        _write_json(
            self.gold_manifest_path,
            {
                "dataset": {
                    "path": self.gold_path.as_posix(),
                    "records": len(cases),
                    "sha256": file_sha256(self.gold_path),
                }
            },
        )
        profile = copy.deepcopy(self.profile)
        profile["profile_id"] = "full_corpus_retrieval_v3_unit"
        profile["retrieval"].update(
            {
                "allowed_record_types": ["CHILD"],
                "runtime_policy_profile": "mvp",
                "product_generation_by_model": {"WPUJAC104DWH": "D"},
            }
        )
        profile_path = self.root / "runtime_policy_profile.json"
        output_directory = self.root / "runtime_policy_output"
        _write_json(profile_path, profile)

        child_rows = [
            row for row in self.corpus_rows if row["record_type"] == "CHILD"
        ]
        child_index = next(
            index for index, row in enumerate(child_rows) if row["chunk_id"] == CHILD_ID
        )
        expanded_query = (
            "정수기 물이 갑자기 졸졸 나와요. "
            "출수량이 적을 경우 출수 속도가 느림"
        )
        provider = DeterministicEmbeddingProvider(
            corpus_rows=child_rows,
            query_target_by_text={expanded_query: child_index},
        )

        manifest = run_baseline(
            profile_path,
            output_directory,
            embedding_provider=provider,
            allow_review_pending=True,
        )

        self.assertEqual(provider.query_inputs, [expanded_query])
        self.assertNotIn(
            "POLICY_BLOCK_RUNTIME_NOT_EXECUTED",
            manifest["official_metrics_blockers"],
        )
        self.assertEqual(
            manifest["retrieval"]["policy_block_execution"],
            "EXECUTED_RUNTIME_POLICY",
        )
        self.assertEqual(
            manifest["retrieval"]["query_expansion_applied_count"], 1
        )
        results = {
            row["case_id"]: row
            for row in _load_jsonl(output_directory / "case_results.jsonl")
        }
        positive = results["RAGV2-GOLD-9101"]
        self.assertTrue(positive["query_expansion_applied"])
        self.assertEqual(
            positive["query_expansion_rule_ids"], ["QUERY-LOW-FLOW-001"]
        )
        policy = results["RAGV2-GOLD-9102"]
        self.assertEqual(
            policy["actual_execution_path"],
            "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
        )
        self.assertEqual(policy["vector_query_count"], 0)
        self.assertEqual(policy["policy_block_status"], "EXECUTED_RUNTIME_POLICY")
        self.assertTrue(policy["metrics"]["policy_block_success"])

    def test_explicit_record_type_allowlist_is_fail_closed(self) -> None:
        invalid_values = (
            [],
            ["CHILD", "TYPO"],
            ["CHILD", "CHILD"],
            ["CHILD", 42],
        )
        for index, invalid in enumerate(invalid_values, start=1):
            with self.subTest(allowed_record_types=invalid):
                profile = copy.deepcopy(self.profile)
                profile["retrieval"]["allowed_record_types"] = invalid
                profile_path = self.root / f"invalid_scope_{index}.json"
                _write_json(profile_path, profile)

                report = build_preflight_report(
                    profile_path,
                    allow_review_pending=True,
                    embedding_provider_supplied=True,
                )

                self.assertEqual(report["status"], "BLOCKED")
                self.assertIn("retrieval_allowed_record_types", report["blockers"])
                self.assertTrue(report["retrieval_scope"]["issues"])

    def test_human_review_gate_blocks_without_explicit_diagnostic_override(self) -> None:
        report = build_preflight_report(
            self.profile_path,
            allow_review_pending=False,
            embedding_provider_supplied=True,
        )

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("gold_human_review_gate", report["blockers"])
        self.assertFalse(report["official_metrics_allowed"])

    def test_policy_runtime_blocker_is_not_reported_without_policy_cases(self) -> None:
        cases = [
            case
            for case in self.cases
            if not str(case["expected_execution_path"]).startswith("POLICY_BLOCK_")
        ]
        _write_jsonl(self.gold_path, cases)
        _write_json(
            self.gold_manifest_path,
            {
                "dataset": {
                    "path": self.gold_path.as_posix(),
                    "records": len(cases),
                    "sha256": file_sha256(self.gold_path),
                }
            },
        )

        report = build_preflight_report(
            self.profile_path,
            allow_review_pending=True,
            embedding_provider_supplied=True,
        )

        self.assertEqual(report["status"], "READY")
        self.assertNotIn(
            "POLICY_BLOCK_RUNTIME_NOT_EXECUTED",
            report["official_metrics_blockers"],
        )

    def test_preferred_registry_manifest_hash_is_fail_closed(self) -> None:
        manifest = json.loads(REGISTRY_MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["output"]["sha256"] = "0" * 64
        manifest_path = self.root / "tampered_registry_manifest.json"
        _write_json(manifest_path, manifest)
        profile = copy.deepcopy(self.profile)
        profile["evidence_groups"]["preferred_manifest_path"] = manifest_path.as_posix()
        profile_path = self.root / "tampered_registry_profile.json"
        _write_json(profile_path, profile)

        report = build_preflight_report(
            profile_path,
            allow_review_pending=True,
            embedding_provider_supplied=True,
        )

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("evidence_group_registry_integrity", report["blockers"])

    def test_preferred_registry_source_hash_is_fail_closed(self) -> None:
        manifest = json.loads(REGISTRY_MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest["source_files"]["corpus"]["sha256"] = "0" * 64
        manifest_path = self.root / "tampered_source_manifest.json"
        _write_json(manifest_path, manifest)
        profile = copy.deepcopy(self.profile)
        profile["evidence_groups"]["preferred_manifest_path"] = manifest_path.as_posix()
        profile_path = self.root / "tampered_source_profile.json"
        _write_json(profile_path, profile)

        report = build_preflight_report(
            profile_path,
            allow_review_pending=True,
            embedding_provider_supplied=True,
        )

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("evidence_group_registry_source_integrity", report["blockers"])


if __name__ == "__main__":
    unittest.main()
