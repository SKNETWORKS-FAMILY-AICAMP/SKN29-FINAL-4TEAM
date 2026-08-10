"""상담사용 요약 초안을 고정 Schema로 생성."""

from __future__ import annotations

from ...safety import RiskClassifier
from ...schemas import ConsultationSummaryRequest, ConsultationSummaryResult, RiskLevel
from ...structuring import SymptomStructurer
from .summary_formatter import ConsultationSummaryFormatter


class ConsultationSummaryGenerator:
    """외부 LLM 없이 동작하는 상담 요약 Fallback 기준선."""

    def __init__(
        self,
        *,
        structurer: SymptomStructurer | None = None,
        risk_classifier: RiskClassifier | None = None,
        formatter: ConsultationSummaryFormatter | None = None,
    ) -> None:
        self.structurer = structurer or SymptomStructurer()
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.formatter = formatter or ConsultationSummaryFormatter()

    def generate(self, request: ConsultationSummaryRequest) -> ConsultationSummaryResult:
        """고객 진술을 요약하되 진단·공식 확정·Backend 상태 변경을 수행하지 않는다."""
        structured = self.structurer.structure(request.customer_raw_text)
        safety = self.risk_classifier.classify(request.customer_raw_text)
        draft = self.formatter.format(
            customer_raw_text=request.customer_raw_text,
            agent_notes=request.agent_notes,
            symptom_type=structured.symptom_type,
            detected_risks=safety.detected_risks,
            requires_consultation=safety.requires_consultation,
            is_danger=safety.risk_level == RiskLevel.DANGER,
        )
        return ConsultationSummaryResult(
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,
            ai_request_id=request.ai_request_id,
            state_version=request.state_version,
            status="SUCCEEDED",
            failure_stage=None,
            retry_count=0,
            summary_text=draft.summary_text,
            key_issues=draft.key_issues,
            recommended_followup=draft.recommended_followup,
        )
