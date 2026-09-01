"""Verify every cause-ledger Evidence reference against Backend authority."""

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
from apps.evidence.services.evidence_reference_verifier import (
    APPROVED_EMBEDDING_MODEL,
    APPROVED_EMBEDDING_REVISION,
    EvidenceReferenceVerifier,
)


class ConsultationCauseLedgerEvidenceVerifier:
    """Fail closed unless all Ledger Evidence is canonical and current."""

    @classmethod
    def validation_errors(
        cls,
        ledger: dict[str, Any],
        inquiry: Any,
    ) -> list[str]:
        references = [
            reference
            for cause in ledger.get("causes", [])
            for reference in cause.get("evidence_refs", [])
        ]
        if not references:
            return []

        canonical_ids = [reference.get("chunk_id") for reference in references]
        if any(not isinstance(value, str) or not value for value in canonical_ids):
            return ["cause ledger evidence identity is invalid"]

        mappings = {
            mapping.canonical_chunk_id: mapping
            for mapping in AIChunkCrosswalk.objects.filter(
                canonical_chunk_id__in=set(canonical_ids),
                is_active=True,
                is_verified=True,
            )
            .select_related(
                "chunk__page__document__ingestion_batch",
                "model_scope__product_model",
                "verified_by",
            )
            .prefetch_related("source_pages__page")
        }
        if set(mappings) != set(canonical_ids):
            return ["cause ledger evidence is not mapped"]

        errors: list[str] = []
        for index, (reference, canonical_id) in enumerate(
            zip(references, canonical_ids, strict=True)
        ):
            if not cls._mapping_is_usable(
                mappings[canonical_id],
                reference,
                inquiry,
            ):
                errors.append(f"cause ledger evidence {index} is not canonical")
        return errors

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

        if (
            mapping.canonical_verification_status
            != EvidenceReferenceVerifier.APPROVED_CANONICAL_STATUS
            or mapping.verified_by_id is None
            or mapping.verified_at is None
            or mapping.embedding_model != APPROVED_EMBEDDING_MODEL
            or mapping.embedding_model_version != APPROVED_EMBEDDING_REVISION
        ):
            return False
        if (
            reference.get("document_id") != document.document_code
            or reference.get("model_code") != product.model_code
            or reference.get("index_version") != mapping.index_version
            or str(reference.get("chunk_set_sha256", "")).casefold()
            != mapping.chunk_set_sha256.casefold()
            or str(reference.get("source_file_sha256", "")).casefold()
            != mapping.source_file_sha256.casefold()
            or str(reference.get("content_sha256", "")).casefold()
            != mapping.chunk_text_sha256.casefold()
        ):
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
            or document.superseding_documents.filter(
                deleted_at__isnull=True
            ).exists()
            or not primary_page.is_rag_eligible
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
            or not product.is_active
            or not product.is_supported_mvp
            or inquiry.subscription.product_model_id != product.id
        ):
            return False
        if (
            mapping.source_file_sha256 != document.sha256_hash
            or mapping.chunk_text_sha256 != chunk.chunk_text_sha256
        ):
            return False

        source_pages = [item.page for item in mapping.source_pages.all()]
        if not source_pages or primary_page.id not in {
            page.id for page in source_pages
        }:
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


__all__ = ["ConsultationCauseLedgerEvidenceVerifier"]
