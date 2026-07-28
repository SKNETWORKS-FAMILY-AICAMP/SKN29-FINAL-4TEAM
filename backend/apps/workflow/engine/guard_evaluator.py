"""역할·동시성·멱등성·도메인 Guard를 fail-closed로 평가한다."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from apps.workflow.contracts.state_machine_loader import (
    load_state_machine_contract,
)
from apps.workflow.domain.transition import Transition
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot


CORE_ROLE_GUARDS = {
    "G-ACTOR-CUSTOMER": "CUSTOMER",
    "G-ACTOR-CONSULTANT": "CONSULTANT",
    "G-ACTOR-TECHNICIAN": "TECHNICIAN",
    "G-ACTOR-SYSTEM": "SYSTEM",
}


@dataclass(frozen=True, slots=True)
class GuardContext:
    """요청 경계에서 검증돼 Guard 평가로 전달되는 값."""

    actor_role: str | None
    is_authenticated: bool
    correlation_id: str | None
    idempotency_key: str | None
    requested_state_version: int | None
    trusted_internal_actor: bool = False
    domain_results: Mapping[str, bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuardFailure:
    guard_id: str
    category: str
    http_status: int
    error_code: str
    message: str
    reason: str


@dataclass(frozen=True, slots=True)
class GuardEvaluation:
    allowed: bool
    failure: GuardFailure | None = None


class GuardEvaluator:
    """계약의 stop-on-first-failure 정책으로 Guard를 평가한다."""

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
        self._guards = {
            guard["id"]: guard
            for guard in self._documents["guards"]["guards"]
        }
        self._defaults = self._documents["transitions"].get(
            "defaults",
            {},
        )
        guard_document = self._documents["guards"]
        self._guard_precedence = self._effective_guard_precedence(
            declared=guard_document["evaluation_policy"][
                "security_precedence"
            ],
            categories=guard_document["guard_categories"],
        )

    def evaluate(
        self,
        *,
        transition: Transition,
        snapshot: WorkflowSnapshot,
        context: GuardContext,
    ) -> GuardEvaluation:
        """기계적으로 확정 가능한 Guard와 주입된 도메인 결과를 검사한다."""

        event = self._events.get(transition.event_code)
        if event is None:
            return self._synthetic_failure(
                guard_id="G-EVENT-CONTRACT",
                category="BUSINESS_RULE",
                http_status=500,
                error_code="INTERNAL_ERROR",
                message="등록되지 않은 이벤트입니다.",
                reason="UNKNOWN_EVENT",
            )

        missing_required_guard = self._missing_required_guard(
            event=event,
            transition=transition,
        )
        if missing_required_guard is not None:
            return self._synthetic_failure(
                guard_id=missing_required_guard,
                category="BUSINESS_RULE",
                http_status=500,
                error_code="INTERNAL_ERROR",
                message="필수 상태 전이 Guard가 구성되지 않았습니다.",
                reason="REQUIRED_GUARD_MISSING",
            )

        actor_failure = self._evaluate_event_actor(
            event=event,
            transition=transition,
            context=context,
        )
        if actor_failure is not None:
            return GuardEvaluation(False, actor_failure)

        if (
            self._defaults.get("require_correlation_id") is True
            and not self._has_text(context.correlation_id)
        ):
            return self._synthetic_failure(
                guard_id="G-CORRELATION-ID",
                category="PAYLOAD",
                http_status=422,
                error_code="VALIDATION_ERROR",
                message="요청 추적 ID가 필요합니다.",
                reason="MISSING_CORRELATION_ID",
            )

        if (
            event.get("requires_idempotency_key") is True
            and not self._valid_idempotency_key(context.idempotency_key)
        ):
            return self._synthetic_failure(
                guard_id="G-IDEMPOTENCY-KEY",
                category="PAYLOAD",
                http_status=422,
                error_code="VALIDATION_ERROR",
                message="올바른 Idempotency-Key가 필요합니다.",
                reason="MISSING_OR_INVALID_IDEMPOTENCY_KEY",
            )

        for guard_id in self._ordered_guard_refs(transition.guard_refs):
            guard = self._guards[guard_id]
            passed, reason = self._evaluate_guard(
                guard_id=guard_id,
                event=event,
                snapshot=snapshot,
                context=context,
            )
            if not passed:
                return GuardEvaluation(
                    False,
                    self._contract_failure(
                        guard,
                        reason=reason,
                    ),
                )

        return GuardEvaluation(True)

    def _evaluate_event_actor(
        self,
        *,
        event: Mapping[str, Any],
        transition: Transition,
        context: GuardContext,
    ) -> GuardFailure | None:
        actor_role = context.actor_role
        if actor_role != "SYSTEM" and not context.is_authenticated:
            return self._synthetic_guard_failure(
                guard_id="G-AUTHENTICATED-ACTOR",
                category="AUTHENTICATION",
                http_status=401,
                error_code="AUTH_REQUIRED",
                message="인증이 필요합니다.",
                reason="UNAUTHENTICATED_ACTOR",
            )
        if actor_role == "SYSTEM":
            if not context.trusted_internal_actor:
                guard = self._guards.get("G-ACTOR-SYSTEM")
                if guard is not None:
                    return self._contract_failure(
                        guard,
                        reason="UNTRUSTED_INTERNAL_ACTOR",
                    )
                return self._synthetic_guard_failure(
                    guard_id="G-INTERNAL-ACTOR",
                    category="AUTHENTICATION",
                    http_status=403,
                    error_code="FORBIDDEN",
                    message="내부 처리 전용 이벤트입니다.",
                    reason="UNTRUSTED_INTERNAL_ACTOR",
                )
        if actor_role not in event.get("actor_roles", []):
            role_guard_id = next(
                (
                    guard_id
                    for guard_id in transition.guard_refs
                    if guard_id in CORE_ROLE_GUARDS
                ),
                None,
            )
            if role_guard_id is not None:
                return self._contract_failure(
                    self._guards[role_guard_id],
                    reason="EVENT_ROLE_MISMATCH",
                )
            return self._synthetic_guard_failure(
                guard_id="G-EVENT-ACTOR-ROLE",
                category="ROLE",
                http_status=403,
                error_code="FORBIDDEN",
                message="이 역할로 수행할 수 없는 작업입니다.",
                reason="EVENT_ROLE_MISMATCH",
            )
        return None

    def _evaluate_guard(
        self,
        *,
        guard_id: str,
        event: Mapping[str, Any],
        snapshot: WorkflowSnapshot,
        context: GuardContext,
    ) -> tuple[bool, str]:
        if guard_id in CORE_ROLE_GUARDS:
            required_role = CORE_ROLE_GUARDS[guard_id]
            if required_role == "SYSTEM":
                return (
                    context.actor_role == "SYSTEM"
                    and context.trusted_internal_actor,
                    "SYSTEM_ACTOR_MISMATCH",
                )
            return (
                context.is_authenticated
                and context.actor_role == required_role,
                "ACTOR_ROLE_MISMATCH",
            )

        if guard_id == "G-STATE-VERSION":
            if event.get("requires_state_version") is not True:
                return False, "UNEXPECTED_STATE_VERSION_GUARD"
            return (
                context.requested_state_version is not None
                and context.requested_state_version
                == snapshot.state_version,
                "STATE_VERSION_MISMATCH",
            )

        if guard_id == "G-IDEMPOTENCY-KEY":
            if event.get("requires_idempotency_key") is not True:
                return False, "UNEXPECTED_IDEMPOTENCY_GUARD"
            return True, ""

        if guard_id not in context.domain_results:
            return False, "DOMAIN_RESULT_MISSING"
        return (
            context.domain_results[guard_id] is True,
            "DOMAIN_GUARD_REJECTED",
        )

    @staticmethod
    def _has_text(value: str | None) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @classmethod
    def _valid_idempotency_key(cls, value: str | None) -> bool:
        return cls._has_text(value) and len(value.strip()) <= 128

    @staticmethod
    def _missing_required_guard(
        *,
        event: Mapping[str, Any],
        transition: Transition,
    ) -> str | None:
        required = []
        if event.get("requires_state_version") is True:
            required.append("G-STATE-VERSION")
        if event.get("requires_idempotency_key") is True:
            required.append("G-IDEMPOTENCY-KEY")
        return next(
            (
                guard_id
                for guard_id in required
                if guard_id not in transition.guard_refs
            ),
            None,
        )

    @staticmethod
    def _effective_guard_precedence(
        *,
        declared: list[str],
        categories: list[str],
    ) -> dict[str, int]:
        """선언된 보안 순서에 누락 category를 표준 위치로 보충한다."""

        effective = list(declared)
        for category_index, category in enumerate(categories):
            if category in effective:
                continue
            next_category = next(
                (
                    candidate
                    for candidate in categories[category_index + 1 :]
                    if candidate in effective
                ),
                None,
            )
            if next_category is None:
                effective.append(category)
            else:
                effective.insert(effective.index(next_category), category)
        return {
            category: index
            for index, category in enumerate(effective)
        }

    def _ordered_guard_refs(
        self,
        guard_refs: tuple[str, ...],
    ) -> tuple[str, ...]:
        indexed = enumerate(guard_refs)
        return tuple(
            guard_id
            for _, guard_id in sorted(
                indexed,
                key=lambda item: (
                    self._guard_precedence.get(
                        self._guards[item[1]]["category"],
                        len(self._guard_precedence),
                    ),
                    item[0],
                ),
            )
        )

    @staticmethod
    def _contract_failure(
        guard: Mapping[str, Any],
        *,
        reason: str,
    ) -> GuardFailure:
        failure = guard["failure"]
        return GuardFailure(
            guard_id=guard["id"],
            category=guard["category"],
            http_status=failure["http_status"],
            error_code=failure["error_code"],
            message=failure["message"],
            reason=reason,
        )

    @staticmethod
    def _synthetic_guard_failure(
        *,
        guard_id: str,
        category: str,
        http_status: int,
        error_code: str,
        message: str,
        reason: str,
    ) -> GuardFailure:
        return GuardFailure(
            guard_id=guard_id,
            category=category,
            http_status=http_status,
            error_code=error_code,
            message=message,
            reason=reason,
        )

    @classmethod
    def _synthetic_failure(
        cls,
        **kwargs,
    ) -> GuardEvaluation:
        return GuardEvaluation(
            False,
            cls._synthetic_guard_failure(**kwargs),
        )
