"""PM YAML 계약을 읽어 상태+이벤트 전이를 fail-closed로 계산한다."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.workflow.contracts.state_machine_loader import (
    load_state_machine_contract,
)
from apps.workflow.domain.transition import Transition
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot


class InvalidStateTransition(ValueError):
    """계약에 없는 전이 또는 모호한 전이를 하나의 공개 코드로 거부한다."""

    code = "INVALID_STATE_TRANSITION"

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class StateMachine:
    """검증된 계약에서 한 개의 결정적 전이만 반환한다."""

    def __init__(
        self,
        documents: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self._documents = (
            documents
            if documents is not None
            else load_state_machine_contract()
        )
        self._events = {
            event["code"]: event
            for event in self._documents["events"]["events"]
        }
        self._transitions = tuple(
            self._documents["transitions"]["transitions"]
        )
        self._terminal_states = frozenset(
            self._documents["states"]["terminal_states"]
        )
        self._allowed_visit_statuses = {
            state["code"]: frozenset(state["allowed_visit_statuses"])
            for state in self._documents["states"]["states"]
        }
        self._defaults = self._documents["transitions"].get(
            "defaults",
            {},
        )

    def event(self, event_code: str) -> Mapping[str, Any]:
        """Guard 평가에서 사용하는 이벤트 계약을 반환한다."""

        event = self._events.get(event_code)
        if event is None:
            raise InvalidStateTransition(
                f"등록되지 않은 이벤트입니다: {event_code!r}",
                reason="UNKNOWN_EVENT",
            )
        return event

    def resolve(
        self,
        *,
        snapshot: WorkflowSnapshot,
        event_code: str,
    ) -> Transition:
        """현재 Snapshot과 이벤트에 맞는 유일한 전이 계획을 계산한다."""

        self.event(event_code)
        if snapshot.inquiry_state in self._terminal_states:
            raise InvalidStateTransition(
                "종료 상태의 문의는 다시 전이할 수 없습니다.",
                reason="TERMINAL_STATE",
            )
        self._ensure_visit_status_allowed(
            inquiry_state=snapshot.inquiry_state,
            visit_status=snapshot.visit_status,
        )

        state_candidates = [
            rule
            for rule in self._transitions
            if rule["event"] == event_code
            and rule.get("from_inquiry_state")
            == snapshot.inquiry_state
        ]
        candidates = [
            rule
            for rule in state_candidates
            if self._visit_matches(rule.get("visit", {}), snapshot)
        ]

        if not candidates:
            raise InvalidStateTransition(
                "현재 문의·방문 상태에서 허용되지 않은 이벤트입니다.",
                reason=(
                    "VISIT_STATE_MISMATCH"
                    if state_candidates
                    else "UNLISTED_TRANSITION"
                ),
            )
        if len(candidates) != 1:
            raise InvalidStateTransition(
                "동일 입력에 둘 이상의 전이 규칙이 일치합니다.",
                reason="AMBIGUOUS_TRANSITION",
            )

        rule = candidates[0]
        visit = rule.get("visit", {})
        version_action = rule.get(
            "version_action",
            self._defaults.get("version_action"),
        )
        next_version = self._next_version(
            snapshot=snapshot,
            version_action=version_action,
        )
        history = rule.get("history", {})
        next_visit_status = self._next_visit_status(
            visit,
            snapshot,
        )
        self._ensure_visit_status_allowed(
            inquiry_state=rule["to_inquiry_state"],
            visit_status=next_visit_status,
        )

        return Transition(
            rule_id=rule["id"],
            event_code=event_code,
            inquiry_state_before=snapshot.inquiry_state,
            inquiry_state_after=rule["to_inquiry_state"],
            visit_mode=visit["mode"],
            visit_status_before=snapshot.visit_status,
            visit_status_after=next_visit_status,
            state_version_before=snapshot.state_version,
            state_version_after=next_version,
            version_action=version_action,
            guard_refs=tuple(rule.get("guard_refs", [])),
            effects=tuple(rule.get("effects", [])),
            record_inquiry_state_history=bool(
                history.get("record_inquiry_state_history")
            ),
            record_visit_state_history=bool(
                history.get("record_visit_state_history")
            ),
            record_business_event=bool(
                history.get(
                    "record_business_event",
                    self._defaults.get("record_business_event", False),
                )
            ),
        )

    @staticmethod
    def _visit_matches(
        visit: Mapping[str, Any],
        snapshot: WorkflowSnapshot,
    ) -> bool:
        mode = visit.get("mode")
        if mode in {"REQUIRE_ABSENT", "CREATE"}:
            return snapshot.visit_status is None
        if mode == "PRESERVE":
            return True
        if mode == "PRESERVE_REQUIRE_STATUS":
            return snapshot.visit_status == visit.get("required_status")
        if mode == "TRANSITION":
            return snapshot.visit_status == visit.get("from_status")
        return False

    @staticmethod
    def _next_visit_status(
        visit: Mapping[str, Any],
        snapshot: WorkflowSnapshot,
    ) -> str | None:
        mode = visit["mode"]
        if mode in {"CREATE", "TRANSITION"}:
            return visit["to_status"]
        if mode in {"PRESERVE", "PRESERVE_REQUIRE_STATUS"}:
            return snapshot.visit_status
        if mode == "REQUIRE_ABSENT":
            return None
        raise InvalidStateTransition(
            f"지원하지 않는 Visit mode입니다: {mode!r}",
            reason="UNKNOWN_VISIT_MODE",
        )

    @staticmethod
    def _next_version(
        *,
        snapshot: WorkflowSnapshot,
        version_action: str,
    ) -> int:
        if version_action == "INITIALIZE_1":
            if (
                snapshot.inquiry_state is not None
                or snapshot.state_version is not None
            ):
                raise InvalidStateTransition(
                    "기존 문의에는 state_version을 초기화할 수 없습니다.",
                    reason="INVALID_VERSION_ACTION",
                )
            return 1
        if version_action == "INCREMENT":
            if snapshot.state_version is None:
                raise InvalidStateTransition(
                    "기존 문의 전이에는 현재 state_version이 필요합니다.",
                    reason="STATE_VERSION_REQUIRED",
                )
            return snapshot.state_version + 1
        raise InvalidStateTransition(
            f"지원하지 않는 version_action입니다: {version_action!r}",
            reason="UNKNOWN_VERSION_ACTION",
        )

    def _ensure_visit_status_allowed(
        self,
        *,
        inquiry_state: str | None,
        visit_status: str | None,
    ) -> None:
        if inquiry_state is None or visit_status is None:
            return
        allowed = self._allowed_visit_statuses.get(inquiry_state)
        if allowed is None or visit_status not in allowed:
            raise InvalidStateTransition(
                "문의 상태와 Visit 상태 조합이 계약에 맞지 않습니다.",
                reason="VISIT_STATUS_NOT_ALLOWED",
            )
