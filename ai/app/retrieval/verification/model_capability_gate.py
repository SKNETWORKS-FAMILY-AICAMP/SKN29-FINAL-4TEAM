"""정확 판매코드와 명시적 조작부 명칭을 pgvector 검색 전에 검증한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import unicodedata

import yaml


@dataclass(frozen=True, slots=True)
class ModelCapabilityDecision:
    """모델 Capability Gate의 허용 여부와 감사 가능한 판정 정보."""

    blocked: bool
    policy_id: str
    execution_path: str
    rule_id: str | None = None
    reason_code: str | None = None
    reason: str | None = None


class ModelCapabilityGate:
    """Gold Label이나 검색 결과를 읽지 않고 모델 조작부 호환성을 판정한다."""

    DEFAULT_CONFIG_PATH = (
        Path(__file__).resolve().parents[3] / "configs" / "model_capabilities.yaml"
    )

    def __init__(self, definition: dict[str, Any] | None = None) -> None:
        if definition is None:
            config = yaml.safe_load(
                self.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
            )
            definition = config["model_capability_gate"]
        self.definition = definition
        self.policy_id = str(definition["policy_id"])
        self._validate_definition()

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFC", value).casefold()
        return " ".join(normalized.split())

    @property
    def registered_model_codes(self) -> frozenset[str]:
        return frozenset(self.definition["known_exact_sales_codes"])

    def _validate_definition(self) -> None:
        controls = self.definition.get("controls", {})
        models = self.definition.get("models", {})
        known_models = set(self.definition.get("known_exact_sales_codes", []))
        if not isinstance(controls, dict) or not isinstance(models, dict) or not models:
            raise ValueError("Model Capability 설정에 controls와 models가 필요합니다.")
        if not known_models or set(models) - known_models:
            raise ValueError("Capability 모델은 등록된 정확 판매코드여야 합니다.")

        alias_owners: dict[str, str] = {}
        for control_id, control in controls.items():
            mentions = control.get("explicit_mentions", [])
            if not mentions:
                raise ValueError(f"조작부 명시 표현이 없습니다: {control_id}")
            for mention in mentions:
                normalized = self._normalize(str(mention))
                owner = alias_owners.setdefault(normalized, str(control_id))
                if owner != control_id:
                    raise ValueError(
                        f"조작부 명시 표현이 여러 Control에 중복됐습니다: {mention}"
                    )

        known_controls = set(controls)
        for model_code, model in models.items():
            supported = set(model.get("supported_control_ids", []))
            unknown = supported - known_controls
            if unknown:
                raise ValueError(
                    f"모델이 알 수 없는 Control을 참조합니다: {model_code}={sorted(unknown)}"
                )
            if model.get("validate_explicit_controls") and not model.get("rule_id"):
                raise ValueError(f"조작부 검사 모델에 Rule ID가 없습니다: {model_code}")

    def evaluate(self, *, query_text: str, model_code: str) -> ModelCapabilityDecision:
        """등록 모델과 명시적으로 언급된 조작부의 호환성을 판정한다."""

        if model_code not in set(self.definition["known_exact_sales_codes"]):
            return ModelCapabilityDecision(
                blocked=True,
                policy_id=self.policy_id,
                execution_path="POLICY_BLOCK_UNREGISTERED_EXACT_SALES_CODE",
                rule_id=str(self.definition["unregistered_rule_id"]),
                reason_code=str(self.definition["unregistered_reason"]),
                reason="등록되지 않은 정확 판매코드",
            )

        models = self.definition["models"]
        model = models.get(model_code)
        if model is None:
            return ModelCapabilityDecision(
                blocked=False,
                policy_id=self.policy_id,
                execution_path="PGVECTOR_QUERY",
            )

        if not model.get("validate_explicit_controls", False):
            return ModelCapabilityDecision(
                blocked=False,
                policy_id=self.policy_id,
                execution_path="PGVECTOR_QUERY",
            )

        normalized_query = self._normalize(query_text)
        mentioned_controls = {
            control_id
            for control_id, control in self.definition["controls"].items()
            if any(
                self._normalize(str(mention)) in normalized_query
                for mention in control["explicit_mentions"]
            )
        }
        supported_controls = set(model.get("supported_control_ids", []))
        if mentioned_controls - supported_controls:
            return ModelCapabilityDecision(
                blocked=True,
                policy_id=self.policy_id,
                execution_path="POLICY_BLOCK_MODEL_CONTROL_MISMATCH",
                rule_id=str(model["rule_id"]),
                reason_code="MODEL_CONTROL_MISMATCH",
                reason="질문에 명시된 조작부가 해당 판매코드의 조작부와 일치하지 않음",
            )

        return ModelCapabilityDecision(
            blocked=False,
            policy_id=self.policy_id,
            execution_path="PGVECTOR_QUERY",
        )


__all__ = ["ModelCapabilityDecision", "ModelCapabilityGate"]
