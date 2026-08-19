"""Load the PM-approved T-020 rule package with fail-closed validation."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from django.utils import timezone

from apps.care.models import CareRecord
from apps.care.models.care_schedule import (
    CareCycleRule,
    CareScheduleBasis,
)
from apps.care.services.care_cycle_rule_registry import (
    ApprovedCareCycleRule,
    ApprovedCareCycleRuleRegistry,
)
from apps.subscriptions.models import CustomerSubscription


POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "policies"
    / "approved_care_cycle_rules_v1.json"
)
ROOT_FIELDS = {
    "schema_version",
    "status",
    "policy_id",
    "approval_reference",
    "effective_on",
    "usage_adjustment_mode",
    "rules",
}
RULE_FIELDS = {
    "product_model_code",
    "management_type_code",
    "care_type_code",
    "interval_months",
    "basis",
    "source_page_id",
    "source_version",
    "source_page_text_sha256",
    "source_file_sha256",
}
SHA256_PATTERN = re.compile(r"^[0-9A-F]{64}$")


class ApprovedCareCyclePolicyError(ValueError):
    """Raised when an approved policy package cannot be trusted."""


def load_approved_care_cycle_rule_registry(
    *,
    as_of: date | None = None,
    policy_path: Path = POLICY_PATH,
) -> ApprovedCareCycleRuleRegistry:
    """Return only rules whose approved effective date has started."""

    package = _load_json_object(policy_path)
    _require_exact_fields(package, ROOT_FIELDS, scope="policy")
    _require_exact(package, "schema_version", "1.0")
    _require_exact(package, "status", "APPROVED")
    _require_nonblank(package, "policy_id")
    _require_nonblank(package, "approval_reference")
    _require_exact(package, "usage_adjustment_mode", "NOTICE_ONLY")
    effective_on = _parse_date(package, "effective_on")

    raw_rules = package["rules"]
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ApprovedCareCyclePolicyError("rules must be a non-empty list")

    active_on = as_of or timezone.localdate()
    if not isinstance(active_on, date):
        raise ApprovedCareCyclePolicyError("as_of must be a date")
    if effective_on > active_on:
        return ApprovedCareCycleRuleRegistry([])

    entries = [_build_entry(raw_rule) for raw_rule in raw_rules]
    return ApprovedCareCycleRuleRegistry(entries)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes().decode("utf-8")
        package = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovedCareCyclePolicyError(
            "approved care-cycle policy is unreadable"
        ) from exc
    if not isinstance(package, dict):
        raise ApprovedCareCyclePolicyError("policy root must be an object")
    return package


def _build_entry(raw_rule: Any) -> ApprovedCareCycleRule:
    if not isinstance(raw_rule, dict):
        raise ApprovedCareCyclePolicyError("each rule must be an object")
    _require_exact_fields(raw_rule, RULE_FIELDS, scope="rule")
    product_model_code = _require_nonblank(
        raw_rule,
        "product_model_code",
    )
    management_type_code = _require_nonblank(
        raw_rule,
        "management_type_code",
    )
    care_type_code = _require_nonblank(raw_rule, "care_type_code")
    basis = _require_nonblank(raw_rule, "basis")
    source_page_id = _require_nonblank(raw_rule, "source_page_id")
    source_version = _require_nonblank(raw_rule, "source_version")
    _require_sha256(raw_rule, "source_page_text_sha256")
    _require_sha256(raw_rule, "source_file_sha256")

    if management_type_code not in CustomerSubscription.ManagementType.values:
        raise ApprovedCareCyclePolicyError(
            "management_type_code is outside the subscription contract"
        )
    if care_type_code not in CareRecord.CareType.values:
        raise ApprovedCareCyclePolicyError(
            "care_type_code is outside the care contract"
        )
    if basis not in CareScheduleBasis.values:
        raise ApprovedCareCyclePolicyError("basis is outside the care contract")

    interval_months = raw_rule["interval_months"]
    if isinstance(interval_months, bool) or not isinstance(interval_months, int):
        raise ApprovedCareCyclePolicyError("interval_months must be an integer")
    if not 1 <= interval_months <= 120:
        raise ApprovedCareCyclePolicyError(
            "interval_months is outside the care contract"
        )

    return ApprovedCareCycleRule(
        product_model_code=product_model_code,
        management_type_code=management_type_code,
        rule=CareCycleRule(
            care_type_code=care_type_code,
            interval_months=interval_months,
            basis=basis,
            source_reference=f"manual-page://{source_page_id}",
            source_version=source_version,
        ),
    )


def _require_exact_fields(
    value: dict[str, Any],
    expected: set[str],
    *,
    scope: str,
) -> None:
    if set(value) != expected:
        raise ApprovedCareCyclePolicyError(f"{scope} fields do not match")


def _require_nonblank(value: dict[str, Any], field: str) -> str:
    raw = value[field]
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        raise ApprovedCareCyclePolicyError(f"{field} must be non-blank")
    return raw


def _require_exact(value: dict[str, Any], field: str, expected: str) -> None:
    if _require_nonblank(value, field) != expected:
        raise ApprovedCareCyclePolicyError(f"{field} is not approved")


def _require_sha256(value: dict[str, Any], field: str) -> str:
    digest = _require_nonblank(value, field)
    if SHA256_PATTERN.fullmatch(digest) is None:
        raise ApprovedCareCyclePolicyError(f"{field} is not canonical SHA-256")
    return digest


def _parse_date(value: dict[str, Any], field: str) -> date:
    raw = _require_nonblank(value, field)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ApprovedCareCyclePolicyError(
            f"{field} must be an ISO date"
        ) from exc
