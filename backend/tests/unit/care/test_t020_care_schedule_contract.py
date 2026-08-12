"""T-020 calculation contract and source boundary tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from apps.care.models.care_schedule import (
    CareScheduleBasis,
    CareScheduleStatus,
)


ROOT = Path(__file__).resolve().parents[4]
SCHEMAS = ROOT / "contracts" / "api" / "components" / "schemas" / "care"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_next_schedule_schema_forbids_unverified_date_guessing():
    schema = load_yaml(SCHEMAS / "NextCareSchedule.yaml")

    assert schema["additionalProperties"] is False
    assert schema["x-rule-policy"]["no_guessing"] is True
    assert schema["x-rule-policy"]["month_end_policy"] == "LAST_VALID_DAY"
    assert schema["properties"]["status"]["enum"] == list(
        CareScheduleStatus.values
    )
    assert schema["properties"]["basis"]["enum"] == [
        *CareScheduleBasis.values,
        None,
    ]
    assert set(schema["required"]) == set(schema["properties"])


def test_cycle_rule_requires_source_version_and_calendar_month_interval():
    schema = load_yaml(SCHEMAS / "CareCycleRule.yaml")

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "care_type_code",
        "interval_months",
        "basis",
        "source_reference",
        "source_version",
    }
    assert schema["properties"]["interval_months"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 120,
    }
    assert schema["properties"]["basis"]["enum"] == list(
        CareScheduleBasis.values
    )
