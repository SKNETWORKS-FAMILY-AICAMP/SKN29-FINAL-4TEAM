"""Runtime tests for T-023 feedback, finalization, and reopen actions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, local
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from django.db import connection, connections
from django.utils import timezone

from apps.accounts.models import User
from apps.consultations.models import Consultation
from apps.inquiries.models import FollowupConfirmation, Inquiry
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.inquiries.repositories.resolution_repository import (
    ResolutionRepository,
)
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


def resolution_runtime_row_counts():
    return {
        "inquiries": Inquiry.objects.count(),
        "consultations": Consultation.objects.count(),
        "visits": Visit.objects.count(),
        "followups": FollowupConfirmation.objects.count(),
        "histories": TransitionHistory.objects.count(),
        "idempotency_records": IdempotencyRecord.objects.count(),
    }


def concurrent_finalize(
    *,
    actor_id: int,
    inquiry_id: UUID,
    state_version: int,
    key: str,
    barrier: Barrier,
) -> tuple[int, dict]:
    connections.close_all()
    try:
        actor = User.objects.get(pk=actor_id)
        barrier.wait(timeout=10)
        response = client_for(actor).post(
            f"/api/v1/inquiries/{inquiry_id}/finalize",
            {"state_version": state_version},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_CORRELATION_ID=str(uuid4()),
        )
        return response.status_code, response.json()
    finally:
        connections.close_all()


def concurrent_feedback(
    *,
    actor_id: int,
    inquiry_id: UUID,
    key: str,
    barrier: Barrier,
) -> tuple[int, dict]:
    connections.close_all()
    try:
        actor = User.objects.get(pk=actor_id)
        barrier.wait(timeout=10)
        response = client_for(actor).post(
            f"/api/v1/inquiries/{inquiry_id}/resolution-feedback",
            feedback_body(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
            HTTP_X_CORRELATION_ID=str(uuid4()),
        )
        return response.status_code, response.json()
    finally:
        connections.close_all()


def staff_lock_barrier(barrier: Barrier):
    """Force both PostgreSQL requests to contend for the inquiry row lock."""

    original = ResolutionRepository.lock_staff_inquiry
    thread_state = local()

    def synchronized_lock(*args, **kwargs):
        if not getattr(thread_state, "lock_attempted", False):
            thread_state.lock_attempted = True
            barrier.wait(timeout=10)
        return original(*args, **kwargs)

    return patch.object(
        ResolutionRepository,
        "lock_staff_inquiry",
        side_effect=synchronized_lock,
    )


def customer_lock_barrier(barrier: Barrier):
    """Force both customer feedback requests onto the inquiry row lock."""

    original = InquiryRepository.lock_owned_inquiry
    thread_state = local()

    def synchronized_lock(*args, **kwargs):
        if not getattr(thread_state, "lock_attempted", False):
            thread_state.lock_attempted = True
            barrier.wait(timeout=10)
        return original(*args, **kwargs)

    return patch.object(
        InquiryRepository,
        "lock_owned_inquiry",
        side_effect=synchronized_lock,
    )


@pytest.mark.parametrize(
    "handling_source",
    ["CONSULTATION", "VISIT"],
)
def test_completed_handling_lock_ignores_unassigned_open_rows(
    handling_source,
):
    if handling_source == "CONSULTATION":
        _customer, consultant, inquiry, _consultation = (
            prepare_consultation_completion(310)
        )
        Consultation.objects.create(
            consultation_code="T023-CONS-UNASSIGNED-310",
            inquiry=inquiry,
            sequence=2,
            consultant=None,
            status=Consultation.Status.WAITING,
            outcome=Consultation.Outcome.PENDING,
            state_version=7,
            idempotency_key="t023-cons-unassigned-310",
            correlation_id=uuid4(),
            data_classification=(
                Consultation.DataClassification.SYNTHETIC
            ),
        )
        expected_handler = consultant
    else:
        _customer, _consultant, technician, inquiry, _consultation = (
            prepare_visit_completion(311)
        )
        Visit.objects.create(
            visit_code="T023-VISIT-UNASSIGNED-311",
            inquiry=inquiry,
            technician=None,
            status=Visit.Status.ASSIGNING,
            requested_at=timezone.now(),
            state_version=7,
            idempotency_key="t023-visit-unassigned-311",
            correlation_id=uuid4(),
            data_classification=Visit.DataClassification.SYNTHETIC,
        )
        expected_handler = technician

    handling = ResolutionRepository.lock_completed_handling(inquiry)

    assert handling is not None
    assert handling.source_code == handling_source
    assert handling.handler == expected_handler


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_finalize_same_key_is_one_write_and_one_replay():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    customer, consultant, inquiry, _consultation = (
        prepare_consultation_completion(312)
    )
    feedback = post_action(
        client_for(customer),
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-concurrent-finalize-feedback",
    )
    assert feedback.status_code == 200

    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    with staff_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_finalize,
                actor_id=consultant.pk,
                inquiry_id=inquiry.public_id,
                state_version=8,
                key="t023-concurrent-finalize-same-key",
                barrier=request_barrier,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 200]
    assert sorted(
        payload["data"]["idempotent_replay"]
        for _status, payload in results
    ) == [False, True]
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.RESOLVED
    assert inquiry.state_version == 9
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="FINALIZE_INQUIRY",
    ).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=consultant,
        operation_id="finalizeInquiry",
        idempotency_key="t023-concurrent-finalize-same-key",
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_finalize_new_keys_have_one_version_winner():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    customer, consultant, inquiry, _consultation = (
        prepare_consultation_completion(313)
    )
    feedback = post_action(
        client_for(customer),
        inquiry,
        "resolution-feedback",
        feedback_body(),
        key="t023-concurrent-conflict-feedback",
    )
    assert feedback.status_code == 200

    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    keys = (
        "t023-concurrent-finalize-key-a",
        "t023-concurrent-finalize-key-b",
    )
    with staff_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_finalize,
                actor_id=consultant.pk,
                inquiry_id=inquiry.public_id,
                state_version=8,
                key=key,
                barrier=request_barrier,
            )
            for key in keys
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 409]
    conflict = next(payload for status, payload in results if status == 409)
    assert conflict["error"]["code"] == "STATE-CONFLICT-01"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.RESOLVED
    assert inquiry.state_version == 9
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="FINALIZE_INQUIRY",
    ).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=consultant,
        operation_id="finalizeInquiry",
        idempotency_key__in=keys,
    ).count() == 1


@pytest.mark.django_db(transaction=True)
def test_postgresql_concurrent_feedback_new_keys_store_one_confirmation():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    customer, _consultant, inquiry, _consultation = (
        prepare_consultation_completion(314)
    )
    request_barrier = Barrier(2)
    lock_barrier = Barrier(2)
    keys = (
        "t023-concurrent-feedback-key-a",
        "t023-concurrent-feedback-key-b",
    )
    with customer_lock_barrier(lock_barrier), ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                concurrent_feedback,
                actor_id=customer.pk,
                inquiry_id=inquiry.public_id,
                key=key,
                barrier=request_barrier,
            )
            for key in keys
        ]
        results = [future.result(timeout=30) for future in futures]

    assert sorted(status for status, _payload in results) == [200, 409]
    conflict = next(payload for status, payload in results if status == 409)
    assert conflict["error"]["code"] == "STATE-CONFLICT-01"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.COMPLETION_PENDING
    assert inquiry.state_version == 8
    assert FollowupConfirmation.objects.filter(inquiry=inquiry).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=customer,
        operation_id="submitResolutionFeedback",
        idempotency_key__in=keys,
    ).count() == 1


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
    assert [
        action["code"]
        for action in accepted.json()["data"]["allowed_actions"]
    ] == ["CUSTOMER_REPORTED_UNRESOLVED"]
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

    duplicate = post_action(
        customer_client,
        inquiry,
        "resolution-feedback",
        feedback_body(version=8),
        key="t023-feedback-new-key",
    )
    reconsult = post_action(
        customer_client,
        inquiry,
        "request-consultation",
        {"state_version": 8},
        key="t023-reconsult-after-resolved",
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "STATE-CONFLICT-01"
    assert duplicate.json()["error"]["details"]["allowed_actions"] == [
        "CUSTOMER_REPORTED_UNRESOLVED"
    ]
    assert reconsult.status_code == 409
    assert reconsult.json()["error"]["code"] == "STATE-CONFLICT-01"
    assert FollowupConfirmation.objects.filter(inquiry=inquiry).count() == 1
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    workflow_snapshot = customer_client.get(
        f"/api/v1/me/inquiries/{inquiry.public_id}"
    )
    assert workflow_snapshot.status_code == 200
    assert [
        action["code"]
        for action in workflow_snapshot.json()["data"]["allowed_actions"]
    ] == ["CUSTOMER_REPORTED_UNRESOLVED"]

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
    before_counts = resolution_runtime_row_counts()
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
    assert resolution_runtime_row_counts() == before_counts
