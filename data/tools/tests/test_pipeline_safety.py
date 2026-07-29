from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.builders import build_rag_preview, build_synthetic_preview
from watercare.config import load_pipeline
from watercare.io import (
    data_path,
    read_lf_bytes,
    sha256_bytes,
    sha256_text_file,
    write_bytes,
)


class PipelineSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)

    def test_path_escape_is_blocked(self) -> None:
        with self.assertRaises(ValueError):
            data_path(DATA_ROOT, "../outside.json")
        with self.assertRaises(ValueError):
            data_path(DATA_ROOT, str(DATA_ROOT.parent / "outside.json"))

    def test_atomic_write_replaces_content_without_temp_residue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "nested/result.json"
            write_bytes(root, target, b'{"version":1}\n')
            write_bytes(root, target, b'{"version":2}\n')
            self.assertEqual(b'{"version":2}\n', target.read_bytes())
            self.assertEqual(
                [],
                list(target.parent.glob(f".{target.name}.*.tmp")),
            )

    def test_text_source_hash_is_line_ending_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lf = root / "lf.txt"
            crlf = root / "crlf.txt"
            lone_cr = root / "cr.txt"
            lf.write_bytes(b"first\nsecond\n")
            crlf.write_bytes(b"first\r\nsecond\r\n")
            lone_cr.write_bytes(b"first\rsecond\r")
            self.assertEqual(sha256_text_file(lf), sha256_text_file(crlf))
            self.assertEqual(sha256_text_file(lf), sha256_text_file(lone_cr))
            self.assertEqual(read_lf_bytes(lf), read_lf_bytes(crlf))
            self.assertEqual(len(read_lf_bytes(lf)), len(read_lf_bytes(crlf)))

    def test_two_builds_are_byte_deterministic(self) -> None:
        first = {**build_rag_preview(self.config), **build_synthetic_preview(self.config)}
        second = {**build_rag_preview(self.config), **build_synthetic_preview(self.config)}
        self.assertEqual(first.keys(), second.keys())
        for key in first:
            self.assertEqual(sha256_bytes(first[key][1]), sha256_bytes(second[key][1]), key)

    def test_declarative_outputs_match_canonical_files(self) -> None:
        previews = {**build_rag_preview(self.config), **build_synthetic_preview(self.config)}
        for name, (path, content, _) in previews.items():
            self.assertEqual(path.read_bytes(), content, name)

    def test_deterministic_ids_and_times_are_preserved(self) -> None:
        synthetic = self.config.config("synthetic")
        inquiries = synthetic["materialized_outputs"]["inquiries"]
        self.assertEqual(24, len({row["id"] for row in inquiries}))
        self.assertEqual(24, len({row["public_id"] for row in inquiries}))
        self.assertTrue(all(isinstance(row["id"], int) for row in inquiries))
        self.assertTrue(all(row["created_at"].endswith("+09:00") for row in inquiries))
        self.assertTrue(all(row["correlation_id"] for row in inquiries))

    def test_raw_non_retention_policy(self) -> None:
        files = [path for path in (DATA_ROOT / "raw").rglob("*") if path.is_file()]
        original_suffixes = {
            ".pdf", ".json", ".jsonl", ".csv", ".html", ".htm", ".jpg", ".jpeg", ".png"
        }
        self.assertEqual(7, len(files))
        self.assertFalse(any(path.suffix.lower() in original_suffixes for path in files))
        self.assertFalse((DATA_ROOT / ".temp").exists())
        self.assertFalse((DATA_ROOT / ".work").exists())

    def test_wrappers_are_thin_and_data_free(self) -> None:
        forbidden = ["SK magic 정수기", "고서온", "https://json-schema.org/draft"]
        for path in sorted(TOOLS_ROOT.glob("build_step*.py")):
            text = path.read_text(encoding="utf-8")
            self.assertLessEqual(len(text.splitlines()), 30, path.name)
            self.assertIn("legacy_main", text)
            self.assertFalse(any(token in text for token in forbidden), path.name)


if __name__ == "__main__":
    unittest.main()
