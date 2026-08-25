"""Static and unit gates for the optimized Backend CI workflow."""

from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.testing import classify_backend_ci_changes as classifier


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
WORKFLOW = ROOT / ".github/workflows/backend-ci.yml"


class BackendCIClassifierTests(unittest.TestCase):
    def test_backend_and_contract_changes_require_the_heavy_gate(self) -> None:
        for path in (
            "backend/apps/inquiries/models/inquiry.py",
            "contracts/api/openapi.yaml",
            "scripts/development/check_environment.py",
            ".github/workflows/backend-ci.yml",
            "scripts/testing/classify_backend_ci_changes.py",
            "tests/deployment/test_backend_ci_workflow.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(classifier.is_backend_relevant(path))

    def test_data_docs_and_web_changes_use_the_lightweight_gate(self) -> None:
        for path in (
            "data/synthetic/fixtures/inquiries.json",
            "docs/README.md",
            "web/src/app/App.tsx",
            ".github/workflows/data-ci.yml",
        ):
            with self.subTest(path=path):
                self.assertFalse(classifier.is_backend_relevant(path))

    @patch.object(classifier, "_git_lines")
    def test_pull_request_uses_three_dot_diff(self, git_lines) -> None:
        git_lines.return_value = ["backend/config/settings/test.py"]
        paths = classifier.changed_paths(
            event_name="pull_request",
            before_sha="",
            base_sha="a" * 40,
            head_sha="b" * 40,
        )
        self.assertEqual(paths, ["backend/config/settings/test.py"])
        git_lines.assert_called_once_with("diff", "--name-only", f"{'a' * 40}...{'b' * 40}")

    @patch.object(classifier, "_git_lines")
    def test_first_push_uses_root_diff_tree(self, git_lines) -> None:
        git_lines.return_value = ["docs/README.md"]
        paths = classifier.changed_paths(
            event_name="push",
            before_sha=classifier.ZERO_SHA,
            base_sha="",
            head_sha="c" * 40,
        )
        self.assertEqual(paths, ["docs/README.md"])
        git_lines.assert_called_once_with(
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            "c" * 40,
        )

    @patch.object(classifier, "_git_lines")
    def test_regular_push_uses_two_dot_diff(self, git_lines) -> None:
        git_lines.return_value = ["contracts/api/openapi.yaml"]
        paths = classifier.changed_paths(
            event_name="push",
            before_sha="d" * 40,
            base_sha="",
            head_sha="e" * 40,
        )
        self.assertEqual(paths, ["contracts/api/openapi.yaml"])
        git_lines.assert_called_once_with("diff", "--name-only", f"{'d' * 40}..{'e' * 40}")

    @patch.object(classifier, "changed_paths", side_effect=AssertionError("diff must not run"))
    @patch.object(classifier, "parse_args")
    def test_manual_and_release_calls_force_the_heavy_gate(self, parse_args, _changed_paths) -> None:
        for event_name, force_full in (("workflow_dispatch", False), ("workflow_call", True)):
            with self.subTest(event_name=event_name):
                parse_args.return_value = SimpleNamespace(
                    print_matrix=False,
                    force_full=force_full,
                    event_name=event_name,
                    before_sha="",
                    base_sha="",
                    head_sha="",
                )
                with redirect_stdout(StringIO()) as stdout:
                    self.assertEqual(classifier.main(), 0)
                self.assertEqual(stdout.getvalue().strip(), "true")

    def test_every_backend_test_file_belongs_to_exactly_one_shard(self) -> None:
        targets = {
            shard: tuple(definition["targets"])
            for shard, definition in classifier.BACKEND_TEST_SHARDS.items()
        }
        test_files = sorted(
            path.relative_to(BACKEND_ROOT).as_posix()
            for path in (BACKEND_ROOT / "tests").rglob("test_*.py")
        )
        self.assertTrue(test_files)
        for test_file in test_files:
            owners = [
                shard
                for shard, shard_targets in targets.items()
                if any(
                    test_file == target or test_file.startswith(f"{target}/")
                    for target in shard_targets
                )
            ]
            with self.subTest(test_file=test_file):
                self.assertEqual(len(owners), 1)

        flattened = [target for shard_targets in targets.values() for target in shard_targets]
        self.assertEqual(len(flattened), len(set(flattened)))


class BackendCIWorkflowTests(unittest.TestCase):
    def test_workflow_keeps_a_stable_lightweight_required_check(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_call:", text)
        self.assertIn("force_full:", text)
        self.assertIn("pull_request:\n", text)
        self.assertIn("branches:\n      - main", text)
        self.assertNotIn('      - "data/**"', text)
        self.assertIn("name: Verify Backend baseline", text)
        self.assertIn("tests.deployment.test_backend_ci_workflow -v", text)
        self.assertIn("if: ${{ always() }}", text)
        self.assertIn('[[ "$SHARD_RESULT" == "success" ]]', text)
        self.assertIn('[[ "$SHARD_RESULT" == "skipped" ]]', text)

    def test_workflow_runs_three_shards_without_failure_suppression(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for shard in classifier.BACKEND_TEST_SHARDS:
            self.assertIn(f'"name":"{shard}"', classifier_output())
        self.assertIn("--durations=20", text)
        self.assertIn("makemigrations", text)
        self.assertIn("git check-ignore -q backend/.venv/pyvenv.cfg", text)
        self.assertNotIn("continue-on-error", text)


def classifier_output() -> str:
    import json

    return json.dumps(classifier.shard_matrix(), separators=(",", ":"))


if __name__ == "__main__":
    unittest.main()
