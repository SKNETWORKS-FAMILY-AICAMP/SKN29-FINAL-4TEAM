"""T-022 확정 API 기준선과 OpenAPI 참조를 검증한다."""

from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_DIR = REPOSITORY_ROOT / "contracts" / "api"
INQUIRY_CONTRACT = OPENAPI_DIR / "paths" / "inquiries.yaml"
WORKFLOW_CONTRACT = OPENAPI_DIR / "paths" / "workflow.yaml"
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


def test_submit_answers_contract_matches_state_machine_operation():
    contract = load_yaml(WORKFLOW_CONTRACT)
    operation = contract["/inquiries/{id}/answers"]["post"]
    path_parameter = contract["/inquiries/{id}/answers"][
        "parameters"
    ][0]
    answer_schema = load_yaml(
        OPENAPI_DIR
        / "components"
        / "schemas"
        / "questionnaire"
        / "FollowUpAnswerRequest.yaml"
    )

    assert path_parameter["schema"] == {
        "type": "string",
        "format": "uuid",
    }
    assert operation["operationId"] == "submitFollowUpAnswers"
    assert operation["x-runtime-status"] == "IMPLEMENTED"
    assert operation["x-state-machine"] == {
        "event": "SUBMIT_ANSWERS",
        "transition_rule": "TR-INQ-003",
        "from_state": "QUESTIONNAIRE_IN_PROGRESS",
        "to_state": "QUESTIONNAIRE_IN_PROGRESS",
        "actor_role": "CUSTOMER",
    }
    assert operation["parameters"] == [
        {"$ref": "../components/parameters/IdempotencyKey.yaml"},
        {"$ref": "../components/parameters/CorrelationId.yaml"},
    ]
    assert answer_schema["required"] == ["question_id"]
    assert answer_schema["properties"]["question_id"]["format"] == (
        "uuid"
    )
    assert set(answer_schema["properties"]) == {
        "question_id",
        "answer_text",
        "answer_payload",
    }
    assert answer_schema["properties"]["answer_payload"] == {
        "type": "object",
        "additionalProperties": False,
        "required": ["selected_option"],
        "properties": {
            "selected_option": {
                "type": "string",
                "minLength": 1,
                "maxLength": 200,
                "pattern": ".*\\S.*",
            }
        },
        "description": "SINGLE_CHOICE 질문에 Backend가 공개한 선택지 값",
    }
    assert "500" in operation["responses"]


def test_submit_answers_openapi_enforces_typed_answer_meaning():
    schema = load_yaml(
        OPENAPI_DIR
        / "components"
        / "schemas"
        / "questionnaire"
        / "FollowUpAnswerRequest.yaml"
    )
    validator = Draft202012Validator(schema)
    question_id = "31b58743-d099-4e9b-99d8-73017c7fb129"

    valid_payloads = (
        {
            "question_id": question_id,
            "answer_text": "필터 교체 직후입니다.",
        },
        {
            "question_id": question_id,
            "answer_payload": {"selected_option": "FILTER_REPLACEMENT"},
        },
    )
    invalid_payloads = (
        {"question_id": question_id},
        {
            "question_id": question_id,
            "answer_text": "   ",
        },
        {
            "question_id": question_id,
            "answer_payload": {},
        },
        {
            "question_id": question_id,
            "answer_text": "답변",
            "answer_payload": {"selected_option": "FILTER_REPLACEMENT"},
        },
    )

    for payload in valid_payloads:
        assert list(validator.iter_errors(payload)) == []
    for payload in invalid_payloads:
        assert list(validator.iter_errors(payload))


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
    assert root["paths"]["/inquiries/{id}/answers"]["$ref"] == (
        "./paths/workflow.yaml#/~1inquiries~1{id}~1answers"
    )
    assert root["paths"]["/inquiries/{id}/action-results"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1action-results"
    )
    assert root["paths"]["/inquiries/{id}/submit"]["$ref"] == (
        "./paths/inquiries.yaml#/~1inquiries~1{id}~1submit"
    )


def test_customer_read_contracts_are_owner_scoped_and_implemented():
    root = load_yaml(OPENAPI_DIR / "openapi.yaml")
    contract = load_yaml(
        OPENAPI_DIR / "paths" / "customer-inquiries.yaml"
    )
    expected = {
        "/me/inquiries/{inquiry_id}": (
            "getMyInquiry",
            "CustomerInquirySnapshot.yaml",
        ),
        "/me/inquiries/{inquiry_id}/questions": (
            "listMyInquiryQuestions",
            "CustomerInquiryQuestions.yaml",
        ),
        "/me/inquiries/{inquiry_id}/guidance": (
            "getMyInquiryGuidance",
            "CustomerInquiryGuidance.yaml",
        ),
    }

    for path, (operation_id, schema_name) in expected.items():
        operation = contract[path]["get"]
        assert operation["operationId"] == operation_id
        assert operation["x-contract-status"] == "CONFIRMED"
        assert operation["x-runtime-status"] == "IMPLEMENTED"
        assert operation["x-permission-scope"] == "OWN_INQUIRY"
        expected_responses = {
            "200",
            "401",
            "403",
            "404",
            "422",
            "500",
        }
        if path.endswith("/guidance"):
            expected_responses.add("409")
        assert set(operation["responses"]) == expected_responses
        assert load_yaml(INQUIRY_SCHEMA_DIR / schema_name)[
            "x-contract-status"
        ] == "CONFIRMED"

    assert root["paths"]["/me/inquiries/{inquiry_id}"]["$ref"] == (
        "./paths/customer-inquiries.yaml#/~1me~1inquiries~1{inquiry_id}"
    )
    assert root["paths"][
        "/me/inquiries/{inquiry_id}/questions"
    ]["$ref"] == (
        "./paths/customer-inquiries.yaml"
        "#/~1me~1inquiries~1{inquiry_id}~1questions"
    )
    assert root["paths"][
        "/me/inquiries/{inquiry_id}/guidance"
    ]["$ref"] == (
        "./paths/customer-inquiries.yaml"
        "#/~1me~1inquiries~1{inquiry_id}~1guidance"
    )
    questions_schema = load_yaml(
        INQUIRY_SCHEMA_DIR / "CustomerInquiryQuestions.yaml"
    )
    snapshot_schema = load_yaml(
        INQUIRY_SCHEMA_DIR / "CustomerInquirySnapshot.yaml"
    )
    guidance_schema = load_yaml(
        INQUIRY_SCHEMA_DIR / "CustomerInquiryGuidance.yaml"
    )
    assert "allowed_actions" in snapshot_schema["required"]
    assert snapshot_schema["properties"]["allowed_actions"] == {
        "type": "array",
        "description": (
            "최신 문의·질문 Snapshot에 대해 Backend 동적 Resolver가 "
            "계산한 현재 호출 가능 Action"
        ),
        "items": {"$ref": "../workflow/AllowedAction.yaml"},
    }
    question_item = questions_schema["properties"]["questions"]["items"]
    assert guidance_schema["additionalProperties"] is False
    assert guidance_schema["properties"]["evidence"]["maxItems"] == 0
    assert guidance_schema["properties"]["safe_actions"]["minItems"] == 1
    assert set(guidance_schema["required"]) == set(
        guidance_schema["properties"]
    )
    assert "required" in question_item["required"]
    assert question_item["properties"]["required"] == {
        "type": "boolean",
        "enum": [True],
        "description": "현재 공개되는 추가 질문은 모두 답변 필수 항목이다.",
    }


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
    assert operation["x-ai-dispatch"] == {
        "boundary": "AFTER_SUCCESSFUL_COMMIT",
        "mechanism": "DJANGO_TRANSACTION_ON_COMMIT",
        "response_snapshot": "COMMIT_TIME_ONLY",
        "response_includes_ai_result": False,
        "idempotency_replay_dispatches": False,
    }
    description = operation["description"]
    assert "on_commit" in description
    assert "AI 결과나 추가 질문 생성 완료를 보장하지 않는다" in description
    assert request_schema["x-contract-status"] == "CONFIRMED"
    assert request_schema["required"] == ["state_version"]
    assert set(request_schema["properties"]) == {"state_version"}
    assert result_schema["x-contract-status"] == "CONFIRMED"
    assert result_schema["properties"]["state"]["const"] == (
        "QUESTIONNAIRE_IN_PROGRESS"
    )
