"""정적 매뉴얼의 답변 가능 범위와 제품 기능을 검색 전에 판정한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class AnswerabilityDecision:
    """Gate의 허용 여부와 재현 가능한 차단 사유."""

    blocked: bool
    policy_id: str
    execution_path: str
    rule_id: str | None = None
    category: str | None = None
    reason: str | None = None


class AnswerabilityCapabilityGate:
    """Query 문자열과 제품 범위만으로 검색 실행 가능 여부를 판정한다."""

    DEFAULT_CONFIG_PATH = (
        Path(__file__).resolve().parents[3] / "configs" / "retrieval_policy.yaml"
    )

    def __init__(self, definition: dict[str, Any] | None = None) -> None:
        if definition is None:
            config = yaml.safe_load(
                self.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
            )
            definition = config["answerability_capability_gate"]
        self.definition = definition
        self.policy_id = definition["policy_id"]

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    def _blocked(
        self,
        *,
        execution_path: str,
        rule_id: str,
        category: str,
        reason: str,
    ) -> AnswerabilityDecision:
        return AnswerabilityDecision(
            blocked=True,
            policy_id=self.policy_id,
            execution_path=execution_path,
            rule_id=rule_id,
            category=category,
            reason=reason,
        )

    def evaluate(
        self,
        *,
        query_text: str,
        model_code: str,
        product_generation: str,
    ) -> AnswerabilityDecision:
        """Gold Label이나 검색 점수를 읽지 않고 답변 가능 범위를 판정한다."""
        supported_models = set(self.definition.get("supported_model_codes", []))
        if supported_models and model_code not in supported_models:
            return self._blocked(
                execution_path="POLICY_BLOCK_UNSUPPORTED_MODEL",
                rule_id=self.definition["unsupported_model_rule_id"],
                category="UNSUPPORTED_PRODUCT_MODEL",
                reason="지원 대상이 아닌 제품 모델",
            )

        supported_generations = set(self.definition.get("supported_generations", []))
        if supported_generations and product_generation not in supported_generations:
            return self._blocked(
                execution_path="POLICY_BLOCK_UNSUPPORTED_GENERATION",
                rule_id=self.definition["unsupported_generation_rule_id"],
                category="UNSUPPORTED_PRODUCT_GENERATION",
                reason="지원 대상이 아닌 제품 세대",
            )

        normalized = self._normalize(query_text)
        for rule in self.definition.get("unsupported_feature_rules", []):
            if model_code not in set(rule.get("model_codes", [])):
                continue
            if any(self._normalize(term) in normalized for term in rule.get("terms", [])):
                return self._blocked(
                    execution_path="POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
                    rule_id=rule["rule_id"],
                    category=rule["category"],
                    reason=rule["reason"],
                )

        for rule in self.definition.get("out_of_manual_rules", []):
            if any(
                self._normalize(term) in normalized
                for term in rule.get("excluded_terms", [])
            ):
                continue
            groups = rule.get("any_term_groups", [])
            if groups and all(
                any(self._normalize(term) in normalized for term in group)
                for group in groups
            ):
                return self._blocked(
                    execution_path="POLICY_BLOCK_OUT_OF_MANUAL_SCOPE",
                    rule_id=rule["rule_id"],
                    category=rule["category"],
                    reason=rule["reason"],
                )

        return AnswerabilityDecision(
            blocked=False,
            policy_id=self.policy_id,
            execution_path="PGVECTOR_QUERY",
        )


__all__ = ["AnswerabilityCapabilityGate", "AnswerabilityDecision"]
