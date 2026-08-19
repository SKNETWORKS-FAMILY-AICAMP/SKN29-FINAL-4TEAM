"""Deterministic Consultation Handoff Agent without new diagnosis generation."""

from __future__ import annotations

import re

from .handoff_input import ConsultationHandoffInput, HandoffQuestionnaireAnswer
from .handoff_result import ConsultationHandoffResult


_PHONE = re.compile(r"(?<!\d)(?:01[016789])[- ]?\d{3,4}[- ]?\d{4}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class ConsultationHandoffAgent:
    """Transform only supplied runtime facts into a counselor-facing structure."""

    def run(self, handoff: ConsultationHandoffInput) -> ConsultationHandoffResult:
        answers = [
            HandoffQuestionnaireAnswer(
                field_name=item.field_name,
                answer=self._redact(item.answer),
            )
            for item in handoff.questionnaire_answers
        ]
        symptom_summary = self._redact(handoff.symptom_summary)
        safety_notes = [self._redact(item) for item in handoff.safety_notes]
        actions = [self._redact(item) for item in handoff.proposed_self_help_actions]
        priority_checks = [self._redact(item) for item in handoff.consultant_priority_checks]

        return ConsultationHandoffResult(
            inquiry_id=handoff.inquiry_id,
            correlation_id=handoff.correlation_id,
            ai_request_id=handoff.ai_request_id,
            model_code=handoff.model_code,
            product_family=handoff.product_family,
            customer_symptom_summary=symptom_summary,
            questionnaire_answers=answers,
            self_help_actions=actions,
            evidence=handoff.evidence,
            safety_level=handoff.safety_level,
            safety_requires_consultation=handoff.safety_requires_consultation,
            safety_notes=safety_notes,
            escalation_reason=self._redact(handoff.escalation_reason),
            consultant_priority_checks=priority_checks,
            source_chunk_ids=[item.chunk_id for item in handoff.evidence],
        )

    @staticmethod
    def _redact(value: str) -> str:
        value = _EMAIL.sub("[REDACTED_EMAIL]", value)
        return _PHONE.sub("[REDACTED_PHONE]", value)
