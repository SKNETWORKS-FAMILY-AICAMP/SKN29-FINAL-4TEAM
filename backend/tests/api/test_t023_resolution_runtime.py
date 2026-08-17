"""Runtime tests for T-023 feedback, finalization, and reopen actions."""

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.consultations.models import Consultation
from apps.inquiries.models import FollowupConfirmation, Inquiry
from apps.visits.models import Visit
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from tests.api.test_consultation_visit_runtime import (
    client_for,
    create_inquiry,
    create_user,
)


pytestmark = pytest.mark.django_db


def prepare_consultation_completion(sequence: int):
    consultant = create_user(sequence + 500, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(
        sequence,
        consultant=consultant,
        status=Inquiry.Status.COMPLETION_PENDING,
        state_version=7,
    )
    now = timezone.now()
    consultation = Consultation.objects.create(
        consultation_code=f"T023-CONS-{sequence:03d}",
        inquiry=inquiry,
        sequence=1,
        consultant=consultant,
        status=Consultation.Status.COMPLETED,
        outcome=Consultation.Outcome.COMPLETED_NO_VISIT,
        summary="고객 조치 안내를 완료했습니다.",
        confirmed_summary="고객 조치 안내를 완료했습니다.",
        summary_confirmed_at=now - timedelta(hours=2),
        state_version=7,
        idempotency_key=f"t023-source-{sequence}",
        correlation_id=uuid4(),
        created_at=now - timedelta(hours=3),
        started_at=now - timedelta(hours=2),
        completed_at=now - timedelta(hours=1),
        data_classification=Consultation.DataClassification.SYNTHETIC,
    )
    customer = inquiry.subscription.customer.user
    return customer, consultant, inquiry, consultation


def prepare_visit_completion(sequence: int):
    customer, consultant, inquiry, consultation = (
        prepare_consultation_completion(sequence)
    )
    technician = create_user(sequence + 900, role=User.Role.TECHNICIAN)
    now = timezone.now()
    Visit.objects.create(
        visit_code=f"T023-VISIT-{sequence:03d}",
        inquiry=inquiry,
        technician=technician,
        status=Visit.Status.COMPLETED,
        requested_at=now - timedelta(minutes=50),
        started_at=now - timedelta(minutes=40),
        completed_at=now - timedelta(minutes=30),
        confirmed_cause="합성 원인",
        action_taken="합성 조치",
        state_version=7,
        idempotency_key=f"t023-visit-source-{sequence}",
        correlation_id=uuid4(),
        data_classification=Visit.DataClassification.SYNTHETIC,
    )
    inquiry.assigned_user = technician
    inquiry.assigned_role_code = Inquiry.AssignedRole.TECHNICIAN
    inquiry.save(update_fields=["assigned_user", "assigned_role_code"])
    return customer, consultant, technician, inquiry, consultation


def post_action(client, inquiry, action: str, body: dict, *, key: str | None):
    headers = {"HTTP_X_CORRELATION_ID": str(uuid4())}
    if key is not None:
        headers["HTTP_IDEMPOTENCY_KEY"] = key
    return client.post(
        f"/api/v1/inquiries/{inquiry.public_id}/{action}",
        body,
        format="json",
        **headers,
    )


def feedback_body(*, version: int = 7, **overrides):
    body = {
        "state_version": version,
        "resolved": True,
        "comment": "안내 후 정상 작동합니다.",
    }
    body.update(overrides)
    return body


def test_resolved_feedback_then_last_consultant_finalizes_with_replay():
    customer, consultant, inquiry, consultation = (
        prepare_consultation_completion(301)
    )
    customer_client = client_for(customer)

    accepted = post_action(
        customer_client,
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-feedback-replay",
    )
    replay = post_action(
        customer_client,
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-feedback-replay",
    )

    assert accepted.status_code == replay.status_code == 200
    assert accepted.json()["data"]["status"] == "COMPLETION_PENDING"
    assert accepted.json()["data"]["state_version"] == 8
    assert accepted.json()["data"]["idempotent_replay"] is False
    assert replay.json()["data"]["idempotent_replay"] is True
    inquiry.refresh_from_db()
    followup = FollowupConfirmation.objects.get(inquiry=inquiry)
    assert inquiry.state_version == 8
    assert followup.consultation == consultation
    assert followup.visit_id is None
    assert followup.resolution_status_code == "RESOLVED"
    assert followup.next_action == "FINALIZE_INQUIRY"
    assert followup.customer_response == "안내 후 정상 작동합니다."
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 0

    final_body = {"state_version": 8, "final_note": "고객 확인 후 종결"}
    finalized = post_action(
        client_for(consultant),
        inquiry,
        "finalize",
        final_body,
        key="t023-finalize-replay",
    )
    final_replay = post_action(
        client_for(consultant),
        inquiry,
        "finalize",
        final_body,
        key="t023-finalize-replay",
    )

    assert finalized.status_code == final_replay.status_code == 200
    assert finalized.json()["data"]["status"] == "RESOLVED"
    assert finalized.json()["data"]["state_version"] == 9
    assert final_replay.json()["data"]["idempotent_replay"] is True
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.RESOLVED
    history = TransitionHistory.objects.get(inquiry=inquiry)
    assert history.event_code == "FINALIZE_INQUIRY"
    assert history.actor == consultant
    assert history.changed_at is not None
    assert history.change_reason == "CONSULTATION | 고객 확인 후 종결"
    assert FollowupConfirmation.objects.filter(inquiry=inquiry).count() == 1


def test_unresolved_report_preserves_open_reason_and_resumes_queue_once():
    customer, consultant, inquiry, _consultation = (
        prepare_consultation_completion(302)
    )
    unresolved_body = {
        "state_version": 7,
        "resolved": False,
        "reason_code": "FUTURE_REGISTRY_CODE",
        "comment": "같은 증상이 남아 있습니다.",
    }

    reopened = post_action(
        client_for(customer),
        inquiry,
        "report-unresolved",
        unresolved_body,
        key="t023-unresolved",
    )

    assert reopened.status_code == 200
    assert reopened.json()["data"]["status"] == "REOPENED"
    inquiry.refresh_from_db()
    followup = FollowupConfirmation.objects.get(inquiry=inquiry)
    assert followup.resolution_status_code == "REOPENED"
    assert followup.unresolved_reason == "FUTURE_REGISTRY_CODE"
    assert followup.customer_response == "같은 증상이 남아 있습니다."
    assert followup.next_action == "RESUME_CONSULTATION"

    resume_body = {"state_version": 8}
    resumed = post_action(
        client_for(consultant),
        inquiry,
        "resume-consultation",
        resume_body,
        key="t023-resume",
    )
    resume_replay = post_action(
        client_for(consultant),
        inquiry,
        "resume-consultation",
        resume_body,
        key="t023-resume",
    )

    assert resumed.status_code == resume_replay.status_code == 200
    assert resumed.json()["data"]["status"] == "CONSULTATION_REQUIRED"
    assert resumed.json()["data"]["state_version"] == 9
    assert resume_replay.json()["data"]["idempotent_replay"] is True
    assert Consultation.objects.filter(inquiry=inquiry).count() == 2
    assert Consultation.objects.filter(
        inquiry=inquiry,
        status=Consultation.Status.WAITING,
    ).count() == 1
    assert list(
        TransitionHistory.objects.filter(inquiry=inquiry)
        .order_by("state_version")
        .values_list("event_code", "state_version")
    ) == [
        ("CUSTOMER_REPORTED_UNRESOLVED", 8),
        ("RESUME_CONSULTATION", 9),
    ]


def test_latest_visit_technician_is_only_valid_visit_finalizer():
    customer, consultant, technician, inquiry, _consultation = (
        prepare_visit_completion(303)
    )
    feedback = post_action(
        client_for(customer),
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-visit-feedback",
    )
    assert feedback.status_code == 200

    wrong_handler = post_action(
        client_for(consultant),
        inquiry,
        "finalize",
        {"state_version": 8},
        key="t023-wrong-handler",
    )
    assert wrong_handler.status_code == 403
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.COMPLETION_PENDING

    finalized = post_action(
        client_for(technician),
        inquiry,
        "finalize",
        {"state_version": 8},
        key="t023-visit-finalize",
    )
    assert finalized.status_code == 200
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.RESOLVED
    history = TransitionHistory.objects.get(
        inquiry=inquiry,
        event_code="FINALIZE_INQUIRY",
    )
    assert history.actor == technician
    assert history.change_reason == "VISIT"


def test_finalize_requires_fresh_resolved_feedback_and_current_version():
    customer, consultant, inquiry, consultation = (
        prepare_consultation_completion(304)
    )
    no_feedback = post_action(
        client_for(consultant),
        inquiry,
        "finalize",
        {"state_version": 7},
        key="t023-no-feedback",
    )
    assert no_feedback.status_code == 422
    assert no_feedback.json()["error"]["code"] == (
        "RESOLVED_CUSTOMER_FEEDBACK_REQUIRED"
    )

    accepted = post_action(
        client_for(customer),
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-stale-feedback",
    )
    assert accepted.status_code == 200
    followup = FollowupConfirmation.objects.get(inquiry=inquiry)
    FollowupConfirmation.objects.filter(pk=followup.pk).update(
        created_at=consultation.completed_at - timedelta(minutes=1)
    )
    stale_feedback = post_action(
        client_for(consultant),
        inquiry,
        "finalize",
        {"state_version": 8},
        key="t023-old-feedback",
    )
    assert stale_feedback.status_code == 422

    stale_version = post_action(
        client_for(customer),
        inquiry,
        "report-unresolved",
        {"state_version": 7, "resolved": False},
        key="t023-stale-version",
    )
    assert stale_version.status_code == 409
    assert stale_version.json()["error"]["code"] == "STATE-CONFLICT-01"


def test_other_owner_is_hidden_and_key_payload_conflict_is_409():
    customer, _consultant, inquiry, _source = (
        prepare_consultation_completion(305)
    )
    other_customer, _other_staff, _other_inquiry, _other_source = (
        prepare_consultation_completion(306)
    )
    hidden = post_action(
        client_for(other_customer),
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-hidden-owner",
    )
    assert hidden.status_code == 404

    first = post_action(
        client_for(customer),
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-payload-conflict",
    )
    conflict = post_action(
        client_for(customer),
        inquiry,
        "resolution-feedback",
        feedback_body(comment="다른 내용"),
        key="t023-payload-conflict",
    )
    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    assert FollowupConfirmation.objects.filter(inquiry=inquiry).count() == 1


@pytest.mark.parametrize(
    ("action", "body"),
    [
        (
            "resolution-feedback",
            {"state_version": 7, "resolved": False},
        ),
        (
            "resolution-feedback",
            {"state_version": 7, "resolved": True, "extra": True},
        ),
        (
            "report-unresolved",
            {"state_version": 7, "resolved": True},
        ),
        (
            "report-unresolved",
            {
                "state_version": 7,
                "resolved": False,
                "reason_code": "not-approved-format",
            },
        ),
    ],
)
def test_confirmed_request_shapes_fail_closed(action, body):
    _customer, _consultant, inquiry, _source = (
        prepare_consultation_completion(307)
    )
    response = post_action(
        client_for(inquiry.subscription.customer.user),
        inquiry,
        action,
        body,
        key="t023-invalid-shape",
    )
    assert response.status_code == 422
    assert FollowupConfirmation.objects.count() == 0
    assert IdempotencyRecord.objects.filter(
        operation_id__in=["submitResolutionFeedback", "reportUnresolved"]
    ).count() == 0


@pytest.mark.parametrize(
    "final_note",
    ["system_prompt=내부값", "원본 위치 s3://private-bucket/source.json"],
)
def test_final_note_rejects_internal_ai_fields_and_raw_storage_paths(final_note):
    customer, consultant, inquiry, _source = (
        prepare_consultation_completion(308)
    )
    accepted = post_action(
        client_for(customer),
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-safe-note-feedback",
    )
    assert accepted.status_code == 200

    rejected = post_action(
        client_for(consultant),
        inquiry,
        "finalize",
        {"state_version": 8, "final_note": final_note},
        key=f"t023-unsafe-note-{uuid4()}",
    )
    assert rejected.status_code == 422
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.COMPLETION_PENDING


def test_missing_headers_and_response_contract_failure_have_no_side_effects():
    customer, _consultant, inquiry, _source = (
        prepare_consultation_completion(309)
    )
    client = client_for(customer)
    missing_key = client.post(
        f"/api/v1/inquiries/{inquiry.public_id}/resolution-feedback",
        feedback_body(),
        format="json",
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )
    missing_trace = client.post(
        f"/api/v1/inquiries/{inquiry.public_id}/resolution-feedback",
        feedback_body(),
        format="json",
        HTTP_IDEMPOTENCY_KEY="t023-missing-trace",
    )
    assert missing_key.status_code == missing_trace.status_code == 422

    with patch(
        "apps.inquiries.api.views.ResolutionTransitionResponseSerializer",
        side_effect=RuntimeError("forced response contract failure"),
    ):
        failed = post_action(
            client,
            inquiry,
            "resolution-feedback",
            feedback_body(),
            key="t023-response-rollback",
        )
    assert failed.status_code == 500
    inquiry.refresh_from_db()
    assert inquiry.state_version == 7
    assert FollowupConfirmation.objects.count() == 0
    assert IdempotencyRecord.objects.filter(
        operation_id="submitResolutionFeedback"
    ).count() == 0
