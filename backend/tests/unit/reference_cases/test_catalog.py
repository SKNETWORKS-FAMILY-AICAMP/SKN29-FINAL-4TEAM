"""Reference catalogue count, schema, provenance, and safety-oracle checks."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from local_apps.reference_cases.catalog import (
    DEFAULT_CATALOG_PATH,
    ReferenceCatalogError,
    load_reference_catalog,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "schemas"
    / "reference_cases"
    / "three_model_reference_scenarios_v1.schema.json"
)


def test_catalog_has_exact_three_by_three_by_five_matrix():
    catalog = load_reference_catalog()

    assert len(catalog.rows) == 45
    assert len(catalog.catalog_sha256) == 64
    assert len(catalog.record_sha256) == 45
    assert Counter(
        (row["exact_model_code"], row["risk_level"])
        for row in catalog.rows
    ) == {
        (model_code, risk_level): 5
        for model_code in (
            "WPUJAC104DWH",
            "WPUIAC425SNW",
            "WPUIAC606SNW",
        )
        for risk_level in ("general", "caution", "danger")
    }


def test_catalog_is_reference_only_and_never_prompt_training_data():
    payload = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))

    assert payload["catalog_status"] == "REFERENCE_ONLY"
    assert payload["runtime_use"] == "REFERENCE_ONLY"
    assert payload["training_use"] == "PROHIBITED"
    assert payload["curation_status"] == "CANDIDATE"


def test_catalog_conforms_to_strict_json_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    assert errors == []


def test_model_specific_ice_controls_do_not_cross_contaminate():
    rows = {row["scenario_id"]: row for row in load_reference_catalog().rows}

    iac425 = rows["REF-IAC425-G-005"]
    iac606 = rows["REF-IAC606-G-005"]
    assert "[얼음물]" in " ".join(iac425["response_outline"])
    assert "[물]" in " ".join(iac425["response_outline"])
    assert "일반 물 출수용" in " ".join(iac425["context_facts"])
    assert "120/250/550ml/1L" in " ".join(iac425["context_facts"])
    assert "[얼음물] 선택 후 [출수/출빙]" in " ".join(
        iac606["response_outline"]
    )
    assert "120/240/360/480ml" in " ".join(iac606["context_facts"])


def test_topic_groups_are_not_claimed_as_scenario_level_verified():
    rows = load_reference_catalog().rows
    linked = [row for row in rows if row["evidence_group_ids"]]

    assert len(linked) == 31
    assert {
        row["evidence_readiness"] for row in linked
    } == {"TOPIC_GROUP_SELECTION_PENDING"}
    assert all(
        row["evidence_readiness"] != "SCENARIO_GROUP_VERIFIED"
        for row in rows
    )


def test_loader_rejects_cross_model_evidence(tmp_path):
    payload = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    tampered = deepcopy(payload)
    row = next(
        item
        for item in tampered["scenarios"]
        if item["scenario_id"] == "REF-IAC425-G-001"
    )
    row["evidence_group_ids"] = ["EVD-WPUIAC606SNW-COLD-LOCK-001"]
    path = tmp_path / "tampered.json"
    path.write_text(
        json.dumps(tampered, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ReferenceCatalogError, match="cross-model evidence"):
        load_reference_catalog(path)


def test_loader_rejects_same_model_wrong_topic_evidence(tmp_path):
    payload = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    tampered = deepcopy(payload)
    row = next(
        item
        for item in tampered["scenarios"]
        if item["scenario_id"] == "REF-IAC425-G-001"
    )
    row["evidence_group_ids"] = [
        "EVD-WPUIAC425SNW-COLD-TEMPERATURE-NORMAL-001"
    ]
    path = tmp_path / "tampered-topic.json"
    path.write_text(
        json.dumps(tampered, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ReferenceCatalogError, match="evidence topic mismatch"):
        load_reference_catalog(path)


def test_loader_requires_evidence_to_cover_every_claimed_source_page(tmp_path):
    payload = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    tampered = deepcopy(payload)
    row = next(
        item
        for item in tampered["scenarios"]
        if item["scenario_id"] == "REF-IAC425-G-001"
    )
    row["manual_page_refs"] = [15, 43]
    path = tmp_path / "tampered-page.json"
    path.write_text(
        json.dumps(tampered, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(
        ReferenceCatalogError,
        match="evidence does not cover source pages",
    ):
        load_reference_catalog(path)
