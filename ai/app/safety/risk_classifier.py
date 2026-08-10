"""위험도 및 안전 규칙 분류기 모듈."""

import re
from typing import List, Optional
from ..schemas import RiskLevel, SafetyAssessment
from .rule_loader import SafetyRuleLoader


class RiskClassifier:
    """명시적 키워드 기반 안전 분기 및 위험도 분류기"""

    _NEGATED_DANGER_PATTERNS = (
        r"누수(?:는|가)?\s*(?:아니(?:에요|예요|고|라|며)?|없(?:어요|습니다|고)?)",
        r"물(?:이)?\s*(?:안\s*새|새지\s*않)",
        r"연기(?:는|가)?\s*(?:안\s*나|없)",
        r"스파크(?:는|가)?\s*(?:안\s*튀|없)",
    )

    def __init__(self, rule_loader: Optional[SafetyRuleLoader] = None):
        self.loader = rule_loader or SafetyRuleLoader()
        self.rules_config = self.loader.get_safety_rules().get("rules", {})

    def classify(self, raw_text: str, selected_symptoms: Optional[List[str]] = None) -> SafetyAssessment:
        """자연어 증상 및 대표 선택 증상을 분석하여 위험도 판정"""
        normalized_text = raw_text
        for pattern in self._NEGATED_DANGER_PATTERNS:
            normalized_text = re.sub(pattern, " ", normalized_text)
        text_to_search = (normalized_text + " " + " ".join(selected_symptoms or [])).strip()

        matched_rule_ids = []
        detected_risks = []
        highest_risk = RiskLevel.GENERAL
        highest_priority = "general_guidance"
        requires_consultation = False
        reasons = []

        # 명시적 위험 규칙 탐색
        for rule_key, rule_def in self.rules_config.items():
            keywords = rule_def.get("keywords", [])
            for kw in keywords:
                if kw in text_to_search:
                    matched_rule_ids.append(rule_def["rule_id"])
                    detected_risks.append(rule_def.get("name", rule_key))
                    reasons.append(f"[{rule_def.get('name')}] 키워드('{kw}') 감지")

                    # 위험도 수준 비교 (danger > caution > general)
                    rule_risk_str = rule_def.get("risk_level", "general")
                    if rule_risk_str == "danger":
                        highest_risk = RiskLevel.DANGER
                        highest_priority = rule_def.get("priority", "priority_consultation")
                        requires_consultation = True
                    elif rule_risk_str == "caution" and highest_risk != RiskLevel.DANGER:
                        highest_risk = RiskLevel.CAUTION
                        highest_priority = rule_def.get("priority", "consultation_recommended")
                        requires_consultation = rule_def.get("requires_consultation", False)
                    break

        if not detected_risks:
            safety_reason = "명시적 위험 키워드가 감지되지 않았습니다. 일반 증상 조치 가이드를 제공합니다."
        else:
            safety_reason = "; ".join(reasons)

        return SafetyAssessment(
            risk_level=highest_risk,
            priority=highest_priority,
            requires_consultation=requires_consultation,
            matched_safety_rule_ids=list(dict.fromkeys(matched_rule_ids)),
            detected_risks=list(dict.fromkeys(detected_risks)),
            safety_reason=safety_reason
        )
