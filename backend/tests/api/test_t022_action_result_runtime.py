"""Runtime tests for the T-022 customer action-result append Slice."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inquiries.models import (
    CustomerActionResult,
    Guidance,
    GuidanceItem,
    Inquiry,
)
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from tests.api.test_t022_submit_symptom import (
    authenticated_client,
    create_inquiry,
    create_user,
)


pytestmark = pytest.mark.django_db


def prepare_guidance(sequence: int):
    owner = create_user(sequence)
    client, inquiry, _subscription = create_inquiry(owner, sequence)
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.AI_GUIDANCE,
        state_version=3,
    )
    inquiry.refresh_from_db()
    guidance = Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=1,
        review_status_code="PENDING",
        title="검증된 고객 안내",
        summary_text="안내된 조치를 수행해 주세요.",
        evidence_sufficiency_code="SUFFICIENT",
        requires_consultation=False,
    )
    item = GuidanceItem.objects.create(
        guidance=guidance,
        step_no=1,
        action_type_code="NEXT_ACTION",
        instruction_text="필터 상태를 확인해 주세요.",
        requires_confirmation=True,
    )
    return owner, client, inquiry, item


def post_result(
    client: APIClient,
    inquiry: Inquiry,
    body: dict,
    *,
    key: str | None,
):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key is not None else {}
    return client.post(
        f"/api/v1/inquiries/{inquiry.public_id}/action-results",
        body,
        format="json",
        **headers,
    )


def result_body(item: GuidanceItem, **overrides):
    body = {
        "guidance_item_id": str(item.public_id),
        "result_code": "NOT_PERFORMED",
        "result_text": "아직 수행하지 않았습니다.",
        "customer_comment": "다음 안내를 기다립니다.",
        "performed_at": None,
        "state_version": 3,
    }
    body.update(overrides)
    return body


def result_idempotency(owner: User):
    return IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="createInquiryActionResult",
    )


def test_action_result_appends_once_and_advances_only_aggregate_version():
    owner, client, inquiry, item = prepare_guidance(201)
    history_count = TransitionHistory.objects.filter(inquiry=inquiry).count()

    response = post_result(
        client,
        inquiry,
        result_body(item, result_code="FUTURE_APPROVED_CODE"),
        key="t022-action-success",
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert set(data) == {
        "id",
        "inquiry_id",
        "guidance_item_id",
        "attempt_no",
        "result_code",
        "result_text",
        "performed_at",
        "customer_comment",
        "submitted_by",
        "state_version",
        "idempotent_replay",
        "created_at",
    }
    assert data["inquiry_id"] == str(inquiry.public_id)
    assert data["guidance_item_id"] == str(item.public_id)
    assert data["result_code"] == "FUTURE_APPROVED_CODE"
    assert data["attempt_no"] == 1
    assert data["state_version"] == 4
    assert data["idempotent_replay"] is False
    assert data["submitted_by"] == str(owner.public_id)

    inquiry.refresh_from_db()
    saved = CustomerActionResult.objects.get()
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.state_version == 4
    assert saved.guidance_item == item
    assert saved.result_code == "FUTURE_APPROVED_CODE"
    assert saved.performed_at is None
    assert result_idempotency(owner).get().response_body == data
    assert (
        TransitionHistory.objects.filter(inquiry=inquiry).count()
        == history_count
    )


def test_same_key_replays_without_duplicate_result_or_version_change():
    owner, client, inquiry, item = prepare_guidance(202)
    body = result_body(item)

    first = post_result(client, inquiry, body, key="t022-action-replay")
    second = post_result(client, inquiry, body, key="t022-action-replay")

    assert first.status_code == second.status_code == 201
    assert first.json()["data"]["idempotent_replay"] is False
    assert second.json()["data"]["idempotent_replay"] is True
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    inquiry.refresh_from_db()
    assert inquiry.state_version == 4
    assert CustomerActionResult.objects.count() == 1
    assert result_idempotency(owner).count() == 1


def test_same_key_with_different_payload_returns_409_without_second_write():
    owner, client, inquiry, item = prepare_guidance(203)
    first = post_result(
        client,
        inquiry,
        result_body(item),
        key="t022-action-conflict",
    )
    conflict = post_result(
        client,
        inquiry,
        result_body(item, result_text="다른 요청"),
        key="t022-action-conflict",
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    inquiry.refresh_from_db()
    assert inquiry.state_version == 4
    assert CustomerActionResult.objects.count() == 1
    assert result_idempotency(owner).count() == 1


def test_stale_version_and_non_guidance_state_fail_closed():
    owner, client, inquiry, item = prepare_guidance(204)
    stale = post_result(
        client,
        inquiry,
        result_body(item, state_version=2),
        key="t022-action-stale",
    )
    Inquiry.objects.filter(pk=inquiry.pk).update(
        status_code=Inquiry.Status.CONSULTATION_REQUIRED,
    )
    invalid_state = post_result(
        client,
        inquiry,
        result_body(item),
        key="t022-action-invalid-state",
    )

    assert stale.status_code == invalid_state.status_code == 409
    assert stale.json()["error"]["code"] == "STATE-CONFLICT-01"
    assert invalid_state.json()["error"]["code"] == "STATE-CONFLICT-01"
    assert CustomerActionResult.objects.count() == 0
    assert result_idempotency(owner).count() == 0


def test_other_owner_and_other_inquiry_guidance_are_hidden_as_404():
    _owner, client, inquiry, item = prepare_guidance(205)
    other = create_user(206)
    other_client, other_inquiry, other_item = prepare_guidance(207)[1:]

    hidden_owner = authenticated_client(other).post(
        f"/api/v1/inquiries/{inquiry.public_id}/action-results",
        result_body(item),
        format="json",
        HTTP_IDEMPOTENCY_KEY="t022-action-hidden-owner",
    )
    hidden_item = post_result(
        client,
        inquiry,
        result_body(other_item),
        key="t022-action-hidden-item",
    )

    assert hidden_owner.status_code == hidden_item.status_code == 404
    assert hidden_owner.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert hidden_item.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert other_inquiry.public_id != inquiry.public_id
    assert CustomerActionResult.objects.count() == 0
    assert IdempotencyRecord.objects.filter(
        operation_id="createInquiryActionResult"
    ).count() == 0


@pytest.mark.parametrize(
    ("body", "key"),
    [
        ({"state_version": 3}, "t022-action-missing"),
        (
            {
                "guidance_item_id": "not-a-uuid",
                "result_code": "OK",
                "state_version": 3,
            },
            "t022-action-bad-id",
        ),
        (
            {
                "guidance_item_id": str(uuid4()),
                "result_code": "   ",
                "state_version": 3,
            },
            "t022-action-blank",
        ),
        (
            {
                "guidance_item_id": str(uuid4()),
                "result_code": "OK",
                "state_version": 3,
                "extra": True,
            },
            "t022-action-extra",
        ),
        (
            {
                "guidance_item_id": str(uuid4()),
                "result_code": "OK",
                "state_version": 3,
            },
            None,
        ),
    ],
)
def test_request_validation_has_no_side_effects(body, key):
    _owner, client, inquiry, _item = prepare_guidance(208)

    response = post_result(client, inquiry, body, key=key)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert CustomerActionResult.objects.count() == 0
    assert IdempotencyRecord.objects.filter(
        operation_id="createInquiryActionResult"
    ).count() == 0


def test_response_contract_failure_rolls_back_result_version_and_idempotency():
    owner, client, inquiry, item = prepare_guidance(209)

    with patch(
        "apps.inquiries.api.views.ActionResultResponseSerializer",
        side_effect=RuntimeError("forced response contract failure"),
    ):
        response = post_result(
            client,
            inquiry,
            result_body(item),
            key="t022-action-rollback",
        )

    assert response.status_code == 500
    inquiry.refresh_from_db()
    assert inquiry.state_version == 3
    assert CustomerActionResult.objects.count() == 0
    assert result_idempotency(owner).count() == 0
