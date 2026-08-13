"""Fail-closed AI evidence reference verification for Backend runtime."""

from __future__ import annotations

from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.evidence.models import (
    AIChunkCrosswalk,
    ChunkEmbedding,
    DataQualityIssue,
)
from apps.evidence.models.chunk_embedding import EMBEDDING_DIMENSION


APPROVED_EMBEDDING_MODEL = "BAAI/bge-m3"
APPROVED_EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"


class EvidenceReferenceVerifier:
    """Translate verified AI canonical IDs into Backend public UUIDs."""

    APPROVED_CANONICAL_STATUS = "TEXT_AND_VISUAL_VERIFIED"
    APPROVED_REFERENCE_STATUS = "official_verified"

    @classmethod
    def verify(
        cls,
        references: list[dict[str, Any]],
        inquiry: Any,
    ) -> list[str]:
        """Return public UUIDs only when every supplied reference is valid."""

        if not references:
            return []
        canonical_ids = [
            reference.get("chunk_id")
            for reference in references
            if isinstance(reference, dict)
        ]
        if (
            len(canonical_ids) != len(references)
            or any(not isinstance(value, str) or not value for value in canonical_ids)
            or len(set(canonical_ids)) != len(canonical_ids)
        ):
            return []

        mappings = {
            mapping.canonical_chunk_id: mapping
            for mapping in AIChunkCrosswalk.objects.filter(
                canonical_chunk_id__in=canonical_ids,
                is_active=True,
                is_verified=True,
            )
            .select_related(
                "chunk__page__document",
                "model_scope__product_model",
            )
            .prefetch_related("source_pages__page")
        }
        if set(mappings) != set(canonical_ids):
            return []
        identity_signatures = {
            (
                mapping.identity_manifest_sha256,
                mapping.chunk_set_sha256,
                mapping.index_version,
                mapping.embedding_model,
                mapping.embedding_model_version,
            )
            for mapping in mappings.values()
        }
        if len(identity_signatures) != 1:
            return []
        identity_signature = next(iter(identity_signatures))
        if identity_signature[3:] != (
            APPROVED_EMBEDDING_MODEL,
            APPROVED_EMBEDDING_REVISION,
        ):
            return []

        verified_public_ids: list[str] = []
        for reference, canonical_id in zip(references, canonical_ids, strict=True):
            mapping = mappings[canonical_id]
            if not cls._mapping_is_usable(mapping, reference, inquiry):
                return []
            verified_public_ids.append(str(mapping.chunk.public_id))
        return verified_public_ids

    @classmethod
    def _mapping_is_usable(
        cls,
        mapping: AIChunkCrosswalk,
        reference: dict[str, Any],
        inquiry: Any,
    ) -> bool:
        chunk = mapping.chunk
        primary_page = chunk.page
        document = primary_page.document
        model_scope = mapping.model_scope
        product = model_scope.product_model

        if mapping.canonical_verification_status != cls.APPROVED_CANONICAL_STATUS:
            return False
        if reference.get("verification_status") != cls.APPROVED_REFERENCE_STATUS:
            return False
        if (
            not chunk.is_active
            or document.deleted_at is not None
            or document.dataset_scope_code != document.DatasetScope.MVP
            or document.status_code != "APPROVED"
            or document.ingestion_batch.dataset_scope_code
            != document.ingestion_batch.DatasetScope.MVP
            or document.ingestion_batch.status_code
            != document.ingestion_batch.Status.SUCCEEDED
            or document.superseding_documents.filter(deleted_at__isnull=True).exists()
        ):
            return False
        if (
            not primary_page.is_rag_eligible
            or primary_page.parse_status_code != "PARSED"
            or primary_page.review_status_code != "APPROVED"
            or primary_page.exclusion_reason is not None
        ):
            return False
        if (
            not model_scope.is_verified
            or model_scope.document_id != document.id
            or model_scope.verified_by_id is None
            or model_scope.verified_at is None
            or (
                model_scope.applicable_from is not None
                and model_scope.applicable_from > timezone.localdate()
            )
            or (
                model_scope.applicable_to is not None
                and model_scope.applicable_to < timezone.localdate()
            )
        ):
            return False
        if (
            not product.is_active
            or not product.is_supported_mvp
            or inquiry.subscription.product_model_id != product.id
        ):
            return False
        if mapping.source_file_sha256 != document.sha256_hash:
            return False
        if mapping.chunk_text_sha256 != chunk.chunk_text_sha256:
            return False

        source_pages = [item.page for item in mapping.source_pages.all()]
        if not source_pages or primary_page.id not in {page.id for page in source_pages}:
            return False
        if any(
            page.document_id != document.id
            or not page.is_rag_eligible
            or page.parse_status_code != "PARSED"
            or page.review_status_code != "APPROVED"
            or page.exclusion_reason is not None
            for page in source_pages
        ):
            return False

        expected_page_refs = [page.page_no for page in source_pages]
        supplied_page_refs = reference.get("page_refs")
        if supplied_page_refs is not None and supplied_page_refs != expected_page_refs:
            return False
        if reference.get("document_title") != document.title:
            return False
        if reference.get("document_version") not in (None, document.revision_label):
            return False
        if reference.get("page") not in (None, primary_page.page_no):
            return False
        if reference.get("official_url") not in (None, document.official_source_url):
            return False

        if DataQualityIssue.objects.filter(
            Q(ingestion_batch=document.ingestion_batch)
            | Q(document=document)
            | Q(page__in=source_pages)
            | Q(chunk=chunk),
            status_code__in=["OPEN", "IN_REVIEW"],
        ).exists():
            return False

        return ChunkEmbedding.objects.filter(
            chunk=chunk,
            embedding_model=mapping.embedding_model,
            embedding_model_version=mapping.embedding_model_version,
            embedding_dimension=EMBEDDING_DIMENSION,
            source_text_sha256=chunk.chunk_text_sha256,
            is_active=True,
        ).exists()
