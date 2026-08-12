"""Deterministic query-only alias expansion for Experiment Lab comparisons."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_alias_text(value: str) -> str:
    """Normalize text for bounded substring matching without changing semantics."""

    return _WHITESPACE_PATTERN.sub(
        " ", unicodedata.normalize("NFKC", value).casefold()
    ).strip()


@dataclass(frozen=True, slots=True)
class AliasExpansionDecision:
    original_query: str
    expanded_query: str
    applied_rule_ids: tuple[str, ...]
    appended_terms: tuple[str, ...]

    @property
    def applied(self) -> bool:
        return bool(self.applied_rule_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original_query,
            "expanded_query": self.expanded_query,
            "applied": self.applied,
            "applied_rule_ids": list(self.applied_rule_ids),
            "appended_terms": list(self.appended_terms),
        }


class DraftAliasQueryExpander:
    """Append reviewable canonical terms to a query using immutable phrase rules."""

    def __init__(self, definition: dict[str, Any]) -> None:
        self.policy_id = str(definition.get("policy_id", "")).strip()
        if not self.policy_id:
            raise ValueError("Alias Policy ID가 필요합니다.")

        rules = definition.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("Alias Rule이 비어 있습니다.")

        validated: list[dict[str, Any]] = []
        seen_rule_ids: set[str] = set()
        for rule in rules:
            rule_id = str(rule.get("rule_id", "")).strip()
            if not rule_id or rule_id in seen_rule_ids:
                raise ValueError(f"Alias Rule ID가 비어 있거나 중복입니다: {rule_id}")
            seen_rule_ids.add(rule_id)
            triggers = tuple(
                normalize_alias_text(value)
                for value in rule.get("trigger_phrases", [])
                if normalize_alias_text(value)
            )
            excluded = tuple(
                normalize_alias_text(value)
                for value in rule.get("excluded_phrases", [])
                if normalize_alias_text(value)
            )
            expansion_terms = tuple(
                str(value).strip()
                for value in rule.get("expansion_terms", [])
                if str(value).strip()
            )
            if not triggers or not expansion_terms:
                raise ValueError(
                    f"Alias Rule은 Trigger와 Expansion Term이 필요합니다: {rule_id}"
                )
            validated.append(
                {
                    "rule_id": rule_id,
                    "triggers": triggers,
                    "excluded": excluded,
                    "expansion_terms": expansion_terms,
                }
            )
        self.rules = tuple(validated)

    def expand(self, query: str) -> AliasExpansionDecision:
        normalized_query = normalize_alias_text(query)
        applied_rule_ids: list[str] = []
        appended_terms: list[str] = []
        seen_terms: set[str] = set()

        for rule in self.rules:
            triggered = any(
                phrase in normalized_query for phrase in rule["triggers"]
            )
            excluded = any(
                phrase in normalized_query for phrase in rule["excluded"]
            )
            if not triggered or excluded:
                continue
            applied_rule_ids.append(rule["rule_id"])
            for term in rule["expansion_terms"]:
                normalized_term = normalize_alias_text(term)
                if normalized_term in seen_terms or normalized_term in normalized_query:
                    continue
                seen_terms.add(normalized_term)
                appended_terms.append(term)

        expanded_query = query
        if appended_terms:
            expanded_query = f"{query.strip()} {' '.join(appended_terms)}"
        return AliasExpansionDecision(
            original_query=query,
            expanded_query=expanded_query,
            applied_rule_ids=tuple(applied_rule_ids),
            appended_terms=tuple(appended_terms),
        )

