"""Validate and synchronize the approved seven-row AI evidence crosswalk."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.evidence.models import (
    AIChunkCrosswalk,
    AIChunkCrosswalkPage,
    ChunkEmbedding,
    DataQualityIssue,
    DocumentChunk,
    DocumentModelScope,
    DocumentPage,
    SourceDocument,
)
from apps.evidence.models.chunk_embedding import EMBEDDING_DIMENSION
from apps.evidence.services.evidence_reference_verifier import (
    APPROVED_EMBEDDING_MODEL,
    APPROVED_EMBEDDING_REVISION,
)
from apps.products.models import ProductModel


REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_IDENTITY_MANIFEST = (
    REPOSITORY_ROOT / "ai" / "configs" / "canonical_evidence_identity.json"
)
DEFAULT_INDEX_MANIFEST = REPOSITORY_ROOT / "ai" / "configs" / "index_manifest.json"
APPROVED_CHUNK_COUNT = 7
APPROVED_IDENTITY_STATUS = "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING"
APPROVED_CANONICAL_STATUS = "TEXT_AND_VISUAL_VERIFIED"
APPLY_ADVISORY_LOCK_ID = 8_102_026_081_207


@dataclass(frozen=True, slots=True)
class CrosswalkPlanItem:
    canonical: dict[str, Any]
    document: SourceDocument
    pages: list[DocumentPage]
    chunk: DocumentChunk
    model_scope: DocumentModelScope
    embedding: ChunkEmbedding


class Command(BaseCommand):
    help = "Validate or atomically synchronize the seven approved AI chunk mappings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--identity-manifest",
            type=Path,
            default=DEFAULT_IDENTITY_MANIFEST,
        )
        parser.add_argument(
            "--index-manifest",
            type=Path,
            default=DEFAULT_INDEX_MANIFEST,
        )
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--verified-by", type=str)

    def handle(self, *args, **options):
        identity_path: Path = options["identity_manifest"]
        index_path: Path = options["index_manifest"]
        identity_bytes, identity = self._load_json(identity_path)
        _index_bytes, index = self._load_json(index_path)
        if not options["apply"]:
            try:
                with transaction.atomic():
                    plan = self._build_plan(identity=identity, index=index)
            except DatabaseError as exc:
                raise CommandError(
                    "The Backend evidence schema must be migrated before crosswalk validation."
                ) from exc
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY_RUN_READY mappings={len(plan)} changes=0"
                )
            )
            return

        username = options.get("verified_by")
        if not username:
            raise CommandError("--verified-by is required with --apply.")
        try:
            verifier = User.objects.get(
                username=username,
                role_code=User.Role.OPERATOR,
                is_active=True,
                is_synthetic=True,
            )
        except User.DoesNotExist as exc:
            raise CommandError(
                "The verifier must be an active synthetic OPERATOR."
            ) from exc

        manifest_digest = sha256(identity_bytes).hexdigest()
        try:
            with transaction.atomic():
                self._acquire_apply_lock()
                plan = self._build_plan(identity=identity, index=index)
                self._apply_plan(
                    plan=plan,
                    identity=identity,
                    index=index,
                    manifest_digest=manifest_digest,
                    verifier=verifier,
                )
        except DatabaseError as exc:
            raise CommandError(
                "Crosswalk synchronization failed and was rolled back."
            ) from exc
        self.stdout.write(
            self.style.SUCCESS(f"APPLIED mappings={len(plan)}")
        )

    @staticmethod
    def _load_json(path: Path) -> tuple[bytes, dict[str, Any]]:
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot load manifest: {path}") from exc
        if not isinstance(payload, dict):
            raise CommandError(f"Manifest root must be an object: {path}")
        return raw, payload

    def _build_plan(
        self,
        *,
        identity: dict[str, Any],
        index: dict[str, Any],
    ) -> list[CrosswalkPlanItem]:
        if identity.get("status") != APPROVED_IDENTITY_STATUS:
            raise CommandError("Canonical identity status is not approved for mapping.")
        if identity.get("schema_version") != "1.0.0":
            raise CommandError("Canonical identity schema version is unsupported.")
        if identity.get("index_version") != index.get("index_version"):
            raise CommandError("Identity and index versions do not match.")
        if index.get("model_name") != APPROVED_EMBEDDING_MODEL:
            raise CommandError("Index embedding model is not the approved BGE-M3 baseline.")
        if index.get("model_revision") != APPROVED_EMBEDDING_REVISION:
            raise CommandError("Index embedding revision is not the approved fixed baseline.")
        if index.get("index_type") != "exact_search":
            raise CommandError("Index search type must use the approved exact-search baseline.")
        chunks = identity.get("chunks")
        if not isinstance(chunks, list) or len(chunks) != APPROVED_CHUNK_COUNT:
            raise CommandError(
                f"Canonical identity must contain exactly {APPROVED_CHUNK_COUNT} chunks."
            )
        canonical_ids = [item.get("chunk_id") for item in chunks]
        if len(set(canonical_ids)) != APPROVED_CHUNK_COUNT:
            raise CommandError("Canonical chunk IDs must be unique.")
        if int(index.get("chunk_count", -1)) != APPROVED_CHUNK_COUNT:
            raise CommandError("Index manifest chunk_count does not match the approved set.")
        if self._lower_hash(identity.get("chunk_set_sha256")) != self._lower_hash(
            index.get("chunk_set_sha256")
        ):
            raise CommandError("Identity and index chunk-set hashes do not match.")
        if int(index.get("dimension", -1)) != EMBEDDING_DIMENSION:
            raise CommandError("Index embedding dimension must be 1024.")
        if any(
            item.get("verification_status") != APPROVED_CANONICAL_STATUS
            for item in chunks
        ):
            raise CommandError("Every canonical chunk must be text-and-visual verified.")

        plan: list[CrosswalkPlanItem] = []
        for canonical in chunks:
            plan.append(self._resolve_item(canonical=canonical, index=index))
        return plan

    def _resolve_item(
        self,
        *,
        canonical: dict[str, Any],
        index: dict[str, Any],
    ) -> CrosswalkPlanItem:
        canonical_id = canonical.get("chunk_id")
        document_code = canonical.get("document_id")
        model_code = canonical.get("model_code")
        page_refs = canonical.get("page_refs")
        if not isinstance(canonical_id, str) or not canonical_id.startswith("RAG-"):
            raise CommandError("Every canonical chunk requires an approved RAG-* ID.")
        if not isinstance(page_refs, list) or not page_refs:
            raise CommandError(f"{canonical_id}: page_refs must be non-empty.")

        try:
            document = (
                SourceDocument.objects.select_for_update()
                .select_related("ingestion_batch")
                .get(document_code=document_code)
            )
            product = ProductModel.objects.select_for_update().get(
                model_code=model_code
            )
        except (SourceDocument.DoesNotExist, ProductModel.DoesNotExist) as exc:
            raise CommandError(
                f"{canonical_id}: official document or product model is missing."
            ) from exc

        source_hash = self._lower_hash(canonical.get("source_file_sha256"))
        if (
            document.dataset_scope_code != SourceDocument.DatasetScope.MVP
            or document.status_code != "APPROVED"
            or document.deleted_at is not None
            or document.ingestion_batch.dataset_scope_code
            != document.ingestion_batch.DatasetScope.MVP
            or document.ingestion_batch.status_code
            != document.ingestion_batch.Status.SUCCEEDED
            or document.superseding_documents.filter(deleted_at__isnull=True).exists()
        ):
            raise CommandError(f"{canonical_id}: official document is not active and complete.")
        if source_hash != document.sha256_hash:
            raise CommandError(f"{canonical_id}: official source hash mismatch.")
        expected_document_hash = self._lower_hash(
            index.get("document_hashes", {}).get(document_code)
        )
        if expected_document_hash != document.sha256_hash:
            raise CommandError(f"{canonical_id}: index document hash mismatch.")
        if product.generation_code != canonical.get("product_generation"):
            raise CommandError(f"{canonical_id}: product generation mismatch.")

        pages = list(
            DocumentPage.objects.select_for_update().filter(
                document=document,
                page_no__in=page_refs,
            ).order_by("page_no")
        )
        if [page.page_no for page in pages] != sorted(page_refs):
            raise CommandError(f"{canonical_id}: reviewed source pages are missing.")
        if any(
            not page.is_rag_eligible
            or page.parse_status_code != "PARSED"
            or page.review_status_code != "APPROVED"
            or page.exclusion_reason is not None
            for page in pages
        ):
            raise CommandError(f"{canonical_id}: every source page must be RAG-approved.")

        chunk_hash = self._lower_hash(canonical.get("chunk_text_sha256"))
        chunk_candidates = list(
            DocumentChunk.objects.select_for_update().filter(
                page__document=document,
                page__page_no__in=page_refs,
                chunk_text_sha256=chunk_hash,
                is_active=True,
            )
        )
        if len(chunk_candidates) != 1:
            raise CommandError(
                f"{canonical_id}: exactly one active Backend chunk must match."
            )
        chunk = chunk_candidates[0]
        evidence_summary = str(
            (chunk.metadata or {}).get("evidence_summary") or ""
        ).strip()
        if not evidence_summary:
            raise CommandError(
                f"{canonical_id}: approved evidence_summary metadata is missing."
            )

        today = timezone.localdate()
        scope_candidates = list(
            DocumentModelScope.objects.select_for_update().filter(
                document=document,
                product_model=product,
                is_verified=True,
            ).filter(
                Q(applicable_from__isnull=True) | Q(applicable_from__lte=today),
                Q(applicable_to__isnull=True) | Q(applicable_to__gte=today),
            )
        )
        if len(scope_candidates) != 1:
            raise CommandError(
                f"{canonical_id}: exactly one verified model scope must match."
            )
        model_scope = scope_candidates[0]

        embedding_candidates = list(
            ChunkEmbedding.objects.select_for_update().filter(
                chunk=chunk,
                embedding_model=index.get("model_name"),
                embedding_model_version=index.get("model_revision"),
                embedding_dimension=EMBEDDING_DIMENSION,
                source_text_sha256=chunk_hash,
                is_active=True,
            )
        )
        if len(embedding_candidates) != 1:
            raise CommandError(
                f"{canonical_id}: exactly one approved active embedding must match."
            )
        if DataQualityIssue.objects.select_for_update().filter(
            Q(ingestion_batch=document.ingestion_batch)
            | Q(document=document)
            | Q(page__in=pages)
            | Q(chunk=chunk),
            status_code__in=["OPEN", "IN_REVIEW"],
        ).exists():
            raise CommandError(f"{canonical_id}: unresolved data-quality issue exists.")
        return CrosswalkPlanItem(
            canonical=canonical,
            document=document,
            pages=pages,
            chunk=chunk,
            model_scope=model_scope,
            embedding=embedding_candidates[0],
        )

    def _apply_plan(
        self,
        *,
        plan: list[CrosswalkPlanItem],
        identity: dict[str, Any],
        index: dict[str, Any],
        manifest_digest: str,
        verifier: User,
    ) -> None:
        canonical_ids = [item.canonical["chunk_id"] for item in plan]
        locked_mappings = AIChunkCrosswalk.objects.select_for_update()
        conflicting = locked_mappings.filter(
            chunk_id__in=[item.chunk.id for item in plan]
        ).exclude(canonical_chunk_id__in=canonical_ids)
        if conflicting.exists():
            raise CommandError("A Backend chunk is already mapped to another canonical ID.")
        locked_mappings.filter(is_active=True).exclude(
            canonical_chunk_id__in=canonical_ids
        ).update(is_active=False)

        verified_at = timezone.now()
        for item in plan:
            canonical = item.canonical
            mapping = locked_mappings.filter(
                canonical_chunk_id=canonical["chunk_id"]
            ).first()
            if mapping is None:
                mapping = AIChunkCrosswalk(
                    canonical_chunk_id=canonical["chunk_id"],
                    chunk=item.chunk,
                    model_scope=item.model_scope,
                )
            elif mapping.chunk_id != item.chunk.id:
                raise CommandError(
                    f"{mapping.canonical_chunk_id}: existing Backend chunk mapping differs."
                )
            mapping.model_scope = item.model_scope
            mapping.manifest_schema_version = str(identity["schema_version"])
            mapping.identity_manifest_sha256 = manifest_digest
            mapping.canonical_verification_status = canonical["verification_status"]
            mapping.source_file_sha256 = self._lower_hash(
                canonical["source_file_sha256"]
            )
            mapping.chunk_text_sha256 = self._lower_hash(
                canonical["chunk_text_sha256"]
            )
            mapping.embedding_model = index["model_name"]
            mapping.embedding_model_version = index["model_revision"]
            mapping.index_version = index["index_version"]
            mapping.chunk_set_sha256 = self._lower_hash(index["chunk_set_sha256"])
            mapping.is_verified = True
            mapping.verified_by = verifier
            mapping.verified_at = verified_at
            mapping.is_active = True
            mapping.full_clean()
            mapping.save()

            mapping.source_pages.all().delete()
            for order, page in enumerate(item.pages, start=1):
                page_mapping = AIChunkCrosswalkPage(
                    crosswalk=mapping,
                    page=page,
                    display_order=order,
                )
                page_mapping.full_clean()
                page_mapping.save()

    @staticmethod
    def _acquire_apply_lock() -> None:
        """Serialize all PostgreSQL Crosswalk activation commands."""

        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                [APPLY_ADVISORY_LOCK_ID],
            )

    @staticmethod
    def _lower_hash(value: Any) -> str:
        if not isinstance(value, str) or len(value) != 64:
            raise CommandError("SHA-256 values must contain 64 hexadecimal characters.")
        normalized = value.lower()
        if any(character not in "0123456789abcdef" for character in normalized):
            raise CommandError("SHA-256 values must contain hexadecimal characters only.")
        return normalized
