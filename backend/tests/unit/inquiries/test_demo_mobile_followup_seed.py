"""Regression tests for the official Mobile follow-up smoke fixture."""

from __future__ import annotations

from io import StringIO
import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.inquiries.management.commands.seed_demo_mobile_followup import (
    DEMO_CHOICE_OPTIONS,
    DEMO_CHOICE_QUESTION_PUBLIC_ID,
    DEMO_FREE_TEXT_QUESTION_PUBLIC_ID,
    DEMO_INQUIRY_PUBLIC_ID,
    DEMO_INQUIRY_SCENARIO_CODE,
    DEMO_INITIAL_STATE_VERSION,
    DEMO_SUBSCRIPTION_CONTRACT_NO,
    DEMO_SUBSCRIPTION_PUBLIC_ID,
)
from apps.inquiries.models import FollowUpAnswer, Inquiry, InquiryQA
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.subscriptions.repositories.subscription_repository import (
    SUPPORTED_PRODUCT_MODEL_CODE,
)


pytestmark = pytest.mark.django_db


def seed_json() -> dict:
    output = StringIO()
    call_command("seed_demo_mobile_followup", "--json", stdout=output)
    return json.loads(output.getvalue())


def test_mobile_followup_seed_requires_demo_accounts():
    with pytest.raises(CommandError, match="seed_demo_accounts"):
        call_command("seed_demo_mobile_followup")


def test_mobile_followup_seed_is_idempotent_and_emits_crosswalk():
    call_command("seed_demo_accounts", verbosity=0)

    first = seed_json()
    second = seed_json()

    assert second == first
    assert first == {
        "customer_id": first["customer_id"],
        "demo_user_code": "DEMO-CUSTOMER-001",
        "fixture": "mobile-followup-v1",
        "inquiry_id": str(DEMO_INQUIRY_PUBLIC_ID),
        "product_model_code": SUPPORTED_PRODUCT_MODEL_CODE,
        "questions": [
            {
                "question_code": "MOBILE-FOLLOWUP-FREE-TEXT-001",
                "question_id": str(DEMO_FREE_TEXT_QUESTION_PUBLIC_ID),
                "question_type": "FREE_TEXT",
            },
            {
                "question_code": "MOBILE-FOLLOWUP-SINGLE-CHOICE-001",
                "question_id": str(DEMO_CHOICE_QUESTION_PUBLIC_ID),
                "question_type": "SINGLE_CHOICE",
            },
        ],
        "state_version": DEMO_INITIAL_STATE_VERSION,
        "subscription_id": str(DEMO_SUBSCRIPTION_PUBLIC_ID),
    }
    assert ProductModel.objects.filter(
        model_code=SUPPORTED_PRODUCT_MODEL_CODE,
        generation_code="D",
        is_supported_mvp=True,
        is_active=True,
    ).count() == 1
    assert CustomerSubscription.objects.filter(
        contract_no=DEMO_SUBSCRIPTION_CONTRACT_NO,
        public_id=DEMO_SUBSCRIPTION_PUBLIC_ID,
        status_code=CustomerSubscription.Status.ACTIVE,
    ).count() == 1
    inquiry = Inquiry.objects.get(
        scenario_code=DEMO_INQUIRY_SCENARIO_CODE
    )
    assert inquiry.public_id == DEMO_INQUIRY_PUBLIC_ID
    assert inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
    assert inquiry.state_version == DEMO_INITIAL_STATE_VERSION
    questions = list(inquiry.qa_entries.order_by("sequence_no"))
    assert [question.public_id for question in questions] == [
        DEMO_FREE_TEXT_QUESTION_PUBLIC_ID,
        DEMO_CHOICE_QUESTION_PUBLIC_ID,
    ]
    assert questions[0].answer_type_code == "FREE_TEXT"
    assert questions[0].question_options == []
    assert questions[1].answer_type_code == "SINGLE_CHOICE"
    assert questions[1].question_options == DEMO_CHOICE_OPTIONS
    assert FollowUpAnswer.objects.count() == 0


def test_mobile_followup_seed_refuses_destructive_answer_reset():
    call_command("seed_demo_accounts", verbosity=0)
    seed_json()
    inquiry = Inquiry.objects.get(
        scenario_code=DEMO_INQUIRY_SCENARIO_CODE
    )
    question = InquiryQA.objects.get(
        public_id=DEMO_FREE_TEXT_QUESTION_PUBLIC_ID
    )
    FollowUpAnswer.objects.create(
        question=question,
        answered_by=inquiry.initiated_by,
        answer_text="Fixture has been consumed.",
        accepted_state_version=DEMO_INITIAL_STATE_VERSION,
    )

    with pytest.raises(CommandError, match="이미 소비"):
        call_command("seed_demo_mobile_followup")

    assert FollowUpAnswer.objects.filter(question=question).count() == 1


def test_mobile_followup_seed_rejects_inactive_supported_product():
    call_command("seed_demo_accounts", verbosity=0)
    ProductModel.objects.create(
        model_code=SUPPORTED_PRODUCT_MODEL_CODE,
        model_name="Conflicting inactive product",
        is_supported_mvp=True,
        is_active=False,
    )

    with pytest.raises(CommandError, match="활성 지원 상태"):
        call_command("seed_demo_mobile_followup")

    assert not Inquiry.objects.filter(
        scenario_code=DEMO_INQUIRY_SCENARIO_CODE
    ).exists()


def test_mobile_followup_seed_normalizes_existing_baseline_generation():
    call_command("seed_demo_accounts", verbosity=0)
    product = ProductModel.objects.create(
        model_code=SUPPORTED_PRODUCT_MODEL_CODE,
        model_name="Legacy active smoke product",
        generation_code="DEMO-G1",
        is_supported_mvp=True,
        is_active=True,
    )

    seed_json()

    product.refresh_from_db()
    assert product.generation_code == "D"
