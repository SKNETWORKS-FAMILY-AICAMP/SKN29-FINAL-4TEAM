"""Label-independent query scope decisions for Experiment Lab retrieval runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class QueryScopeDecision:
    blocked: bool
    policy_id: str
    rule_id: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentalQueryScopePolicy:
    """Apply explicit model and capability rules without reading Gold labels."""

    def __init__(self, definition: dict[str, Any]) -> None:
        self.definition = definition
        self.policy_id = definition["policy_id"]

    def evaluate(self, *, product_model_code: str, query: str) -> QueryScopeDecision:
        if not self.definition.get("enabled", False):
            return QueryScopeDecision(False, self.policy_id)

        supported = set(self.definition.get("supported_model_codes", []))
        if supported and product_model_code not in supported:
            return QueryScopeDecision(
                True,
                self.policy_id,
                self.definition.get("unsupported_model_rule_id"),
                "실험 Profile이 지원하지 않는 제품 모델",
            )

        normalized_query = query.casefold()
        for rule in self.definition.get("unsupported_feature_rules", []):
            if product_model_code not in set(rule.get("model_codes", [])):
                continue
            if any(term.casefold() in normalized_query for term in rule.get("terms", [])):
                return QueryScopeDecision(
                    True,
                    self.policy_id,
                    rule["rule_id"],
                    rule["reason"],
                )
        return QueryScopeDecision(False, self.policy_id)
