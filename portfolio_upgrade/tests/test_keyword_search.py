"""직접 설계한 세 가지 작은 요구사항 검사 (표준 unittest)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from keyword_search import search  # noqa: E402


class KeywordSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = json.loads((ROOT / "data" / "mini_corpus.json").read_text(encoding="utf-8"))["chunks"]

    def test_exact_manual_headings_are_first(self):
        for section, expected_id in [
            ("물이 출수되지 않음", "WB-DEMO-001"),
            ("출수량이 적을 경우", "WB-DEMO-002"),
            ("제품 누수 발생", "WB-DEMO-003"),
        ]:
            with self.subTest(section=section):
                self.assertEqual(search(section, self.chunks, top_k=1)[0]["chunk_id"], expected_id)

    def test_no_keyword_overlap_returns_empty(self):
        self.assertEqual(search("고양이 우주선", self.chunks), [])

    def test_top_k_is_respected(self):
        self.assertLessEqual(len(search("필터 교체", self.chunks, top_k=1)), 1)


if __name__ == "__main__":
    unittest.main()
