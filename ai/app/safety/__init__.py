"""안전 분류기 패키지 모듈."""

from .risk_classifier import RiskClassifier
from .rule_loader import SafetyRuleLoader
from .usage_guidance_classifier import UsageGuidanceClassifier
from .no_evidence_policy import NoEvidencePolicy
from .prohibited_action_guard import ProhibitedActionGuard

__all__ = [
    "DiagnosisExpressionGuard",
    "NoEvidencePolicy",
    "ProhibitedActionGuard",
    "RiskClassifier",
    "SafetyRuleLoader",
    "UsageGuidanceClassifier",
]


def __getattr__(name: str):
    """순환 Import 없이 기존 공개 ``DiagnosisExpressionGuard``를 지연 노출한다."""

    if name == "DiagnosisExpressionGuard":
        from .diagnosis_expression_guard import DiagnosisExpressionGuard

        return DiagnosisExpressionGuard
    raise AttributeError(name)
