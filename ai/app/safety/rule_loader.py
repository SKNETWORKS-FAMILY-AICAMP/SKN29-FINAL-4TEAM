"""안전 규칙 및 금지 표현 YAML 로더 모듈."""

import os
from typing import Any, Dict
import yaml

from ..schemas import RiskLevel, UsageGuidanceStatus


class SafetyRuleLoader:
    """안전 규칙 및 정책 YAML 로더 (캐싱 지원)"""
    _instance = None
    _safety_rules: Dict[str, Any] = {}
    _prohibited_expressions: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SafetyRuleLoader, cls).__new__(cls)
            cls._instance._load_all()
        return cls._instance

    def _load_all(self):
        """YAML 설정 파일 로딩"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        configs_dir = os.path.join(base_dir, "configs")

        safety_rules_path = os.path.join(configs_dir, "safety_rules.yaml")
        if os.path.exists(safety_rules_path):
            with open(safety_rules_path, "r", encoding="utf-8") as f:
                self._safety_rules = yaml.safe_load(f) or {}

        prohibited_path = os.path.join(configs_dir, "prohibited_expressions.yaml")
        if os.path.exists(prohibited_path):
            with open(prohibited_path, "r", encoding="utf-8") as f:
                self._prohibited_expressions = yaml.safe_load(f) or {}

        self._validate()

    def _validate(self) -> None:
        rules = self._safety_rules.get("rules")
        no_evidence = self._safety_rules.get("no_evidence_policy")
        if not isinstance(rules, dict) or not rules or not isinstance(no_evidence, dict):
            raise ValueError("safety_rules.yaml에는 rules와 no_evidence_policy가 필요합니다.")
        for rule_id, rule in rules.items():
            required = {"risk_level", "usage_guidance_status", "keywords", "requires_consultation"}
            missing = required.difference(rule)
            if missing:
                raise ValueError(f"안전 규칙 {rule_id} 필수 키 누락: {sorted(missing)}")
            RiskLevel(rule["risk_level"])
            status = UsageGuidanceStatus(rule["usage_guidance_status"])
            if rule["risk_level"] == RiskLevel.DANGER.value and status == UsageGuidanceStatus.NORMAL:
                raise ValueError(f"안전 규칙 {rule_id}: danger와 NORMAL을 함께 사용할 수 없습니다.")

    def get_safety_rules(self) -> Dict[str, Any]:
        """안전 규칙 딕셔너리 반환"""
        return self._safety_rules

    def get_prohibited_expressions(self) -> Dict[str, Any]:
        """금지 표현 딕셔너리 반환"""
        return self._prohibited_expressions
