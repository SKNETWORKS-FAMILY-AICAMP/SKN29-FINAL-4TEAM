"""검색 원문은 보존하고 임베딩 질의만 제한적으로 확장한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import unicodedata

import yaml


@dataclass(frozen=True, slots=True)
class QueryExpansionDecision:
    """원문과 실제 임베딩 입력의 차이를 감사 가능하게 보존한다."""

    original_query: str
    expanded_query: str
    policy_id: str
    applied_rule_ids: tuple[str, ...] = ()
    appended_terms: tuple[str, ...] = ()

    @property
    def applied(self) -> bool:
        return self.expanded_query != self.original_query


class RetrievalQueryExpander:
    """검수 가능한 Phrase Rule로 Query-only 확장을 수행한다.

    이 클래스는 Corpus나 Gold 문장을 바꾸지 않는다. 원문 질의는 Policy Gate와
    추적 Context에 그대로 남기고, ``expanded_query``만 Embedding Provider에
    전달한다.
    """

    DEFAULT_CONFIG_PATH = (
        Path(__file__).resolve().parents[3] / "configs" / "retrieval_policy.yaml"
    )

    def __init__(self, definition: dict[str, Any] | None = None) -> None:
        if definition is None:
            config = yaml.safe_load(
                self.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
            )
            definition = config["query_expansion"]
        self.definition = definition
        self.policy_id = str(definition.get("policy_id", "")).strip()
        self.max_expanded_length = int(
            definition.get("max_expanded_length", 4096)
        )
        self.rules = self._validate_rules(definition.get("rules"))

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        return " ".join(normalized.split())

    def _validate_rules(self, raw_rules: object) -> tuple[dict[str, Any], ...]:
        if not self.policy_id:
            raise ValueError("검색 Query 확장 Policy ID가 필요합니다.")
        if self.max_expanded_length < 1:
            raise ValueError("검색 Query 확장 길이 제한은 1 이상이어야 합니다.")
        if not isinstance(raw_rules, list) or not raw_rules:
            raise ValueError("검색 Query 확장 Rule이 필요합니다.")

        validated: list[dict[str, Any]] = []
        seen_rule_ids: set[str] = set()
        for raw_rule in raw_rules:
            if not isinstance(raw_rule, dict):
                raise ValueError("검색 Query 확장 Rule은 Object여야 합니다.")
            rule_id = str(raw_rule.get("rule_id", "")).strip()
            if not rule_id or rule_id in seen_rule_ids:
                raise ValueError(
                    f"검색 Query 확장 Rule ID가 비어 있거나 중복입니다: {rule_id}"
                )
            seen_rule_ids.add(rule_id)
            model_codes = frozenset(
                str(value).strip()
                for value in raw_rule.get("model_codes", [])
                if str(value).strip()
            )
            triggers = tuple(
                self._normalize(str(value))
                for value in raw_rule.get("trigger_phrases", [])
                if self._normalize(str(value))
            )
            exclusions = tuple(
                self._normalize(str(value))
                for value in raw_rule.get("excluded_phrases", [])
                if self._normalize(str(value))
            )
            expansion_terms = tuple(
                str(value).strip()
                for value in raw_rule.get("expansion_terms", [])
                if str(value).strip()
            )
            if not model_codes or not triggers or not expansion_terms:
                raise ValueError(
                    "검색 Query 확장 Rule에는 모델·Trigger·확장 용어가 필요합니다: "
                    f"{rule_id}"
                )
            validated.append(
                {
                    "rule_id": rule_id,
                    "model_codes": model_codes,
                    "triggers": triggers,
                    "exclusions": exclusions,
                    "expansion_terms": expansion_terms,
                }
            )
        return tuple(validated)

    def expand(self, query_text: str, *, model_code: str) -> QueryExpansionDecision:
        """모델 범위와 제외 표현을 모두 통과한 경우에만 공식 용어를 덧붙인다."""

        normalized_query = self._normalize(query_text)
        appended_terms: list[str] = []
        applied_rule_ids: list[str] = []
        seen_terms: set[str] = set()

        for rule in self.rules:
            if model_code not in rule["model_codes"]:
                continue
            if any(term in normalized_query for term in rule["exclusions"]):
                continue
            if not any(term in normalized_query for term in rule["triggers"]):
                continue

            rule_terms: list[str] = []
            for term in rule["expansion_terms"]:
                normalized_term = self._normalize(term)
                if normalized_term in normalized_query or normalized_term in seen_terms:
                    continue
                rule_terms.append(term)
                seen_terms.add(normalized_term)
            if rule_terms:
                applied_rule_ids.append(rule["rule_id"])
                appended_terms.extend(rule_terms)

        expanded_query = query_text
        if appended_terms:
            candidate = f"{query_text.strip()} {' '.join(appended_terms)}"
            if len(candidate) <= self.max_expanded_length:
                expanded_query = candidate
            else:
                appended_terms = []
                applied_rule_ids = []

        return QueryExpansionDecision(
            original_query=query_text,
            expanded_query=expanded_query,
            policy_id=self.policy_id,
            applied_rule_ids=tuple(applied_rule_ids),
            appended_terms=tuple(appended_terms),
        )


__all__ = ["QueryExpansionDecision", "RetrievalQueryExpander"]
