from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
REPO_ROOT = DATA_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import sha256_file


class CliCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.generated_at = cls.config.generated_at

    def run_command(self, *arguments: str) -> None:
        result = subprocess.run(
            [sys.executable, "-B", *arguments],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def hashes(self, keys: list[str]) -> dict[str, str]:
        return {key: sha256_file(self.config.path(key)) for key in keys}

    def test_rag_wrapper_and_unified_cli_are_equivalent(self) -> None:
        keys = ["faq_input", "ocr_output", "asset_output", "rag_output", "evidence_output"]
        self.run_command(
            str(TOOLS_ROOT / "build_step3.py"),
            "--generated-at",
            self.generated_at,
        )
        wrapper = self.hashes(keys)
        self.run_command(
            str(TOOLS_ROOT / "pipeline.py"),
            "build",
            "rag",
            "--generated-at",
            self.generated_at,
        )
        self.assertEqual(wrapper, self.hashes(keys))

    def test_synthetic_wrapper_and_unified_cli_are_equivalent(self) -> None:
        paths = [
            DATA_ROOT / relative
            for relative in self.config.config("synthetic")["outputs"].values()
        ]
        self.run_command(
            str(TOOLS_ROOT / "build_step4.py"),
            "--generated-at",
            self.generated_at,
        )
        wrapper = {path.as_posix(): sha256_file(path) for path in paths}
        self.run_command(
            str(TOOLS_ROOT / "pipeline.py"),
            "build",
            "synthetic",
            "--generated-at",
            self.generated_at,
        )
        self.assertEqual(wrapper, {path.as_posix(): sha256_file(path) for path in paths})

    def test_all_entry_points_expose_help(self) -> None:
        scripts = [TOOLS_ROOT / "pipeline.py", *sorted(TOOLS_ROOT.glob("build_step*.py"))]
        for script in scripts:
            self.run_command(str(script), "--help")


if __name__ == "__main__":
    unittest.main()
