"""계약 규칙으로 계산한 상태 전이 결과."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Transition:
    """DB 쓰기 전에 Guard와 Service가 소비하는 불변 전이 계획."""

    rule_id: str
    event_code: str
    inquiry_state_before: str | None
    inquiry_state_after: str
    visit_mode: str
    visit_status_before: str | None
    visit_status_after: str | None
    state_version_before: int | None
    state_version_after: int
    version_action: str
    guard_refs: tuple[str, ...]
    effects: tuple[str, ...]
    record_inquiry_state_history: bool
    record_visit_state_history: bool
    record_business_event: bool
