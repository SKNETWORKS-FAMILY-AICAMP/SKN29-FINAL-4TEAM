"""PM이 승인한 5주차 E2E Action 기계 계약을 검증한다."""

from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
API_DIR = REPO_ROOT / "contracts" / "api"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

EXPECTED = {
    "/inquiries/{id}/answers": (
        "submitFollowUpAnswers",
        "SUBMIT_ANSWERS",
    ),
    "/inquiries/{id}/request-consultation": (
        "requestConsultation",
        "REQUEST_CONSULTATION",
    ),
    "/visits/{visit_id}/start": ("startVisit", "START_VISIT"),
    "/visits/{visit_id}/complete": (
        "completeVisit",
        "VISIT_COMPLETED",
    ),
    "/inquiries/{id}/resolution-feedback": (
        "submitResolutionFeedback",
        "SUBMIT_RESOLUTION_FEEDBACK",
    ),
    "/inquiries/{id}/finalize": (
        "finalizeInquiry",
        "FINALIZE_INQUIRY",
    ),
    "/inquiries/{id}/report-unresolved": (
        "reportUnresolved",
        "CUSTOMER_REPORTED_UNRESOLVED",
    ),
    "/inquiries/{id}/resume-consultation": (
        "resumeConsultation",
        "RESUME_CONSULTATION",
    ),
}


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_pointer(document, fragment: str):
    current = document
    for token in fragment.removeprefix("/").split("/"):
        if token:
            decoded = token.replace("~1", "/").replace("~0", "~")
            current = current[decoded]
    return current


def operation_for(path: str):
    root = load_yaml(API_DIR / "openapi.yaml")
    reference = root["paths"][path]["$ref"]
    relative, _, fragment = reference.partition("#")
    item = resolve_pointer(load_yaml(API_DIR / relative), fragment)
    methods = [name for name in item if name in HTTP_METHODS]
    assert methods == ["post"]
    return item["post"]


def parameter_refs(operation):
    return {
        item["$ref"].rsplit("/", 1)[-1]
        for item in operation["parameters"]
        if "$ref" in item
    }


def test_eight_pm_actions_are_confirmed_with_selective_runtime_status():
    root = load_yaml(API_DIR / "openapi.yaml")
    assert root["info"]["version"] == "0.8.0"

    for path, (operation_id, event) in EXPECTED.items():
        operation = operation_for(path)
        assert operation["operationId"] == operation_id
        assert operation["x-contract-status"] == "CONFIRMED"
        expected_runtime = (
            "IMPLEMENTED"
            if path == "/inquiries/{id}/answers"
            else "NOT_IMPLEMENTED"
        )
        assert operation["x-runtime-status"] == expected_runtime
        assert operation["x-state-machine"]["event"] == event
        assert parameter_refs(operation) == {
            "IdempotencyKey.yaml",
            "CorrelationId.yaml",
        }
        assert set(operation["responses"]) == {
            "200",
            "400",
            "401",
            "403",
            "404",
            "409",
            "422",
            "500",
        }

    operation_ids = {
        operation_for(path)["operationId"] for path in EXPECTED
    }
    assert "SAFE_GUIDANCE_READY" not in operation_ids


def test_submit_answers_uses_text_or_payload_exclusively():
    schema = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "questionnaire"
        / "FollowUpAnswerRequest.yaml"
    )
    validator = Draft202012Validator(schema)
    question_id = "31b58743-d099-4e9b-99d8-73017c7fb129"
    valid = (
        {"question_id": question_id, "answer_text": "정상 답변"},
        {
            "question_id": question_id,
            "answer_payload": {"selected_option": "FILTER_REPLACEMENT"},
        },
    )
    invalid = (
        {"question_id": question_id},
        {
            "question_id": question_id,
            "answer_text": "답변",
            "answer_payload": {"selected_option": "FILTER_REPLACEMENT"},
        },
        {"question_id": question_id, "answer_text": "   "},
        {"question_id": question_id, "answer_payload": {}},
        {
            "question_id": question_id,
            "answer_payload": {
                "selected_option": "FILTER_REPLACEMENT",
                "target_field": "internal-only",
            },
        },
    )
    for payload in valid:
        assert list(validator.iter_errors(payload)) == []
    for payload in invalid:
        assert list(validator.iter_errors(payload))


def test_visit_completion_codes_match_registry_and_versions_are_required():
    schema = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "visit"
        / "SubmitVisitResultRequest.yaml"
    )
    codes = load_yaml(REPO_ROOT / "contracts" / "codes" / "care-results.yaml")
    assert schema["properties"]["result_code"]["enum"] == codes["codes"]
    assert set(schema["required"]) == {
        "state_version",
        "visit_state_version",
        "result_code",
        "work_summary",
        "completed_at",
    }
    assert schema["properties"]["work_summary"]["maxLength"] == 4000


def test_feedback_and_unresolved_contracts_have_opposite_resolution_constants():
    feedback = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "inquiry"
        / "ResolutionFeedbackRequest.yaml"
    )
    unresolved = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "inquiry"
        / "ReportUnresolvedRequest.yaml"
    )
    finalized = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "inquiry"
        / "FinalizeInquiryRequest.yaml"
    )
    assert feedback["properties"]["resolved"]["const"] is True
    assert unresolved["properties"]["resolved"]["const"] is False
    assert "resolved" not in finalized["properties"]
