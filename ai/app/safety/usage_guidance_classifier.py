"""정수기 사용 안내 상태 판정 모듈."""

from typing import Optional
from ..schemas import RiskLevel, SafetyAssessment, UsageGuidance, UsageGuidanceStatus
from .no_evidence_policy import NoEvidencePolicy
from .rule_loader import SafetyRuleLoader
from .rule_precedence import merge_rule_list_field, select_effective_safety_rules


class UsageGuidanceClassifier:
    """위험도 평가 및 근거 유무에 따라 정수기 사용 안내 상태 판정"""

    def __init__(self, rule_loader: Optional[SafetyRuleLoader] = None):
        self.loader = rule_loader or SafetyRuleLoader()
        self.rules_config = self.loader.get_safety_rules().get("rules", {})
        self.no_evidence_policy = self.loader.get_safety_rules().get("no_evidence_policy", {})

    def determine_guidance(
        self,
        safety_assessment: SafetyAssessment,
        raw_text: str,
        has_evidence: bool = True
    ) -> UsageGuidance:
        """위험 평가 결과와 RAG 근거 유무를 종합하여 사용 안내 상태(4개 규격) 생성"""

        # 1. 공식 근거 미발견 시 정책 적용
        if not has_evidence and safety_assessment.risk_level != RiskLevel.DANGER:
            return NoEvidencePolicy(self.loader).apply()

        # 2. 위험도 danger 인 경우 안전 가드레일 (절대 NORMAL 반환 금지)
        if safety_assessment.risk_level == RiskLevel.DANGER:
            status = UsageGuidanceStatus.TOTAL_STOP
            restricted_funcs = ["전체 출수 기능 중지", "제품 전원 차단 필요"]
            next_actions = ["원수 공급 밸브(원수 밸브)를 잠그세요.", "전원 플러그를 뽑고 사용을 즉시 중단하세요.", "전문 기사 방문 점검을 신청하세요."]

            # 명시적 세부 규칙 매칭 확인
            effective_rules = select_effective_safety_rules(
                self.rules_config,
                safety_assessment.matched_safety_rule_ids,
                risk_level=RiskLevel.DANGER,
            )
            # RiskClassifier가 부정 표현을 제거해 확정한 Rule ID만 신뢰한다.
            # 원문 키워드를 다시 검사하면 "누수는 아님" 같은 문장이 오탐된다.
            # 여러 Rule이 매칭되면 YAML 선언 순서가 아니라 명시적 제한 범위
            # 우선순위(TOTAL_STOP > PARTIAL_STOP)로 최종 안내를 선택한다.
            if effective_rules:
                status = UsageGuidanceStatus(
                    effective_rules[0].get(
                        "usage_guidance_status",
                        "TOTAL_STOP",
                    )
                )
                restricted_funcs = merge_rule_list_field(
                    effective_rules,
                    "restricted_functions",
                ) or restricted_funcs
                next_actions = merge_rule_list_field(
                    effective_rules,
                    "next_actions",
                ) or next_actions

            return UsageGuidance(
                guidance_status=status,
                message="위험 신호가 감지되어 정수기 사용 제한 및 안전 조치가 필요합니다.",
                restricted_functions=restricted_funcs,
                next_actions=next_actions
            )

        # 3. 위험도 caution 인 경우
        if safety_assessment.risk_level == RiskLevel.CAUTION:
            return UsageGuidance(
                guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
                message="일부 기능에 이상이 감지되었습니다. 관련 기능 확인 및 자가조치를 진행해 보세요.",
                restricted_functions=["해당 기능(냉수/온수/출수) 확인 필요"],
                next_actions=["안내된 자가조치 단계별 점검 수행", "증상 미개선 시 상담 연결"]
            )

        # 4. 일반 (general) 정상 케이스
        return UsageGuidance(
            guidance_status=UsageGuidanceStatus.NORMAL,
            message="정수기를 정상적으로 사용하실 수 있습니다. 자가 점검 및 케어 가이드를 확인하세요.",
            restricted_functions=[],
            next_actions=["기본 필터 및 사용 환경 유지", "정기 관리 일정 확인"]
        )

    def determine_assessment_and_guidance(
        self,
        safety_assessment: SafetyAssessment,
        raw_text: str,
        has_evidence: bool = True,
    ) -> tuple[SafetyAssessment, UsageGuidance]:
        """근거 유무를 반영한 안전 평가와 사용 안내를 함께 확정한다."""

        if not has_evidence and safety_assessment.risk_level != RiskLevel.DANGER:
            policy = NoEvidencePolicy(self.loader)
            return policy.apply_to_assessment(safety_assessment), policy.apply()
        return safety_assessment, self.determine_guidance(
            safety_assessment,
            raw_text,
            has_evidence=has_evidence,
        )
