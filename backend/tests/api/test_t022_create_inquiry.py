"""End-to-end API and OpenAPI checks for T-022 START_INQUIRY."""

from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
import yaml
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory


pytestmark = pytest.mark.django_db
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INQUIRY_PATH = (
    REPOSITORY_ROOT / "contracts" / "api" / "paths" / "inquiries.yaml"
)
CREATE_REQUEST_SCHEMA = (
    REPOSITORY_ROOT
    / "contracts"
    / "api"
    / "components"
    / "schemas"
    / "inquiry"
    / "CreateInquiryRequest.yaml"
)
CREATE_RESULT_SCHEMA = CREATE_REQUEST_SCHEMA.with_name(
    "CreateInquiryResult.yaml"
)


def create_customer(sequence: int, *, role: str = "CUSTOMER") -> User:
    employee_no = (
        None
        if role == User.Role.CUSTOMER
        else f"T022-API-EMP-{sequence:03d}"
    )
    user = User.objects.create_user(
        username=f"T022-API-{role}-{sequence:03d}",
        password=None,
        full_name=f"T022 API {role} {sequence}",
        role_code=role,
        employee_no=employee_no,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"T022-API-CUS-{sequence:03d}",
            customer_name=f"T022 API customer {sequence}",
        )
    return user


def create_subscription(
    owner: User,
    sequence: int,
    *,
    status_code: str = CustomerSubscription.Status.ACTIVE,
) -> CustomerSubscription:
    product = ProductModel.objects.create(
        model_code=f"T022-API-PMD-{sequence:03d}",
        model_name=f"T022 API product {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"T022-API-SUB-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"T022-API-SERIAL-{sequence:03d}",
        status_code=status_code,
        started_on=date(2026, 7, 1),
        ended_on=(
            date(2026, 7, 20)
            if status_code
            in {
                CustomerSubscription.Status.CANCELLED,
                CustomerSubscription.Status.EXPIRED,
            }
            else None
        ),
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def request_body(subscription: CustomerSubscription) -> dict:
    return {
        "subscription_id": str(subscription.public_id),
        "channel_code": "WEB",
        "raw_text": "  Water flow is lower than usual.  ",
        "representative_symptom_code": "LOW_FLOW",
    }


def post_create(
    client: APIClient,
    body: dict,
    *,
    key: str | None = "t022-create-key",
):
    headers = (
        {"HTTP_IDEMPOTENCY_KEY": key}
        if key is not None
        else {}
    )
    return client.post(
        "/api/v1/inquiries",
        body,
        format="json",
        **headers,
    )


def iter_contract_values(value, key: str):
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            if item_key == key:
                yield item_value
            yield from iter_contract_values(item_value, key)
    elif isinstance(value, list):
        for item in value:
            yield from iter_contract_values(item, key)


def assert_external_references_exist(
    document_path: Path,
    *,
    visited: set[Path] | None = None,
) -> None:
    visited = set() if visited is None else visited
    resolved_path = document_path.resolve()
    if resolved_path in visited:
        return
    visited.add(resolved_path)

    document = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    for reference in iter_contract_values(document, "$ref"):
        external_path = str(reference).partition("#")[0]
        if not external_path:
            continue
        target = (resolved_path.parent / external_path).resolve()
        assert target.is_file(), f"Missing OpenAPI reference: {target}"
        if target.suffix.lower() in {".yaml", ".yml"}:
            assert_external_references_exist(target, visited=visited)

    for external_value in iter_contract_values(document, "externalValue"):
        target = (resolved_path.parent / str(external_value)).resolve()
        assert target.is_file(), f"Missing OpenAPI example: {target}"


def test_create_inquiry_returns_public_three_layer_result_and_history():
    owner = create_customer(1)
    subscription = create_subscription(owner, 1)

    response = post_create(
        authenticated_client(owner),
        request_body(subscription),
    )

    assert response.status_code == 201
    payload = response.json()
    data = payload["data"]
    assert payload["success"] is True
    assert payload["error"] is None
    assert UUID(data["inquiry_id"])
    assert set(data) == {
        "inquiry_id",
        "inquiry_code",
        "status_code",
        "state_version",
        "idempotent_replay",
        "allowed_actions",
    }
    assert data["inquiry_code"].startswith("INQ-")
    assert data["status_code"] == "DRAFT"
    assert data["state_version"] == 1
    assert data["idempotent_replay"] is False
    assert [item["code"] for item in data["allowed_actions"]] == [
        "SUBMIT_SYMPTOM",
        "CANCEL_INQUIRY",
    ]

    inquiry = Inquiry.objects.get(public_id=data["inquiry_id"])
    assert isinstance(inquiry.pk, int)
    assert inquiry.inquiry_code == data["inquiry_code"]
    assert inquiry.subscription == subscription
    assert inquiry.initiated_by == owner
    assert inquiry.raw_text == "Water flow is lower than usual."

    symptom = SymptomEntry.objects.get(inquiry=inquiry)
    assert symptom.symptom_type_code == "LOW_FLOW"
    assert symptom.structured_payload == {
        "representative_symptom_code": "LOW_FLOW",
    }

    history = TransitionHistory.objects.get(inquiry=inquiry)
    assert history.event_code == "START_INQUIRY"
    assert history.from_state is None
    assert history.to_state == "DRAFT"
    assert history.state_version == 1
    assert history.actor == owner
    assert str(history.correlation_id) == payload["metadata"][
        "correlation_id"
    ]

    idempotency = IdempotencyRecord.objects.get(
        actor=owner,
        operation_id="startInquiry",
        idempotency_key="t022-create-key",
    )
    assert idempotency.completed_at is not None
    assert idempotency.response_status == 201
    assert idempotency.resource_public_id == inquiry.public_id
    assert "id" not in idempotency.response_body


def test_same_key_and_payload_replays_without_duplicate_side_effects():
    owner = create_customer(2)
    subscription = create_subscription(owner, 2)
    client = authenticated_client(owner)
    body = request_body(subscription)

    first = post_create(client, body, key="t022-replay-key")
    second = post_create(
        client,
        {
            **body,
            "raw_text": "Water flow is lower than usual.",
        },
        key="t022-replay-key",
    )

    assert first.status_code == second.status_code == 201
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["idempotent_replay"] is False
    assert second_data["idempotent_replay"] is True
    assert second_data["inquiry_id"] == first_data["inquiry_id"]
    assert second_data["inquiry_code"] == first_data["inquiry_code"]
    assert second_data["allowed_actions"] == first_data["allowed_actions"]
    assert Inquiry.objects.count() == 1
    assert SymptomEntry.objects.count() == 1
    assert TransitionHistory.objects.count() == 1
    assert IdempotencyRecord.objects.count() == 1


def test_same_key_with_different_payload_returns_public_duplicate_conflict():
    owner = create_customer(3)
    subscription = create_subscription(owner, 3)
    client = authenticated_client(owner)
    body = request_body(subscription)

    first = post_create(client, body, key="t022-conflict-key")
    second = post_create(
        client,
        {
            **body,
            "raw_text": "A different symptom description.",
        },
        key="t022-conflict-key",
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    assert Inquiry.objects.count() == 1
    assert TransitionHistory.objects.count() == 1


def test_owner_scope_hides_other_or_inactive_subscription():
    owner = create_customer(4)
    other_owner = create_customer(5)
    other_subscription = create_subscription(other_owner, 4)
    inactive_subscription = create_subscription(
        owner,
        5,
        status_code=CustomerSubscription.Status.SUSPENDED,
    )
    client = authenticated_client(owner)

    other_response = post_create(
        client,
        request_body(other_subscription),
        key="t022-other-owner",
    )
    inactive_response = post_create(
        client,
        request_body(inactive_subscription),
        key="t022-inactive",
    )

    assert other_response.status_code == 404
    assert inactive_response.status_code == 404
    assert other_response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert inactive_response.json()["error"]["code"] == (
        "RESOURCE_NOT_FOUND"
    )
    assert Inquiry.objects.count() == 0


def test_non_customer_is_forbidden_before_resource_lookup():
    owner = create_customer(6)
    subscription = create_subscription(owner, 6)
    consultant = create_customer(7, role=User.Role.CONSULTANT)

    response = post_create(
        authenticated_client(consultant),
        request_body(subscription),
        key="t022-role",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert Inquiry.objects.count() == 0


def test_header_and_body_validation_fail_without_side_effects():
    owner = create_customer(8)
    subscription = create_subscription(owner, 8)
    client = authenticated_client(owner)

    missing_header = post_create(
        client,
        request_body(subscription),
        key=None,
    )
    missing_body = post_create(
        client,
        {
            "channel_code": "WEB",
            "raw_text": "Valid text",
        },
        key="t022-missing-body",
    )
    invalid_uuid = post_create(
        client,
        {
            **request_body(subscription),
            "subscription_id": "not-a-uuid",
        },
        key="t022-invalid-uuid",
    )

    assert missing_header.status_code == 422
    assert missing_body.status_code == 422
    assert invalid_uuid.status_code == 422
    assert missing_header.json()["error"]["code"] == "VALIDATION_ERROR"
    assert missing_body.json()["error"]["code"] == "VALIDATION_ERROR"
    assert invalid_uuid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert Inquiry.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


def test_representative_symptom_is_optional():
    owner = create_customer(9)
    subscription = create_subscription(owner, 9)
    body = request_body(subscription)
    body.pop("representative_symptom_code")

    response = post_create(
        authenticated_client(owner),
        body,
        key="t022-no-symptom",
    )

    assert response.status_code == 201
    assert Inquiry.objects.count() == 1
    assert SymptomEntry.objects.count() == 0


def test_openapi_create_inquiry_matches_start_inquiry_contract():
    path_document = yaml.safe_load(INQUIRY_PATH.read_text(encoding="utf-8"))
    operation = path_document["/inquiries"]["post"]
    request_schema = yaml.safe_load(
        CREATE_REQUEST_SCHEMA.read_text(encoding="utf-8")
    )
    result_schema = yaml.safe_load(
        CREATE_RESULT_SCHEMA.read_text(encoding="utf-8")
    )

    assert operation["operationId"] == "startInquiry"
    assert operation["parameters"] == [
        {
            "$ref": (
                "../components/parameters/IdempotencyKey.yaml"
            )
        }
    ]
    assert operation["x-state-machine"] == {
        "event": "START_INQUIRY",
        "operation_id": "startInquiry",
        "transition_rule": "TR-INQ-001",
        "from_state": None,
        "to_state": "DRAFT",
        "actor_role": "CUSTOMER",
    }
    assert request_schema["properties"]["subscription_id"] == {
        "type": "string",
        "format": "uuid",
        "description": "인증 고객 본인의 ACTIVE 구독 공개 UUID",
    }
    assert operation["responses"]["201"]["content"][
        "application/json"
    ]["schema"]["allOf"][1]["properties"]["data"]["$ref"].endswith(
        "CreateInquiryResult.yaml"
    )
    assert operation["responses"]["409"]["$ref"].endswith(
        "WorkflowConflict.yaml"
    )
    assert "404" in operation["responses"]
    assert "422" in operation["responses"]
    assert result_schema["required"] == [
        "inquiry_id",
        "inquiry_code",
        "status_code",
        "state_version",
        "idempotent_replay",
        "allowed_actions",
    ]
    assert result_schema["properties"]["inquiry_id"]["format"] == "uuid"
    assert result_schema["properties"]["status_code"]["const"] == "DRAFT"
    assert result_schema["properties"]["state_version"]["const"] == 1


def test_openapi_create_inquiry_external_references_are_resolvable():
    assert_external_references_exist(INQUIRY_PATH)
