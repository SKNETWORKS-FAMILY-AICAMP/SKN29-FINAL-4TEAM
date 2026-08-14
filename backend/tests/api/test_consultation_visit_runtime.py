"""Runtime verification for DEC-003 consultation and DEC-004 visit APIs."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import HandoffReport, Visit, VisitResult
from apps.visits.repositories.visit_repository import VisitRepository
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from apps.workflow.repositories.workflow_repository import WorkflowRepository


pytestmark = pytest.mark.django_db


def create_user(sequence: int, *, role: str) -> User:
    user = User.objects.create_user(
        username=f"RUNTIME-{role}-{sequence:03d}",
        full_name=f"합성 {role} {sequence}",
        phone=f"010-9000-{sequence:04d}",
        role_code=role,
        employee_no=(
            None
            if role == User.Role.CUSTOMER
            else f"RUNTIME-EMP-{sequence:03d}"
        ),
        is_synthetic=True,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"RUNTIME-CUSTOMER-{sequence:03d}",
            customer_name=f"합성 고객 {sequence}",
            phone=f"010-8000-{sequence:04d}",
            address_line1="비노출 합성 주소",
            is_synthetic=True,
        )
    return user


def create_inquiry(
    sequence: int,
    *,
    consultant: User,
    status: str = Inquiry.Status.CONSULTATION_REQUIRED,
    state_version: int = 2,
) -> Inquiry:
    customer = create_user(sequence, role=User.Role.CUSTOMER)
    product = ProductModel.objects.create(
        model_code=f"RUNTIME-MODEL-{sequence:03d}",
        model_name=f"합성 제품 {sequence}",
        manufacturer="SK매직",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"RUNTIME-CONTRACT-{sequence:03d}",
        customer=customer.customer_profile,
        product_model=product,
        serial_no=f"RUNTIME-SERIAL-{sequence:03d}",
        management_type_code=(
            CustomerSubscription.ManagementType.VISIT_CARE
        ),
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 7, 1),
        installation_address="비노출 설치 주소",
    )
    return Inquiry.objects.create(
        inquiry_code=f"RUNTIME-INQ-{sequence:03d}",
        subscription=subscription,
        initiated_by=customer,
        assigned_user=consultant,
        assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="정수기 출수량이 감소했습니다.",
        risk_level_code=Inquiry.RiskLevel.CAUTION,
        status_code=status,
        state_version=state_version,
    )


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def request(
    client: APIClient,
    method: str,
    path: str,
    body: dict,
    *,
    key: str | None,
):
    headers = (
        {"HTTP_IDEMPOTENCY_KEY": key}
        if key is not None
        else {}
    )
    return getattr(client, method)(path, body, format="json", **headers)


def start_consultation(
    client: APIClient,
    inquiry: Inquiry,
    *,
    key: str,
):
    return request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": inquiry.state_version},
        key=key,
    )


def prepare_confirmed_consultation(
    *,
    sequence: int,
    result_code: str,
) -> tuple[User, APIClient, Inquiry, Consultation]:
    consultant = create_user(sequence + 500, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(sequence, consultant=consultant)
    client = client_for(consultant)

    started = start_consultation(
        client,
        inquiry,
        key=f"runtime-start-{sequence}",
    )
    assert started.status_code == 200, started.json()
    inquiry.refresh_from_db()

    saved = request(
        client,
        "patch",
        f"/api/v1/inquiries/{inquiry.public_id}/consultation-summary",
        {
            "state_version": inquiry.state_version,
            "summary": "필터와 급수 밸브를 확인하고 고객에게 안내했습니다.",
            "consultation_note": "합성 상담 메모",
            "additional_check": "방문 시 유량을 재확인합니다.",
            "customer_guidance": "사용을 잠시 중단해 주세요.",
            "result_code": result_code,
            "usage_guidance_status": "PARTIAL_STOP",
        },
        key=f"runtime-save-{sequence}",
    )
    assert saved.status_code == 200, saved.json()
    inquiry.refresh_from_db()

    confirmed = request(
        client,
        "post",
        (
            f"/api/v1/inquiries/{inquiry.public_id}"
            "/consultation-summary/confirm"
        ),
        {"state_version": inquiry.state_version},
        key=f"runtime-confirm-summary-{sequence}",
    )
    assert confirmed.status_code == 200, confirmed.json()
    inquiry.refresh_from_db()
    return (
        consultant,
        client,
        inquiry,
        Consultation.objects.get(inquiry=inquiry),
    )


def visit_handoff() -> dict:
    return {
        "product_summary": "합성 정수기 모델",
        "symptom_summary": "출수량 감소",
        "action_summary": "필터와 급수 밸브 원격 확인",
        "risk_summary": "주의 단계이며 부분 사용 중단 안내",
        "priority_check_items": ["필터 장착", "급수 밸브"],
        "consultant_final": "현장 유량과 필터 체결 상태를 확인해 주세요.",
    }


def prepare_visit_review(
    sequence: int,
) -> tuple[User, APIClient, Inquiry, Consultation]:
    consultant, client, inquiry, consultation = (
        prepare_confirmed_consultation(
            sequence=sequence,
            result_code=Consultation.Outcome.VISIT_REQUIRED,
        )
    )
    reviewed = request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/visit-review",
        {
            "state_version": inquiry.state_version,
            "reason_code": "PHYSICAL_INSPECTION_REQUIRED",
            "reason_detail": "원격 확인만으로 원인을 확정할 수 없습니다.",
        },
        key=f"runtime-review-{sequence}",
    )
    assert reviewed.status_code == 200, reviewed.json()
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    return consultant, client, inquiry, consultation


def create_visit_request(
    client: APIClient,
    inquiry: Inquiry,
    *,
    key: str,
):
    return request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/visits",
        {
            "state_version": inquiry.state_version,
            "visit_reason": "현장 점검 필요",
            "preferred_date": "2026-08-12",
            "usage_guidance_status": "PARTIAL_STOP",
            "handoff": visit_handoff(),
        },
        key=key,
    )


def test_consultation_start_save_confirm_complete_and_replay():
    consultant = create_user(1, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(1, consultant=consultant)
    client = client_for(consultant)

    first = start_consultation(client, inquiry, key="consult-start-replay")
    replay = start_consultation(client, inquiry, key="consult-start-replay")

    assert first.status_code == replay.status_code == 200
    assert first.json()["data"]["status"] == "CONSULTATION_IN_PROGRESS"
    assert first.json()["data"]["state_version"] == 3
    assert first.json()["data"]["idempotent_replay"] is False
    assert replay.json()["data"]["idempotent_replay"] is True
    assert first["X-Correlation-ID"] == (
        first.json()["metadata"]["correlation_id"]
    )
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    inquiry.refresh_from_db()

    saved = request(
        client,
        "patch",
        f"/api/v1/inquiries/{inquiry.public_id}/consultation-summary",
        {
            "state_version": inquiry.state_version,
            "summary": "상담 결과 방문 없이 해결되었습니다.",
            "consultation_note": "합성 기록",
            "result_code": "COMPLETED_NO_VISIT",
            "usage_guidance_status": "NORMAL",
        },
        key="consult-save",
    )
    assert saved.status_code == 200, saved.json()
    inquiry.refresh_from_db()

    confirmed = request(
        client,
        "post",
        (
            f"/api/v1/inquiries/{inquiry.public_id}"
            "/consultation-summary/confirm"
        ),
        {"state_version": inquiry.state_version},
        key="consult-summary-confirm",
    )
    assert confirmed.status_code == 200, confirmed.json()
    inquiry.refresh_from_db()

    completed = request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/complete-consultation",
        {"state_version": inquiry.state_version},
        key="consult-complete",
    )
    assert completed.status_code == 200, completed.json()
    data = completed.json()["data"]
    assert data["status"] == "COMPLETION_PENDING"
    assert data["state_version"] == 6
    assert data["resource"]["result_code"] == "COMPLETED_NO_VISIT"
    assert data["resource"]["summary"]["confirmed_summary"] == (
        "상담 결과 방문 없이 해결되었습니다."
    )

    detail = client.get(f"/api/v1/inquiries/{inquiry.public_id}")
    assert detail.status_code == 200, detail.json()
    assert detail.json()["data"]["consultation"] == data["resource"]

    consultation = Consultation.objects.get(inquiry=inquiry)
    assert consultation.status == Consultation.Status.COMPLETED
    assert consultation.completed_at is not None
    assert list(
        TransitionHistory.objects.filter(
            inquiry=inquiry,
            event_code__in=[
                "START_CONSULTATION",
                "UPDATE_CONSULTATION_SUMMARY",
                "CONFIRM_CONSULTATION_SUMMARY",
                "CONSULTATION_COMPLETED",
            ],
        )
        .order_by("state_version")
        .values_list("event_code", "state_version")
    ) == [
        ("START_CONSULTATION", 3),
        ("UPDATE_CONSULTATION_SUMMARY", 4),
        ("CONFIRM_CONSULTATION_SUMMARY", 5),
        ("CONSULTATION_COMPLETED", 6),
    ]
    assert IdempotencyRecord.objects.filter(actor=consultant).count() == 4


def test_reassigned_consultant_cannot_replay_previous_assignee_response():
    original_consultant = create_user(91, role=User.Role.CONSULTANT)
    replacement_consultant = create_user(92, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(91, consultant=original_consultant)
    original_client = client_for(original_consultant)
    key = "consult-reassigned-replay"

    first = request(
        original_client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 2},
        key=key,
    )
    assert first.status_code == 200, first.json()

    Inquiry.objects.filter(pk=inquiry.pk).update(
        assigned_user=replacement_consultant,
        assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
    )
    replay = request(
        original_client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 2},
        key=key,
    )

    assert replay.status_code == 404
    assert replay.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1
    assert IdempotencyRecord.objects.filter(
        actor=original_consultant,
        operation_id="startConsultation",
        idempotency_key=key,
    ).count() == 1


def test_consultation_success_and_stale_409_share_allowed_action_snapshot():
    consultant = create_user(93, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(93, consultant=consultant)
    client = client_for(consultant)

    success = request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 2},
        key="consult-parity-success",
    )
    stale = request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 2},
        key="consult-parity-stale",
    )

    assert success.status_code == 200, success.json()
    assert stale.status_code == 409, stale.json()
    success_codes = [
        action["code"] for action in success.json()["data"]["allowed_actions"]
    ]
    assert stale.json()["error"]["details"]["allowed_actions"] == success_codes


def test_visit_review_create_schedule_confirm_date_only_flow():
    consultant, client, inquiry, _consultation = prepare_visit_review(10)

    created = create_visit_request(
        client,
        inquiry,
        key="visit-create-success",
    )
    assert created.status_code == 200, created.json()
    created_data = created.json()["data"]
    assert created_data["status"] == "VISIT_SCHEDULING"
    assert created_data["resource"]["schedule"] == {
        "preferred_date": "2026-08-12",
        "confirmed_date": None,
        "schedule_status": "ASSIGNING",
        "synthetic_technician_id": None,
    }
    inquiry.refresh_from_db()
    visit = Visit.objects.get(inquiry=inquiry)
    assert HandoffReport.objects.filter(inquiry=inquiry).count() == 1

    technician = create_user(610, role=User.Role.TECHNICIAN)
    scheduled = request(
        client,
        "patch",
        f"/api/v1/visits/{visit.public_id}/schedule",
        {
            "state_version": inquiry.state_version,
            "synthetic_technician_id": str(technician.public_id),
            "preferred_date": "2026-08-12",
            "confirmed_date": "2026-08-13",
        },
        key="visit-schedule-success",
    )
    assert scheduled.status_code == 200, scheduled.json()
    schedule = scheduled.json()["data"]["resource"]["schedule"]
    assert schedule["schedule_status"] == "SCHEDULING"
    assert schedule["preferred_date"] == "2026-08-12"
    assert schedule["confirmed_date"] == "2026-08-13"
    assert schedule["synthetic_technician_id"] == str(
        technician.public_id
    )
    assert scheduled.json()["data"]["resource"]["technician"] == {
        "is_synthetic": True,
        "technician_id": str(technician.public_id),
        "display_name": technician.full_name,
        "phone": technician.phone,
    }
    inquiry.refresh_from_db()

    confirmed = request(
        client,
        "post",
        f"/api/v1/visits/{visit.public_id}/confirm",
        {"state_version": inquiry.state_version},
        key="visit-confirm-success",
    )
    assert confirmed.status_code == 200, confirmed.json()
    assert confirmed.json()["data"]["status"] == "VISIT_SCHEDULED"
    assert confirmed.json()["data"]["resource"]["schedule"][
        "schedule_status"
    ] == "CONFIRMED"

    inquiry.refresh_from_db()
    visit.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.VISIT_SCHEDULED
    assert inquiry.state_version == 9
    assert visit.status == Visit.Status.CONFIRMED
    assert visit.preferred_date.isoformat() == "2026-08-12"
    assert visit.confirmed_date.isoformat() == "2026-08-13"
    assert visit.scheduled_at is not None
    assert list(
        TransitionHistory.objects.filter(
            visit=visit,
        )
        .order_by("state_version")
        .values_list("from_state", "to_state", "state_version")
    ) == [
        (None, "ASSIGNING", 1),
        ("ASSIGNING", "SCHEDULING", 2),
        ("SCHEDULING", "CONFIRMED", 3),
    ]


def test_update_visit_schedule_supports_revisit_transition_tr_inq_028():
    consultant = create_user(612, role=User.Role.CONSULTANT)
    original_technician = create_user(613, role=User.Role.TECHNICIAN)
    replacement_technician = create_user(614, role=User.Role.TECHNICIAN)
    inquiry = create_inquiry(
        12,
        consultant=consultant,
        status=Inquiry.Status.REVISIT_REQUIRED,
        state_version=9,
    )
    now = timezone.now()
    visit = Visit.objects.create(
        visit_code="VIS-REVISIT-TR-INQ-028",
        inquiry=inquiry,
        technician=original_technician,
        status=Visit.Status.FOLLOW_UP_REQUIRED,
        requested_at=now - timedelta(days=3),
        scheduled_at=now - timedelta(days=2),
        preferred_date=date(2026, 8, 9),
        confirmed_date=date(2026, 8, 9),
        visit_reason="첫 방문 이후 추가 점검이 필요합니다.",
        usage_guidance_status=Inquiry.UsageGuidanceStatus.PARTIAL_STOP,
        handoff_payload=visit_handoff(),
        started_at=now - timedelta(days=1, hours=2),
        completed_at=now - timedelta(days=1),
        confirmed_cause="필터 체결 불량",
        action_taken="필터 재체결 및 추가 방문 권고",
        state_version=4,
        idempotency_key="revisit-original-visit",
        correlation_id=uuid4(),
        data_classification=Visit.DataClassification.SYNTHETIC,
    )
    result = VisitResult.objects.create(
        visit=visit,
        cause_category_code="FILTER",
        inspection_summary="필터 체결 상태를 점검했습니다.",
        action_summary="재체결 후 추가 확인이 필요합니다.",
        resolved_on_site=False,
        revisit_required=True,
        revisit_reason="유량 재확인이 필요합니다.",
        submitted_by=original_technician,
        idempotency_key="revisit-original-result",
        completed_at=now - timedelta(days=1),
    )
    unassigned_consultant = create_user(
        615,
        role=User.Role.CONSULTANT,
    )
    denied = request(
        client_for(unassigned_consultant),
        "patch",
        f"/api/v1/visits/{visit.public_id}/schedule",
        {
            "state_version": inquiry.state_version,
            "synthetic_technician_id": str(
                replacement_technician.public_id
            ),
            "preferred_date": "2026-08-15",
            "confirmed_date": "2026-08-16",
        },
        key="revisit-schedule-unassigned",
    )

    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    inquiry.refresh_from_db()
    visit.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.REVISIT_REQUIRED
    assert inquiry.state_version == 9
    assert visit.status == Visit.Status.FOLLOW_UP_REQUIRED
    assert not IdempotencyRecord.objects.filter(
        actor=unassigned_consultant,
        operation_id="updateVisitSchedule",
    ).exists()

    response = request(
        client_for(consultant),
        "patch",
        f"/api/v1/visits/{visit.public_id}/schedule",
        {
            "state_version": inquiry.state_version,
            "synthetic_technician_id": str(
                replacement_technician.public_id
            ),
            "preferred_date": "2026-08-15",
            "confirmed_date": "2026-08-16",
        },
        key="revisit-schedule-tr-inq-028",
    )

    assert response.status_code == 200, response.json()
    inquiry.refresh_from_db()
    visit.refresh_from_db()
    result.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.VISIT_SCHEDULING
    assert inquiry.state_version == 10
    assert visit.status == Visit.Status.SCHEDULING
    assert visit.technician == replacement_technician
    assert visit.preferred_date == date(2026, 8, 15)
    assert visit.confirmed_date == date(2026, 8, 16)
    assert visit.scheduled_at is None
    assert visit.started_at is None
    assert visit.completed_at is None
    assert visit.confirmed_cause is None
    assert visit.action_taken is None
    assert result.submitted_by == original_technician
    assert result.revisit_required is True
    assert result.revisit_reason == "유량 재확인이 필요합니다."
    assert TransitionHistory.objects.filter(
        inquiry=inquiry,
        event_code="UPDATE_VISIT_SCHEDULE",
        from_state=Inquiry.Status.REVISIT_REQUIRED,
        to_state=Inquiry.Status.VISIT_SCHEDULING,
        state_version=10,
    ).exists()
    assert TransitionHistory.objects.filter(
        visit=visit,
        event_code="UPDATE_VISIT_SCHEDULE",
        from_state=Visit.Status.FOLLOW_UP_REQUIRED,
        to_state=Visit.Status.SCHEDULING,
        state_version=5,
    ).exists()
    history_count = TransitionHistory.objects.filter(
        event_code="UPDATE_VISIT_SCHEDULE",
        inquiry=inquiry,
    ).count()
    replay_body = {
        "state_version": 9,
        "synthetic_technician_id": str(
            replacement_technician.public_id
        ),
        "preferred_date": "2026-08-15",
        "confirmed_date": "2026-08-16",
    }
    replay = request(
        client_for(consultant),
        "patch",
        f"/api/v1/visits/{visit.public_id}/schedule",
        replay_body,
        key="revisit-schedule-tr-inq-028",
    )
    stale = request(
        client_for(consultant),
        "patch",
        f"/api/v1/visits/{visit.public_id}/schedule",
        replay_body,
        key="revisit-schedule-stale-version",
    )

    assert replay.status_code == 200
    assert replay.json()["data"]["idempotent_replay"] is True
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STATE-CONFLICT-01"
    inquiry.refresh_from_db()
    visit.refresh_from_db()
    assert inquiry.state_version == 10
    assert visit.state_version == 5
    assert TransitionHistory.objects.filter(
        event_code="UPDATE_VISIT_SCHEDULE",
        inquiry=inquiry,
    ).count() == history_count


def test_visit_not_needed_completes_without_creating_visit():
    _consultant, client, inquiry, consultation = prepare_visit_review(20)

    response = request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/visit-not-needed",
        {
            "state_version": inquiry.state_version,
            "reason_code": "MONITORING_AGREED",
            "reason_detail": "고객과 원격 모니터링에 합의했습니다.",
        },
        key="visit-not-needed",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["data"]["status"] == "COMPLETION_PENDING"
    assert Visit.objects.filter(inquiry=inquiry).count() == 0
    inquiry.refresh_from_db()
    consultation.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.COMPLETION_PENDING
    assert consultation.status == Consultation.Status.COMPLETED
    assert consultation.outcome == Consultation.Outcome.COMPLETED_NO_VISIT
    assert consultation.visit_not_needed_reason_code == "MONITORING_AGREED"


def test_consultation_role_assignment_state_and_header_boundaries():
    consultant = create_user(30, role=User.Role.CONSULTANT)
    other = create_user(31, role=User.Role.CONSULTANT)
    customer = create_user(32, role=User.Role.CUSTOMER)
    inquiry = create_inquiry(30, consultant=consultant)
    path = f"/api/v1/inquiries/{inquiry.public_id}/start-consultation"

    anonymous = request(
        APIClient(),
        "post",
        path,
        {"state_version": 2},
        key="role-anonymous",
    )
    wrong_role = request(
        client_for(customer),
        "post",
        path,
        {"state_version": 2},
        key="role-customer",
    )
    other_assignee = request(
        client_for(other),
        "post",
        path,
        {"state_version": 2},
        key="role-other-consultant",
    )
    missing_header = request(
        client_for(consultant),
        "post",
        path,
        {"state_version": 2},
        key=None,
    )
    stale = request(
        client_for(consultant),
        "post",
        path,
        {"state_version": 1},
        key="role-stale",
    )

    assert anonymous.status_code == 401
    assert wrong_role.status_code == 403
    assert other_assignee.status_code == 404
    assert missing_header.status_code == 422
    assert stale.status_code == 409
    assert stale.json()["error"]["details"] == {
        "current_status": "CONSULTATION_REQUIRED",
        "current_state_version": 2,
        "allowed_actions": ["START_CONSULTATION"],
    }
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert Consultation.objects.filter(inquiry=inquiry).count() == 0


def test_same_key_different_request_returns_duplicate_event():
    consultant = create_user(40, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(40, consultant=consultant)
    client = client_for(consultant)

    first = start_consultation(client, inquiry, key="consult-key-conflict")
    second = request(
        client,
        "post",
        f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        {"state_version": 3},
        key="consult-key-conflict",
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE-EVENT-01"
    assert Consultation.objects.filter(inquiry=inquiry).count() == 1


def test_consultation_save_rejects_null_not_allowed_by_openapi():
    consultant = create_user(41, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(41, consultant=consultant)
    client = client_for(consultant)
    started = start_consultation(client, inquiry, key="consult-null-start")
    assert started.status_code == 200
    inquiry.refresh_from_db()

    response = request(
        client,
        "patch",
        f"/api/v1/inquiries/{inquiry.public_id}/consultation-summary",
        {
            "state_version": inquiry.state_version,
            "consultation_note": None,
        },
        key="consult-null-save",
    )

    assert response.status_code == 422
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_IN_PROGRESS
    assert inquiry.state_version == 3


def test_visit_schedule_rejects_non_synthetic_technician_and_missing_date():
    _consultant, client, inquiry, _consultation = prepare_visit_review(50)
    created = create_visit_request(client, inquiry, key="visit-invalid-create")
    assert created.status_code == 200
    inquiry.refresh_from_db()
    visit = Visit.objects.get(inquiry=inquiry)

    invalid_technician = create_user(650, role=User.Role.TECHNICIAN)
    invalid_technician.is_synthetic = False
    invalid_technician.save(update_fields=["is_synthetic"])
    invalid_schedule = request(
        client,
        "patch",
        f"/api/v1/visits/{visit.public_id}/schedule",
        {
            "state_version": inquiry.state_version,
            "synthetic_technician_id": str(invalid_technician.public_id),
            "preferred_date": "2026-08-12",
            "confirmed_date": "2026-08-13",
        },
        key="visit-invalid-technician",
    )
    assert invalid_schedule.status_code == 422
    assert invalid_schedule.json()["error"]["code"] == (
        "INVALID_VISIT_SCHEDULE"
    )

    technician = create_user(651, role=User.Role.TECHNICIAN)
    schedule_without_date = request(
        client,
        "patch",
        f"/api/v1/visits/{visit.public_id}/schedule",
        {
            "state_version": inquiry.state_version,
            "synthetic_technician_id": str(technician.public_id),
            "preferred_date": "2026-08-12",
            "confirmed_date": None,
        },
        key="visit-no-confirmed-date",
    )
    assert schedule_without_date.status_code == 200
    inquiry.refresh_from_db()

    confirm = request(
        client,
        "post",
        f"/api/v1/visits/{visit.public_id}/confirm",
        {"state_version": inquiry.state_version},
        key="visit-confirm-missing-date",
    )
    assert confirm.status_code == 422
    assert confirm.json()["error"]["code"] == (
        "CONFIRMED_VISIT_DATE_REQUIRED"
    )
    visit.refresh_from_db()
    assert visit.status == Visit.Status.SCHEDULING


def test_consultation_start_rolls_back_all_writes_on_late_failure(
    monkeypatch,
):
    consultant = create_user(60, role=User.Role.CONSULTANT)
    inquiry = create_inquiry(60, consultant=consultant)

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-late-database-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = start_consultation(
        client_for(consultant),
        inquiry,
        key="consult-rollback",
    )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-late-database-error" not in response.content.decode()
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
    assert inquiry.state_version == 2
    assert Consultation.objects.filter(inquiry=inquiry).count() == 0
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == 0
    assert IdempotencyRecord.objects.filter(actor=consultant).count() == 0


def test_visit_creation_rolls_back_visit_handoff_history_and_key(
    monkeypatch,
):
    consultant, client, inquiry, _consultation = prepare_visit_review(70)
    before_version = inquiry.state_version
    before_history = TransitionHistory.objects.filter(inquiry=inquiry).count()

    def fail_completion(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("private-visit-database-error")

    monkeypatch.setattr(
        WorkflowRepository,
        "complete_idempotency_record",
        fail_completion,
    )
    response = create_visit_request(
        client,
        inquiry,
        key="visit-create-rollback",
    )

    assert response.status_code == 500
    assert "private-visit-database-error" not in response.content.decode()
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.VISIT_REVIEW_PENDING
    assert inquiry.state_version == before_version
    assert Visit.objects.filter(inquiry=inquiry).count() == 0
    assert HandoffReport.objects.filter(inquiry=inquiry).count() == 0
    assert TransitionHistory.objects.filter(inquiry=inquiry).count() == (
        before_history
    )
    assert not IdempotencyRecord.objects.filter(
        actor=consultant,
        operation_id="createVisitRequest",
    ).exists()


def test_all_nine_routes_are_registered_and_reject_unknown_ids():
    consultant = create_user(80, role=User.Role.CONSULTANT)
    client = client_for(consultant)
    unknown = uuid4()
    state_body = {"state_version": 1}
    cases = (
        (
            "post",
            f"/api/v1/inquiries/{unknown}/start-consultation",
            state_body,
        ),
        (
            "patch",
            f"/api/v1/inquiries/{unknown}/consultation-summary",
            {"state_version": 1, "summary": "unknown"},
        ),
        (
            "post",
            f"/api/v1/inquiries/{unknown}/consultation-summary/confirm",
            state_body,
        ),
        (
            "post",
            f"/api/v1/inquiries/{unknown}/complete-consultation",
            state_body,
        ),
        (
            "post",
            f"/api/v1/inquiries/{unknown}/visit-review",
            {
                "state_version": 1,
                "reason_code": "PHYSICAL_INSPECTION_REQUIRED",
            },
        ),
        (
            "post",
            f"/api/v1/inquiries/{unknown}/visits",
            {
                "state_version": 1,
                "visit_reason": "unknown inquiry",
                "preferred_date": None,
                "usage_guidance_status": "NORMAL",
                "handoff": visit_handoff(),
            },
        ),
        (
            "post",
            f"/api/v1/inquiries/{unknown}/visit-not-needed",
            {
                "state_version": 1,
                "reason_code": "MONITORING_AGREED",
            },
        ),
        (
            "patch",
            f"/api/v1/visits/{unknown}/schedule",
            {
                "state_version": 1,
                "synthetic_technician_id": str(uuid4()),
                "preferred_date": None,
                "confirmed_date": None,
            },
        ),
        (
            "post",
            f"/api/v1/visits/{unknown}/confirm",
            state_body,
        ),
    )

    responses = [
        request(
            client,
            method,
            path,
            body,
            key=f"unknown-{index}",
        )
        for index, (method, path, body) in enumerate(cases)
    ]
    assert [response.status_code for response in responses] == [404] * 9
    assert {
        response.json()["error"]["code"] for response in responses
    } == {"RESOURCE_NOT_FOUND"}


@pytest.mark.django_db(transaction=True)
def test_postgresql_visit_lock_targets_visit_row_only_for_null_technician():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")

    _consultant, _client, inquiry, _consultation = (
        prepare_confirmed_consultation(
            sequence=90,
            result_code=Consultation.Outcome.VISIT_REQUIRED,
        )
    )
    visit = Visit.objects.create(
        visit_code="VIS-POSTGRES-LOCK-090",
        inquiry=inquiry,
        technician=None,
        status=Visit.Status.ASSIGNING,
        requested_at=timezone.now(),
        preferred_date=date(2026, 8, 12),
        confirmed_date=None,
        visit_reason="기사 미배정 방문 Lock 회귀 검증",
        usage_guidance_status="PARTIAL_STOP",
        handoff_payload=visit_handoff(),
        state_version=1,
        idempotency_key="visit-postgresql-lock-090",
        correlation_id=uuid4(),
        data_classification=Visit.DataClassification.SYNTHETIC,
    )

    with transaction.atomic():
        latest = VisitRepository.lock_latest(inquiry)
        by_public_id = VisitRepository.lock_by_public_id(
            inquiry=inquiry,
            visit_public_id=visit.public_id,
        )

    assert latest is not None
    assert latest.pk == visit.pk
    assert latest.technician is None
    assert by_public_id is not None
    assert by_public_id.pk == visit.pk
    assert by_public_id.technician is None
