"""Runtime tests for the CUSTOMER SUBMIT_ANSWERS vertical Slice."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inquiries.models import FollowUpAnswer, Inquiry, InquiryQA
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from tests.api.test_t022_submit_symptom import (
    authenticated_client,
    create_inquiry,
    create_user,
    post_submit,
)


pytestmark = pytest.mark.django_db


def prepare_questionnaire(sequence: int):
    owner = create_user(sequence)
    client, inquiry, _subscription = create_inquiry(owner, sequence)
    response = post_submit(
        client,
        inquiry,
        {"state_version": 1},
        key=f"t022a-submit-{sequence}",
    )
    assert response.status_code == 200
    inquiry.refresh_from_db()
    return owner, client, inquiry


def create_question(
    inquiry: Inquiry,
    sequence: int,
    *,
    answer_type: str = "FREE_TEXT",
    options: list[str] | None = None,
) -> InquiryQA:
    return InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=sequence,
        question_code=f"T022A-Q-{sequence:03d}",
        question_text=f"Question {sequence}",
        answer_type_code=answer_type,
        answer_payload=(
            {"question_options": options}
            if options
            else None
        ),
        asked_by_type_code="RULE",
    )


def post_answers(
    client: APIClient,
    inquiry: Inquiry,
    body: dict,
    *,
    key: str | None,
    correlation_id: str | None = "AUTO",
):
    headers = {"HTTP_IDEMPOTENCY_KEY": key} if key is not None else {}
    if correlation_id == "AUTO":
        correlation_id = str(uuid4())
    if correlation_id is not None:
        headers["HTTP_X_CORRELATION_ID"] = correlation_id
    return client.post(
        f"/api/v1/inquiries/{inquiry.public_id}/answers",
        body,
        format="json",
        **headers,
    )


def answer_history(inquiry: Inquiry):
    return TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="SUBMIT_ANSWERS",
    )


def answer_idempotency(owner: User):
    return IdempotencyRecord.objects.filter(
        actor=owner,
        operation_id="submitFollowUpAnswers",
    )


def test_text_and_choice_answers_are_appended_and_versioned_once():
    owner, client, inquiry = prepare_questionnaire(101)
    text_question = create_question(inquiry, 1)
    choice_question = create_question(
        inquiry,
        2,
        answer_type="SINGLE_CHOICE",
        options=["FILTER_REPLACEMENT", "OTHER"],
    )

    response = post_answers(
        client,
        inquiry,
        {
            "state_version": 2,
            "answers": [
                {
                    "question_id": str(text_question.public_id),
                    "answer_text": "  Two days ago.  ",
                },
                {
                    "question_id": str(choice_question.public_id),
                    "answer_payload": {
                        "selected_option": "FILTER_REPLACEMENT"
                    },
                },
            ],
        },
        key="t022a-success",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {
        "message",
        "inquiry_id",
        "status",
        "state_version",
        "allowed_actions",
        "idempotent_replay",
        "resource",
    }
    assert data["inquiry_id"] == str(inquiry.public_id)
    assert data["status"] == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert data["state_version"] == 3
    assert data["idempotent_replay"] is False
    assert data["resource"] is None
    assert [item["code"] for item in data["allowed_actions"]] == [
        "CANCEL_INQUIRY",
    ]

    inquiry.refresh_from_db()
    assert inquiry.state_version == 3
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert FollowUpAnswer.objects.count() == 2
    assert text_question.customer_answer.answer_text == "Two days ago."
    assert choice_question.customer_answer.answer_payload == {
        "selected_option": "FILTER_REPLACEMENT"
    }
    assert text_question.customer_answer.accepted_state_version == 2
    assert choice_question.customer_answer.accepted_state_version == 2
    assert text_question.question_options == []
    assert choice_question.question_options == [
        "FILTER_REPLACEMENT",
        "OTHER",
    ]
    history = answer_history(inquiry).get()
    assert history.from_state == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert history.to_state == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert history.state_version == 3
    assert history.actor == owner
    assert answer_idempotency(owner).get().response_body == data


def test_success_requests_ai_reevaluation_once_after_durable_commit(
    django_capture_on_commit_callbacks,
):
    owner, client, inquiry = prepare_questionnaire(109)
    question = create_question(inquiry, 1)
    correlation_id = str(uuid4())

    with patch(
        "apps.inquiries.services.inquiry_ai_service."
        "InquiryAIService.analyze_inquiry"
    ) as analyze:
        with django_capture_on_commit_callbacks(execute=True):
            response = post_answers(
                client,
                inquiry,
                {
                    "state_version": 2,
                    "answers": [
                        {
                            "question_id": str(question.public_id),
                            "answer_text": "Today.",
                        }
                    ],
                },
                key="t022a-ai-reevaluation",
                correlation_id=correlation_id,
            )
            analyze.assert_not_called()

    assert response.status_code == 200
    analyze.assert_called_once()
    kwargs = analyze.call_args.kwargs
    assert kwargs["inquiry_public_id"] == inquiry.public_id
    assert str(kwargs["correlation_id"]) == correlation_id
    assert kwargs["ai_request_id"] == answer_idempotency(owner).get().public_id


def test_same_key_replays_without_duplicate_answers_or_history(
    django_capture_on_commit_callbacks,
):
    owner, client, inquiry = prepare_questionnaire(102)
    question = create_question(inquiry, 1)
    body = {
        "state_version": 2,
        "answers": [
            {
                "question_id": str(question.public_id),
                "answer_text": "Today.",
            }
        ],
    }

    with patch(
        "apps.inquiries.services.inquiry_ai_service."
        "InquiryAIService.analyze_inquiry"
    ) as analyze:
        with django_capture_on_commit_callbacks(execute=True):
            first = post_answers(client, inquiry, body, key="t022a-replay")
            second = post_answers(client, inquiry, body, key="t022a-replay")
            analyze.assert_not_called()

    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["idempotent_replay"] is False
    assert second.json()["data"]["idempotent_replay"] is True
    assert FollowUpAnswer.objects.filter(question=question).count() == 1
    assert answer_history(inquiry).count() == 1
    assert answer_idempotency(owner).count() == 1
    analyze.assert_called_once()


def test_answer_replay_requires_current_customer_object_scope():
    owner, client, inquiry = prepare_questionnaire(112)
    question = create_question(inquiry, 1)
    body = {
        "state_version": 2,
        "answers": [
            {
                "question_id": str(question.public_id),
                "answer_text": "Today.",
            }
        ],
    }
    key = "t022a-owner-scope-replay"

    first = post_answers(client, inquiry, body, key=key)
    assert first.status_code == 200

    owner.customer_profile.deleted_at = timezone.now()
    owner.customer_profile.save(update_fields=["deleted_at", "updated_at"])
    replay = post_answers(client, inquiry, body, key=key)

    assert replay.status_code == 404
    assert replay.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert FollowUpAnswer.objects.filter(question=question).count() == 1
    assert answer_history(inquiry).count() == 1
    assert answer_idempotency(owner).count() == 1


@pytest.mark.parametrize(
    "answers",
    [
        lambda question: [
            {
                "question_id": str(question.public_id),
                "answer_payload": {"selected_option": "NOT_AN_OPTION"},
            }
        ],
        lambda question: [
            {
                "question_id": str(uuid4()),
                "answer_text": "Unknown question",
            }
        ],
    ],
)
def test_invalid_or_unknown_answer_is_422_without_writes(answers):
    owner, client, inquiry = prepare_questionnaire(103)
    question = create_question(
        inquiry,
        1,
        answer_type="SINGLE_CHOICE",
        options=["YES", "NO"],
    )

    response = post_answers(
        client,
        inquiry,
        {"state_version": 2, "answers": answers(question)},
        key=f"t022a-invalid-{uuid4()}",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_FOLLOWUP_ANSWERS"
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2
    assert FollowUpAnswer.objects.count() == 0
    assert answer_history(inquiry).count() == 0
    assert answer_idempotency(owner).count() == 0


def test_already_answered_question_cannot_be_written_again_with_new_key():
    owner, client, inquiry = prepare_questionnaire(104)
    question = create_question(inquiry, 1)
    first = post_answers(
        client,
        inquiry,
        {
            "state_version": 2,
            "answers": [
                {
                    "question_id": str(question.public_id),
                    "answer_text": "First",
                }
            ],
        },
        key="t022a-first",
    )
    assert first.status_code == 200

    second = post_answers(
        client,
        inquiry,
        {
            "state_version": 3,
            "answers": [
                {
                    "question_id": str(question.public_id),
                    "answer_text": "Second",
                }
            ],
        },
        key="t022a-second",
    )

    assert second.status_code == 422
    assert FollowUpAnswer.objects.get(question=question).answer_text == "First"
    assert answer_history(inquiry).count() == 1
    assert answer_idempotency(owner).count() == 1


def test_stale_version_and_other_owner_are_closed_without_answer_leak():
    owner, client, inquiry = prepare_questionnaire(105)
    question = create_question(inquiry, 1)
    body = {
        "state_version": 1,
        "answers": [
            {
                "question_id": str(question.public_id),
                "answer_text": "Answer",
            }
        ],
    }
    stale = post_answers(client, inquiry, body, key="t022a-stale")

    other = create_user(106)
    hidden = post_answers(
        authenticated_client(other),
        inquiry,
        {**body, "state_version": 2},
        key="t022a-hidden",
    )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STATE-CONFLICT-01"
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert FollowUpAnswer.objects.count() == 0
    assert answer_history(inquiry).count() == 0
    assert answer_idempotency(owner).count() == 0


@pytest.mark.parametrize(
    "body,key,correlation_id",
    [
        ({"state_version": 2, "answers": []}, "t022a-empty", "AUTO"),
        (
            {"state_version": 2, "answers": [], "extra": True},
            "t022a-extra",
            "AUTO",
        ),
        ({"state_version": 2, "answers": []}, None, "AUTO"),
        ({"state_version": 2, "answers": []}, "t022a-no-corr", None),
        (
            {"state_version": 2, "answers": []},
            "t022a-bad-corr",
            "not-a-uuid",
        ),
    ],
)
def test_request_validation_has_no_side_effects(body, key, correlation_id):
    owner, client, inquiry = prepare_questionnaire(107)
    create_question(inquiry, 1)

    response = post_answers(
        client,
        inquiry,
        body,
        key=key,
        correlation_id=correlation_id,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert FollowUpAnswer.objects.count() == 0
    assert answer_history(inquiry).count() == 0
    assert answer_idempotency(owner).count() == 0


@pytest.mark.parametrize("correlation_id", [None, "not-a-uuid", "PADDED"])
def test_correlation_header_is_strictly_required_for_valid_answer_body(
    correlation_id,
):
    owner, client, inquiry = prepare_questionnaire(111)
    question = create_question(inquiry, 1)
    if correlation_id == "PADDED":
        correlation_id = f" {uuid4()} "

    response = post_answers(
        client,
        inquiry,
        {
            "state_version": 2,
            "answers": [
                {
                    "question_id": str(question.public_id),
                    "answer_text": "Valid answer",
                }
            ],
        },
        key=f"t022a-correlation-{uuid4()}",
        correlation_id=correlation_id,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert FollowUpAnswer.objects.count() == 0
    assert answer_history(inquiry).count() == 0
    assert answer_idempotency(owner).count() == 0


def test_get_normalized_choice_can_be_posted_without_contract_mismatch():
    _owner, client, inquiry = prepare_questionnaire(110)
    question = create_question(
        inquiry,
        1,
        answer_type="SINGLE_CHOICE",
        options=[" YES "],
    )
    questions = client.get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/questions"
    )
    public_value = questions.json()["data"]["questions"][0]["options"][
        0
    ]["value"]

    response = post_answers(
        client,
        inquiry,
        {
            "state_version": 2,
            "answers": [
                {
                    "question_id": str(question.public_id),
                    "answer_payload": {"selected_option": public_value},
                }
            ],
        },
        key="t022a-normalized-choice",
    )

    assert public_value == "YES"
    assert response.status_code == 200
    assert question.customer_answer.answer_payload == {
        "selected_option": "YES"
    }

def test_response_contract_failure_rolls_back_answers_version_and_records(
    django_capture_on_commit_callbacks,
):
    owner, client, inquiry = prepare_questionnaire(108)
    question = create_question(inquiry, 1)

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with patch(
            "apps.inquiries.api.views.SubmitFollowUpAnswersResponseSerializer",
            side_effect=RuntimeError("forced response contract failure"),
        ):
            response = post_answers(
                client,
                inquiry,
                {
                    "state_version": 2,
                    "answers": [
                        {
                            "question_id": str(question.public_id),
                            "answer_text": "Rollback",
                        }
                    ],
                },
                key="t022a-rollback",
            )

    assert response.status_code == 500
    inquiry.refresh_from_db()
    assert inquiry.state_version == 2
    assert FollowUpAnswer.objects.count() == 0
    assert answer_history(inquiry).count() == 0
    assert answer_idempotency(owner).count() == 0
    assert callbacks == []
