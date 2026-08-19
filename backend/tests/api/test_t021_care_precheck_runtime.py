"""T-021 CARE_PRECHECK API, lifecycle, replay, and inquiry-link tests."""

from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
import yaml
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.questionnaires.models import QuestionnaireSession
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory


pytestmark = pytest.mark.django_db
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
QUESTIONNAIRE_PATH = (
    REPOSITORY_ROOT / "contracts" / "api" / "paths" / "questionnaires.yaml"
)


def create_customer(sequence: int, *, role: str = User.Role.CUSTOMER) -> User:
    user = User.objects.create_user(
        username=f"T021-{role}-{sequence:03d}",
        password=None,
        full_name=f"T021 {role} {sequence}",
        role_code=role,
        employee_no=(
            None if role == User.Role.CUSTOMER else f"T021-EMP-{sequence:03d}"
        ),
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"T021-CUS-{sequence:03d}",
            customer_name=f"T021 customer {sequence}",
        )
    return user


def create_subscription(
    owner: User,
    sequence: int,
    *,
    status_code: str = CustomerSubscription.Status.ACTIVE,
) -> CustomerSubscription:
    product = ProductModel.objects.create(
        model_code=f"T021-PMD-{sequence:03d}",
        model_name=f"T021 product {sequence}",
    )
    return CustomerSubscription.objects.create(
        contract_no=f"T021-SUB-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"T021-SERIAL-{sequence:03d}",
        status_code=status_code,
        started_on=date(2026, 8, 1),
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def start_session(
    client: APIClient,
    subscription: CustomerSubscription,
    *,
    key: str = "t021-start",
):
    return client.post(
        "/api/v1/me/questionnaire-sessions",
        {"subscription_id": str(subscription.public_id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def save_session(
    client: APIClient,
    session_id: str,
    *,
    state_version: int,
    answers: dict,
    key: str,
):
    return client.patch(
        f"/api/v1/me/questionnaire-sessions/{session_id}",
        {"state_version": state_version, "answers": answers},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def submit_session(
    client: APIClient,
    session_id: str,
    *,
    state_version: int,
    answers: dict,
    key: str,
):
    return client.post(
        f"/api/v1/me/questionnaire-sessions/{session_id}/submit",
        {"state_version": state_version, "answers": answers},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def inquiry_body(
    subscription: CustomerSubscription,
    session_id: str,
) -> dict:
    return {
        "subscription_id": str(subscription.public_id),
        "channel_code": "MOBILE",
        "raw_text": "사전 문진 결과 증상 상담이 필요합니다.",
        "representative_symptom_code": "LOW_FLOW",
        "questionnaire_session_id": session_id,
    }


def test_start_creates_unanswered_session_without_inquiry_and_recovers_it():
    owner = create_customer(1)
    subscription = create_subscription(owner, 1)
    client = authenticated_client(owner)

    response = start_session(client, subscription)

    assert response.status_code == 201
    data = response.json()["data"]
    assert UUID(data["questionnaire_session_id"])
    assert data["subscription_id"] == str(subscription.public_id)
    assert data["questionnaire_type_code"] == "CARE_PRECHECK"
    assert data["questionnaire_version"] == "CARE_PRECHECK-v1"
    assert data["status_code"] == "UNANSWERED"
    assert data["state_version"] == 1
    assert data["answers"] == {}
    assert data["submitted_at"] is None
    assert data["linked_inquiry_id"] is None
    assert data["idempotent_replay"] is False
    assert Inquiry.objects.count() == 0

    session = QuestionnaireSession.objects.get(
        public_id=data["questionnaire_session_id"]
    )
    history = TransitionHistory.objects.get(questionnaire_session=session)
    assert history.event_code == "START_CARE_PRECHECK"
    assert history.from_state is None
    assert history.to_state == "UNANSWERED"
    assert history.state_version == 1
    assert history.actor == owner

    recovered = client.get(
        f"/api/v1/me/questionnaire-sessions/{session.public_id}"
    )
    assert recovered.status_code == 200
    assert recovered.json()["data"]["questionnaire_session_id"] == str(
        session.public_id
    )
    assert "idempotent_replay" not in recovered.json()["data"]


def test_start_replay_and_same_key_conflict_do_not_duplicate():
    owner = create_customer(2)
    first_subscription = create_subscription(owner, 2)
    second_subscription = create_subscription(owner, 3)
    client = authenticated_client(owner)

    first = start_session(client, first_subscription, key="t021-start-replay")
    replay = start_session(client, first_subscription, key="t021-start-replay")
    conflict = start_session(client, second_subscription, key="t021-start-replay")

    assert first.status_code == replay.status_code == 201
    assert replay.json()["data"]["idempotent_replay"] is True
    assert replay.json()["data"]["questionnaire_session_id"] == (
        first.json()["data"]["questionnaire_session_id"]
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    assert QuestionnaireSession.objects.count() == 1
    assert TransitionHistory.objects.count() == 1
    assert IdempotencyRecord.objects.count() == 1


def test_save_submit_and_replay_preserve_lifecycle_and_history():
    owner = create_customer(4)
    subscription = create_subscription(owner, 4)
    client = authenticated_client(owner)
    started = start_session(client, subscription, key="t021-lifecycle-start")
    session_id = started.json()["data"]["questionnaire_session_id"]

    saved = save_session(
        client,
        session_id,
        state_version=1,
        answers={"WATER_FLOW": "LOW", "LEAK": False},
        key="t021-save",
    )
    saved_replay = save_session(
        client,
        session_id,
        state_version=1,
        answers={"WATER_FLOW": "LOW", "LEAK": False},
        key="t021-save",
    )
    submitted = submit_session(
        client,
        session_id,
        state_version=2,
        answers={"WATER_FLOW": "LOW", "LEAK": False},
        key="t021-submit",
    )

    assert saved.status_code == saved_replay.status_code == 200
    assert saved.json()["data"]["status_code"] == "IN_PROGRESS"
    assert saved.json()["data"]["state_version"] == 2
    assert saved_replay.json()["data"]["idempotent_replay"] is True
    assert submitted.status_code == 200
    assert submitted.json()["data"]["status_code"] == "SUBMITTED"
    assert submitted.json()["data"]["state_version"] == 3
    assert submitted.json()["data"]["submitted_at"] is not None

    session = QuestionnaireSession.objects.get(public_id=session_id)
    assert session.answers_payload == {"WATER_FLOW": "LOW", "LEAK": False}
    assert list(
        session.transition_history.order_by("state_version").values_list(
            "event_code", "state_version"
        )
    ) == [
        ("START_CARE_PRECHECK", 1),
        ("SAVE_CARE_PRECHECK", 2),
        ("SUBMIT_CARE_PRECHECK", 3),
    ]


def test_stale_version_and_submitted_rewrite_return_current_snapshot():
    owner = create_customer(5)
    subscription = create_subscription(owner, 5)
    client = authenticated_client(owner)
    started = start_session(client, subscription, key="t021-stale-start")
    session_id = started.json()["data"]["questionnaire_session_id"]
    save_session(
        client,
        session_id,
        state_version=1,
        answers={"WATER_FLOW": "LOW"},
        key="t021-stale-save",
    )

    stale = save_session(
        client,
        session_id,
        state_version=1,
        answers={"WATER_FLOW": "NORMAL"},
        key="t021-stale-write",
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STATE-CONFLICT-01"
    assert stale.json()["error"]["details"] == {
        "current_status": "IN_PROGRESS",
        "current_state_version": 2,
    }
    assert not IdempotencyRecord.objects.filter(
        idempotency_key="t021-stale-write"
    ).exists()

    submit_session(
        client,
        session_id,
        state_version=2,
        answers={"WATER_FLOW": "LOW"},
        key="t021-stale-submit",
    )
    rewrite = save_session(
        client,
        session_id,
        state_version=3,
        answers={"WATER_FLOW": "NORMAL"},
        key="t021-after-submit",
    )
    assert rewrite.status_code == 409
    assert rewrite.json()["error"]["details"]["current_status"] == "SUBMITTED"


def test_owner_role_query_and_answer_validation_fail_closed():
    owner = create_customer(6)
    other = create_customer(7)
    consultant = create_customer(8, role=User.Role.CONSULTANT)
    subscription = create_subscription(owner, 6)
    client = authenticated_client(owner)
    started = start_session(client, subscription, key="t021-guard-start")
    session_id = started.json()["data"]["questionnaire_session_id"]

    assert authenticated_client(other).get(
        f"/api/v1/me/questionnaire-sessions/{session_id}"
    ).status_code == 404
    assert authenticated_client(consultant).post(
        "/api/v1/me/questionnaire-sessions",
        {"subscription_id": str(subscription.public_id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-consultant",
    ).status_code == 403
    assert APIClient().post(
        "/api/v1/me/questionnaire-sessions",
        {"subscription_id": str(subscription.public_id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-anonymous",
    ).status_code == 401

    unknown_query = client.get(
        f"/api/v1/me/questionnaire-sessions/{session_id}?debug=true"
    )
    empty_answers = save_session(
        client,
        session_id,
        state_version=1,
        answers={},
        key="t021-empty",
    )
    invalid_code = save_session(
        client,
        session_id,
        state_version=1,
        answers={"lower-case": "x"},
        key="t021-invalid-code",
    )
    nested = save_session(
        client,
        session_id,
        state_version=1,
        answers={"MULTI": [["x"]]},
        key="t021-nested",
    )
    for response in (unknown_query, empty_answers, invalid_code, nested):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert QuestionnaireSession.objects.get(public_id=session_id).state_version == 1


def test_submitted_session_links_to_exactly_one_new_inquiry_and_replays():
    owner = create_customer(9)
    subscription = create_subscription(owner, 9)
    client = authenticated_client(owner)
    started = start_session(client, subscription, key="t021-link-start")
    session_id = started.json()["data"]["questionnaire_session_id"]
    submit_session(
        client,
        session_id,
        state_version=1,
        answers={"WATER_FLOW": "LOW"},
        key="t021-link-submit",
    )
    body = inquiry_body(subscription, session_id)

    linked = client.post(
        "/api/v1/inquiries",
        body,
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-link-inquiry",
    )
    replay = client.post(
        "/api/v1/inquiries",
        body,
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-link-inquiry",
    )

    assert linked.status_code == replay.status_code == 201
    assert replay.json()["data"]["idempotent_replay"] is True
    inquiry = Inquiry.objects.get(public_id=linked.json()["data"]["inquiry_id"])
    session = QuestionnaireSession.objects.get(public_id=session_id)
    assert inquiry.questionnaire_session_public_id == session.public_id
    assert session.inquiry == inquiry
    assert session.linked_at is not None
    assert session.state_version == 3
    assert session.transition_history.get(state_version=3).event_code == "START_INQUIRY"
    assert Inquiry.objects.count() == 1

    second = client.post(
        "/api/v1/inquiries",
        body,
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-link-second-inquiry",
    )
    assert second.status_code == 409
    assert Inquiry.objects.count() == 1


def test_unsubmitted_other_owner_or_other_subscription_session_cannot_link():
    owner = create_customer(10)
    other = create_customer(11)
    subscription = create_subscription(owner, 10)
    other_subscription = create_subscription(owner, 11)
    foreign_subscription = create_subscription(other, 12)
    client = authenticated_client(owner)
    unsubmitted = start_session(client, subscription, key="t021-unsubmitted")
    unsubmitted_id = unsubmitted.json()["data"]["questionnaire_session_id"]

    unsubmitted_response = client.post(
        "/api/v1/inquiries",
        inquiry_body(subscription, unsubmitted_id),
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-unsubmitted-inquiry",
    )
    assert unsubmitted_response.status_code == 409

    other_client = authenticated_client(other)
    foreign = start_session(
        other_client,
        foreign_subscription,
        key="t021-foreign-start",
    )
    foreign_id = foreign.json()["data"]["questionnaire_session_id"]
    submit_session(
        other_client,
        foreign_id,
        state_version=1,
        answers={"WATER_FLOW": "LOW"},
        key="t021-foreign-submit",
    )
    foreign_response = client.post(
        "/api/v1/inquiries",
        inquiry_body(subscription, foreign_id),
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-foreign-inquiry",
    )
    assert foreign_response.status_code == 404

    own_other = start_session(
        client,
        other_subscription,
        key="t021-own-other-start",
    )
    own_other_id = own_other.json()["data"]["questionnaire_session_id"]
    submit_session(
        client,
        own_other_id,
        state_version=1,
        answers={"WATER_FLOW": "LOW"},
        key="t021-own-other-submit",
    )
    mismatch_response = client.post(
        "/api/v1/inquiries",
        inquiry_body(subscription, own_other_id),
        format="json",
        HTTP_IDEMPOTENCY_KEY="t021-mismatch-inquiry",
    )
    assert mismatch_response.status_code == 404
    assert Inquiry.objects.count() == 0


def test_start_rolls_back_session_and_idempotency_when_history_write_fails(
    monkeypatch,
):
    owner = create_customer(13)
    subscription = create_subscription(owner, 13)
    client = authenticated_client(owner)
    client.raise_request_exception = False

    def fail_history(**_kwargs):
        raise RuntimeError("synthetic history failure")

    monkeypatch.setattr(
        "apps.questionnaires.services.questionnaire_service."
        "TransitionHistoryService.record_questionnaire_action",
        fail_history,
    )
    response = start_session(client, subscription, key="t021-rollback")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert QuestionnaireSession.objects.count() == 0
    assert TransitionHistory.objects.count() == 0
    assert IdempotencyRecord.objects.count() == 0


def test_openapi_registers_runtime_paths_and_examples():
    openapi = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts" / "api" / "openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    paths = yaml.safe_load(QUESTIONNAIRE_PATH.read_text(encoding="utf-8"))

    assert openapi["paths"]["/me/questionnaire-sessions"]["$ref"].endswith(
        "questionnaires.yaml#/~1me~1questionnaire-sessions"
    )
    assert paths["/me/questionnaire-sessions"]["post"]["operationId"] == (
        "startCarePrecheck"
    )
    assert paths[
        "/me/questionnaire-sessions/{questionnaire_session_id}"
    ]["patch"]["operationId"] == "saveCarePrecheck"
    assert paths[
        "/me/questionnaire-sessions/{questionnaire_session_id}/submit"
    ]["post"]["operationId"] == "submitCarePrecheck"
    for external_value in _iter_values(paths, "externalValue"):
        assert (QUESTIONNAIRE_PATH.parent / external_value).resolve().is_file()


def _iter_values(value, key: str):
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            if item_key == key:
                yield item_value
            yield from _iter_values(item_value, key)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_values(item, key)
