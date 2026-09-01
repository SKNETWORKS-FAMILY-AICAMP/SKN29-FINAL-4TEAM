"""안전 규칙 및 금지 표현 YAML 로더 모듈."""

import os
import re
from typing import Any, Dict
import yaml

from ..schemas import RiskLevel, SafetyPriority, UsageGuidanceStatus


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
        stable_rule_ids: set[str] = set()
        for rule_key, rule in rules.items():
            required = {
                "rule_id",
                "risk_level",
                "usage_guidance_status",
                "keywords",
                "requires_consultation",
            }
            missing = required.difference(rule)
            if missing:
                raise ValueError(f"안전 규칙 {rule_key} 필수 키 누락: {sorted(missing)}")
            stable_rule_id = rule["rule_id"]
            if not isinstance(stable_rule_id, str) or re.fullmatch(
                r"SAFETY-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}",
                stable_rule_id,
            ) is None:
                raise ValueError(f"안전 규칙 {rule_key}의 rule_id 형식이 잘못되었습니다.")
            if stable_rule_id in stable_rule_ids:
                raise ValueError(f"중복 안전 rule_id입니다: {stable_rule_id}")
            stable_rule_ids.add(stable_rule_id)
            RiskLevel(rule["risk_level"])
            status = UsageGuidanceStatus(rule["usage_guidance_status"])
            if rule["risk_level"] == RiskLevel.DANGER.value and status == UsageGuidanceStatus.NORMAL:
                raise ValueError(f"안전 규칙 {rule_key}: danger와 NORMAL을 함께 사용할 수 없습니다.")
            applicability_policy = rule.get("applicability_policy")
            if applicability_policy is not None and (
                applicability_policy != "RUNTIME_APPROVED_PRODUCTS"
            ):
                raise ValueError(
                    f"안전 규칙 {rule_key}: 적용 범위 정책이 잘못되었습니다."
                )
            negated_expressions = rule.get("negated_expressions", [])
            if not isinstance(negated_expressions, list) or any(
                not isinstance(expression, str) or not expression.strip()
                for expression in negated_expressions
            ):
                raise ValueError(
                    f"안전 규칙 {rule_key}: 부정 표현 목록이 잘못되었습니다."
                )
            next_action_merge_policy = rule.get("next_action_merge_policy")
            if next_action_merge_policy is not None and (
                next_action_merge_policy != "EXCLUSIVE"
            ):
                raise ValueError(
                    f"안전 규칙 {rule_key}: 다음 행동 병합 정책이 잘못되었습니다."
                )

        required_no_evidence = {
            "default_risk_level",
            "default_priority",
            "default_usage_guidance_status",
            "requires_consultation",
            "safety_reason",
            "message",
        }
        missing_no_evidence = required_no_evidence.difference(no_evidence)
        if missing_no_evidence:
            raise ValueError(
                "근거 없음 정책 필수 키 누락: "
                f"{sorted(missing_no_evidence)}"
            )
        no_evidence_risk = RiskLevel(no_evidence["default_risk_level"])
        no_evidence_priority = SafetyPriority(no_evidence["default_priority"])
        no_evidence_status = UsageGuidanceStatus(
            no_evidence["default_usage_guidance_status"]
        )
        if no_evidence_risk != RiskLevel.CAUTION:
            raise ValueError("근거 없음 정책 위험도는 caution이어야 합니다.")
        if no_evidence_priority != SafetyPriority.CONSULTATION_RECOMMENDED:
            raise ValueError(
                "근거 없음 정책 우선순위는 consultation_recommended여야 합니다."
            )
        if no_evidence_status != UsageGuidanceStatus.PENDING_CONSULTATION:
            raise ValueError(
                "근거 없음 정책은 PENDING_CONSULTATION이어야 합니다."
            )
        if no_evidence["requires_consultation"] is not True:
            raise ValueError("근거 없음 정책은 상담 필요 상태여야 합니다.")

    def get_safety_rules(self) -> Dict[str, Any]:
        """안전 규칙 딕셔너리 반환"""
        return self._safety_rules

    def get_prohibited_expressions(self) -> Dict[str, Any]:
        """금지 표현 딕셔너리 반환"""
        return self._prohibited_expressions
