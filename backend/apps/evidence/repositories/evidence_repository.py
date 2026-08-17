"""Verified EvidenceLink reads for the T-028B preparation boundary."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.evidence.models import EvidenceLink


class EvidenceRepository:
    """Return only verified snapshots after the caller authorizes an inquiry."""

    @staticmethod
    def verified_links_for_inquiry(
        *,
        inquiry_id: int,
    ) -> QuerySet[EvidenceLink]:
        return (
            EvidenceLink.objects.filter(
                inquiry_id=inquiry_id,
                is_verified=True,
                verified_by__isnull=False,
                verified_at__isnull=False,
            )
            .order_by("display_order", "public_id")
        )
