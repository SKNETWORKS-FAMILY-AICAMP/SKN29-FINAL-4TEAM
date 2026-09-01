"""Regression tests for the data pipeline's JSON Schema boundary."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.io import read_json
from watercare.validation import validate_schema


class SchemaValidationTests(unittest.TestCase):
    def test_inquiry_rejects_zero_state_version(self) -> None:
        schema = read_json(DATA_ROOT / "schemas/synthetic/syntheticInquiry.schema.json")
        inquiry = deepcopy(read_json(DATA_ROOT / "synthetic/fixtures/inquiries.json")[0])
        self.assertEqual([], validate_schema(inquiry, schema))
        inquiry["state_version"] = 0
        errors = validate_schema(inquiry, schema)
        self.assertTrue(any("state_version" in error for error in errors))

    def test_real_config_enforces_local_refs_and_array_limit(self) -> None:
        schema = read_json(DATA_ROOT / "schemas/config/productExpansionE2ECases.schema.json")
        config = read_json(DATA_ROOT / "config/synthetic/product_expansion_e2e_cases.json")
        self.assertEqual([], validate_schema(config, schema))
        config["cases"] = [{}, {}, {}]
        errors = validate_schema(config, schema)
        self.assertTrue(any("maxItems" in error for error in errors))
        self.assertTrue(any("cases[0]" in error and "required" in error for error in errors))

    def test_representative_schema_matches_fourteen_step_fixture(self) -> None:
        schema = read_json(DATA_ROOT / "schemas/config/representativeCase.schema.json")
        case = read_json(DATA_ROOT / "config/e2e/representative_case.json")
        self.assertEqual(14, case["final_state_version"])
        self.assertEqual(14, case["expected_counts"]["representative_steps"])
        self.assertEqual(14, len(case["expected_events"]))
        self.assertEqual([], validate_schema(case, schema))
        for events in (case["expected_events"][:-1], [*case["expected_events"], "EXTRA_EVENT"]):
            with self.subTest(count=len(events)):
                changed = {**case, "expected_events": events}
                self.assertTrue(validate_schema(changed, schema))

    def test_composition_and_contains_are_enforced(self) -> None:
        examples = (
            (3, {"allOf": [{"minimum": 1}, {"maximum": 2}]}),
            (True, {"anyOf": [{"type": "string"}, {"type": "number"}]}),
            (2, {"oneOf": [{"type": "number"}, {"type": "integer"}]}),
            (["other"], {"type": "array", "contains": {"const": "required"}}),
            ({"enabled": True}, {
                "if": {"properties": {"enabled": {"const": True}}},
                "then": {"required": ["reason"]},
            }),
        )
        for value, schema in examples:
            with self.subTest(schema=schema):
                self.assertTrue(validate_schema(value, schema))

    def test_formats_do_not_silently_accept_invalid_values(self) -> None:
        for format_name, value in (
            ("uuid", "not-a-uuid"),
            ("uri", "not a uri"),
            ("uri", "https://"),
            ("uri", "https://example.invalid:invalid"),
            ("date", "2026-02-30"),
            ("date-time", "2026-08-31"),
            ("date-time", "2026-08-31T12:00:00"),
            ("date-time", "2026-02-30T12:00:00Z"),
        ):
            with self.subTest(format=format_name, value=value):
                self.assertTrue(validate_schema(value, {"type": "string", "format": format_name}))

    def test_datetime_preserves_valid_offsets(self) -> None:
        schema = {"type": "string", "format": "date-time"}
        for value in ("2026-08-31T00:00:00Z", "2026-08-31T09:00:00+09:00"):
            self.assertEqual([], validate_schema(value, schema))

    def test_existing_type_and_format_guards_are_preserved(self) -> None:
        self.assertTrue(validate_schema(True, {"type": "integer"}))
        self.assertTrue(validate_schema(False, {"type": "number"}))
        self.assertTrue(validate_schema({"extra": 1}, {"type": "object", "additionalProperties": False}))
        self.assertTrue(validate_schema([1, 1], {"type": "array", "uniqueItems": True}))
        self.assertEqual([], validate_schema("https://example.invalid/manual.pdf", {"format": "uri"}))
        self.assertEqual([], validate_schema(None, {"type": ["integer", "null"], "minimum": 1}))

    def test_errors_are_deterministic_and_do_not_include_input_values(self) -> None:
        schema = {"type": "object", "properties": {"rows": {
            "type": "array", "items": {"type": "integer", "minimum": 1},
        }}}
        value = {"rows": ["synthetic-private-sentinel", 0]}
        errors = validate_schema(value, schema, path="fixture")
        self.assertTrue(errors)
        self.assertEqual(errors, validate_schema(value, schema, path="fixture"))
        self.assertTrue(any("fixture.rows[0]" in error for error in errors))
        self.assertNotIn("synthetic-private-sentinel", str(errors))

    def test_invalid_schema_and_unresolvable_refs_fail_closed(self) -> None:
        for schema in ({"type": "not-a-type"}, {"$ref": "#/$defs/missing"}):
            with self.subTest(schema=schema):
                self.assertTrue(validate_schema({}, schema))

    def test_external_ref_never_fetches_network_resources(self) -> None:
        with patch("urllib.request.urlopen", side_effect=AssertionError("network prohibited")) as fetch:
            errors = validate_schema({}, {"$ref": "https://example.invalid/schema.json"})
        self.assertTrue(errors)
        fetch.assert_not_called()

    def test_schema_mutation_does_not_reuse_stale_validation(self) -> None:
        schema = {"type": "integer", "minimum": 1}
        self.assertEqual([], validate_schema(2, schema))
        schema["minimum"] = 3
        self.assertTrue(validate_schema(2, schema))


if __name__ == "__main__":
    unittest.main()
