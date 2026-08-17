"""T-020 approved care-cycle rule lookup without embedded policy values."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from apps.care.models import CareRecord
from apps.care.models.care_schedule import CareCycleRule
from apps.subscriptions.models import CustomerSubscription


RuleKey = tuple[str, str, str]


@dataclass(frozen=True)
class ApprovedCareCycleRule:
    """Bind one externally approved rule to its exact subscription scope."""

    product_model_code: str
    management_type_code: str
    rule: CareCycleRule

    def __post_init__(self) -> None:
        if (
            not isinstance(self.product_model_code, str)
            or not self.product_model_code.strip()
        ):
            raise ValueError("product_model_code is required")
        if self.product_model_code != self.product_model_code.strip():
            raise ValueError("product_model_code must not contain outer whitespace")
        if (
            self.management_type_code
            not in CustomerSubscription.ManagementType.values
        ):
            raise ValueError(
                "management_type_code is not in the subscription contract"
            )
        if not isinstance(self.rule, CareCycleRule):
            raise ValueError("rule must be a CareCycleRule")
        if self.rule.care_type_code not in CareRecord.CareType.values:
            raise ValueError("care_type_code is not in the CareRecord contract")

    @property
    def key(self) -> RuleKey:
        return (
            self.product_model_code,
            self.management_type_code,
            self.rule.care_type_code,
        )


class ApprovedCareCycleRuleRegistry:
    """Immutable exact-match adapter populated only by an approved source."""

    def __init__(self, entries: Iterable[ApprovedCareCycleRule]) -> None:
        rules: dict[RuleKey, CareCycleRule] = {}
        for entry in entries:
            if entry.key in rules:
                raise ValueError("duplicate approved care-cycle rule scope")
            rules[entry.key] = entry.rule
        self._rules: Mapping[RuleKey, CareCycleRule] = MappingProxyType(rules)

    @property
    def size(self) -> int:
        return len(self._rules)

    def resolve(
        self,
        *,
        product_model_code: str,
        management_type_code: str,
        care_type_code: str,
    ) -> CareCycleRule | None:
        """Return an exact approved rule or fail closed with no rule."""

        if (
            not isinstance(product_model_code, str)
            or not isinstance(management_type_code, str)
            or not isinstance(care_type_code, str)
        ):
            return None
        return self._rules.get(
            (
                product_model_code,
                management_type_code,
                care_type_code,
            )
        )
