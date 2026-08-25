"""Runtime checks for assigned-consultant inquiry reads."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.care.models import CareRecord
from apps.consultations.models import Consultation
from apps.inquiries.models import (
    FollowUpAnswer,
    Guidance,
    Inquiry,
    InquiryQA,
    SymptomAssessment,
)
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.visits.models import Visit
from apps.workflow.models import IdempotencyRecord, TransitionHistory


pytestmark = pytest.mark.django_db


def create_user(sequence: int, *, role: str) -> User:
    employee_no = (
        None
        if role == User.Role.CUSTOMER
        else f"CONSULTANT-READ-EMP-{sequence:03d}"
    )
    user = User.objects.create_user(
        username=f"CONSULTANT-READ-{role}-{sequence:03d}",
        full_name=f"Consultant read {role} {sequence}",
        role_code=role,
        employee_no=employee_no,
        is_synthetic=True,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"CONSULTANT-READ-CUSTOMER-{sequence:03d}",
            customer_name=f"합성고객 {sequence:02d}",
            phone=f"010-0000-{sequence:04d}",
            address_line1="목록과 상세에 노출하면 안 되는 주소",
            is_synthetic=True,
        )
    return user


def create_subscription(owner: User, sequence: int) -> CustomerSubscription:
    product = ProductModel.objects.create(
        model_code=f"CONSULTANT-READ-MODEL-{sequence:03d}",
        model_name=f"상담 조회 제품 {sequence}",
        generation_code="D",
        manufacturer="SK매직",
        features={"internal": "must-not-leak"},
        is_supported_mvp=True,
        is_active=True,
    )
    return CustomerSubscription.objects.create(
        contract_no=f"CONSULTANT-READ-CONTRACT-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"CONSULTANT-READ-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 7, 1),
        installation_address="노출 금지 설치 주소",
    )


def create_assigned_inquiry(
    *,
    sequence: int,
    owner: User,
    consultant: User,
    status: str = Inquiry.Status.CONSULTATION_REQUIRED,
    raw_text: str = "출수량이 평소보다 감소했습니다.",
    risk: str | None = None,
    public_id: UUID | None = None,
) -> Inquiry:
    inquiry = Inquiry.objects.create(
        public_id=public_id or uuid4(),
        inquiry_code=f"SYN-INQ-{sequence:04d}",
        subscription=create_subscription(owner, sequence),
        initiated_by=owner,
        assigned_user=consultant,
        assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text=raw_text,
        risk_level_code=risk,
        status_code=status,
        state_version=2,
    )
    return inquiry


def create_assessment(
    inquiry: Inquiry,
    *,
    risk: str,
    priority: str,
) -> SymptomAssessment:
    usage_status = {
        "danger": "TOTAL_STOP",
        "caution": "PENDING_CONSULTATION",
        "general": "NORMAL",
    }[risk]
    return SymptomAssessment.objects.create(
        inquiry=inquiry,
        assessment_version=1,
        ruleset_version="consultant-read-v1",
        risk_level_code=risk,
        priority_code=priority,
        usage_guidance_status=usage_status,
        requires_consultation=risk != "general",
        reason="합성 위험도 평가",
        rule_result={"risk_level": risk, "priority": priority},
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_validated_guidance(
    inquiry: Inquiry,
    *,
    sequence: int,
    restricted_functions,
    run_status: str = AIRun.Status.SUCCEEDED,
    schema_status: str = AIRun.SchemaValidationStatus.PASSED,
    review_status: str = "PENDING",
) -> Guidance:
    now = timezone.now()
    payload = {
        "usage_guidance": {
            "guidance_status": "PARTIAL_STOP",
            "message": "Validated AI guidance for consultant review.",
            "restricted_functions": restricted_functions,
            "next_actions": ["Request a consultation."],
        }
    }
    persisted_payload = (
        payload
        if schema_status == AIRun.SchemaValidationStatus.PASSED
        and run_status
        in {AIRun.Status.SUCCEEDED, AIRun.Status.NO_EVIDENCE}
        else None
    )
    ai_run = AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.ANALYZE_SYMPTOM,
        response_schema_version="3.0.0",
        model_provider="local",
        model_name="consultant-read-test",
        prompt_version="consultant-read-v1",
        input_payload={"inquiry_id": str(inquiry.public_id)},
        input_sha256="a" * 64,
        idempotency_key=f"consultant-read-ai-{sequence:03d}",
        validated_output_payload=persisted_payload,
        schema_validation_status_code=schema_status,
        schema_validation_errors=(
            []
            if schema_status == AIRun.SchemaValidationStatus.PASSED
            else [{"path": "usage_guidance", "message": "invalid"}]
        ),
        status_code=run_status,
        error_code=(
            "AI-FAILED-01" if run_status == AIRun.Status.FAILED else None
        ),
        error_message=(
            "Synthetic failed run for fail-closed projection test."
            if run_status == AIRun.Status.FAILED
            else None
        ),
        started_at=now,
        completed_at=now,
        correlation_id=uuid4(),
    )
    return Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=sequence,
        review_status_code=review_status,
        title="Validated AI guidance",
        summary_text=payload["usage_guidance"]["message"],
        evidence_sufficiency_code="SUFFICIENT",
        requires_consultation=True,
        generated_by_ai_run=ai_run,
    )


def test_consultant_list_returns_only_assigned_synthetic_projection(
    django_assert_max_num_queries,
):
    consultant = create_user(1, role=User.Role.CONSULTANT)
    other_consultant = create_user(2, role=User.Role.CONSULTANT)
    owner = create_user(3, role=User.Role.CUSTOMER)
    other_owner = create_user(4, role=User.Role.CUSTOMER)
    visible = create_assigned_inquiry(
        sequence=1,
        owner=owner,
        consultant=consultant,
        risk="caution",
    )
    create_assessment(
        visible,
        risk="caution",
        priority="consultation_recommended",
    )
    second_visible = create_assigned_inquiry(
        sequence=3,
        owner=owner,
        consultant=consultant,
        risk="general",
    )
    create_assessment(
        second_visible,
        risk="general",
        priority="general_guidance",
    )
    third_visible = create_assigned_inquiry(
        sequence=4,
        owner=owner,
        consultant=consultant,
        risk="danger",
    )
    create_assessment(
        third_visible,
        risk="danger",
        priority="general_guidance",
    )
    create_assigned_inquiry(
        sequence=2,
        owner=other_owner,
        consultant=other_consultant,
    )

    with django_assert_max_num_queries(5):
        response = authenticated_client(consultant).get(
            "/api/v1/inquiries"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["metadata"]["correlation_id"] == response[
        "X-Correlation-ID"
    ]
    data = payload["data"]
    assert data["page_info"] == {"page": 1, "size": 20, "total": 3}
    assert data["status_counts"] == {"CONSULTATION_REQUIRED": 3}
    assert len(data["items"]) == 3

    item = next(
        item
        for item in data["items"]
        if item["inquiry_id"] == str(visible.public_id)
    )
    assert set(item) == {
        "inquiry_id",
        "inquiry_code",
        "status",
        "state_version",
        "risk_level",
        "priority",
        "symptom_summary",
        "customer_display_name_masked",
        "product_model",
        "current_assignee_type",
        "received_at",
        "updated_at",
        "waiting_seconds",
        "allowed_actions",
    }
    assert item["inquiry_id"] == str(visible.public_id)
    assert item["risk_level"] == "caution"
    assert item["priority"] == "HIGH"
    assert item["customer_display_name_masked"] == "합*****3"
    assert item["product_model"] == visible.subscription.product_model.model_code
    assert item["current_assignee_type"] == "CONSULTANT"
    assert item["waiting_seconds"] >= 0
    assert [action["code"] for action in item["allowed_actions"]] == [
        "START_CONSULTATION"
    ]
    third_item = next(
        item
        for item in data["items"]
        if item["inquiry_id"] == str(third_visible.public_id)
    )
    assert third_item["risk_level"] == "danger"
    assert third_item["priority"] == "URGENT"

    serialized = str(item)
    for forbidden in (
        owner.customer_profile.phone,
        owner.customer_profile.address_line1,
        visible.subscription.contract_no,
        visible.subscription.serial_no,
        "installation_address",
        "features",
        "evidence",
    ):
        assert forbidden not in serialized


def test_consultant_list_filters_searches_sorts_and_paginates():
    consultant = create_user(10, role=User.Role.CONSULTANT)
    owner = create_user(11, role=User.Role.CUSTOMER)
    older = create_assigned_inquiry(
        sequence=10,
        owner=owner,
        consultant=consultant,
        status=Inquiry.Status.CONSULTATION_REQUIRED,
        raw_text="필터 검색 대상 증상",
    )
    urgent = create_assigned_inquiry(
        sequence=11,
        owner=owner,
        consultant=consultant,
        status=Inquiry.Status.CONSULTATION_IN_PROGRESS,
        raw_text="급수 밸브 확인",
    )
    create_assessment(older, risk="general", priority="general_guidance")
    create_assessment(urgent, risk="danger", priority="priority_consultation")
    now = timezone.now()
    Inquiry.objects.filter(pk=older.pk).update(
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
    )
    Inquiry.objects.filter(pk=urgent.pk).update(
        created_at=now - timedelta(minutes=30),
        updated_at=now - timedelta(minutes=10),
    )
    business_today = timezone.localtime(
        now,
        ZoneInfo("Asia/Seoul"),
    ).date()

    client = authenticated_client(consultant)
    response = client.get(
        "/api/v1/inquiries",
        {
            "status": [
                Inquiry.Status.CONSULTATION_REQUIRED,
                Inquiry.Status.CONSULTATION_IN_PROGRESS,
            ],
            "risk_level": ["general", "danger"],
            "priority": ["NORMAL", "URGENT"],
            "from": (business_today - timedelta(days=1)).isoformat(),
            "to": business_today.isoformat(),
            "sort": "RISK_DESC",
            "page": 1,
            "size": 1,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page_info"] == {"page": 1, "size": 1, "total": 2}
    assert data["items"][0]["inquiry_id"] == str(urgent.public_id)
    assert data["status_counts"] == {
        "CONSULTATION_IN_PROGRESS": 1,
        "CONSULTATION_REQUIRED": 1,
    }

    search = client.get("/api/v1/inquiries", {"q": older.inquiry_code})
    assert search.status_code == 200
    assert [item["inquiry_id"] for item in search.json()["data"]["items"]] == [
        str(older.public_id)
    ]

    phone_search = client.get(
        "/api/v1/inquiries",
        {"q": owner.customer_profile.phone},
    )
    assert phone_search.status_code == 200
    assert phone_search.json()["data"]["items"] == []

    status_filter = client.get(
        "/api/v1/inquiries",
        {"status": Inquiry.Status.CONSULTATION_REQUIRED},
    )
    assert [
        item["inquiry_id"] for item in status_filter.json()["data"]["items"]
    ] == [str(older.public_id)]

    risk_filter = client.get(
        "/api/v1/inquiries",
        {"risk_level": "danger"},
    )
    assert [
        item["inquiry_id"] for item in risk_filter.json()["data"]["items"]
    ] == [str(urgent.public_id)]

    priority_filter = client.get(
        "/api/v1/inquiries",
        {"priority": "NORMAL"},
    )
    assert [
        item["inquiry_id"]
        for item in priority_filter.json()["data"]["items"]
    ] == [str(older.public_id)]

    out_of_range = client.get(
        "/api/v1/inquiries",
        {"page": 99, "size": 1},
    )
    assert out_of_range.status_code == 200
    assert out_of_range.json()["data"]["items"] == []
    assert out_of_range.json()["data"]["page_info"]["total"] == 2


def test_consultant_list_auth_role_and_query_validation_boundaries():
    consultant = create_user(20, role=User.Role.CONSULTANT)
    customer = create_user(21, role=User.Role.CUSTOMER)

    assert APIClient().get("/api/v1/inquiries").status_code == 401
    assert authenticated_client(customer).get("/api/v1/inquiries").status_code == 403

    consultant.is_active = False
    assert authenticated_client(consultant).get("/api/v1/inquiries").status_code == 403
    consultant.is_active = True

    client = authenticated_client(consultant)
    invalid_queries = (
        {"assignee": "ALL"},
        {"page": 0},
        {"size": 101},
        {"status": "UNKNOWN"},
        {"risk_level": "unknown"},
        {"priority": "CRITICAL"},
        {"sort": "UNKNOWN"},
        {"from": "2026-08-10", "to": "2026-08-09"},
    )
    for query in invalid_queries:
        response = client.get("/api/v1/inquiries", query)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    full_date_range = client.get(
        "/api/v1/inquiries",
        {"from": "0001-01-01", "to": "9999-12-31"},
    )
    assert full_date_range.status_code == 200


def test_consultant_detail_returns_closed_assigned_projection(
    django_assert_max_num_queries,
):
    consultant = create_user(30, role=User.Role.CONSULTANT)
    owner = create_user(31, role=User.Role.CUSTOMER)
    inquiry = create_assigned_inquiry(
        sequence=30,
        owner=owner,
        consultant=consultant,
        risk="caution",
    )
    CustomerProfile.objects.filter(pk=owner.customer_profile.pk).update(
        customer_name="A" * 100,
    )
    owner.customer_profile.refresh_from_db()
    create_assessment(
        inquiry,
        risk="caution",
        priority="consultation_recommended",
    )
    free_text_question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="FILTER_FLOW",
        question_text="Did the flow decrease after replacement?",
    )
    FollowUpAnswer.objects.create(
        question=free_text_question,
        answer_text="Yes, the flow decreased.",
        answered_by=owner,
    )
    selected_question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=2,
        question_code="INTERNAL_OPTIONS",
        question_text="Which symptom option did you select?",
        answer_type_code="SINGLE_CHOICE",
        answer_payload={
            "question_options": ["internal-a", "internal-b"],
            "target_field": "internal_target",
        },
    )
    FollowUpAnswer.objects.create(
        question=selected_question,
        answer_payload={"selected_option": "internal-a"},
        answered_by=owner,
    )
    Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=1,
        review_status_code="CONFIRMED",
        title="Consultant handoff",
        summary_text="Keep usage paused until the consultant review.",
        evidence_sufficiency_code="SUFFICIENT",
        requires_consultation=True,
    )
    Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=2,
        review_status_code="PENDING",
        title="Unreviewed draft",
        summary_text="This unreviewed draft must not be projected.",
        evidence_sufficiency_code="PENDING",
        requires_consultation=True,
    )
    create_validated_guidance(
        inquiry,
        sequence=3,
        restricted_functions=[
            " HOT_WATER ",
            "",
            None,
            "ICE",
            "X" * 121,
        ],
    )
    CareRecord.objects.create(
        care_code="CONSULTANT-READ-CARE-029",
        subscription=inquiry.subscription,
        inquiry=inquiry,
        care_type_code=CareRecord.CareType.PERIODIC_CHECK,
        status_code=CareRecord.Status.COMPLETED,
        performed_on=date(2026, 7, 15),
        result_code=CareRecord.Result.NORMAL,
        source_code=CareRecord.Source.IMPORT,
    )
    CareRecord.objects.create(
        care_code="CONSULTANT-READ-CARE-030",
        subscription=inquiry.subscription,
        inquiry=inquiry,
        care_type_code=CareRecord.CareType.PERIODIC_CHECK,
        status_code=CareRecord.Status.COMPLETED,
        performed_on=date(2026, 8, 1),
        result_code=CareRecord.Result.NORMAL,
        source_code=CareRecord.Source.IMPORT,
    )
    TransitionHistory.objects.create(
        target_type_code=TransitionHistory.TargetType.INQUIRY,
        inquiry=inquiry,
        actor=owner,
        changed_by_type_code=TransitionHistory.ChangedByType.USER,
        event_code="REQUIRE_CONSULTATION",
        from_state=Inquiry.Status.AI_GUIDANCE,
        to_state=Inquiry.Status.CONSULTATION_REQUIRED,
        state_version=2,
        correlation_id=uuid4(),
        idempotency_key="consultant-read-detail-030",
    )

    with django_assert_max_num_queries(8):
        response = authenticated_client(consultant).get(
            f"/api/v1/inquiries/{inquiry.public_id}"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["metadata"]["correlation_id"] == response[
        "X-Correlation-ID"
    ]
    data = payload["data"]
    assert set(data) == {
        "inquiry",
        "customer",
        "product_and_care",
        "symptom_and_questionnaire",
        "guidance_and_actions",
        "consultation",
        "visit",
        "state_history",
        "workflow",
        "section_errors",
    }
    inquiry_projection = data["inquiry"]
    assert set(inquiry_projection) == {
        "inquiry_id",
        "inquiry_code",
        "status",
        "state_version",
        "risk_level",
        "priority",
        "received_at",
        "updated_at",
    }
    assert {
        key: value
        for key, value in inquiry_projection.items()
        if key not in {"received_at", "updated_at"}
    } == {
        "inquiry_id": str(inquiry.public_id),
        "inquiry_code": inquiry.inquiry_code,
        "status": Inquiry.Status.CONSULTATION_REQUIRED,
        "state_version": 2,
        "risk_level": "caution",
        "priority": "HIGH",
    }
    assert parse_datetime(inquiry_projection["received_at"]) == (
        inquiry.created_at
    )
    assert parse_datetime(inquiry_projection["updated_at"]) == (
        inquiry.updated_at
    )
    assert data["customer"] == {
        "is_synthetic": True,
        "display_name": "A" * 80,
        "phone": "010-****-0031",
        "phone_masked": "010-****-0031",
    }
    assert data["product_and_care"] == {
        "product_model": inquiry.subscription.product_model.model_code,
        "product_model_name": inquiry.subscription.product_model.model_name,
        "subscription_status": CustomerSubscription.Status.ACTIVE,
        "management_type": CustomerSubscription.ManagementType.VISIT_CARE,
        "recent_care_date": "2026-08-01",
    }
    assert data["symptom_and_questionnaire"] == {
        "symptom_summary": inquiry.raw_text,
        "answers": [
            {
                "question_code": "FILTER_FLOW",
                "question_text": "Did the flow decrease after replacement?",
                "answer": "Yes, the flow decreased.",
            },
            {
                "question_code": "INTERNAL_OPTIONS",
                "question_text": "Which symptom option did you select?",
                "answer": "internal-a",
            },
        ],
    }
    assert data["guidance_and_actions"] == {
        "usage_guidance_status": "PENDING_CONSULTATION",
        "usage_guidance_display_label": "상담 확인 필요",
        "usage_guidance_message": (
            "Validated AI guidance for consultant review."
        ),
        "restricted_functions": ["HOT_WATER", "ICE", "X" * 120],
    }
    assert data["consultation"] is None
    assert data["visit"] is None
    assert data["section_errors"] == []
    assert data["state_history"][0]["from_status"] == "AI_GUIDANCE"
    assert data["state_history"][0]["to_status"] == (
        "CONSULTATION_REQUIRED"
    )
    assert data["state_history"][0]["actor_role"] == "CUSTOMER"
    assert data["workflow"]["status"] == "CONSULTATION_REQUIRED"
    assert data["workflow"]["state_version"] == 2
    assert [
        action["code"] for action in data["workflow"]["allowed_actions"]
    ] == ["START_CONSULTATION"]

    serialized = str(data)
    for forbidden in (
        owner.customer_profile.phone,
        owner.customer_profile.address_line1,
        inquiry.subscription.contract_no,
        inquiry.subscription.serial_no,
        inquiry.subscription.installation_address,
        "features",
        "evidence_ids",
        "source_correlation_id",
        "idempotency_key",
        "internal-b",
        "internal_target",
    ):
        assert forbidden not in serialized


def test_consultant_detail_projects_latest_synthetic_visit():
    consultant = create_user(32, role=User.Role.CONSULTANT)
    owner = create_user(33, role=User.Role.CUSTOMER)
    technician = create_user(34, role=User.Role.TECHNICIAN)
    technician.phone = "010-9999-0034"
    technician.save(update_fields=["phone"])
    inquiry = create_assigned_inquiry(
        sequence=32,
        owner=owner,
        consultant=consultant,
        status=Inquiry.Status.VISIT_SCHEDULING,
    )
    visit = Visit.objects.create(
        visit_code="CONSULTANT-READ-VISIT-032",
        inquiry=inquiry,
        technician=technician,
        status=Visit.Status.SCHEDULING,
        requested_at=timezone.now(),
        preferred_date=date(2026, 8, 20),
        usage_guidance_status=Inquiry.UsageGuidanceStatus.PARTIAL_STOP,
        state_version=1,
        idempotency_key="consultant-read-visit-032",
        correlation_id=uuid4(),
        data_classification=Visit.DataClassification.SYNTHETIC,
    )

    response = authenticated_client(consultant).get(
        f"/api/v1/inquiries/{inquiry.public_id}"
    )

    assert response.status_code == 200
    assert response.json()["data"]["visit"] == {
        "visit_id": str(visit.public_id),
        "inquiry_id": str(inquiry.public_id),
        "schedule": {
            "preferred_date": "2026-08-20",
            "confirmed_date": None,
            "schedule_status": Visit.Status.SCHEDULING,
            "synthetic_technician_id": str(technician.public_id),
        },
        "technician": {
            "is_synthetic": True,
            "technician_id": str(technician.public_id),
            "display_name": technician.full_name,
            "phone": technician.phone,
        },
    }


@pytest.mark.parametrize(
    ("status", "display_label"),
    (
        (Inquiry.UsageGuidanceStatus.NORMAL, "정상 사용 가능"),
        (Inquiry.UsageGuidanceStatus.PARTIAL_STOP, "일부 기능 사용 중단"),
        (Inquiry.UsageGuidanceStatus.TOTAL_STOP, "제품 사용 중단"),
        (Inquiry.UsageGuidanceStatus.PENDING_CONSULTATION, "상담 확인 필요"),
    ),
)
def test_consultant_detail_projects_official_guidance_display_label(
    status,
    display_label,
):
    consultant = create_user(70, role=User.Role.CONSULTANT)
    owner = create_user(71, role=User.Role.CUSTOMER)
    inquiry = create_assigned_inquiry(
        sequence=70,
        owner=owner,
        consultant=consultant,
    )
    Inquiry.objects.filter(pk=inquiry.pk).update(
        usage_guidance_status=status,
    )

    response = authenticated_client(consultant).get(
        f"/api/v1/inquiries/{inquiry.public_id}"
    )

    assert response.status_code == 200
    guidance = response.json()["data"]["guidance_and_actions"]
    assert guidance["usage_guidance_status"] == status
    assert guidance["usage_guidance_display_label"] == display_label


def test_consultant_detail_projects_latest_persisted_consultation():
    consultant = create_user(35, role=User.Role.CONSULTANT)
    owner = create_user(36, role=User.Role.CUSTOMER)
    inquiry = create_assigned_inquiry(
        sequence=35,
        owner=owner,
        consultant=consultant,
        status=Inquiry.Status.CONSULTATION_IN_PROGRESS,
    )
    now = timezone.now()
    Consultation.objects.create(
        consultation_code="CONSULTANT-READ-CONSULT-OLD-035",
        inquiry=inquiry,
        sequence=1,
        consultant=consultant,
        status=Consultation.Status.COMPLETED,
        outcome=Consultation.Outcome.COMPLETED_NO_VISIT,
        summary="Old summary must not be projected.",
        state_version=2,
        idempotency_key="consultant-read-old-035",
        correlation_id=uuid4(),
        started_at=now - timedelta(minutes=2),
        completed_at=now - timedelta(minutes=1),
        created_at=now - timedelta(minutes=3),
        data_classification=Consultation.DataClassification.SYNTHETIC,
    )
    latest = Consultation.objects.create(
        consultation_code="CONSULTANT-READ-CONSULT-LATEST-035",
        inquiry=inquiry,
        sequence=2,
        consultant=consultant,
        status=Consultation.Status.IN_PROGRESS,
        outcome=Consultation.Outcome.PENDING,
        summary="Consultant edited summary.",
        ai_draft_summary="AI draft summary.",
        confirmed_summary="Consultant confirmed summary.",
        summary_confirmed_at=now,
        consultation_note="Persisted consultation note.",
        additional_check="Check the cold-water flow.",
        customer_guidance="Keep hot water paused.",
        usage_guidance_status=Inquiry.UsageGuidanceStatus.PARTIAL_STOP,
        state_version=4,
        idempotency_key="consultant-read-latest-035",
        correlation_id=uuid4(),
        started_at=now,
        created_at=now,
        data_classification=Consultation.DataClassification.SYNTHETIC,
    )

    response = authenticated_client(consultant).get(
        f"/api/v1/inquiries/{inquiry.public_id}"
    )

    assert response.status_code == 200
    assert response.json()["data"]["consultation"] == {
        "consultation_id": str(latest.public_id),
        "result_code": Consultation.Outcome.PENDING,
        "summary": {
            "ai_draft_summary": "AI draft summary.",
            "edited_summary": "Consultant edited summary.",
            "confirmed_summary": "Consultant confirmed summary.",
            "confirmed_at": now.isoformat(),
        },
        "consultation_note": "Persisted consultation note.",
        "additional_check": "Check the cold-water flow.",
        "customer_guidance": "Keep hot water paused.",
        "usage_guidance_status": "PARTIAL_STOP",
    }


@pytest.mark.parametrize(
    ("run_status", "schema_status"),
    (
        (AIRun.Status.FAILED, AIRun.SchemaValidationStatus.PASSED),
    ),
)
def test_consultant_detail_rejects_untrusted_ai_restrictions(
    run_status,
    schema_status,
):
    consultant = create_user(37, role=User.Role.CONSULTANT)
    owner = create_user(38, role=User.Role.CUSTOMER)
    inquiry = create_assigned_inquiry(
        sequence=37,
        owner=owner,
        consultant=consultant,
    )
    create_validated_guidance(
        inquiry,
        sequence=1,
        restricted_functions=["MALICIOUS_UNTRUSTED_RESTRICTION"],
        run_status=run_status,
        schema_status=schema_status,
        review_status="CONFIRMED",
    )
    guidance = Guidance.objects.get(inquiry=inquiry)
    ai_run = guidance.generated_by_ai_run
    AIRun.objects.filter(pk=ai_run.pk).update(
        validated_output_payload={
            "usage_guidance": {
                "restricted_functions": [
                    "MALICIOUS_UNTRUSTED_RESTRICTION"
                ]
            }
        }
    )

    response = authenticated_client(consultant).get(
        f"/api/v1/inquiries/{inquiry.public_id}"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["guidance_and_actions"]["restricted_functions"] == []
    assert "MALICIOUS_UNTRUSTED_RESTRICTION" not in str(data)


def test_consultant_detail_uses_same_404_for_all_invisible_inquiries():
    consultant = create_user(40, role=User.Role.CONSULTANT)
    other_consultant = create_user(41, role=User.Role.CONSULTANT)
    owner = create_user(42, role=User.Role.CUSTOMER)
    assigned_elsewhere = create_assigned_inquiry(
        sequence=40,
        owner=owner,
        consultant=other_consultant,
    )
    unassigned = create_assigned_inquiry(
        sequence=41,
        owner=owner,
        consultant=consultant,
    )
    Inquiry.objects.filter(pk=unassigned.pk).update(
        assigned_user=None,
        assigned_role_code=Inquiry.AssignedRole.NONE,
    )
    nonsynthetic_owner = create_user(43, role=User.Role.CUSTOMER)
    nonsynthetic_owner.is_synthetic = False
    nonsynthetic_owner.save(update_fields=["is_synthetic"])
    nonsynthetic = create_assigned_inquiry(
        sequence=42,
        owner=nonsynthetic_owner,
        consultant=consultant,
    )

    client = authenticated_client(consultant)
    paths = (
        f"/api/v1/inquiries/{assigned_elsewhere.public_id}",
        f"/api/v1/inquiries/{unassigned.public_id}",
        f"/api/v1/inquiries/{uuid4()}",
        "/api/v1/inquiries/not-a-uuid",
        f"/api/v1/inquiries/{nonsynthetic.public_id}",
    )
    responses = [client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [404] * 5
    assert {
        response.json()["error"]["code"] for response in responses
    } == {"RESOURCE_NOT_FOUND"}
    assert len(
        {
            str(
                {
                    "success": response.json()["success"],
                    "data": response.json()["data"],
                    "error": response.json()["error"],
                }
            )
            for response in responses
        }
    ) == 1


def test_consultant_detail_auth_and_role_boundaries():
    consultant = create_user(50, role=User.Role.CONSULTANT)
    customer = create_user(51, role=User.Role.CUSTOMER)
    inquiry = create_assigned_inquiry(
        sequence=50,
        owner=customer,
        consultant=consultant,
    )
    path = f"/api/v1/inquiries/{inquiry.public_id}"

    assert APIClient().get(path).status_code == 401
    assert authenticated_client(customer).get(path).status_code == 403
    assert authenticated_client(customer).head(
        "/api/v1/inquiries"
    ).status_code == 403
    assert authenticated_client(consultant).head(
        "/api/v1/inquiries"
    ).status_code == 200
    technician = create_user(52, role=User.Role.TECHNICIAN)
    operator = create_user(53, role=User.Role.OPERATOR)
    assert authenticated_client(technician).get(path).status_code == 403
    assert authenticated_client(operator).get(path).status_code == 403

    consultant.is_active = False
    assert authenticated_client(consultant).get(path).status_code == 403


def test_consultant_gets_do_not_mutate_domain_or_workflow_state():
    consultant = create_user(60, role=User.Role.CONSULTANT)
    owner = create_user(61, role=User.Role.CUSTOMER)
    inquiry = create_assigned_inquiry(
        sequence=60,
        owner=owner,
        consultant=consultant,
    )
    before_inquiry = Inquiry.objects.values(
        "status_code",
        "state_version",
        "updated_at",
        "assigned_user_id",
        "assigned_role_code",
    ).get(pk=inquiry.pk)
    before_counts = {
        "inquiries": Inquiry.objects.count(),
        "history": TransitionHistory.objects.count(),
        "idempotency": IdempotencyRecord.objects.count(),
        "guidance": Guidance.objects.count(),
        "care": CareRecord.objects.count(),
        "qa": InquiryQA.objects.count(),
    }

    client = authenticated_client(consultant)
    list_response = client.get("/api/v1/inquiries")
    detail_response = client.get(f"/api/v1/inquiries/{inquiry.public_id}")
    consultant_post = client.post(
        "/api/v1/inquiries",
        {},
        format="json",
    )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert consultant_post.status_code == 403
    assert Inquiry.objects.values(
        "status_code",
        "state_version",
        "updated_at",
        "assigned_user_id",
        "assigned_role_code",
    ).get(pk=inquiry.pk) == before_inquiry
    assert {
        "inquiries": Inquiry.objects.count(),
        "history": TransitionHistory.objects.count(),
        "idempotency": IdempotencyRecord.objects.count(),
        "guidance": Guidance.objects.count(),
        "care": CareRecord.objects.count(),
        "qa": InquiryQA.objects.count(),
    } == before_counts
