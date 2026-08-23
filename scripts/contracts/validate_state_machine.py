from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[2]
SM = ROOT / "contracts" / "state-machine"

def load(name):
    return yaml.safe_load((SM / name).read_text(encoding="utf-8"))

states = load("inquiry-states.yaml")
events = load("inquiry-events.yaml")
rules = load("transition-rules.yaml")
guards = load("transition-guards.yaml")
actions = load("allowed-actions.yaml")
permissions = load("role-permissions.yaml")
completion = load("completion-policy.yaml")
concurrency = load("concurrency-policy.yaml")
crosswalk = load("data-state-crosswalk.yaml")
representative = load("examples/representative-e2e.yaml")
flow_examples = [
    load("examples/consultation-resolution.yaml"),
    load("examples/danger-detected.yaml"),
    load("examples/no-evidence.yaml"),
    load("examples/reopened-inquiry.yaml"),
    load("examples/self-resolution.yaml"),
    load("examples/visit-resolution.yaml"),
]

CONTRACT_VERSION = "1.0.0"
APPROVED_STATUS = "TEAM_APPROVED"

approved_documents = [
    states,
    events,
    rules,
    guards,
    actions,
    permissions,
    completion,
    concurrency,
    crosswalk,
    representative,
    *flow_examples,
]

for document in approved_documents:
    assert document["contract"]["version"] == CONTRACT_VERSION
    assert document["contract"]["status"] == APPROVED_STATUS

state_codes = {x["code"] for x in states["states"]}
event_by_code = {x["code"]: x for x in events["events"]}
rule_by_id = {x["id"]: x for x in rules["transitions"]}
guard_ids = {x["id"] for x in guards["guards"]}
action_by_code = {x["code"]: x for x in actions["action_catalog"]}

assert len(state_codes) == len(states["states"])
assert len(event_by_code) == len(events["events"])
assert len(rule_by_id) == len(rules["transitions"])
assert len(guard_ids) == len(guards["guards"])
assert len(action_by_code) == len(actions["action_catalog"])

for rule in rules["transitions"]:
    assert rule["event"] in event_by_code
    if rule["from_inquiry_state"] is not None:
        assert rule["from_inquiry_state"] in state_codes
    assert rule["to_inquiry_state"] in state_codes
    for guard in rule.get("guard_refs", []):
        assert guard in guard_ids, f"Undefined guard: {guard}"
    if rule["from_inquiry_state"] != rule["to_inquiry_state"]:
        assert rule["history"]["record_inquiry_state_history"] is True

for action, item in action_by_code.items():
    event = event_by_code[action]
    assert event["external_action"]["exposed"] is True
    assert event["category"] != "SYSTEM_EVENT"
    assert item["operation_id"] == event["external_action"]["operation_id"]

for state, role_map in actions["state_role_actions"].items():
    assert state in state_codes
    for role, entries in role_map.items():
        for entry in entries:
            action = entry["action"]
            assert action in action_by_code
            assert role in event_by_code[action]["actor_roles"]
            for rid in entry["transition_rule_ids"]:
                assert rid in rule_by_id
                assert rule_by_id[rid]["event"] == action
                assert rule_by_id[rid]["from_inquiry_state"] == state

for terminal in states["terminal_states"]:
    assert actions["state_role_actions"][terminal] == {}

for role in permissions["roles"]:
    for event_code in role["allowed_events"]:
        assert event_code in event_by_code
        assert role["code"] in event_by_code[event_code]["actor_roles"]

assert "VISIT_NOT_NEEDED" in event_by_code
assert any(
    r["event"] == "VISIT_NOT_NEEDED"
    and r["from_inquiry_state"] == "VISIT_REVIEW_PENDING"
    and r["to_inquiry_state"] == "COMPLETION_PENDING"
    for r in rules["transitions"]
)
assert any(
    e["action"] == "VISIT_NOT_NEEDED"
    for e in actions["state_role_actions"]["VISIT_REVIEW_PENDING"]["CONSULTANT"]
)

assert completion["terminal_state_policy"]["allow_transition"] is False
assert concurrency["state_version"]["conflict_response"]["http_status"] == 409

assert crosswalk["terminal_and_reopen_policy"]["terminal_states"] == (
    states["terminal_states"]
)
assert crosswalk["terminal_and_reopen_policy"][
    "same_inquiry_reopen_from_terminal"
] is False

representative_steps = representative["steps"]
representative_events = [step["event"] for step in representative_steps]
assert len(representative_steps) == 15
assert [step["order"] for step in representative_steps] == list(range(1, 16))
assert [step["state_version_after"] for step in representative_steps] == list(
    range(1, 16)
)
assert representative_events == crosswalk["representative_flow"][
    "event_sequence"
]

for step in representative_steps:
    assert step["event"] in event_by_code
    if step["from_inquiry_state"] is not None:
        assert step["from_inquiry_state"] in state_codes
    assert step["to_inquiry_state"] in state_codes
    assert step["actor"] in event_by_code[step["event"]]["actor_roles"]
    assert any(
        rule["event"] == step["event"]
        and rule["from_inquiry_state"] == step["from_inquiry_state"]
        and rule["to_inquiry_state"] == step["to_inquiry_state"]
        for rule in rules["transitions"]
    )

assert representative["expected_result"] == {
    "inquiry_state": "RESOLVED",
    "state_version": 15,
    "visit_status": "COMPLETED",
    "terminal": True,
    "additional_allowed_actions": [],
}

print("State Machine contract validation PASSED")
print(f"- contract version: {CONTRACT_VERSION} ({APPROVED_STATUS})")
print(f"- states: {len(state_codes)}")
print(f"- events: {len(event_by_code)}")
print(f"- transitions: {len(rule_by_id)}")
print(f"- guards: {len(guard_ids)}")
print(f"- external actions: {len(action_by_code)}")
print(f"- representative steps: {len(representative_steps)}")
