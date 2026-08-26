from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from jsonschema import Draft202012Validator

from ai.scripts.build_gold_v2_evidence_group_registry import (
    DEFAULT_CONTRACT_PATH,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_OUTPUT_PATH,
    OverlayBuildError,
    build_overlay,
)
from ai.scripts.validate_gold_corpus_compatibility_v2 import (
    build_compatibility_report,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_GROUPS_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/evidence/full_corpus_v3_evidence_groups.jsonl"
)
GROUP_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/schemas/evidence_group_registry_v2.schema.json"
)
CHILDREN_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/rag/experimental/full_corpus_v3_children.jsonl"
)
CORPUS_PATH = (
    REPOSITORY_ROOT
    / "data/processed/structured/rag/experimental/full_corpus_chunks_v3.jsonl"
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GoldV2EvidenceGroupOverlayTests(unittest.TestCase):
    def _mutated_contract(
        self,
        directory: Path,
        mutate: Callable[[dict[str, Any]], None],
    ) -> Path:
        contract = _read_json(DEFAULT_CONTRACT_PATH)
        mutate(contract)
        path = directory / "contract.json"
        path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def test_committed_artifacts_rebuild_byte_identically(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "groups.jsonl"
            manifest = root / "manifest.json"
            build_overlay(DEFAULT_CONTRACT_PATH, output, manifest)

            self.assertEqual(DEFAULT_OUTPUT_PATH.read_bytes(), output.read_bytes())
            self.assertEqual(DEFAULT_MANIFEST_PATH.read_bytes(), manifest.read_bytes())

    def test_overlay_preserves_every_canonical_group_field(self) -> None:
        canonical_rows = _read_jsonl(CANONICAL_GROUPS_PATH)
        overlay_rows = _read_jsonl(DEFAULT_OUTPUT_PATH)
        self.assertEqual(34, len(canonical_rows))
        self.assertEqual(34, len(overlay_rows))

        canonical_by_id = {row["evidence_group_id"]: row for row in canonical_rows}
        overlay_by_id = {row["evidence_group_id"]: row for row in overlay_rows}
        self.assertEqual(set(canonical_by_id), set(overlay_by_id))
        for group_id, canonical in canonical_by_id.items():
            overlay = overlay_by_id[group_id]
            self.assertEqual(
                {
                    key: value
                    for key, value in canonical.items()
                    if key != "consultation_conditions"
                },
                {
                    key: value
                    for key, value in overlay.items()
                    if key != "consultation_conditions"
                },
                group_id,
            )

    def test_overlay_rows_pass_existing_registry_schema(self) -> None:
        schema = _read_json(GROUP_SCHEMA_PATH)
        validator = Draft202012Validator(schema)
        errors = [
            error
            for row in _read_jsonl(DEFAULT_OUTPUT_PATH)
            for error in validator.iter_errors(row)
        ]
        self.assertEqual([], errors)

    def test_selected_conditions_are_narrow_and_noise_is_excluded(self) -> None:
        rows = _read_jsonl(DEFAULT_OUTPUT_PATH)
        conditions = [
            condition
            for row in rows
            for condition in row["consultation_conditions"]
        ]
        self.assertEqual(10, len(conditions))
        self.assertEqual(
            {
                "COND-WPUJAC104DWH-NO-WATER-AFTER-FILTER-001",
                "COND-WPUJAC104DWH-COLD-AFTER-2H-001",
                "COND-WPUJAC104DWH-LOW-FLOW-AFTER-FILTER-001",
                "COND-WPUJAC104DWH-HOT-STEAM-PERSISTS-001",
                "COND-WPUIAC425SNW-COLD-AFTER-2H-001",
                "COND-WPUIAC425SNW-HOT-STEAM-PERSISTENCE-001",
                "COND-WPUIAC425SNW-LOW-FLOW-AFTER-FILTER-001",
                "COND-WPUIAC425SNW-NO-HOT-AFTER-UNLOCK-001",
                "COND-WPUIAC425SNW-NO-WATER-AFTER-FILTER-001",
                "COND-WPUIAC425SNW-PARTICLES-PERSISTENCE-001",
            },
            {condition["condition_id"] for condition in conditions},
        )
        self.assertTrue(
            all(
                not row["consultation_conditions"]
                for row in rows
                if "NOISE" in row["topic_code"]
            )
        )

    def test_manifest_keeps_noncanonical_and_signoff_boundaries(self) -> None:
        manifest = _read_json(DEFAULT_MANIFEST_PATH)
        self.assertEqual("PASS", manifest["build_status"])
        self.assertEqual("HUMAN_SIGNOFF_PENDING", manifest["status"])
        self.assertEqual(
            "AI_EVALUATION_OVERLAY_NOT_CANONICAL_DATA",
            manifest["publication_scope"],
        )
        self.assertEqual("NOT_APPROVED", manifest["promotion_status"])
        self.assertEqual(34, manifest["output"]["group_count"])
        self.assertEqual(10, manifest["output"]["condition_count"])
        self.assertEqual(
            {"WPUIAC425SNW": 6, "WPUJAC104DWH": 4},
            manifest["output"]["conditions_by_product"],
        )

    def test_overlay_passes_group_child_corpus_compatibility(self) -> None:
        with TemporaryDirectory() as directory:
            empty_gold = Path(directory) / "empty-gold.jsonl"
            empty_gold.write_text("", encoding="utf-8")
            report = build_compatibility_report(
                empty_gold,
                DEFAULT_OUTPUT_PATH,
                CHILDREN_PATH,
                CORPUS_PATH,
            )
        self.assertEqual("PASS", report["status"], report["error_code_counts"])
        self.assertEqual(34, report["counts"]["linked_evidence_groups"])
        self.assertEqual(37, report["counts"]["linked_group_children"])
        self.assertEqual(10, report["counts"]["registered_conditions"])

    def test_source_hash_drift_fails_closed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            contract_path = self._mutated_contract(
                root,
                lambda contract: contract["source_files"]["children"].update(
                    {"sha256": "0" * 64}
                ),
            )
            with self.assertRaisesRegex(
                OverlayBuildError, "SOURCE_HASH_MISMATCH:children"
            ):
                build_overlay(contract_path, root / "groups.jsonl", root / "manifest.json")

    def test_condition_text_hash_drift_fails_closed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def mutate(contract: dict[str, Any]) -> None:
                contract["conditions"][0]["source_condition_sha256"] = "0" * 64

            contract_path = self._mutated_contract(root, mutate)
            with self.assertRaisesRegex(
                OverlayBuildError, "CHILD_FREE_TEXT_CONDITION_HASH_MISMATCH"
            ):
                build_overlay(contract_path, root / "groups.jsonl", root / "manifest.json")

    def test_child_group_lineage_drift_fails_closed(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def mutate(contract: dict[str, Any]) -> None:
                contract["conditions"][0]["evidence_group_id"] = (
                    "EVD-WPUJAC104DWH-NOISE-001"
                )

            contract_path = self._mutated_contract(root, mutate)
            with self.assertRaisesRegex(
                OverlayBuildError, "CONDITION_GROUP_CHILD_LINEAGE_MISMATCH"
            ):
                build_overlay(contract_path, root / "groups.jsonl", root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
