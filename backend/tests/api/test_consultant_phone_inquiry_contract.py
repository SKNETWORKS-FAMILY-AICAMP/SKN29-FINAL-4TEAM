"""CR-001 OpenAPI and State Machine contract tests."""

from pathlib import Path

from jsonschema import Draft202012Validator
import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_DIR = REPOSITORY_ROOT / "contracts" / "api"
STATE_DIR = REPOSITORY_ROOT / "contracts" / "state-machine"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_phone_inquiry_operations_are_confirmed_implemented_and_role_split():
    root = load_yaml(API_DIR / "openapi.yaml")
    contract = load_yaml(
        API_DIR / "paths" / "consultant-phone-inquiries.yaml"
    )
    assert root["info"]["version"] == "0.9.0"
    assert root["paths"]["/consultant/customer-subscriptions/search"] == {
        "$ref": (
            "./paths/consultant-phone-inquiries.yaml#/~1consultant"
            "~1customer-subscriptions~1search"
        )
    }
    assert root["paths"]["/consultant/phone-inquiries"] == {
        "$ref": (
            "./paths/consultant-phone-inquiries.yaml#/~1consultant"
            "~1phone-inquiries"
        )
    }
    search = contract["/consultant/customer-subscriptions/search"]["post"]
    register = contract["/consultant/phone-inquiries"]["post"]
    assert search["operationId"] == "searchConsultantCustomerSubscriptions"
    assert register["operationId"] == "registerConsultantPhoneInquiry"
    assert search["x-contract-status"] == register["x-contract-status"] == "CONFIRMED"
    assert search["x-runtime-status"] == register["x-runtime-status"] == "IMPLEMENTED"
    assert register["x-state-machine"] == {
        "event": "REGISTER_PHONE_INQUIRY",
        "transition_rule": "TR-INQ-035",
        "from_state": None,
        "to_state": "CONSULTATION_REQUIRED",
        "actor_role": "CONSULTANT",
    }

    existing = load_yaml(API_DIR / "paths" / "inquiries.yaml")
    assert existing["/inquiries"]["post"]["operationId"] == "startInquiry"
    assert existing["/inquiries"]["post"]["x-state-machine"]["actor_role"] == "CUSTOMER"


def test_phone_inquiry_schemas_close_public_fields_and_validate_examples():
    search_request = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "inquiry"
        / "ConsultantCustomerSubscriptionSearchRequest.yaml"
    )
    register_request = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "inquiry"
        / "RegisterConsultantPhoneInquiryRequest.yaml"
    )
    search_result = load_yaml(
        API_DIR
        / "components"
        / "schemas"
        / "inquiry"
        / "ConsultantCustomerSubscriptionSearchResult.yaml"
    )

    assert search_request["additionalProperties"] is False
    assert register_request["additionalProperties"] is False
    assert set(register_request["required"]) == {
        "subscription_id",
        "raw_text",
        "representative_symptom_code",
        "priority_code",
    }
    item = search_result["properties"]["items"]["items"]
    assert item["additionalProperties"] is False
    assert "phone" not in item["properties"]
    assert "phone_masked" in item["properties"]

    validator = Draft202012Validator(register_request)
    valid = {
        "subscription_id": "00000000-0000-4000-8000-000000000001",
        "raw_text": "전화 접수 누수 문의",
        "representative_symptom_code": "LEAK",
        "priority_code": "HIGH",
    }
    assert list(validator.iter_errors(valid)) == []
    assert list(validator.iter_errors(dict(valid, priority_code="P0")))
    assert list(validator.iter_errors(dict(valid, customer_name="unsafe")))


def test_phone_inquiry_event_transition_guard_and_role_are_consistent():
    events = load_yaml(STATE_DIR / "inquiry-events.yaml")["events"]
    transitions = load_yaml(STATE_DIR / "transition-rules.yaml")["transitions"]
    guards = load_yaml(STATE_DIR / "transition-guards.yaml")["guards"]
    roles = load_yaml(STATE_DIR / "role-permissions.yaml")["roles"]

    event = next(item for item in events if item["code"] == "REGISTER_PHONE_INQUIRY")
    transition = next(item for item in transitions if item["id"] == "TR-INQ-035")
    guard = next(
        item
        for item in guards
        if item["id"] == "G-CONSULTANT-PHONE-SUBSCRIPTION"
    )
    consultant = next(item for item in roles if item["code"] == "CONSULTANT")

    assert event["actor_roles"] == ["CONSULTANT"]
    assert event["external_action"] == {
        "exposed": True,
        "operation_id": "registerConsultantPhoneInquiry",
    }
    assert transition["event"] == event["code"]
    assert transition["from_inquiry_state"] is None
    assert transition["to_inquiry_state"] == "CONSULTATION_REQUIRED"
    assert transition["version_action"] == "INITIALIZE_1"
    assert transition["guard_refs"] == [
        "G-ACTOR-CONSULTANT",
        "G-CONSULTANT-PHONE-SUBSCRIPTION",
        "G-IDEMPOTENCY-KEY",
    ]
    assert guard["failure"]["http_status"] == 404
    assert "REGISTER_PHONE_INQUIRY" in consultant["allowed_events"]
    assert "SYNTHETIC_ACTIVE_CUSTOMER_SUBSCRIPTIONS" in consultant["resource_scope"]
