"""Resolve callable external actions from the PM contracts and DB facts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from apps.workflow.contracts.state_machine_loader import (
    REPOSITORY_ROOT,
    load_state_machine_contract,
    load_yaml_mapping,
)
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.state_machine import InvalidStateTransition, StateMachine


ACTION_RESPONSE_FIELDS = (
    "code",
    "label",
    "operation_id",
    "style",
    "requires_confirmation",
    "confirmation_message",
)
INQUIRY_CANCEL_DJANGO_PERMISSION = "inquiries.cancel_inquiry"
_UNSET = object()


@lru_cache(maxsize=1)
def _contract_documents():
    return load_state_machine_contract()


@lru_cache(maxsize=1)
def _runtime_action_contract() -> dict[str, dict[str, str]]:
    """Load the executable action set instead of duplicating twelve codes."""

    path = REPOSITORY_ROOT / "contracts" / "api" / "action-operation-crosswalk.yaml"
    document = load_yaml_mapping(path)
    result: dict[str, dict[str, str]] = {}
    for item in document.get("actions", []):
        runtime = item.get("runtime", {})
        if (
            item.get("classification") != "RUNTIME_IMPLEMENTED"
            or runtime.get("implemented") is not True
        ):
            continue
        action = item.get("action")
        event = item.get("event")
        operation_id = item.get("operation_id")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (action, event, operation_id)
        ):
            raise ValueError("Invalid executable action crosswalk entry")
        if action in result:
            raise ValueError(f"Duplicate executable action: {action}")
        result[action] = {
            "event": event,
            "operation_id": operation_id,
        }
    return result


@dataclass(frozen=True, slots=True)
class AllowedActionContext:
    """Request-independent facts used to decide whether an action is callable."""

    inquiry_state: str
    state_version: int
    actor_role: str
    actor_id: Any | None = None
    owner_id: Any | None = None
    assigned_user_id: Any | None = None
    actor_permissions: frozenset[str] = frozenset()
    product_present: bool = False
    symptom_payload_valid: bool = False
    open_followup_questions: bool = False
    consultation_exists: bool = False
    consultation_summary: str = ""
    consultation_confirmed_summary: str | None = None
    consultation_summary_confirmed: bool = False
    consultation_outcome: str | None = None
    consultation_completed: bool = False
    visit_exists: bool = False
    visit_status: str | None = None
    visit_is_latest: bool = False
    visit_confirmed_date: bool = False
    technician_assigned: bool = False
    technician_active: bool = False
    technician_synthetic: bool = False
    technician_role: str | None = None

    @classmethod
    def from_models(
        cls,
        *,
        inquiry: Any,
        actor: Any,
        consultation: Any = _UNSET,
        visit: Any = _UNSET,
        open_followup_questions: Any = _UNSET,
    ) -> "AllowedActionContext":
        """Build a stable projection from locked or preloaded aggregate rows."""

        if consultation is _UNSET:
            preloaded = getattr(inquiry, "allowed_action_consultations", None)
            consultation = (
                preloaded[0]
                if preloaded is not None and preloaded
                else None
                if preloaded is not None
                else inquiry.consultations.order_by("-sequence", "-id").first()
            )
        if visit is _UNSET:
            preloaded = getattr(inquiry, "allowed_action_visits", None)
            visit = (
                preloaded[0]
                if preloaded is not None and preloaded
                else None
                if preloaded is not None
                else inquiry.visits.select_related("technician")
                .order_by("-created_at", "-id")
                .first()
            )

        actor_role = str(getattr(actor, "role_code", "") or "")
        permissions: set[str] = set()
        if (
            actor_role == "OPERATOR"
            and bool(getattr(actor, "is_authenticated", False))
            and actor.has_perm(INQUIRY_CANCEL_DJANGO_PERMISSION)
        ):
            permissions.add("INQUIRY_CANCEL")

        technician = getattr(visit, "technician", None) if visit else None
        customer = getattr(getattr(inquiry, "subscription", None), "customer", None)
        product_present = bool(
            getattr(getattr(inquiry, "subscription", None), "product_model_id", None)
        )
        raw_text = getattr(inquiry, "raw_text", None)
        normalized_text = raw_text.strip() if isinstance(raw_text, str) else ""
        if open_followup_questions is _UNSET:
            open_followup_questions = False
            if (
                actor_role == "CUSTOMER"
                and inquiry.status_code == "QUESTIONNAIRE_IN_PROGRESS"
            ):
                open_followup_questions = inquiry.qa_entries.filter(
                    customer_answer__isnull=True
                ).exists()
        else:
            open_followup_questions = bool(open_followup_questions)
        return cls(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            actor_role=actor_role,
            actor_id=getattr(actor, "pk", None),
            owner_id=getattr(customer, "user_id", None),
            assigned_user_id=getattr(inquiry, "assigned_user_id", None),
            actor_permissions=frozenset(permissions),
            product_present=product_present,
            symptom_payload_valid=bool(
                2 <= len(normalized_text) <= 2000
                and product_present
                and getattr(getattr(inquiry, "subscription", None), "status_code", None)
                == "ACTIVE"
            ),
            open_followup_questions=open_followup_questions,
            consultation_exists=consultation is not None,
            consultation_summary=(getattr(consultation, "summary", "") or ""),
            consultation_confirmed_summary=getattr(
                consultation, "confirmed_summary", None
            ),
            consultation_summary_confirmed=(
                getattr(consultation, "summary_confirmed_at", None) is not None
            ),
            consultation_outcome=getattr(consultation, "outcome", None),
            consultation_completed=(
                getattr(consultation, "completed_at", None) is not None
            ),
            visit_exists=visit is not None,
            visit_status=getattr(visit, "status", None),
            visit_is_latest=visit is not None,
            visit_confirmed_date=(
                getattr(visit, "confirmed_date", None) is not None
            ),
            technician_assigned=technician is not None,
            technician_active=bool(getattr(technician, "is_active", False)),
            technician_synthetic=bool(
                getattr(technician, "is_synthetic", False)
            ),
            technician_role=getattr(technician, "role_code", None),
        )


class AllowedActionResolver:
    """Apply state, transition, persisted guards, and Runtime availability."""

    @classmethod
    def resolve(
        cls,
        *,
        context: AllowedActionContext,
    ) -> list[dict[str, Any]]:
        documents = _contract_documents()
        document = documents["allowed_actions"]
        role_actions = (
            document["state_role_actions"]
            .get(context.inquiry_state, {})
            .get(context.actor_role, [])
        )
        catalog = {item["code"]: item for item in document["action_catalog"]}
        runtime_actions = _runtime_action_contract()
        state_machine = StateMachine(documents)

        result = []
        for assignment in role_actions:
            action_code = assignment["action"]
            runtime = runtime_actions.get(action_code)
            if runtime is None:
                continue
            action = catalog.get(action_code)
            if action is None or action.get("operation_id") != runtime["operation_id"]:
                raise ValueError(f"Action catalog drift: {action_code}")
            try:
                transition = state_machine.resolve(
                    snapshot=WorkflowSnapshot(
                        inquiry_state=context.inquiry_state,
                        state_version=context.state_version,
                        visit_status=context.visit_status,
                    ),
                    event_code=runtime["event"],
                )
            except InvalidStateTransition:
                continue
            if transition.rule_id not in assignment.get("transition_rule_ids", []):
                continue
            if not all(
                cls._guard_available(guard_id, context=context)
                for guard_id in transition.guard_refs
            ):
                continue
            result.append(
                {
                    field: action.get(field)
                    for field in ACTION_RESPONSE_FIELDS
                }
            )
        return result

    @staticmethod
    def _guard_available(
        guard_id: str,
        *,
        context: AllowedActionContext,
    ) -> bool:
        role_guards = {
            "G-ACTOR-CUSTOMER": "CUSTOMER",
            "G-ACTOR-CONSULTANT": "CONSULTANT",
            "G-ACTOR-TECHNICIAN": "TECHNICIAN",
            "G-ACTOR-SYSTEM": "SYSTEM",
        }
        if guard_id in role_guards:
            return context.actor_role == role_guards[guard_id]
        if guard_id == "G-INQUIRY-OWNER":
            return context.actor_id == context.owner_id
        if guard_id == "G-ASSIGNED-CONSULTANT":
            return (
                context.actor_role == "CONSULTANT"
                and context.actor_id == context.assigned_user_id
            )
        if guard_id == "G-CANCEL-ACTOR-AUTHORIZED":
            return bool(
                (
                    context.actor_role == "CUSTOMER"
                    and context.actor_id == context.owner_id
                )
                or (
                    context.actor_role == "CONSULTANT"
                    and context.actor_id == context.assigned_user_id
                )
                or (
                    context.actor_role == "OPERATOR"
                    and "INQUIRY_CANCEL" in context.actor_permissions
                )
            )

        # These values are supplied and revalidated only when the user invokes
        # the action. Their absence in a read Snapshot must not hide a button.
        if guard_id in {
            "G-STATE-VERSION",
            "G-IDEMPOTENCY-KEY",
            "G-CANCELLATION-REASON",
        }:
            return True
        if guard_id == "G-SYMPTOM-PAYLOAD-VALID":
            return context.symptom_payload_valid
        if guard_id == "G-FOLLOWUP-ANSWERS-VALID":
            return context.open_followup_questions
        if guard_id == "G-CONSULTATION-SUMMARY-PAYLOAD-VALID":
            return context.consultation_exists
        if guard_id == "G-CONSULTATION-SUMMARY-CONFIRMABLE":
            return bool(
                context.consultation_exists
                and context.consultation_summary.strip()
                and not context.consultation_summary_confirmed
            )
        if guard_id == "G-CONSULTATION-RESULT-COMPLETE":
            return bool(
                context.consultation_exists
                and context.consultation_outcome
                in {
                    "COMPLETED_NO_VISIT",
                    "VISIT_REQUIRED",
                    "REOPENED_FOLLOWUP",
                }
                and context.consultation_confirmed_summary
                and context.consultation_summary_confirmed
                and not context.consultation_completed
            )
        if guard_id == "G-VISIT-REVIEW-PAYLOAD-VALID":
            return bool(
                context.consultation_exists
                and context.consultation_outcome == "VISIT_REQUIRED"
                and context.consultation_confirmed_summary
                and not context.visit_exists
            )
        if guard_id == "G-VISIT-HANDOFF-COMPLETE":
            return bool(
                context.consultation_exists
                and context.consultation_outcome == "VISIT_REQUIRED"
                and context.consultation_confirmed_summary
                and context.product_present
                and not context.visit_exists
            )
        if guard_id == "G-VISIT-NOT-NEEDED-RESULT-COMPLETE":
            return bool(
                context.consultation_exists
                and context.consultation_outcome == "VISIT_REQUIRED"
                and context.consultation_confirmed_summary
                and context.consultation_summary_confirmed
                and not context.visit_exists
            )
        if guard_id == "G-VISIT-SCHEDULE-PAYLOAD-VALID":
            return context.visit_exists and context.visit_is_latest
        if guard_id == "G-CONFIRMED-VISIT-DATE":
            return context.visit_is_latest and context.visit_confirmed_date
        if guard_id == "G-ASSIGNED-TECHNICIAN-PRESENT":
            return bool(
                context.visit_is_latest
                and context.technician_assigned
                and context.technician_active
                and context.technician_synthetic
                and context.technician_role == "TECHNICIAN"
            )
        return False
