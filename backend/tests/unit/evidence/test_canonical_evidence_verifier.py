"""Fail-closed tests for the Backend state-transition evidence verifier."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date

import pytest

from apps.accounts.models import CustomerProfile, User
from apps.evidence.services.evidence_validation_service import (
    BASELINE_CORPUS_PATH,
    verify_canonical_evidence,
)
from apps.inquiries.models import Inquiry
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription


pytestmark = pytest.mark.django_db


def baseline_row() -> dict:
    with BASELINE_CORPUS_PATH.open(encoding="utf-8") as source:
        return json.loads(next(line for line in source if line.strip()))


def reference_from(row: dict) -> dict:
    return {
        "document_title": row["section_title"],
        "document_version": row["version"],
        "page": row["page_start"],
        "page_refs": row["page_refs"],
        "chunk_id": row["chunk_id"],
        "official_url": row["source_url"],
        "summary": row["chunk_text"],
        "similarity_score": 0.9,
        "verification_status": "official_verified",
    }


def inquiry_for(row: dict, *, sequence: int, model_code: str | None = None):
    owner = User.objects.create_user(
        username=f"CANONICAL-EVIDENCE-{sequence:03d}",
        full_name=f"Canonical evidence owner {sequence}",
        role_code=User.Role.CUSTOMER,
    )
    profile = CustomerProfile.objects.create(
        user=owner,
        customer_no=f"CANONICAL-EVIDENCE-{sequence:03d}",
        customer_name=f"Canonical evidence owner {sequence}",
    )
    product = ProductModel.objects.create(
        model_code=model_code or row["exact_sales_code"],
        model_name=f"Canonical product {sequence}",
        generation_code=row["product_generation"],
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"CANONICAL-EVIDENCE-{sequence:03d}",
        customer=profile,
        product_model=product,
        serial_no=f"CANONICAL-EVIDENCE-SERIAL-{sequence:03d}",
        status_code=CustomerSubscription.Status.ACTIVE,
        started_on=date(2026, 8, 1),
    )
    return Inquiry.objects.create(
        subscription=subscription,
        initiated_by=owner,
        channel_code=Inquiry.Channel.MOBILE,
        raw_text="정수기에서 물이 나오지 않습니다.",
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=2,
    )


def test_exact_baseline_reference_returns_canonical_evidence_id():
    row = baseline_row()
    inquiry = inquiry_for(row, sequence=1)

    result = verify_canonical_evidence([reference_from(row)], inquiry)

    assert result == [row["evidence_id"]]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chunk_id", "UNKNOWN-CHUNK"),
        ("document_title", "tampered title"),
        ("page", 999),
        ("page_refs", [999]),
        ("official_url", "https://invalid.example"),
        ("summary", "tampered summary"),
        ("verification_status", "team_verified"),
    ],
)
def test_tampered_reference_is_rejected(field, value):
    row = baseline_row()
    inquiry = inquiry_for(row, sequence=10)
    reference = reference_from(row)
    reference[field] = value

    assert verify_canonical_evidence([reference], inquiry) == []


def test_wrong_product_and_partial_reference_sets_are_rejected():
    row = baseline_row()
    wrong_product = inquiry_for(
        row,
        sequence=20,
        model_code="OTHER-MODEL",
    )
    reference = reference_from(row)

    assert verify_canonical_evidence([reference], wrong_product) == []

    exact_product = inquiry_for(row, sequence=21)
    tampered = deepcopy(reference)
    tampered["summary"] = "tampered"
    assert verify_canonical_evidence(
        [reference, tampered],
        exact_product,
    ) == []
