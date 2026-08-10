"""상담 요약을 화면·API 전달 형식으로 정리."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class ConsultationSummaryDraft:
    """공개 계약 식별자를 붙이기 전의 결정론적 요약 본문."""

    summary_text: str
    key_issues: list[str]
    recommended_followup: str


class ConsultationSummaryFormatter:
    """입력에 존재하는 사실과 안전 판정만 사용해 상담 검토용 초안을 만든다."""

    _SUMMARY_MAX_LENGTH = 4000
    _ISSUE_MAX_LENGTH = 500
    _FOLLOWUP_MAX_LENGTH = 2000

    def format(
        self,
        *,
        customer_raw_text: str,
        agent_notes: str | None,
        symptom_type: str,
        detected_risks: list[str],
        requires_consultation: bool,
        is_danger: bool,
    ) -> ConsultationSummaryDraft:
        customer_text = self._normalize(customer_raw_text)
        notes = self._normalize(agent_notes or "")

        sections = [f"고객 진술: {customer_text}"]
        if notes:
            sections.append(f"상담 기록: {notes}")
        if is_danger:
            sections.append("명시적 안전 위험 신호가 감지되어 우선 확인이 필요합니다.")
        summary_text = self._truncate(" ".join(sections), self._SUMMARY_MAX_LENGTH)

        issues = []
        if symptom_type and symptom_type != "기타 증상":
            issues.append(symptom_type)
        issues.extend(detected_risks)
        if not issues:
            issues.append(customer_text)
        key_issues = [
            self._truncate(issue, self._ISSUE_MAX_LENGTH)
            for issue in dict.fromkeys(issues)
            if issue
        ][:5]

        if is_danger:
            followup = "사용 제한 상태와 즉시 상담·방문 필요 여부를 우선 확인합니다."
        elif requires_consultation:
            followup = "공식 근거와 상담 기록을 검토하고 상담 또는 방문 필요 여부를 결정합니다."
        else:
            followup = "고객 진술과 상담 기록을 검토하고 후속 안내를 확정합니다."

        return ConsultationSummaryDraft(
            summary_text=summary_text,
            key_issues=key_issues,
            recommended_followup=self._truncate(followup, self._FOLLOWUP_MAX_LENGTH),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 1].rstrip() + "…"
