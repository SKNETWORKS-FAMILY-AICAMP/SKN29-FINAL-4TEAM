from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from ai.scripts.run_rag_experiment import (
    REPOSITORY_ROOT,
    RESULT_FILES,
    run_validation_only,
)


class RagExperimentRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_path = (
            REPOSITORY_ROOT
            / "ai/configs/experiments/experiment_runner_contract_v1.yaml"
        )
        cls.schema = json.loads((
            REPOSITORY_ROOT
            / "ai/evaluation/schemas/experiment_result_bundle_v1.schema.json"
        ).read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(
            cls.schema,
            format_checker=FormatChecker(),
        )

    def test_validation_only_creates_six_schema_valid_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = run_validation_only(
                profile_path=self.profile_path,
                dataset_alias="rag_gold_v1",
                split="DEV",
                run_id="a3-test-dev",
                output_directory=output,
            )

            self.assertEqual(manifest["run_status"], "VALIDATION_ONLY_COMPLETE")
            self.assertEqual(manifest["dataset"]["selected_case_count"], 35)
            self.assertFalse(
                manifest["dataset"]["gold_approved_for_official_metrics"]
            )
            self.assertEqual(set(path.name for path in output.iterdir()), set(
                RESULT_FILES.values()
            ))
            self.assertEqual(list(self.validator.iter_errors(manifest)), [])

            case_results = [
                json.loads(line)
                for line in (output / "case_results.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(len(case_results), 35)
            self.assertTrue(all(
                row["execution_status"] == "NOT_EXECUTED_VALIDATION_ONLY"
                and row["actual"] is None
                and row["metrics"] is None
                for row in case_results
            ))
            self.assertEqual(
                [error.message for row in case_results for error in self.validator.iter_errors(row)],
                [],
            )

            summaries = [
                json.loads((output / filename).read_text(encoding="utf-8"))
                for filename in [
                    "retrieval_summary.json",
                    "generation_summary.json",
                    "safety_summary.json",
                    "performance_summary.json",
                ]
            ]
            self.assertTrue(all(row["executed_case_count"] == 0 for row in summaries))
            self.assertEqual(
                [error.message for row in summaries for error in self.validator.iter_errors(row)],
                [],
            )

    def test_each_split_selects_only_its_expected_cases(self) -> None:
        expected = {"DEV": 35, "TEST": 15, "SAFETY": 10}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for split, count in expected.items():
                manifest = run_validation_only(
                    profile_path=self.profile_path,
                    dataset_alias="rag_gold_v1",
                    split=split,
                    run_id=f"a3-test-{split.lower()}",
                    output_directory=root / split.lower(),
                )
                self.assertEqual(manifest["dataset"]["selected_case_count"], count)

    def test_dataset_alias_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Dataset alias 불일치"):
                run_validation_only(
                    profile_path=self.profile_path,
                    dataset_alias="wrong_dataset",
                    split="DEV",
                    run_id="a3-test-wrong",
                    output_directory=Path(directory),
                )


if __name__ == "__main__":
    unittest.main()
