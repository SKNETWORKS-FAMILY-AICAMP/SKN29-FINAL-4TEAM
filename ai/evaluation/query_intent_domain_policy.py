"""Label-independent Query Intent·Domain Policy for B2-2 experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class QueryIntentDecision:
    blocked: bool
    policy_id: str
    rule_id: str | None = None
    intent_family: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentalQueryIntentDomainPolicy:
    """Apply explicit conjunction rules without reading evaluation labels."""

    def __init__(self, definition: dict[str, Any]) -> None:
        self.definition = definition
        self.policy_id = definition["policy_id"]

    def evaluate(self, *, product_model_code: str, query: str) -> QueryIntentDecision:
        del product_model_code  # Reserved for product-specific intent rules.
        if not self.definition.get("enabled", False):
            return QueryIntentDecision(False, self.policy_id)

        normalized = " ".join(query.casefold().split())
        for rule in self.definition.get("rules", []):
            if any(term.casefold() in normalized for term in rule.get("excluded_terms", [])):
                continue
            groups = rule.get("any_term_groups", [])
            if groups and all(
                any(term.casefold() in normalized for term in group)
                for group in groups
            ):
                return QueryIntentDecision(
                    True,
                    self.policy_id,
                    rule["rule_id"],
                    rule["intent_family"],
                    rule["reason"],
                )
        return QueryIntentDecision(False, self.policy_id)
