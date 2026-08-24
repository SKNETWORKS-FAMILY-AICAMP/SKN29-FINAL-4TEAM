"""Repository-level tests for Code, OpenAPI, and Example validators."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "contracts"
sys.path.insert(0, str(SCRIPT_DIR))

import validate_codes  # noqa: E402
import validate_examples  # noqa: E402
import validate_openapi  # noqa: E402
import render_state_machine  # noqa: E402


class ContractValidatorsTest(unittest.TestCase):
    def test_code_registries_match_state_machine_sources(self) -> None:
        result = validate_codes.validate_repository(REPO_ROOT)

        self.assertEqual(29, result.registry_files)
        self.assertEqual(13, result.inquiry_statuses)
        self.assertEqual(24, result.workflow_actions)
        self.assertEqual(4, result.user_roles)
        self.assertEqual(7, result.visit_statuses)

    def test_openapi_refs_paths_and_operations_are_resolvable(self) -> None:
        result = validate_openapi.validate_repository(REPO_ROOT)

        self.assertEqual(54, result.paths)
        self.assertEqual(59, result.operations)
        self.assertGreater(result.references, 0)

    def test_json_examples_are_parseable_and_referenced(self) -> None:
        result = validate_examples.validate_repository(REPO_ROOT)

        self.assertEqual(72, result.api_examples)
        self.assertEqual(result.api_examples, result.referenced_examples)
        self.assertEqual(5, result.integration_examples)
        self.assertEqual(52, result.wrapped_responses)

    def test_state_machine_digest_input_is_line_ending_independent(self) -> None:
        with patch.object(
            Path,
            "read_bytes",
            side_effect=[
                b"contract:\n  version: 1.0.0\n",
                b"contract:\r\n  version: 1.0.0\r\n",
            ],
        ):
            self.assertEqual(
                render_state_machine.normalized_source_bytes(Path("lf.yaml")),
                render_state_machine.normalized_source_bytes(Path("crlf.yaml")),
            )


if __name__ == "__main__":
    unittest.main()
