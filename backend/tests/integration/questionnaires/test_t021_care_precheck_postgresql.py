"""PostgreSQL row-lock tests for T-021 precheck mutation and link."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection

from apps.accounts.models import CustomerProfile, User
from apps.inquiries.models import Inquiry
from apps.inquiries.services.inquiry_service import InquiryService
from apps.products.models import ProductModel
from apps.questionnaires.models import QuestionnaireSession
from apps.questionnaires.services.questionnaire_service import (
    QuestionnaireService,
)
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import IdempotencyRecord, TransitionHistory
from common.exceptions.business import BusinessError


pytestmark = pytest.mark.django_db(transaction=True)


def create_owner_and_subscription(sequence: int):
    owner = User.objects.create_user(
        username=f"T021-PG-{sequence:03d}",
        password=None,
        full_name=f"T021 PG {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    customer = CustomerProfile.objects.create(
        user=owner,
        customer_no=f"T021-PG-CUS-{sequence:03d}",
        customer_name=f"T021 PG customer {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=f"T021-PG-PMD-{sequence:03d}",
        model_name=f"T021 PG product {sequence}",
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"T021-PG-SUB-{sequence:03d}",
        customer=customer,
        product_model=product,
        serial_no=f"T021-PG-SERIAL-{sequence:03d}",
        started_on=date(2026, 8, 1),
    )
    return owner, subscription


def start_session(owner, subscription, key: str):
    return QuestionnaireService.start(
        actor=owner,
        subscription_public_id=subscription.public_id,
        idempotency_key=key,
        correlation_id=uuid4(),
    )


def test_concurrent_same_version_save_allows_one_writer():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")
    owner, subscription = create_owner_and_subscription(1)
    started = start_session(owner, subscription, "t021-pg-save-start")
    session_id = started.data["questionnaire_session_id"]
    barrier = Barrier(2)

    def save(index: int):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return QuestionnaireService.save(
                actor=owner,
                session_public_id=session_id,
                state_version=1,
                answers={"WATER_FLOW": f"LOW-{index}"},
                idempotency_key=f"t021-pg-save-{index}",
                correlation_id=uuid4(),
            )
        except BusinessError as exc:
            return exc
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(save, range(2)))

    assert sorted(
        outcome.status_code
        for outcome in outcomes
    ) == [200, 409]
    session = QuestionnaireSession.objects.get(public_id=session_id)
    assert session.status_code == QuestionnaireSession.Status.IN_PROGRESS
    assert session.state_version == 2
    assert session.transition_history.count() == 2
    assert IdempotencyRecord.objects.filter(
        operation_id="saveCarePrecheck"
    ).count() == 1


def test_concurrent_inquiry_link_creates_one_inquiry():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock verification only")
    owner, subscription = create_owner_and_subscription(2)
    started = start_session(owner, subscription, "t021-pg-link-start")
    session_id = started.data["questionnaire_session_id"]
    QuestionnaireService.submit(
        actor=owner,
        session_public_id=session_id,
        state_version=1,
        answers={"WATER_FLOW": "LOW"},
        idempotency_key="t021-pg-link-submit",
        correlation_id=uuid4(),
    )
    barrier = Barrier(2)

    def create_inquiry(index: int):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return InquiryService.create(
                actor=owner,
                validated_data={
                    "subscription_id": subscription.public_id,
                    "channel_code": Inquiry.Channel.MOBILE,
                    "raw_text": "사전 문진 후 상담이 필요합니다.",
                    "questionnaire_session_id": session_id,
                },
                idempotency_key=f"t021-pg-link-inquiry-{index}",
                correlation_id=uuid4(),
            )
        except BusinessError as exc:
            return exc
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(create_inquiry, range(2)))

    assert sorted(
        outcome.status_code
        for outcome in outcomes
    ) == [201, 409]
    session = QuestionnaireSession.objects.get(public_id=session_id)
    assert session.inquiry_id is not None
    assert session.state_version == 3
    assert Inquiry.objects.count() == 1
    assert TransitionHistory.objects.filter(
        questionnaire_session=session,
        event_code="START_INQUIRY",
    ).count() == 1
