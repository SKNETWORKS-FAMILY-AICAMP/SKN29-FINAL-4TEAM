"""T-028B non-public safe projection and rejection tests."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.evidence.models import EvidenceLink
from apps.evidence.services.evidence_card_service import EvidenceCardService
from apps.evidence.services.evidence_validation_service import (
    PREPARATION_STATUS,
    PROHIBITED_FIELDS,
    EvidenceValidationService,
    UnsafeEvidenceProjection,
)
from tests.unit.evidence.test_evidence_link_model import (
    create_verifier,
    link_values,
)


pytestmark = pytest.mark.django_db


def create_verified_link(sequence: int) -> EvidenceLink:
    verifier = create_verifier(
        sequence,
        role_code=User.Role.OPERATOR,
    )
    link = EvidenceLink(
        **link_values(
            sequence,
            is_verified=True,
            verified_by=verifier,
            verified_at=timezone.now(),
        )
    )
    link.full_clean()
    link.save()
    return link


def collect_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for nested in value.values()
            for key in collect_keys(nested)
        }
    if isinstance(value, list):
        return {
            key
            for nested in value
            for key in collect_keys(nested)
        }
    return set()


@pytest.mark.parametrize(
    "consumer_role",
    ["CUSTOMER", "CONSULTANT", "TECHNICIAN"],
)
def test_verified_snapshot_projects_same_minimum_safe_candidate(consumer_role):
    link = create_verified_link(sequence=201)

    payload = EvidenceCardService.prepare_link(
        link=link,
        consumer_role=consumer_role,
    )

    assert payload["projection_status"] == PREPARATION_STATUS
    assert payload["consumer_role"] == consumer_role
    assert payload["evidence_id"] == str(link.public_id)
    assert payload["document"] == {
        "document_code": link.document_code_snapshot,
        "title": link.document_title_snapshot,
        "revision": link.revision_label_snapshot,
        "source_org": link.source_org_snapshot,
        "landing_url": link.official_source_url_snapshot,
    }
    assert payload["location"] == {
        "page_no": link.page_no_snapshot,
        "section": link.section_snapshot,
    }
    assert payload["evidence_summary"] == link.evidence_summary
    assert payload["product_model_codes"] == (
        link.product_model_codes_snapshot
    )
    assert payload["verification"] == {"is_verified": True}
    assert not (collect_keys(payload) & PROHIBITED_FIELDS)

    rendered = json.dumps(payload, ensure_ascii=False)
    assert link.cited_text_snapshot not in rendered
    assert link.document_sha256_snapshot not in rendered


def test_repository_path_returns_only_verified_links_for_authorized_inquiry():
    verified = create_verified_link(sequence=202)
    inquiry = verified.inquiry
    unverified = EvidenceLink.objects.create(
        **link_values(
            203,
            inquiry=inquiry,
            target_kind="consultation",
        )
    )

    payloads = EvidenceCardService.prepare_for_authorized_inquiry(
        inquiry_id=inquiry.pk,
        consumer_role="CUSTOMER",
    )

    assert [payload["evidence_id"] for payload in payloads] == [
        str(verified.public_id)
    ]
    assert str(unverified.public_id) not in json.dumps(payloads)


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("source_path", "C:/private/manual.pdf"),
        ("manual_page_text", "raw source page"),
        ("retrieval_text", "private retrieval query"),
        ("similarity_score", 0.99),
        ("vector_score", 0.99),
        ("prompt", "private prompt"),
        ("raw_text", "private symptom"),
        ("verified_by", "internal-user-id"),
    ],
)
def test_prohibited_field_is_rejected_even_when_nested(
    field_name,
    field_value,
):
    link = create_verified_link(sequence=204)
    payload = EvidenceCardService.prepare_link(
        link=link,
        consumer_role="CUSTOMER",
    )
    unsafe = deepcopy(payload)
    unsafe["document"][field_name] = field_value

    with pytest.raises(
        UnsafeEvidenceProjection,
        match="prohibited fields",
    ):
        EvidenceValidationService.validate_preparation_candidate(unsafe)


def test_unapproved_extra_field_and_public_status_fail_closed():
    link = create_verified_link(sequence=205)
    payload = EvidenceCardService.prepare_link(
        link=link,
        consumer_role="CONSULTANT",
    )

    extra = deepcopy(payload)
    extra["risk_level"] = "danger"
    with pytest.raises(
        UnsafeEvidenceProjection,
        match="not approved",
    ):
        EvidenceValidationService.validate_preparation_candidate(extra)

    public = deepcopy(payload)
    public["projection_status"] = "PUBLIC"
    with pytest.raises(
        UnsafeEvidenceProjection,
        match="public projection is not approved",
    ):
        EvidenceValidationService.validate_preparation_candidate(public)


def test_unverified_link_unsafe_url_and_unknown_role_are_rejected():
    unverified = EvidenceLink.objects.create(**link_values(206))
    with pytest.raises(
        UnsafeEvidenceProjection,
        match="unverified evidence",
    ):
        EvidenceCardService.prepare_link(
            link=unverified,
            consumer_role="CUSTOMER",
        )

    verified = create_verified_link(sequence=207)
    payload = EvidenceCardService.prepare_link(
        link=verified,
        consumer_role="CUSTOMER",
    )
    payload["document"]["landing_url"] = "file:///private/manual.pdf"
    with pytest.raises(
        UnsafeEvidenceProjection,
        match="landing_url is unsafe",
    ):
        EvidenceValidationService.validate_preparation_candidate(payload)

    with pytest.raises(
        UnsafeEvidenceProjection,
        match="unsupported consumer role",
    ):
        EvidenceCardService.prepare_for_authorized_inquiry(
            inquiry_id=verified.inquiry_id,
            consumer_role="OPERATOR",
        )
