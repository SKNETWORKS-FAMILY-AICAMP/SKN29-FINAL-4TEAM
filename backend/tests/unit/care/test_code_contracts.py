"""CareRecord TextChoices와 공통 코드 YAML parity 검증."""

from pathlib import Path

import yaml

from apps.care.models import CareRecord


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CODE_CONTRACT_DIR = REPOSITORY_ROOT / "contracts" / "codes"


def contract_codes(filename: str) -> set[str]:
    document = yaml.safe_load(
        (CODE_CONTRACT_DIR / filename).read_text(encoding="utf-8")
    )
    return set(document["codes"])


def test_care_type_contract_matches_text_choices():
    assert contract_codes("care-types.yaml") == set(
        CareRecord.CareType.values
    )


def test_care_status_contract_matches_text_choices():
    assert contract_codes("care-statuses.yaml") == set(
        CareRecord.Status.values
    )


def test_care_result_contract_matches_text_choices():
    assert contract_codes("care-results.yaml") == set(
        CareRecord.Result.values
    )


def test_data_source_contract_matches_text_choices():
    assert contract_codes("data-sources.yaml") == set(
        CareRecord.Source.values
    )
