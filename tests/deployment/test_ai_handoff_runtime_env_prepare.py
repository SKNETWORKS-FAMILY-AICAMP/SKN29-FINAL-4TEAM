"""Runtime tests for fail-closed AI Handoff environment preparation."""

from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/deployment/production/prepare_ai_handoff_runtime_env.py"
)
SPEC = importlib.util.spec_from_file_location("ai_handoff_env_prepare", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AIHandoffRuntimeEnvPrepareTests(unittest.TestCase):
    def _write_env(self, directory: Path, content: str) -> Path:
        path = directory / "ai.env"
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
        return path

    def test_missing_defaults_are_added_without_exposing_or_changing_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_env(
                Path(temporary),
                "OPENAI_API_KEY=protected\nAI_HANDOFF_INTERNAL_TOKEN=secret-token\n",
            )

            MODULE.prepare_runtime_env(path, require_root=False)

            text = path.read_text(encoding="utf-8")
            self.assertIn("AI_HANDOFF_INTERNAL_TOKEN=secret-token\n", text)
            for key, value in MODULE.CANONICAL_VALUES.items():
                self.assertEqual(text.count(f"{key}="), 1)
                self.assertIn(f"{key}={value}\n", text)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_existing_true_value_is_forced_false(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_env(
                Path(temporary),
                "AI_HANDOFF_INTERNAL_TOKEN=secret-token\n"
                "AI_HANDOFF_BACKEND_ENABLED=true\n"
                "AI_BACKEND_BASE_URL=http://unexpected:9999\n"
                "AI_HANDOFF_TIMEOUT_SECONDS=9\n",
            )

            MODULE.prepare_runtime_env(path, require_root=False)

            text = path.read_text(encoding="utf-8")
            self.assertIn("AI_HANDOFF_BACKEND_ENABLED=false\n", text)
            self.assertIn("AI_BACKEND_BASE_URL=http://backend:8000\n", text)
            self.assertIn("AI_HANDOFF_TIMEOUT_SECONDS=2.0\n", text)

    def test_duplicate_protected_key_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = (
                "AI_HANDOFF_INTERNAL_TOKEN=secret-token\n"
                "AI_HANDOFF_BACKEND_ENABLED=false\n"
                "AI_HANDOFF_BACKEND_ENABLED=true\n"
            )
            path = self._write_env(Path(temporary), original)

            with self.assertRaises(MODULE.RuntimeEnvironmentError):
                MODULE.prepare_runtime_env(path, require_root=False)

            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_missing_or_empty_token_fails_without_mutation(self) -> None:
        for content in ("OPENAI_API_KEY=protected\n", "AI_HANDOFF_INTERNAL_TOKEN=\n"):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as temporary:
                    path = self._write_env(Path(temporary), content)
                    with self.assertRaises(MODULE.RuntimeEnvironmentError):
                        MODULE.prepare_runtime_env(path, require_root=False)
                    self.assertEqual(path.read_text(encoding="utf-8"), content)

    @unittest.skipUnless(os.name == "posix", "POSIX permission gate")
    def test_group_readable_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_env(
                Path(temporary), "AI_HANDOFF_INTERNAL_TOKEN=secret-token\n"
            )
            path.chmod(0o640)
            with self.assertRaises(MODULE.RuntimeEnvironmentError):
                MODULE.prepare_runtime_env(path, require_root=False)


if __name__ == "__main__":
    unittest.main()
