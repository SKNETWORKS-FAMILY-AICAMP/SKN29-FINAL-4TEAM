"""Contract-consumption tests for dynamic Backend allowed_actions."""

from apps.workflow.engine.allowed_action_resolver import (
    ACTION_RESPONSE_FIELDS,
    AllowedActionContext,
    AllowedActionResolver,
)


def resolve_codes(**overrides):
    values = {
        "inquiry_state": "DRAFT",
        "state_version": 1,
        "actor_role": "CUSTOMER",
        "actor_id": 10,
        "owner_id": 10,
        "assigned_user_id": None,
        "actor_permissions": frozenset(),
        "product_present": True,
        "symptom_payload_valid": True,
    }
    values.update(overrides)
    actions = AllowedActionResolver.resolve(
        context=AllowedActionContext(**values)
    )
    return actions, [action["code"] for action in actions]


def test_runtime_filter_keeps_only_callable_backend_actions():
    actions, codes = resolve_codes(inquiry_state="AI_GUIDANCE")

    assert len(actions) == 1
    assert codes == ["REQUEST_CONSULTATION"]


def test_request_consultation_is_available_in_all_confirmed_states():
    _actions, guidance = resolve_codes(inquiry_state="AI_GUIDANCE")
    _actions, required = resolve_codes(
        inquiry_state="CONSULTATION_REQUIRED",
        state_version=4,
    )
    _actions, completion_pending = resolve_codes(
        inquiry_state="COMPLETION_PENDING",
        state_version=8,
    )

    assert guidance == ["REQUEST_CONSULTATION"]
    assert required == ["REQUEST_CONSULTATION"]
    assert "REQUEST_CONSULTATION" in completion_pending


def test_resolved_feedback_hides_repeat_and_reconsult_but_keeps_unresolved():
    _actions, codes = resolve_codes(
        inquiry_state="COMPLETION_PENDING",
        state_version=8,
        fresh_resolved_feedback_exists=True,
    )

    assert codes == ["CUSTOMER_REPORTED_UNRESOLVED"]


def test_consultant_claim_requires_both_unassigned_waiting_rows():
    base = {
        "inquiry_state": "CONSULTATION_REQUIRED",
        "state_version": 4,
        "actor_role": "CONSULTANT",
        "actor_id": 20,
        "owner_id": 10,
        "assigned_user_id": None,
        "assigned_role_code": "NONE",
        "consultation_exists": True,
        "consultation_status": "WAITING",
        "consultation_consultant_id": None,
    }
    _actions, claimable = resolve_codes(**base)
    _actions, missing_consultation = resolve_codes(
        **{**base, "consultation_exists": False}
    )
    _actions, assigned_inquiry = resolve_codes(
        **{
            **base,
            "assigned_user_id": 21,
            "assigned_role_code": "CONSULTANT",
        }
    )
    _actions, assigned_consultation = resolve_codes(
        **{**base, "consultation_consultant_id": 21}
    )
    _actions, started_consultation = resolve_codes(
        **{**base, "consultation_status": "IN_PROGRESS"}
    )

    assert claimable == ["CLAIM_CONSULTATION"]
    assert missing_consultation == []
    assert assigned_inquiry == []
    assert assigned_consultation == []
    assert started_consultation == []


def test_cancel_availability_uses_owner_assignment_and_operator_capability():
    _actions, owner_codes = resolve_codes()
    _actions, assigned_codes = resolve_codes(
        actor_role="CONSULTANT",
        actor_id=20,
        owner_id=10,
        assigned_user_id=20,
    )
    _actions, unassigned_codes = resolve_codes(
        actor_role="CONSULTANT",
        actor_id=21,
        owner_id=10,
        assigned_user_id=20,
    )
    _actions, operator_codes = resolve_codes(
        actor_role="OPERATOR",
        actor_id=30,
        owner_id=10,
        actor_permissions=frozenset({"INQUIRY_CANCEL"}),
    )
    _actions, operator_without_permission = resolve_codes(
        actor_role="OPERATOR",
        actor_id=31,
        owner_id=10,
    )

    assert owner_codes == ["SUBMIT_SYMPTOM", "CANCEL_INQUIRY"]
    assert assigned_codes == ["CANCEL_INQUIRY"]
    assert unassigned_codes == []
    assert operator_codes == ["CANCEL_INQUIRY"]
    assert operator_without_permission == []


def test_consultation_actions_follow_persisted_summary_and_result_guards():
    _actions, missing_consultation = resolve_codes(
        inquiry_state="CONSULTATION_IN_PROGRESS",
        state_version=4,
        actor_role="CONSULTANT",
        actor_id=20,
        owner_id=10,
        assigned_user_id=20,
    )
    _actions, editable = resolve_codes(
        inquiry_state="CONSULTATION_IN_PROGRESS",
        state_version=4,
        actor_role="CONSULTANT",
        actor_id=20,
        owner_id=10,
        assigned_user_id=20,
        consultation_exists=True,
    )
    _actions, confirmable = resolve_codes(
        inquiry_state="CONSULTATION_IN_PROGRESS",
        state_version=4,
        actor_role="CONSULTANT",
        actor_id=20,
        owner_id=10,
        assigned_user_id=20,
        consultation_exists=True,
        consultation_summary="Checked and edited summary",
    )
    _actions, confirmed_visit_result = resolve_codes(
        inquiry_state="CONSULTATION_IN_PROGRESS",
        state_version=5,
        actor_role="CONSULTANT",
        actor_id=20,
        owner_id=10,
        assigned_user_id=20,
        consultation_exists=True,
        consultation_summary="Checked and edited summary",
        consultation_confirmed_summary="Confirmed summary",
        consultation_summary_confirmed=True,
        consultation_outcome="VISIT_REQUIRED",
    )

    assert missing_consultation == []
    assert editable == ["UPDATE_CONSULTATION_SUMMARY"]
    assert confirmable == [
        "UPDATE_CONSULTATION_SUMMARY",
        "CONFIRM_CONSULTATION_SUMMARY",
    ]
    assert confirmed_visit_result == [
        "UPDATE_CONSULTATION_SUMMARY",
        "CONSULTATION_COMPLETED",
        "VISIT_REVIEW_REQUIRED",
    ]


def test_visit_actions_follow_latest_visit_date_and_technician_guards():
    base = {
        "inquiry_state": "VISIT_SCHEDULING",
        "state_version": 8,
        "actor_role": "CONSULTANT",
        "actor_id": 20,
        "owner_id": 10,
        "assigned_user_id": 20,
        "visit_exists": True,
        "visit_is_latest": True,
    }
    _actions, assigning = resolve_codes(
        **base,
        visit_status="ASSIGNING",
    )
    _actions, scheduling = resolve_codes(
        **base,
        visit_status="SCHEDULING",
    )
    _actions, confirmable = resolve_codes(
        **base,
        visit_status="SCHEDULING",
        visit_confirmed_date=True,
        technician_assigned=True,
        technician_active=True,
        technician_synthetic=True,
        technician_role="TECHNICIAN",
    )

    assert assigning == ["UPDATE_VISIT_SCHEDULE"]
    assert scheduling == ["UPDATE_VISIT_SCHEDULE"]
    assert confirmable == ["UPDATE_VISIT_SCHEDULE", "CONFIRM_VISIT"]


def test_revisit_schedule_requires_latest_followup_visit_and_assignment():
    base = {
        "inquiry_state": "REVISIT_REQUIRED",
        "state_version": 10,
        "actor_role": "CONSULTANT",
        "actor_id": 20,
        "owner_id": 10,
        "assigned_user_id": 20,
        "visit_exists": True,
        "visit_is_latest": True,
        "visit_status": "FOLLOW_UP_REQUIRED",
    }
    _actions, callable_codes = resolve_codes(**base)
    _actions, unassigned_codes = resolve_codes(
        **{**base, "actor_id": 21}
    )
    _actions, wrong_visit_status = resolve_codes(
        **{**base, "visit_status": "COMPLETED"}
    )

    assert callable_codes == ["UPDATE_VISIT_SCHEDULE"]
    assert unassigned_codes == []
    assert wrong_visit_status == []


def test_response_shape_and_contract_order_remain_stable():
    actions, _codes = resolve_codes()

    assert [tuple(action) for action in actions] == [
        ACTION_RESPONSE_FIELDS,
        ACTION_RESPONSE_FIELDS,
    ]


def test_persisted_payload_guards_hide_actions_that_cannot_start():
    _actions, no_symptom = resolve_codes(symptom_payload_valid=False)
    _actions, no_open_question = resolve_codes(
        inquiry_state="QUESTIONNAIRE_IN_PROGRESS",
        state_version=2,
        open_followup_questions=False,
    )
    _actions, open_question = resolve_codes(
        inquiry_state="QUESTIONNAIRE_IN_PROGRESS",
        state_version=2,
        open_followup_questions=True,
    )

    assert no_symptom == ["CANCEL_INQUIRY"]
    assert no_open_question == ["CANCEL_INQUIRY"]
    assert open_question == ["SUBMIT_ANSWERS", "CANCEL_INQUIRY"]
