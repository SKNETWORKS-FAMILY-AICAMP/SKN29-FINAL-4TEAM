"""Runtime tests for fail-closed Backend-to-AI Resume environment setup."""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/deployment/production/prepare_ai_resume_runtime_env.py"
)
SPEC = importlib.util.spec_from_file_location("ai_resume_env_prepare", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AIResumeRuntimeEnvPrepareTests(unittest.TestCase):
    SOURCE = "handoff-source-token-with-more-than-32-bytes"

    def _write_env(self, directory: Path, name: str, content: str) -> Path:
        path = directory / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o600)
        return path

    def _pair(self, directory: Path) -> tuple[Path, Path]:
        content = f"AI_HANDOFF_INTERNAL_TOKEN={self.SOURCE}\n"
        return (
            self._write_env(directory, "backend.env", content),
            self._write_env(directory, "ai.env", content),
        )

    @staticmethod
    def _values(path: Path) -> dict[str, str]:
        return dict(
            line.split("=", 1)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        )

    def test_installs_distinct_matching_resume_token_and_false_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend, ai = self._pair(Path(temporary))

            MODULE.prepare_resume_runtime_envs(
                backend,
                ai,
                require_root=False,
            )

            backend_values = self._values(backend)
            ai_values = self._values(ai)
            self.assertEqual(
                backend_values[MODULE.RESUME_ENABLED_KEY],
                "false",
            )
            self.assertEqual(ai_values[MODULE.RESUME_ENABLED_KEY], "false")
            self.assertEqual(
                backend_values[MODULE.RESUME_TOKEN_KEY],
                ai_values[MODULE.RESUME_TOKEN_KEY],
            )
            self.assertNotEqual(
                backend_values[MODULE.RESUME_TOKEN_KEY],
                self.SOURCE,
            )
            self.assertEqual(
                len(backend_values[MODULE.RESUME_TOKEN_KEY]),
                64,
            )

    def test_existing_true_and_stale_token_are_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend, ai = self._pair(Path(temporary))
            for path in (backend, ai):
                with path.open("a", encoding="utf-8") as stream:
                    stream.write("AI_HUMAN_REVIEW_RESUME_ENABLED=true\n")
                    stream.write("AI_HUMAN_REVIEW_RESUME_TOKEN=stale\n")

            MODULE.prepare_resume_runtime_envs(
                backend,
                ai,
                require_root=False,
            )

            for path in (backend, ai):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(
                    text.count("AI_HUMAN_REVIEW_RESUME_ENABLED="),
                    1,
                )
                self.assertIn("AI_HUMAN_REVIEW_RESUME_ENABLED=false\n", text)
                self.assertNotIn("AI_HUMAN_REVIEW_RESUME_TOKEN=stale", text)

    def test_mismatched_source_tokens_fail_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            backend = self._write_env(
                directory,
                "backend.env",
                f"AI_HANDOFF_INTERNAL_TOKEN={self.SOURCE}\n",
            )
            ai = self._write_env(
                directory,
                "ai.env",
                "AI_HANDOFF_INTERNAL_TOKEN=different-source-token-with-32-bytes\n",
            )
            originals = (backend.read_bytes(), ai.read_bytes())

            with self.assertRaises(MODULE.ResumeRuntimeEnvironmentError):
                MODULE.prepare_resume_runtime_envs(
                    backend,
                    ai,
                    require_root=False,
                )

            self.assertEqual((backend.read_bytes(), ai.read_bytes()), originals)

    def test_duplicate_or_short_source_fails_without_mutation(self) -> None:
        cases = (
            (
                f"AI_HANDOFF_INTERNAL_TOKEN={self.SOURCE}\n"
                f"AI_HANDOFF_INTERNAL_TOKEN={self.SOURCE}\n"
            ),
            "AI_HANDOFF_INTERNAL_TOKEN=short\n",
        )
        for content in cases:
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    backend = self._write_env(
                        directory,
                        "backend.env",
                        content,
                    )
                    ai = self._write_env(
                        directory,
                        "ai.env",
                        f"AI_HANDOFF_INTERNAL_TOKEN={self.SOURCE}\n",
                    )
                    originals = (backend.read_bytes(), ai.read_bytes())
                    with self.assertRaises(
                        MODULE.ResumeRuntimeEnvironmentError
                    ):
                        MODULE.prepare_resume_runtime_envs(
                            backend,
                            ai,
                            require_root=False,
                        )
                    self.assertEqual(
                        (backend.read_bytes(), ai.read_bytes()),
                        originals,
                    )

    @unittest.skipUnless(os.name == "posix", "POSIX permission gate")
    def test_group_readable_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend, ai = self._pair(Path(temporary))
            ai.chmod(0o640)
            with self.assertRaises(MODULE.ResumeRuntimeEnvironmentError):
                MODULE.prepare_resume_runtime_envs(
                    backend,
                    ai,
                    require_root=False,
                )
            self.assertEqual(stat.S_IMODE(ai.stat().st_mode), 0o640)


if __name__ == "__main__":
    unittest.main()
