"""구독 TextChoices와 공통 코드 YAML parity 검증."""

from pathlib import Path

import yaml

from apps.subscriptions.models import CustomerSubscription


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CODE_CONTRACT_DIR = REPOSITORY_ROOT / "contracts" / "codes"


def contract_codes(filename: str) -> set[str]:
    document = yaml.safe_load(
        (CODE_CONTRACT_DIR / filename).read_text(encoding="utf-8")
    )
    return set(document["codes"])


def test_management_type_contract_matches_text_choices():
    assert contract_codes("management-types.yaml") == set(
        CustomerSubscription.ManagementType.values
    )


def test_subscription_status_contract_matches_text_choices():
    assert contract_codes("subscription-statuses.yaml") == set(
        CustomerSubscription.Status.values
    )
