"""W5-G05 Backend AI result to State Machine event conformance tests."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from apps.workflow.contracts import load_state_machine_contract
from integrations.ai.request_mapper import build_symptom_analysis_request
from integrations.ai.response_mapper import map_success_response
from integrations.ai.schema_validator import DEFAULT_CONTRACT_ROOT


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
STATE_MACHINE_DIR = REPOSITORY_ROOT / "contracts" / "state-machine"
EVENT_EXPECTATIONS = {
    "SAFE_GUIDANCE_READY": {
        "fixture": "general-guidance.json",
        "to_state": "AI_GUIDANCE",
        "guards": {
            "G-ACTOR-SYSTEM",
            "G-STATE-VERSION",
            "G-SAFE-GUIDANCE-VALID",
            "G-OFFICIAL-EVIDENCE-AVAILABLE",
            "G-NO-DANGER-CONFLICT",
        },
        "effects": {
            "STORE_VALIDATED_GUIDANCE",
            "STORE_VALIDATED_EVIDENCE_REFERENCES",
        },
    },
    "DANGER_DETECTED": {
        "fixture": "danger-detected.json",
        "to_state": "CONSULTATION_REQUIRED",
        "guards": {
            "G-ACTOR-SYSTEM",
            "G-STATE-VERSION",
            "G-DANGER-ASSESSMENT-VALID",
        },
        "effects": {
            "BLOCK_GENERAL_SELF_GUIDANCE",
            "SET_REQUIRES_CONSULTATION",
            "STORE_USAGE_RESTRICTION",
        },
    },
    "NO_EVIDENCE": {
        "fixture": "no-evidence.json",
        "to_state": "CONSULTATION_REQUIRED",
        "guards": {
            "G-ACTOR-SYSTEM",
            "G-STATE-VERSION",
            "G-NO-USABLE-EVIDENCE",
        },
        "effects": {
            "BLOCK_UNGROUNDED_GUIDANCE",
            "SET_REQUIRES_CONSULTATION",
            "SET_USAGE_GUIDANCE_PENDING_CONSULTATION",
        },
    },
}


def request_payload() -> dict:
    return build_symptom_analysis_request(
        inquiry_id=uuid4(),
        correlation_id=uuid4(),
        ai_request_id=uuid4(),
        state_version=2,
        raw_symptom="Water temperature is unstable.",
        model_code="WPUJAC104DWH",
        selected_symptoms=["TEMPERATURE_UNSTABLE"],
        previous_answers=[],
    )


def mapped_event_candidate(fixture_name: str) -> str | None:
    request = request_payload()
    fixture_path = (
        DEFAULT_CONTRACT_ROOT
        / "examples"
        / "symptom-analysis"
        / fixture_name
    )
    response = json.loads(fixture_path.read_text(encoding="utf-8"))[
        "response"
    ]
    for field in (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
    ):
        response[field] = request[field]
    return map_success_response(
        response,
        expected_request=request,
    ).event_candidate


def test_mapper_candidates_match_team_approved_internal_events():
    documents = load_state_machine_contract(STATE_MACHINE_DIR)
    events = {
        event["code"]: event for event in documents["events"]["events"]
    }

    mapped = {
        mapped_event_candidate(expectation["fixture"])
        for expectation in EVENT_EXPECTATIONS.values()
    }

    assert mapped == set(EVENT_EXPECTATIONS)
    for event_code in mapped:
        event = events[event_code]
        assert event["category"] == "SYSTEM_EVENT"
        assert event["scope"] == "AI_RESULT"
        assert event["actor_roles"] == ["SYSTEM"]
        assert event["requires_state_version"] is True
        assert event["external_action"] == {
            "exposed": False,
            "operation_id": None,
        }


def test_mapper_candidates_have_exact_transition_guards_and_effects():
    documents = load_state_machine_contract(STATE_MACHINE_DIR)
    transitions = {
        transition["event"]: transition
        for transition in documents["transitions"]["transitions"]
        if transition["event"] in EVENT_EXPECTATIONS
    }
    guard_ids = {
        guard["id"] for guard in documents["guards"]["guards"]
    }

    assert set(transitions) == set(EVENT_EXPECTATIONS)
    for event_code, expectation in EVENT_EXPECTATIONS.items():
        transition = transitions[event_code]
        assert transition["from_inquiry_state"] == (
            "QUESTIONNAIRE_IN_PROGRESS"
        )
        assert transition["to_inquiry_state"] == expectation["to_state"]
        assert set(transition["guard_refs"]) == expectation["guards"]
        assert set(transition["effects"]) == expectation["effects"]
        assert set(transition["guard_refs"]) <= guard_ids
        assert transition["history"] == {
            "record_inquiry_state_history": True,
            "record_visit_state_history": False,
            "record_business_event": True,
        }


def test_mapping_evidence_uses_only_team_approved_contract_documents():
    documents = load_state_machine_contract(STATE_MACHINE_DIR)

    for document_name in ("events", "transitions", "guards"):
        assert documents[document_name]["contract"]["status"] == (
            "TEAM_APPROVED"
        )
