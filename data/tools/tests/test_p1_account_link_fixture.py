from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import read_json
from watercare.validation import (
    count_synthetic_fixture_records,
    validate_p1_account_link_candidates,
    validate_schema,
)


class P1AccountLinkFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.target = cls.config.path("p1_account_link_candidate_output")

    def _validate_tampered(self, rows: list[dict]) -> list[str]:
        real_read_json = read_json

        def substitute(path: Path):
            if Path(path).resolve() == self.target.resolve():
                return rows
            return real_read_json(path)

        with patch("watercare.validation.read_json", side_effect=substitute):
            return validate_p1_account_link_candidates(self.config)["errors"]

    def test_candidate_schema_and_business_gate_pass(self) -> None:
        rows = read_json(self.target)
        schema = read_json(
            DATA_ROOT
            / "schemas"
            / "synthetic"
            / "p1AccountLinkCandidate.schema.json"
        )
        self.assertEqual(1, len(rows))
        self.assertEqual([], validate_schema(rows[0], schema))
        self.assertEqual(
            {
                "status": "PASS",
                "errors": [],
                "records": 1,
                "fixture_ids": ["P1-ACCOUNT-LINK-001"],
            },
            validate_p1_account_link_candidates(self.config),
        )

    def test_candidate_is_not_in_backend_import_crosswalk(self) -> None:
        crosswalk = self.config.config("backend_crosswalk")
        fixtures = {row["fixture"] for row in crosswalk["entity_mappings"]}
        self.assertNotIn(
            "synthetic/candidates/p1_account_link_candidates.json",
            fixtures,
        )

    def test_candidate_does_not_change_p0_fixture_total(self) -> None:
        synthetic = self.config.config("synthetic")
        outputs = {
            key: read_json(DATA_ROOT / path)
            for key, path in synthetic["outputs"].items()
        }
        self.assertEqual(369, count_synthetic_fixture_records(outputs))

    def test_actual_email_is_rejected(self) -> None:
        tampered = deepcopy(read_json(self.target))
        tampered[0]["contract_email"]["synthetic_address"] = (
            "customer@example.com"
        )
        self.assertIn(
            "p1_account_link:non_synthetic_email:P1-ACCOUNT-LINK-001",
            self._validate_tampered(tampered),
        )

    def test_forbidden_identity_and_secret_fields_are_rejected(self) -> None:
        tampered = deepcopy(read_json(self.target))
        tampered[0]["customer_candidate"]["user_id"] = 1
        tampered[0]["contract_email"]["secret"] = "not-a-real-secret"
        errors = self._validate_tampered(tampered)
        self.assertTrue(
            any("forbidden_field" in error and "user_id" in error for error in errors)
        )
        self.assertTrue(
            any("forbidden_field" in error and "secret" in error for error in errors)
        )

    def test_unsupported_product_is_rejected(self) -> None:
        tampered = deepcopy(read_json(self.target))
        tampered[0]["subscription"]["product_model_code"] = "DEMO-PMD-001"
        self.assertIn(
            "p1_account_link:unsupported_product:P1-ACCOUNT-LINK-001:DEMO-PMD-001",
            self._validate_tampered(tampered),
        )

    def test_premature_promotion_is_rejected(self) -> None:
        tampered = deepcopy(read_json(self.target))
        tampered[0]["promotion"]["canonical_fixture_included"] = True
        self.assertIn(
            "p1_account_link:promotion_state_mismatch:P1-ACCOUNT-LINK-001",
            self._validate_tampered(tampered),
        )


if __name__ == "__main__":
    unittest.main()
