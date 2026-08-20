from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.builders import build_synthetic_preview
from watercare.config import load_pipeline
from watercare.io import read_json, sha256_file
from watercare.validation import validate_product_expansion_coverage


EXPECTED_FIXTURE_HASHES = {
    "audit_events.json": "2B9A586B14B0F44E9A30A458D6E152B87F6161D3D7367AEEA46BFD3208A90FFD",
    "care_histories.json": "643C0E160E25E07E81C7C1406F90D877EE24080FAC1A597B3D78221F89EB0470",
    "consultations.json": "0DA954EF7615A10385145CD583B3B3C7B2D4FBB3D4C65E67BC8618B2D102E7EB",
    "customer_products.json": "83FF8FF825380AF9ECA07C952655D2096CCB8F33B1D33B264547B207E65AFCE3",
    "customer_profiles.json": "5918EC8D52D731402CCDFCC6DAEEF468BCDEFFA850A045CB35EBD5D8A3129CA8",
    "followup_confirmations.json": "5172FEF53B6AB4F2DC292F15B96F68DB801C7247C79A3C5D3720475C0594703A",
    "inquiries.json": "4F43D4EDC7ECFEA682728C77E3A79740AA62AD6BB411D2170FD13371596B6CC5",
    "inquiry_status_histories.json": "26E49C6E468AAEF5E1FD18340E9A7B0DF58E290ADA61075749511FB71DA7D7AF",
    "products.json": "1CBED4342ABDD21185B66475D0D41CE2F70B843CF1A2ABE88081F43E2F0249A6",
    "subscriptions.json": "2667B19F662FFAAC1A473E263E35C28642E360ACEBA07FF55563CB24759DC77F",
    "users.json": "C450F72529C3A288E8175B3FDDD504C16EA7BCBB93FBABBA03AE78342A971FC0",
    "visits.json": "1D4892E06A9CE189DC984516A5894DCC8B93509EE2D07087C61A762BE33E6F00",
}


class ProductExpansionCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)

    def test_coverage_gate_passes_for_canonical_and_candidate_chains(self) -> None:
        report = validate_product_expansion_coverage(self.config)
        self.assertEqual([], report["errors"])
        self.assertEqual("PASS", report["status"])
        self.assertEqual(12, report["canonical"]["customer_products"])
        self.assertEqual(12, report["canonical"]["subscriptions"])
        self.assertEqual(22, report["canonical"]["inquiries"])
        self.assertEqual(2, report["candidates"]["records"])

    def test_candidate_output_matches_deterministic_builder(self) -> None:
        preview = build_synthetic_preview(self.config)[
            "product_expansion_e2e_candidates"
        ]
        path, content, records = preview
        self.assertEqual(2, records)
        self.assertEqual(path.read_bytes(), content)

    def test_candidate_cannot_claim_runtime_verification(self) -> None:
        target = self.config.path("product_expansion_candidate_output")
        tampered = deepcopy(read_json(target))
        tampered[0]["runtime_status"] = "VERIFIED"
        real_read_json = read_json

        def substitute(path: Path):
            if Path(path).resolve() == target.resolve():
                return tampered
            return real_read_json(path)

        with patch("watercare.validation.read_json", side_effect=substitute):
            report = validate_product_expansion_coverage(self.config)
        self.assertIn(
            "product_coverage:candidate_status_mismatch:WPUIAC425SNW",
            report["errors"],
        )

    def test_cross_model_evidence_is_rejected(self) -> None:
        target = self.config.path("product_expansion_candidate_output")
        tampered = deepcopy(read_json(target))
        tampered[0]["evidence"]["exact_sales_code"] = "WPUIAC606SNW"
        real_read_json = read_json

        def substitute(path: Path):
            if Path(path).resolve() == target.resolve():
                return tampered
            return real_read_json(path)

        with patch("watercare.validation.read_json", side_effect=substitute):
            report = validate_product_expansion_coverage(self.config)
        self.assertIn(
            "product_coverage:grounding_mismatch:WPUIAC425SNW",
            report["errors"],
        )

    def test_broken_candidate_relation_is_rejected(self) -> None:
        target = self.config.path("product_expansion_candidate_output")
        tampered = deepcopy(read_json(target))
        tampered[1]["subscription"]["parent_ref"] = "CAND-CP-IAC425-001"
        real_read_json = read_json

        def substitute(path: Path):
            if Path(path).resolve() == target.resolve():
                return tampered
            return real_read_json(path)

        with patch("watercare.validation.read_json", side_effect=substitute):
            report = validate_product_expansion_coverage(self.config)
        self.assertIn(
            "product_coverage:chain_reference_mismatch:WPUIAC606SNW",
            report["errors"],
        )

    def test_backend_fixture_files_remain_byte_identical(self) -> None:
        fixture_root = DATA_ROOT / "synthetic" / "fixtures"
        actual = {
            path.name: sha256_file(path)
            for path in sorted(fixture_root.glob("*.json"))
        }
        self.assertEqual(EXPECTED_FIXTURE_HASHES, actual)


if __name__ == "__main__":
    unittest.main()
