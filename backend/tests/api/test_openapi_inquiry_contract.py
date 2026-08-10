"""T-022 확정 API 기준선과 OpenAPI 참조를 검증한다."""

from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_DIR = REPOSITORY_ROOT / "contracts" / "api"
INQUIRY_CONTRACT = OPENAPI_DIR / "paths" / "inquiries.yaml"
INQUIRY_SCHEMA_DIR = OPENAPI_DIR / "components" / "schemas" / "inquiry"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_inquiry_operations_track_confirmed_runtime_status():
    contract = load_yaml(INQUIRY_CONTRACT)
    operations = {
        (path, method): operation
        for path, path_item in contract.items()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }

    assert set(operations) == {
        ("/inquiries", "get"),
        ("/inquiries", "post"),
        ("/inquiries/{id}", "get"),
        ("/inquiries/{id}/questionnaire", "patch"),
        ("/inquiries/{id}/action-results", "post"),
        ("/inquiries/{id}/submit", "post"),
    }
    assert {
        operation["x-contract-status"]
        for operation in operations.values()
    } == {"CONFIRMED"}
    assert all(operation.get("responses") for operation in operations.values())
    assert operations[("/inquiries", "get")][
        "x-runtime-status"
    ] == "IMPLEMENTED"
    assert operations[("/inquiries/{id}", "get")][
        "x-runtime-status"
    ] == "IMPLEMENTED"


def test_inquiry_request_and_result_schemas_are_confirmed():
    schema_names = (
        "CreateInquiryRequest.yaml",
        "InquiryQuestionnaireRequest.yaml",
        "ActionResultRequest.yaml",
        "ActionResult.yaml",
    )

    for name in schema_names:
        schema = load_yaml(INQUIRY_SCHEMA_DIR / name)
        assert schema["x-contract-status"] == "CONFIRMED"
        assert "x-open-decisions" not in schema


def test_confirmed_inquiry_schema_preserves_v05_fields():
    create = load_yaml(INQUIRY_SCHEMA_DIR / "CreateInquiryRequest.yaml")
    questionnaire = load_yaml(
        INQUIRY_SCHEMA_DIR / "InquiryQuestionnaireRequest.yaml"
    )
    action_result = load_yaml(
        INQUIRY_SCHEMA_DIR / "ActionResultRequest.yaml"
    )

    assert "representative_symptom_code" in create["properties"]
    assert "representative_symptom_code" in questionnaire["properties"]
    assert set(questionnaire["properties"]["answers"]["oneOf"][0]) >= {
        "type",
        "additionalProperties",
    }
    assert action_result["properties"]["performed_at"]["format"] == (
        "date-time"
    )


def test_openapi_root_references_confirmed_inquiry_paths():
    root = load_yaml(OPENAPI_DIR / "openapi.yaml")

    assert root["paths"]["/inquiries"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries"
    )
    assert root["paths"]["/inquiries/{id}"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}"
    )
    assert root["paths"]["/inquiries/{id}/questionnaire"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1questionnaire"
    )
    assert root["paths"]["/inquiries/{id}/action-results"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1action-results"
    )
    assert root["paths"]["/inquiries/{id}/submit"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1submit"
    )


def test_submit_symptom_contract_uses_saved_input_and_state_version_only():
    contract = load_yaml(INQUIRY_CONTRACT)
    operation = contract["/inquiries/{id}/submit"]["post"]
    request_schema = load_yaml(
        OPENAPI_DIR
        / "components"
        / "schemas"
        / "questionnaire"
        / "SymptomSubmissionRequest.yaml"
    )
    result_schema = load_yaml(
        INQUIRY_SCHEMA_DIR / "SubmitSymptomResult.yaml"
    )

    assert operation["operationId"] == "submitSymptom"
    assert operation["x-state-machine"] == {
        "event": "SUBMIT_SYMPTOM",
        "operation_id": "submitSymptom",
        "transition_rule": "TR-INQ-002",
        "from_state": "DRAFT",
        "to_state": "QUESTIONNAIRE_IN_PROGRESS",
        "actor_role": "CUSTOMER",
        "symptom_source": "Inquiry.raw_text",
        "adhoc_questionnaire_projection": "INQUIRY_STATE_AND_HISTORY",
    }
    assert operation["x-runtime-preconditions"] == {
        "subscription_status": "ACTIVE",
        "product_model_required": True,
    }
    assert request_schema["x-contract-status"] == "CONFIRMED"
    assert request_schema["required"] == ["state_version"]
    assert set(request_schema["properties"]) == {"state_version"}
    assert result_schema["x-contract-status"] == "CONFIRMED"
    assert result_schema["properties"]["state"]["const"] == (
        "QUESTIONNAIRE_IN_PROGRESS"
    )
