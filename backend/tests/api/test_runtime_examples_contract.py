"""구현된 Runtime API의 JSON 예시와 OpenAPI 참조를 검증한다."""

from copy import deepcopy
import json
from pathlib import Path
import re
from uuid import UUID

import yaml

from apps.accounts.api.serializers import (
    AuthenticatedUserSerializer,
    DemoLoginRequestSerializer,
    RefreshTokenRequestSerializer,
)
from apps.inquiries.api.serializers import (
    CancelInquiryResponseSerializer,
    CancelInquirySerializer,
    CreateInquirySerializer,
    InquiryResponseSerializer,
    SubmitSymptomResponseSerializer,
    SymptomSubmissionSerializer,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_DIR = REPOSITORY_ROOT / "contracts" / "api"
EXAMPLES_DIR = API_DIR / "examples"

EXPECTED_JSON_FILES = {
    "auth/demo-login-request.json",
    "auth/demo-login-success-response.json",
    "auth/logout-request.json",
    "auth/logout-success-response.json",
    "auth/me-success-response.json",
    "auth/refresh-request.json",
    "auth/refresh-success-response.json",
    "errors/auth-required.json",
    "errors/body-validation-error.json",
    "errors/forbidden.json",
    "errors/idempotency-key-validation-error.json",
    "errors/internal-error.json",
    "errors/invalid-request.json",
    "errors/resource-not-found.json",
    "consultations/save-consultation-request.json",
    "care/create-replay.json",
    "care/create-success.json",
    "care/detail-success.json",
    "care/idempotency-conflict.json",
    "care/list-success.json",
    "care/validation-error.json",
    "inquiries/consultant-inquiry-detail-success.json",
    "inquiries/consultant-inquiry-list-success.json",
    "inquiries/customer-active-inquiry-empty.json",
    "inquiries/customer-active-inquiry-success.json",
    "inquiries/customer-timeout-snapshot-success.json",
    "inquiries/start-inquiry-replay-response.json",
    "inquiries/start-inquiry-request.json",
    "inquiries/start-inquiry-success-response.json",
    "inquiries/submit-symptom-replay-response.json",
    "inquiries/submit-symptom-request.json",
    "inquiries/submit-symptom-success-response.json",
    "subscriptions/detail-active-success.json",
    "subscriptions/create-replay.json",
    "subscriptions/create-success.json",
    "subscriptions/duplicate-active-error.json",
    "subscriptions/list-active-success.json",
    "subscriptions/list-empty-success.json",
    "subscriptions/query-validation-error.json",
    "subscriptions/unsupported-product-error.json",
    "subscriptions/update-success.json",
    "visits/create-visit-request.json",
    "visits/complete-visit-request.json",
    "visits/complete-visit-success-response.json",
    "visits/start-visit-request.json",
    "visits/start-visit-success-response.json",
    "visits/update-visit-schedule-request.json",
    "workflow/cancel-inquiry-replay-response.json",
    "workflow/cancel-inquiry-request.json",
    "workflow/cancel-inquiry-success-response.json",
    "workflow/idempotency-key-reuse-conflict.json",
    "workflow/finalize-inquiry-request.json",
    "workflow/finalize-inquiry-success-response.json",
    "workflow/report-unresolved-request.json",
    "workflow/report-unresolved-success-response.json",
    "workflow/request-consultation-request.json",
    "workflow/request-consultation-success-response.json",
    "workflow/resolution-feedback-request.json",
    "workflow/resolution-feedback-success-response.json",
    "workflow/resume-consultation-request.json",
    "workflow/resume-consultation-success-response.json",
    "workflow/state-version-conflict.json",
    "workflow/submit-followup-answers-request.json",
    "workflow/submit-followup-answers-success-response.json",
}


def load_json(relative_path: str):
    return json.loads(
        (EXAMPLES_DIR / relative_path).read_text(encoding="utf-8")
    )


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def collect_external_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "externalValue":
                yield item
            else:
                yield from collect_external_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from collect_external_values(item)


def test_json_example_allowlist_and_parseability():
    actual_files = {
        path.relative_to(EXAMPLES_DIR).as_posix()
        for path in EXAMPLES_DIR.rglob("*.json")
    }

    assert actual_files == EXPECTED_JSON_FILES
    for relative_path in actual_files:
        assert load_json(relative_path) is not None


def test_response_examples_use_exact_wrapper_and_uuid_metadata():
    request_files = {
        path for path in EXPECTED_JSON_FILES if path.endswith("-request.json")
    }
    response_files = EXPECTED_JSON_FILES - request_files

    for relative_path in response_files:
        payload = load_json(relative_path)

        assert set(payload) == {
            "success",
            "data",
            "error",
            "metadata",
        }
        UUID(payload["metadata"]["correlation_id"])
        if payload["success"]:
            assert payload["data"] is not None
            assert payload["error"] is None
        else:
            assert payload["data"] is None
            assert set(payload["error"]) == {
                "code",
                "message",
                "details",
            }


def test_request_and_response_examples_match_runtime_serializers():
    login_request = load_json("auth/demo-login-request.json")
    refresh_request = load_json("auth/refresh-request.json")
    logout_request = load_json("auth/logout-request.json")
    start_request = load_json("inquiries/start-inquiry-request.json")
    cancel_request = load_json("workflow/cancel-inquiry-request.json")
    submit_request = load_json("inquiries/submit-symptom-request.json")

    request_serializers = (
        DemoLoginRequestSerializer(data=login_request),
        RefreshTokenRequestSerializer(data=refresh_request),
        RefreshTokenRequestSerializer(data=logout_request),
        CreateInquirySerializer(data=start_request),
        CancelInquirySerializer(data=cancel_request),
        SymptomSubmissionSerializer(data=submit_request),
    )
    for serializer in request_serializers:
        assert serializer.is_valid(), serializer.errors

    demo_data = load_json("auth/demo-login-success-response.json")["data"]
    me_data = load_json("auth/me-success-response.json")["data"]
    start_data = load_json(
        "inquiries/start-inquiry-success-response.json"
    )["data"]
    cancel_data = load_json(
        "workflow/cancel-inquiry-success-response.json"
    )["data"]
    submit_data = load_json(
        "inquiries/submit-symptom-success-response.json"
    )["data"]

    assert AuthenticatedUserSerializer(data=demo_data["user"]).is_valid()
    assert AuthenticatedUserSerializer(data=me_data).is_valid()
    assert InquiryResponseSerializer(data=start_data).is_valid()
    assert CancelInquiryResponseSerializer(data=cancel_data).is_valid()
    assert SubmitSymptomResponseSerializer(data=submit_data).is_valid()


def test_auth_tokens_are_explicit_non_secret_placeholders():
    demo = load_json("auth/demo-login-success-response.json")["data"]
    refresh = load_json("auth/refresh-success-response.json")["data"]
    refresh_request = load_json("auth/refresh-request.json")
    logout_request = load_json("auth/logout-request.json")

    assert demo["access_token"] == (
        "EXAMPLE_ACCESS_TOKEN_NOT_FOR_AUTHENTICATION"
    )
    assert demo["refresh_token"] == (
        "EXAMPLE_REFRESH_TOKEN_NOT_FOR_AUTHENTICATION"
    )
    assert refresh["access_token"] == (
        "EXAMPLE_ROTATED_ACCESS_TOKEN_NOT_FOR_AUTHENTICATION"
    )
    assert refresh["refresh_token"] == (
        "EXAMPLE_ROTATED_REFRESH_TOKEN_NOT_FOR_AUTHENTICATION"
    )
    assert refresh_request == logout_request == {
        "refresh_token": "REPLACE_WITH_REFRESH_TOKEN_FROM_DEMO_LOGIN"
    }

    jwt_pattern = re.compile(
        r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"
    )
    for path in EXAMPLES_DIR.rglob("*.json"):
        assert jwt_pattern.search(path.read_text(encoding="utf-8")) is None


def test_replay_examples_only_change_replay_flag_in_response_data():
    pairs = (
        (
            "inquiries/start-inquiry-success-response.json",
            "inquiries/start-inquiry-replay-response.json",
        ),
        (
            "workflow/cancel-inquiry-success-response.json",
            "workflow/cancel-inquiry-replay-response.json",
        ),
        (
            "inquiries/submit-symptom-success-response.json",
            "inquiries/submit-symptom-replay-response.json",
        ),
    )

    for success_path, replay_path in pairs:
        success = load_json(success_path)
        replay = load_json(replay_path)
        success_data = deepcopy(success["data"])
        replay_data = deepcopy(replay["data"])

        assert success_data.pop("idempotent_replay") is False
        assert replay_data.pop("idempotent_replay") is True
        assert success_data == replay_data
        assert (
            success["metadata"]["correlation_id"]
            != replay["metadata"]["correlation_id"]
        )


def test_start_allowed_actions_match_pm_state_contract():
    contract = load_yaml(
        REPOSITORY_ROOT / "contracts" / "state-machine"
        / "allowed-actions.yaml"
    )
    catalog = {
        item["code"]: item for item in contract["action_catalog"]
    }
    action_codes = [
        item["action"]
        for item in contract["state_role_actions"]["DRAFT"]["CUSTOMER"]
    ]
    expected = [catalog[code] for code in action_codes]
    actual = load_json(
        "inquiries/start-inquiry-success-response.json"
    )["data"]["allowed_actions"]

    assert action_codes == ["SUBMIT_SYMPTOM", "CANCEL_INQUIRY"]
    assert actual == expected


def test_submit_example_applies_dynamic_open_question_guard():
    contract = load_yaml(
        REPOSITORY_ROOT / "contracts" / "state-machine"
        / "allowed-actions.yaml"
    )
    catalog = {
        item["code"]: item for item in contract["action_catalog"]
    }
    action_codes = [
        item["action"]
        for item in contract["state_role_actions"]
        ["QUESTIONNAIRE_IN_PROGRESS"]["CUSTOMER"]
    ]
    expected = [catalog["CANCEL_INQUIRY"]]
    actual = load_json(
        "inquiries/submit-symptom-success-response.json"
    )["data"]["allowed_actions"]

    assert action_codes == ["SUBMIT_ANSWERS", "CANCEL_INQUIRY"]
    assert actual == expected


def test_error_examples_use_registered_codes_and_messages():
    registry = load_yaml(
        REPOSITORY_ROOT / "contracts" / "error-codes"
        / "error-codes.yaml"
    )
    registered = {
        item["code"]: item for item in registry["errors"]
    }
    error_files = {
        path
        for path in EXPECTED_JSON_FILES
        if path.startswith("errors/")
        or path.endswith("-conflict.json")
    }

    for relative_path in error_files:
        error = load_json(relative_path)["error"]
        entry = registered[error["code"]]
        assert error["message"] == entry["user_message"]


def test_every_json_is_referenced_by_a_resolvable_external_value():
    referenced_files = set()

    for yaml_path in API_DIR.rglob("*.yaml"):
        contract = load_yaml(yaml_path)
        for external_value in collect_external_values(contract):
            target = (yaml_path.parent / external_value).resolve()
            assert target.is_relative_to(EXAMPLES_DIR.resolve())
            assert target.is_file()
            referenced_files.add(
                target.relative_to(EXAMPLES_DIR.resolve()).as_posix()
            )

    assert referenced_files == EXPECTED_JSON_FILES


def test_action_results_and_week5_runtime_statuses_are_explicit():
    inquiry_paths = load_yaml(API_DIR / "paths" / "inquiries.yaml")
    workflow_paths = load_yaml(API_DIR / "paths" / "workflow.yaml")
    visit_paths = load_yaml(API_DIR / "paths" / "visits.yaml")
    openapi = load_yaml(API_DIR / "openapi.yaml")

    for path in ("/inquiries/{id}/action-results",):
        assert list(collect_external_values(inquiry_paths[path])) == []
    implemented = {
        "/inquiries/{id}/resolution-feedback": workflow_paths,
        "/inquiries/{id}/finalize": workflow_paths,
        "/inquiries/{id}/report-unresolved": workflow_paths,
        "/inquiries/{id}/resume-consultation": workflow_paths,
    }
    for path, document in implemented.items():
        assert document[path]["post"]["x-runtime-status"] == "IMPLEMENTED"
    pending = {
        "/visits/{visit_id}/start": visit_paths,
        "/visits/{visit_id}/complete": visit_paths,
    }
    for path, document in pending.items():
        assert document[path]["post"]["x-runtime-status"] == (
            "NOT_IMPLEMENTED"
        )
    assert workflow_paths["/inquiries/{id}/answers"]["post"][
        "x-runtime-status"
    ] == "IMPLEMENTED"
    assert workflow_paths["/inquiries/{id}/request-consultation"][
        "post"
    ]["x-runtime-status"] == "IMPLEMENTED"
    assert list(collect_external_values(openapi["paths"]["/health"])) == []
