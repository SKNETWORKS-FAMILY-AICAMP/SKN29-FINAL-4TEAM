"""T-020 approved care-cycle policy package tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest

from apps.care.models import CareRecord
from apps.care.services.approved_care_cycle_rule_loader import (
    POLICY_PATH,
    ApprovedCareCyclePolicyError,
    load_approved_care_cycle_rule_registry,
)
from apps.subscriptions.models import CustomerSubscription


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
OFFICIAL_PAGE_DATASET = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "documents"
    / "manuals"
    / "mvp"
    / "manual_pages_jac104d.jsonl"
)


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def write_policy(tmp_path: Path, package: dict) -> Path:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    return path


def test_approved_policy_resolves_only_exact_p0_scope():
    registry = load_approved_care_cycle_rule_registry(
        as_of=date(2026, 8, 18)
    )

    approved = registry.resolve(
        product_model_code="WPUJAC104DWH",
        management_type_code=CustomerSubscription.ManagementType.SELF_MANAGED,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
    )

    assert registry.size == 1
    assert approved is not None
    assert approved.interval_months == 4
    assert approved.basis == "OFFICIAL"
    assert approved.source_reference.endswith("REV00-P031")
    assert registry.resolve(
        product_model_code="WPUJAC104DWH",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
    ) is None
    assert registry.resolve(
        product_model_code="WPUIAC425SNW",
        management_type_code=CustomerSubscription.ManagementType.SELF_MANAGED,
        care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
    ) is None


def test_policy_source_identity_matches_the_official_page_dataset():
    package = load_policy()
    rule = package["rules"][0]
    pages = [
        json.loads(line)
        for line in OFFICIAL_PAGE_DATASET.read_text(
            encoding="utf-8-sig"
        ).splitlines()
        if line.strip()
    ]
    page = next(
        item for item in pages if item["page_id"] == rule["source_page_id"]
    )

    assert page["exact_sales_code"] == rule["product_model_code"]
    assert page["version"] == rule["source_version"]
    assert page["text_sha256"] == rule["source_page_text_sha256"]
    assert page["source_file_sha256"] == rule["source_file_sha256"]
    assert "4 개월" in page["text"]
    assert "12 개월" in page["text"]


def test_future_policy_is_not_activated(tmp_path: Path):
    package = load_policy()
    package["effective_on"] = "2026-08-19"

    registry = load_approved_care_cycle_rule_registry(
        as_of=date(2026, 8, 18),
        policy_path=write_policy(tmp_path, package),
    )

    assert registry.size == 0


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda package: package.update(status="DRAFT"), "status"),
        (
            lambda package: package["rules"][0].update(
                interval_months="4"
            ),
            "interval_months",
        ),
        (
            lambda package: package["rules"][0].update(
                source_page_text_sha256="not-a-digest"
            ),
            "source_page_text_sha256",
        ),
        (
            lambda package: package["rules"][0].update(
                unexpected="value"
            ),
            "fields",
        ),
    ],
)
def test_policy_validation_fails_closed(tmp_path: Path, mutator, reason: str):
    package = deepcopy(load_policy())
    mutator(package)

    with pytest.raises(ApprovedCareCyclePolicyError, match=reason):
        load_approved_care_cycle_rule_registry(
            as_of=date(2026, 8, 18),
            policy_path=write_policy(tmp_path, package),
        )
