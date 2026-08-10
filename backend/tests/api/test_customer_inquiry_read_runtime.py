"""Runtime checks for CUSTOMER-owned inquiry and question reads."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import FollowUpAnswer, Inquiry, InquiryQA
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def create_user(sequence: int, *, role: str = User.Role.CUSTOMER) -> User:
    user = User.objects.create_user(
        username=f"CUSTOMER-INQUIRY-READ-{role}-{sequence:03d}",
        full_name=f"Customer inquiry read {role} {sequence}",
        role_code=role,
        employee_no=(None if role == User.Role.CUSTOMER else f"EMP-{sequence:03d}"),
        is_synthetic=True,
    )
    if role == User.Role.CUSTOMER:
        CustomerProfile.objects.create(
            user=user,
            customer_no=f"CUSTOMER-INQUIRY-READ-{sequence:03d}",
            customer_name=f"합성 고객 {sequence}",
            phone=f"010-9999-{sequence:04d}",
            address_line1="고객 읽기 API에 노출하면 안 되는 주소",
            is_synthetic=True,
        )
    return user


def create_subscription(owner: User, sequence: int) -> CustomerSubscription:
    product = ProductModel.objects.create(
        model_code=f"CUSTOMER-READ-MODEL-{sequence:03d}",
        model_name=f"고객 조회 제품 {sequence}",
        generation_code="D",
        manufacturer="SK매직",
        features={"private": "must-not-leak"},
        is_supported_mvp=True,
        is_active=True,
    )
    return CustomerSubscription.objects.create(
        contract_no=f"CUSTOMER-READ-CONTRACT-{sequence:03d}",
        customer=owner.customer_profile,
        product_model=product,
        serial_no=f"CUSTOMER-READ-SERIAL-{sequence:03d}",
        management_type_code=CustomerSubscription.ManagementType.VISIT_CARE,
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 7, 1),
        installation_address="고객 조회 API에 노출하면 안 되는 설치 주소",
    )


def create_inquiry(
    owner: User,
    sequence: int,
    *,
    public_id: UUID | None = None,
) -> Inquiry:
    return Inquiry.objects.create(
        public_id=public_id or uuid4(),
        inquiry_code=f"CUSTOMER-READ-INQ-{sequence:03d}",
        subscription=create_subscription(owner, sequence),
        initiated_by=owner,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="고객 원문은 Snapshot에 노출하지 않습니다.",
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=2,
        risk_level_code=Inquiry.RiskLevel.CAUTION,
        evidence_ids=["INTERNAL-EVIDENCE-ID"],
    )


def authenticated_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_customer_snapshot_returns_exact_owned_projection(
    django_assert_num_queries,
):
    owner = create_user(1)
    inquiry = create_inquiry(owner, 1)

    with django_assert_num_queries(1):
        response = authenticated_client(owner).get(
            f"/api/v1/me/inquiries/{inquiry.public_id}"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["metadata"]["correlation_id"] == response[
        "X-Correlation-ID"
    ]
    data = payload["data"]
    assert data == {
        "inquiry_id": str(inquiry.public_id),
        "status_code": Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        "state_version": 2,
        "subscription_id": str(inquiry.subscription.public_id),
        "product": {
            "model_code": inquiry.subscription.product_model.model_code,
        },
        "updated_at": inquiry.updated_at.isoformat().replace("+00:00", "Z"),
    }

    serialized = str(data)
    for forbidden in (
        inquiry.inquiry_code,
        inquiry.raw_text,
        inquiry.subscription.contract_no,
        inquiry.subscription.serial_no,
        inquiry.subscription.installation_address,
        owner.customer_profile.customer_name,
        owner.customer_profile.phone,
        "INTERNAL-EVIDENCE-ID",
        "features",
        "risk_level_code",
        "assigned_user",
    ):
        assert forbidden not in serialized


def test_customer_questions_return_only_unanswered_public_metadata(
    django_assert_num_queries,
):
    owner = create_user(10)
    inquiry = create_inquiry(owner, 10)
    choice = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="FILTER_REPLACEMENT",
        question_text="필터를 최근 교체하셨나요?",
        answer_type_code="SINGLE_CHOICE",
        answer_payload={
            "question_options": ["최근 교체함", "교체하지 않음"],
            "target_field": "filter_replacement",
        },
        asked_by_type_code="RULE",
    )
    free_text = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=2,
        question_code="OCCURRENCE_TIME",
        question_text="언제부터 증상이 시작되었나요?",
        answer_type_code="FREE_TEXT",
        asked_by_type_code="RULE",
    )
    third_question = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=3,
        question_code="ANSWER_RELATION_INDEPENDENT",
        question_text="별도 답변 관계와 분리된 질문입니다.",
        answer_type_code="FREE_TEXT",
        asked_by_type_code="RULE",
    )
    FollowUpAnswer.objects.create(
        question=third_question,
        answered_by=owner,
        answer_text="이미 제출한 답변",
    )
    unsupported = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=4,
        question_code="UNSUPPORTED_MULTI",
        question_text="복수 선택은 아직 공개하지 않습니다.",
        answer_type_code="MULTI_CHOICE",
        answer_payload={"question_options": ["A", "B"]},
        asked_by_type_code="RULE",
    )
    optionless = InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=5,
        question_code="OPTIONLESS_SINGLE",
        question_text="선택지가 없는 단일 선택 질문",
        answer_type_code="SINGLE_CHOICE",
        asked_by_type_code="RULE",
    )

    with django_assert_num_queries(2):
        response = authenticated_client(owner).get(
            f"/api/v1/me/inquiries/{inquiry.public_id}/questions"
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["inquiry_id"] == str(inquiry.public_id)
    assert data["state_version"] == 2
    assert data["questions"] == [
        {
            "question_id": str(choice.public_id),
            "question_type": "SINGLE_CHOICE",
            "prompt": "필터를 최근 교체하셨나요?",
            "required": True,
            "options": [
                {"value": "최근 교체함", "label": "최근 교체함"},
                {"value": "교체하지 않음", "label": "교체하지 않음"},
            ],
        },
        {
            "question_id": str(free_text.public_id),
            "question_type": "FREE_TEXT",
            "prompt": "언제부터 증상이 시작되었나요?",
            "required": True,
            "options": [],
        },
    ]
    serialized = str(data)
    for forbidden in (
        "target_field",
        "filter_replacement",
        "customer_answer",
        "question_code",
        "source_ai_run",
        str(third_question.public_id),
        str(unsupported.public_id),
        str(optionless.public_id),
        "이미 제출한 답변",
    ):
        assert forbidden not in serialized


def test_customer_reads_use_same_404_for_other_owner_missing_and_invalid_uuid():
    owner = create_user(20)
    other = create_user(21)
    other_inquiry = create_inquiry(other, 20)
    client = authenticated_client(owner)

    paths = (
        f"/api/v1/me/inquiries/{other_inquiry.public_id}",
        f"/api/v1/me/inquiries/{uuid4()}",
        "/api/v1/me/inquiries/not-a-uuid",
        f"/api/v1/me/inquiries/{other_inquiry.public_id}/questions",
        f"/api/v1/me/inquiries/{uuid4()}/questions",
        "/api/v1/me/inquiries/not-a-uuid/questions",
    )
    responses = [client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [404] * 6
    assert {
        response.json()["error"]["code"] for response in responses
    } == {"RESOURCE_NOT_FOUND"}
    assert {
        str(
            {
                "success": response.json()["success"],
                "data": response.json()["data"],
                "error": response.json()["error"],
            }
        )
        for response in responses
    } == {
        str(
            {
                "success": False,
                "data": None,
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "요청한 대상을 찾을 수 없습니다.",
                    "details": {},
                },
            }
        )
    }


def test_customer_read_auth_role_and_query_boundaries():
    owner = create_user(30)
    consultant = create_user(31, role=User.Role.CONSULTANT)
    technician = create_user(32, role=User.Role.TECHNICIAN)
    inquiry = create_inquiry(owner, 30)
    paths = (
        f"/api/v1/me/inquiries/{inquiry.public_id}",
        f"/api/v1/me/inquiries/{inquiry.public_id}/questions",
    )

    for path in paths:
        assert APIClient().get(path).status_code == 401
        assert authenticated_client(consultant).get(path).status_code == 403
        assert authenticated_client(technician).get(path).status_code == 403
        invalid_query = authenticated_client(owner).get(f"{path}?expand=all")
        assert invalid_query.status_code == 422
        assert invalid_query.json()["error"]["code"] == "VALIDATION_ERROR"

    owner.is_active = False
    for path in paths:
        assert authenticated_client(owner).get(path).status_code == 403


def test_customer_reads_are_side_effect_free():
    owner = create_user(40)
    inquiry = create_inquiry(owner, 40)
    InquiryQA.objects.create(
        inquiry=inquiry,
        sequence_no=1,
        question_code="SIDE_EFFECT_CHECK",
        question_text="읽기 전용 확인 질문",
        asked_by_type_code="RULE",
    )
    before_inquiry = Inquiry.objects.values(
        "status_code",
        "state_version",
        "updated_at",
        "assigned_user_id",
        "assigned_role_code",
    ).get(pk=inquiry.pk)
    before_qa = list(
        InquiryQA.objects.filter(inquiry=inquiry).values(
            "public_id",
            "question_text",
            "answer_payload",
        )
    )

    client = authenticated_client(owner)
    assert client.get(
        f"/api/v1/me/inquiries/{inquiry.public_id}"
    ).status_code == 200
    assert client.get(
        f"/api/v1/me/inquiries/{inquiry.public_id}/questions"
    ).status_code == 200

    assert Inquiry.objects.values(
        "status_code",
        "state_version",
        "updated_at",
        "assigned_user_id",
        "assigned_role_code",
    ).get(pk=inquiry.pk) == before_inquiry
    assert list(
        InquiryQA.objects.filter(inquiry=inquiry).values(
            "public_id",
            "question_text",
            "answer_payload",
        )
    ) == before_qa
