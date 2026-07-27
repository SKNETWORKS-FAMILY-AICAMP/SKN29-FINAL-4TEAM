"""금지 표현 및 출력 가드레일 검증기 모듈."""

from typing import List, Optional, Tuple
from ...safety.rule_loader import SafetyRuleLoader


class ProhibitedPhraseValidator:
    """LLM 생성 문장에 대한 금지 표현(확정진단, 보증, 직접수리유도) 출력 가드레일"""

    def __init__(self, rule_loader: Optional[SafetyRuleLoader] = None):
        self.loader = rule_loader or SafetyRuleLoader()
        self.prohibited_config = self.loader.get_prohibited_expressions()
        self.diagnosis_phrases: List[str] = self.prohibited_config.get("prohibited_diagnosis_phrases", [])
        self.guarantee_phrases: List[str] = self.prohibited_config.get("prohibited_guarantee_phrases", [])
        self.repair_phrases: List[str] = self.prohibited_config.get("prohibited_repair_action_phrases", [])
        self.enforcement = self.prohibited_config.get("enforcement_policy", {})

    def validate(self, generated_text: str) -> Tuple[bool, str, List[str]]:
        """생성된 문장을 검사하여 (통과여부, 최종문구, 감지된 금지어목록) 반환"""
        if not generated_text:
            return True, generated_text, []

        detected_phrases = []

        # 1. 확정 진단 표현 감지
        for phrase in self.diagnosis_phrases:
            if phrase in generated_text:
                detected_phrases.append(f"[확정진단 금지] {phrase}")

        # 2. 안전 보증 표현 감지
        for phrase in self.guarantee_phrases:
            if phrase in generated_text:
                detected_phrases.append(f"[안전보증 금지] {phrase}")

        # 3. 위험 수리 유도 감지
        for phrase in self.repair_phrases:
            if phrase in generated_text:
                detected_phrases.append(f"[직접수리유도 금지] {phrase}")

        if not detected_phrases:
            return True, generated_text, []

        # 금지 표현 감지 시 Fallback 문구 치환
        fallback_msg = self.enforcement.get(
            "fallback_message",
            "안전하고 검증된 안내를 위해 확정적인 진단 문구 대신 점검 필요 사항 및 공식 서비스 상담을 권장해 드립니다."
        )
        return False, fallback_msg, detected_phrases
