"""Minimal non-public Evidence projection for T-028B preparation."""

from __future__ import annotations

from typing import Any

from apps.evidence.models import EvidenceLink
from apps.evidence.repositories.evidence_repository import EvidenceRepository
from apps.evidence.services.evidence_validation_service import (
    PREPARATION_STATUS,
    SUPPORTED_CONSUMER_ROLES,
    EvidenceValidationService,
    UnsafeEvidenceProjection,
)


class EvidenceCardService:
    """Build safe candidates without defining an Endpoint or public DTO."""

    @classmethod
    def prepare_for_authorized_inquiry(
        cls,
        *,
        inquiry_id: int,
        consumer_role: str,
    ) -> list[dict[str, Any]]:
        """Project links after the calling use case has authorized the inquiry."""

        if consumer_role not in SUPPORTED_CONSUMER_ROLES:
            raise UnsafeEvidenceProjection("unsupported consumer role")
        return [
            cls.prepare_link(link=link, consumer_role=consumer_role)
            for link in EvidenceRepository.verified_links_for_inquiry(
                inquiry_id=inquiry_id,
            )
        ]

    @staticmethod
    def prepare_link(
        *,
        link: EvidenceLink,
        consumer_role: str,
    ) -> dict[str, Any]:
        """Use immutable snapshots only; never traverse raw source or trace data."""

        if (
            link.is_verified is not True
            or link.verified_by_id is None
            or link.verified_at is None
        ):
            raise UnsafeEvidenceProjection("unverified evidence is prohibited")
        payload = {
            "projection_status": PREPARATION_STATUS,
            "consumer_role": consumer_role,
            "evidence_id": str(link.public_id),
            "document": {
                "document_code": link.document_code_snapshot,
                "title": link.document_title_snapshot,
                "revision": link.revision_label_snapshot,
                "source_org": link.source_org_snapshot,
                "landing_url": link.official_source_url_snapshot,
            },
            "location": {
                "page_no": link.page_no_snapshot,
                "section": link.section_snapshot,
            },
            "evidence_summary": link.evidence_summary,
            "product_model_codes": list(
                link.product_model_codes_snapshot
            ),
            "verification": {"is_verified": True},
        }
        EvidenceValidationService.validate_preparation_candidate(payload)
        return payload
