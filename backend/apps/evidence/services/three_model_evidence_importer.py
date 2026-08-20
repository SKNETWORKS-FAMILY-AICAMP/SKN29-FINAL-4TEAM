"""Fail-closed importer for the approved three-model 53-row evidence set."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5

from django.core.management.base import CommandError
from django.db.models import Max
from django.utils.dateparse import parse_datetime

from apps.accounts.models import User
from apps.evidence.models import (
    ChunkEmbedding,
    DocumentChunk,
    DocumentModelScope,
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)
from apps.evidence.services.canonical_evidence_importer import (
    APPROVED_EMBEDDING_DTYPE,
    APPROVED_EMBEDDING_FIXTURE_STATUS,
    EXPECTED_EMBEDDING_FIXTURE_FIELDS,
    EXPECTED_EMBEDDING_ROW_FIELDS,
    FIXED_LICENSE_NOTE,
    FIXED_USAGE_TERMS_URL,
    CanonicalEvidenceImporter,
)
from apps.products.models import ProductModel


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SOURCE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "rag"
    / "expansion"
    / "rag_child_chunks_3model_v1.jsonl"
)
INVENTORY_PATH = (
    REPOSITORY_ROOT / "data" / "processed" / "metadata" / "source_inventory.csv"
)
PAGE_PATHS = {
    "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00": (
        REPOSITORY_ROOT
        / "data"
        / "processed"
        / "documents"
        / "manuals"
        / "mvp"
        / "manual_pages_jac104d.jsonl"
    ),
    "MAN-SKMAGIC-WPU-IAC425-REV02": (
        REPOSITORY_ROOT
        / "data"
        / "processed"
        / "documents"
        / "manuals"
        / "expansion"
        / "manual_pages_iac425.jsonl"
    ),
    "MAN-SKMAGIC-WPU-IAC606-REV00": (
        REPOSITORY_ROOT
        / "data"
        / "processed"
        / "documents"
        / "manuals"
        / "expansion"
        / "manual_pages_iac606.jsonl"
    ),
}
DOCUMENT_CONFIG = {
    "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00": {
        "inventory_id": "SRC-JAC104D-MANUAL",
        "model_code": "WPUJAC104DWH",
        "generation_code": "D",
        "source_path_env": "BACKEND_AI_OFFICIAL_SOURCE_PATH_JAC104",
    },
    "MAN-SKMAGIC-WPU-IAC425-REV02": {
        "inventory_id": "SRC-IAC425-MANUAL",
        "model_code": "WPUIAC425SNW",
        "generation_code": "IAC425",
        "source_path_env": "BACKEND_AI_OFFICIAL_SOURCE_PATH_IAC425",
    },
    "MAN-SKMAGIC-WPU-IAC606-REV00": {
        "inventory_id": "SRC-IAC606-MANUAL",
        "model_code": "WPUIAC606SNW",
        "generation_code": "IAC606",
        "source_path_env": "BACKEND_AI_OFFICIAL_SOURCE_PATH_IAC606",
    },
}
EXPECTED_MODEL_COUNTS = {
    "WPUJAC104DWH": 15,
    "WPUIAC425SNW": 19,
    "WPUIAC606SNW": 19,
}
EXPECTED_CHUNK_COUNT = sum(EXPECTED_MODEL_COUNTS.values())
IDENTITY_STATUS = "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING"
IDENTITY_SCHEMA_VERSION = "1.0.0"
INDEX_VERSION = "2.0.0"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
EMBEDDING_DIMENSION = 1024
CHUNKING_VERSION = "rag_child_chunks_3model/1.0.0"


@dataclass(frozen=True, slots=True)
class ThreeModelImportPackage:
    identity: dict[str, Any]
    index: dict[str, Any]
    chunks: list[dict[str, Any]]
    pages: dict[str, dict[int, dict[str, Any]]]
    inventory: dict[str, dict[str, str]]
    embeddings: dict[str, dict[str, Any]]
    identity_sha256: str
    index_sha256: str
    embedding_fixture_sha256: str


@dataclass(slots=True)
class ThreeModelImportResult:
    created: dict[str, int] = field(default_factory=dict)
    unchanged: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, *, created: bool) -> None:
        target = self.created if created else self.unchanged
        target[key] = target.get(key, 0) + 1

    def summary(self) -> str:
        keys = ("batches", "documents", "pages", "scopes", "chunks", "embeddings")
        created = ",".join(f"{key}:{self.created.get(key, 0)}" for key in keys)
        unchanged = ",".join(
            f"{key}:{self.unchanged.get(key, 0)}" for key in keys
        )
        return f"created=[{created}] unchanged=[{unchanged}]"


class ThreeModelEvidenceImporter:
    """Validate repository and runtime inputs before one atomic DB write."""

    def load_package(
        self,
        *,
        identity_path: Path,
        identity_sha256: str,
        index_path: Path,
        index_sha256: str,
        embedding_fixture_path: Path,
        embedding_fixture_sha256: str,
        runtime_environment: Mapping[str, str] | None = None,
    ) -> ThreeModelImportPackage:
        identity, identity_digest = self._verified_json(
            identity_path, identity_sha256, label="Canonical identity"
        )
        index, index_digest = self._verified_json(
            index_path, index_sha256, label="Index manifest"
        )
        fixture, fixture_digest = self._verified_canonical_json(
            embedding_fixture_path,
            embedding_fixture_sha256,
            label="Embedding fixture",
        )
        chunks = self._load_jsonl(SOURCE_PATH)
        inventory = self._load_inventory()
        pages = {
            document_id: self._load_selected_pages(path, document_id=document_id)
            for document_id, path in PAGE_PATHS.items()
        }
        self._validate_sources(
            chunks=chunks,
            pages=pages,
            inventory=inventory,
            environment=runtime_environment if runtime_environment is not None else os.environ,
        )
        self._validate_identity(identity=identity, chunks=chunks)
        self._validate_index(index=index, identity=identity)
        embeddings = self._validate_embeddings(
            fixture=fixture,
            identity=identity,
            chunks=chunks,
        )
        return ThreeModelImportPackage(
            identity=identity,
            index=index,
            chunks=sorted(chunks, key=lambda row: str(row["child_id"])),
            pages=pages,
            inventory=inventory,
            embeddings=embeddings,
            identity_sha256=identity_digest,
            index_sha256=index_digest,
            embedding_fixture_sha256=fixture_digest,
        )

    def persist(
        self,
        *,
        package: ThreeModelImportPackage,
        verifier: User,
    ) -> ThreeModelImportResult:
        result = ThreeModelImportResult()
        chunks_by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in package.chunks:
            chunks_by_document[str(row["document_id"])].append(row)

        page_models: dict[tuple[str, int], DocumentPage] = {}
        indexed_at = self._parse_datetime(
            package.index.get("indexed_at"), label="Index manifest indexed_at"
        )

        for document_id, config in DOCUMENT_CONFIG.items():
            product = self._locked_product(
                model_code=str(config["model_code"]),
                generation_code=str(config["generation_code"]),
            )
            inventory = package.inventory[document_id]
            reviewed_at = self._parse_datetime(
                inventory.get("verified_at"),
                label=f"{document_id}: source verified_at",
            )
            document = SourceDocument.objects.select_for_update().filter(
                document_code=document_id
            ).first()
            if document is None:
                batch = self._create_or_validate_batch(
                    document_id=document_id,
                    count=len(chunks_by_document[document_id]),
                    verifier=verifier,
                    reviewed_at=reviewed_at,
                    package=package,
                )
                result.add("batches", created=batch[1])
                document = self._create_document(
                    document_id=document_id,
                    batch=batch[0],
                    inventory=inventory,
                    verifier=verifier,
                    reviewed_at=reviewed_at,
                )
                result.add("documents", created=True)
            else:
                self._validate_existing_document(
                    document=document,
                    inventory=inventory,
                )
                result.add("documents", created=False)
            for page_no, row in package.pages[document_id].items():
                page, created = self._create_or_validate_page(
                    document=document,
                    page_no=page_no,
                    row=row,
                    verifier=verifier,
                    reviewed_at=reviewed_at,
                )
                page_models[(document_id, page_no)] = page
                result.add("pages", created=created)

            scope = DocumentModelScope.objects.select_for_update().filter(
                document=document,
                product_model=product,
            ).first()
            if scope is None:
                scope = DocumentModelScope(
                    document=document,
                    product_model=product,
                    applicability_note=(
                        f"Exact three-model canonical scope for {product.model_code}."
                    ),
                    is_verified=True,
                    verified_by=verifier,
                    verified_at=reviewed_at,
                )
                scope.full_clean()
                scope.save(force_insert=True)
                result.add("scopes", created=True)
            else:
                if (
                    not scope.is_verified
                    or scope.verified_by_id is None
                    or scope.verified_at is None
                    or scope.applicable_from is not None
                    or scope.applicable_to is not None
                ):
                    raise CommandError(f"{document_id}: existing model scope differs.")
                result.add("scopes", created=False)
        next_positions: dict[tuple[str, int], int] = {}
        for document_id, selected_pages in package.pages.items():
            for page_no in selected_pages:
                page = page_models[(document_id, page_no)]
                current = (
                    DocumentChunk.objects.select_for_update()
                    .filter(page=page)
                    .aggregate(maximum=Max("chunk_no"))["maximum"]
                    or 0
                )
                next_positions[(document_id, page_no)] = int(current)

        for row in package.chunks:
            document_id = str(row["document_id"])
            canonical_id = str(row["child_id"])
            primary_page_no = int(row["page_refs"][0])
            chunk = DocumentChunk.objects.select_for_update().filter(
                metadata__canonical_chunk_id=canonical_id
            ).first()
            metadata = {
                "canonical_chunk_id": canonical_id,
                "evidence_group_id": row["evidence_group_id"],
                "page_refs": row["page_refs"],
                "evidence_summary": row["child_text"],
                "safe_actions": row["safe_actions"],
                "consultation_conditions": row["consultation_conditions"],
                "risk_level": row["risk_level"],
                "requires_consultation": row["requires_consultation"],
                "verification_status": row["verification_status"],
                "source_variant_id": row["source_variant_id"],
            }
            expected = {
                "page_id": page_models[(document_id, primary_page_no)].pk,
                "chunk_type_code": "PARAGRAPH",
                "section_path": row["section_title"],
                "chunk_text": row["child_text"],
                "chunk_text_sha256": str(row["child_text_sha256"]).lower(),
                "start_offset": None,
                "end_offset": None,
                "token_count": None,
                "tokenizer_name": None,
                "tokenizer_version": None,
                "symptom_tags": [],
                "metadata": metadata,
                "chunking_version": CHUNKING_VERSION,
                "is_active": True,
            }
            if chunk is None:
                key = (document_id, primary_page_no)
                next_positions[key] += 1
                chunk = DocumentChunk(chunk_no=next_positions[key], **expected)
                chunk.full_clean()
                chunk.save(force_insert=True)
                result.add("chunks", created=True)
            else:
                for field_name, expected_value in expected.items():
                    if getattr(chunk, field_name) != expected_value:
                        raise CommandError(
                            f"{canonical_id}: existing {field_name} differs."
                        )
                result.add("chunks", created=False)

            fixture_row = package.embeddings[canonical_id]
            embedding = ChunkEmbedding.objects.select_for_update().filter(
                chunk=chunk,
                embedding_model=EMBEDDING_MODEL,
                embedding_model_version=EMBEDDING_REVISION,
            ).first()
            embedding_expected = {
                "embedding_dimension": EMBEDDING_DIMENSION,
                "source_text_sha256": str(row["child_text_sha256"]).lower(),
                "embedded_at": indexed_at,
                "is_active": True,
            }
            if embedding is None:
                embedding = ChunkEmbedding(
                    chunk=chunk,
                    embedding_model=EMBEDDING_MODEL,
                    embedding_model_version=EMBEDDING_REVISION,
                    embedding=fixture_row["embedding"],
                    **embedding_expected,
                )
                embedding.full_clean()
                embedding.save(force_insert=True)
                result.add("embeddings", created=True)
            else:
                for field_name, expected_value in embedding_expected.items():
                    if getattr(embedding, field_name) != expected_value:
                        raise CommandError(
                            f"{canonical_id}: existing embedding {field_name} differs."
                        )
                if not CanonicalEvidenceImporter._vectors_equal(
                    embedding.embedding, fixture_row["embedding"]
                ):
                    raise CommandError(f"{canonical_id}: existing embedding differs.")
                result.add("embeddings", created=False)
        return result

    def _validate_sources(
        self,
        *,
        chunks: list[dict[str, Any]],
        pages: dict[str, dict[int, dict[str, Any]]],
        inventory: dict[str, dict[str, str]],
        environment: Mapping[str, str],
    ) -> None:
        if len(chunks) != EXPECTED_CHUNK_COUNT:
            raise CommandError("Three-model source must contain exactly 53 rows.")
        ids = [row.get("child_id") for row in chunks]
        if (
            any(not isinstance(value, str) or not value for value in ids)
            or len(set(ids)) != EXPECTED_CHUNK_COUNT
        ):
            raise CommandError("Three-model source child IDs must be unique.")
        counts = Counter(str(row.get("exact_sales_code")) for row in chunks)
        if dict(counts) != EXPECTED_MODEL_COUNTS:
            raise CommandError("Three-model source model distribution differs.")
        for document_id, config in DOCUMENT_CONFIG.items():
            source = inventory[document_id]
            if (
                source.get("exact_sales_code") != config["model_code"]
                or source.get("sha256") is None
                or source.get("source_type") != "official_manual"
                or source.get("deletion_scope") != "external_backup_preserved"
            ):
                raise CommandError(f"{document_id}: source inventory differs.")
            source_path = self._runtime_source_path(
                environment, key=str(config["source_path_env"])
            )
            CanonicalEvidenceImporter._verify_official_source_file(
                source_path,
                expected_sha256=str(source["sha256"]).lower(),
                expected_size=self._positive_int(
                    source.get("file_size_bytes"),
                    label=f"{document_id}: file_size_bytes",
                ),
            )
        for row in chunks:
            chunk_id = str(row.get("child_id") or "")
            document_id = str(row.get("document_id") or "")
            config = DOCUMENT_CONFIG.get(document_id)
            if config is None:
                raise CommandError(f"{chunk_id}: document is outside the approved set.")
            expected_pairs = (
                (row.get("record_type"), "child"),
                (row.get("retrieval_role"), "SEARCH_CANDIDATE"),
                (row.get("allowed_use"), "RAG_HANDOFF_ONLY"),
                (row.get("verification_status"), "TEXT_AND_VISUAL_VERIFIED"),
                (row.get("exact_sales_code"), config["model_code"]),
                (row.get("product_generation"), config["generation_code"]),
                (
                    row.get("source_file_sha256"),
                    inventory[document_id]["sha256"],
                ),
            )
            if any(actual != expected for actual, expected in expected_pairs):
                raise CommandError(f"{chunk_id}: approved source metadata differs.")
            text = row.get("child_text")
            if not isinstance(text, str) or not text:
                raise CommandError(f"{chunk_id}: child_text must be non-empty.")
            if sha256(text.encode("utf-8")).hexdigest().upper() != row.get(
                "child_text_sha256"
            ):
                raise CommandError(f"{chunk_id}: child text hash differs.")
            page_refs = row.get("page_refs")
            if (
                not isinstance(page_refs, list)
                or not page_refs
                or any(page not in pages[document_id] for page in page_refs)
            ):
                raise CommandError(f"{chunk_id}: approved page refs are unavailable.")
        for document_id, selected_pages in pages.items():
            for page_no, row in selected_pages.items():
                text = row.get("text")
                if not isinstance(text, str) or not text:
                    raise CommandError(f"{document_id} page {page_no}: text is empty.")
                if sha256(text.encode("utf-8")).hexdigest().upper() != row.get(
                    "text_sha256"
                ):
                    raise CommandError(f"{document_id} page {page_no}: hash differs.")
                if row.get("source_file_sha256") != inventory[document_id]["sha256"]:
                    raise CommandError(
                        f"{document_id} page {page_no}: source hash differs."
                    )

    def _validate_identity(
        self,
        *,
        identity: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> None:
        if identity.get("schema_version") != IDENTITY_SCHEMA_VERSION:
            raise CommandError("Canonical identity schema version is unsupported.")
        if identity.get("status") != IDENTITY_STATUS:
            raise CommandError("Canonical identity status is not mapping-ready.")
        if identity.get("index_version") != INDEX_VERSION:
            raise CommandError("Canonical identity index version differs.")
        if identity.get("chunk_count") != EXPECTED_CHUNK_COUNT:
            raise CommandError("Canonical identity chunk_count must be 53.")
        if identity.get("model_chunk_counts") != EXPECTED_MODEL_COUNTS:
            raise CommandError("Canonical identity model distribution differs.")
        expected_chunk_set = self._chunk_set_sha256(chunks)
        if identity.get("chunk_set_sha256") != expected_chunk_set:
            raise CommandError("Canonical identity chunk-set hash differs.")
        identity_rows = identity.get("chunks")
        if not isinstance(identity_rows, list) or len(identity_rows) != 53:
            raise CommandError("Canonical identity must contain exactly 53 rows.")
        identity_by_id = {item.get("chunk_id"): item for item in identity_rows}
        if len(identity_by_id) != 53:
            raise CommandError("Canonical identity chunk IDs must be unique.")
        for row in chunks:
            chunk_id = str(row["child_id"])
            canonical = identity_by_id.get(chunk_id)
            if not isinstance(canonical, dict):
                raise CommandError(f"{chunk_id}: Canonical identity is missing.")
            expected = {
                "document_id": row["document_id"],
                "page_refs": row["page_refs"],
                "model_code": row["exact_sales_code"],
                "product_generation": row["product_generation"],
                "verification_status": row["verification_status"],
                "source_file_sha256": row["source_file_sha256"],
                "chunk_text_sha256": row["child_text_sha256"],
            }
            if any(canonical.get(key) != value for key, value in expected.items()):
                raise CommandError(f"{chunk_id}: Canonical identity differs.")

    def _validate_index(
        self,
        *,
        index: dict[str, Any],
        identity: dict[str, Any],
    ) -> None:
        expected = {
            "model_name": EMBEDDING_MODEL,
            "model_revision": EMBEDDING_REVISION,
            "dimension": EMBEDDING_DIMENSION,
            "index_type": "exact_search",
            "index_version": INDEX_VERSION,
            "chunk_count": EXPECTED_CHUNK_COUNT,
            "chunk_set_sha256": identity["chunk_set_sha256"],
        }
        if any(index.get(key) != value for key, value in expected.items()):
            raise CommandError("Actual index manifest differs from the approved target.")
        hashes = index.get("document_hashes")
        if not isinstance(hashes, dict) or set(hashes) != set(DOCUMENT_CONFIG):
            raise CommandError("Index document hash set differs.")
        identity_hashes = {
            str(row["document_id"]): str(row["source_file_sha256"]).lower()
            for row in identity["chunks"]
        }
        if any(
            not isinstance(value, str)
            or value.lower() != identity_hashes[document_id]
            for document_id, value in hashes.items()
        ):
            raise CommandError("Index document hash values differ.")
        self._parse_datetime(index.get("indexed_at"), label="Index manifest indexed_at")

    def _validate_embeddings(
        self,
        *,
        fixture: dict[str, Any],
        identity: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        expected = {
            "schema_version": "1.0.0",
            "status": APPROVED_EMBEDDING_FIXTURE_STATUS,
            "model_name": EMBEDDING_MODEL,
            "model_revision": EMBEDDING_REVISION,
            "dimension": EMBEDDING_DIMENSION,
            "embedding_dtype": APPROVED_EMBEDDING_DTYPE,
            "index_version": INDEX_VERSION,
            "chunk_set_sha256": identity["chunk_set_sha256"],
        }
        if set(fixture) != EXPECTED_EMBEDDING_FIXTURE_FIELDS:
            raise CommandError("Embedding fixture root fields do not match contract v1.")
        if any(fixture.get(key) != value for key, value in expected.items()):
            raise CommandError("Embedding fixture metadata differs.")
        rows = fixture.get("rows")
        if not isinstance(rows, list) or len(rows) != EXPECTED_CHUNK_COUNT:
            raise CommandError("Embedding fixture must contain exactly 53 rows.")
        if any(not isinstance(row, dict) or set(row) != EXPECTED_EMBEDDING_ROW_FIELDS for row in rows):
            raise CommandError("Embedding fixture row fields differ.")
        row_ids = [row.get("chunk_id") for row in rows]
        if row_ids != sorted(row_ids) or len(set(row_ids)) != EXPECTED_CHUNK_COUNT:
            raise CommandError("Embedding fixture IDs must be unique and sorted.")
        source_by_id = {str(row["child_id"]): row for row in chunks}
        if set(row_ids) != set(source_by_id):
            raise CommandError("Embedding fixture chunk set differs.")
        for row in rows:
            chunk_id = str(row["chunk_id"])
            if row.get("chunk_text_sha256") != str(
                source_by_id[chunk_id]["child_text_sha256"]
            ).lower():
                raise CommandError(f"{chunk_id}: embedding source hash differs.")
            vector = row.get("embedding")
            if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSION:
                raise CommandError(f"{chunk_id}: embedding must contain 1024 values.")
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in vector
            ):
                raise CommandError(f"{chunk_id}: embedding contains invalid values.")
        return {str(row["chunk_id"]): row for row in rows}

    def _load_inventory(self) -> dict[str, dict[str, str]]:
        try:
            with INVENTORY_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        except OSError as exc:
            raise CommandError("Cannot load source inventory.") from exc
        by_id = {row.get("data_id"): row for row in rows}
        result = {}
        for document_id, config in DOCUMENT_CONFIG.items():
            row = by_id.get(config["inventory_id"])
            if not isinstance(row, dict):
                raise CommandError(f"{document_id}: source inventory row is missing.")
            result[document_id] = row
        return result

    def _load_selected_pages(
        self,
        path: Path,
        *,
        document_id: str,
    ) -> dict[int, dict[str, Any]]:
        rows = self._load_jsonl(path)
        needed = {
            int(page)
            for row in self._load_jsonl(SOURCE_PATH)
            if row.get("document_id") == document_id
            for page in row.get("page_refs", [])
        }
        selected = {
            int(row["page"]): row
            for row in rows
            if row.get("document_id") == document_id and row.get("page") in needed
        }
        if set(selected) != needed:
            raise CommandError(f"{document_id}: reviewed source pages are missing.")
        return selected

    def _create_or_validate_batch(
        self,
        *,
        document_id: str,
        count: int,
        verifier: User,
        reviewed_at,
        package: ThreeModelImportPackage,
    ):
        model_code = str(DOCUMENT_CONFIG[document_id]["model_code"])
        return CanonicalEvidenceImporter._get_or_create_exact(
            IngestionBatch,
            lookup={"batch_no": f"AI-3MODEL-{model_code}-V2"},
            expected={
                "dataset_scope_code": IngestionBatch.DatasetScope.MVP,
                "source_type_code": IngestionBatch.SourceType.LOCAL_FILE,
                "status_code": IngestionBatch.Status.SUCCEEDED,
                "idempotency_key": (
                    f"backend-ai-3model:{model_code}:{package.identity_sha256}"
                ),
                "correlation_id": uuid5(
                    NAMESPACE_URL, f"waterbridge:ai-3model:{model_code}:v2"
                ),
                "started_by_id": verifier.pk,
                "started_at": reviewed_at,
                "completed_at": reviewed_at,
                "total_count": count,
                "success_count": count,
                "failure_count": 0,
                "pipeline_version": "backend-ai-three-model/2.0.0",
                "log_uri": "repository://data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl",
                "error_summary": None,
            },
            label=f"{document_id}: ingestion batch",
        )

    def _create_document(
        self,
        *,
        document_id: str,
        batch: IngestionBatch,
        inventory: dict[str, str],
        verifier: User,
        reviewed_at,
    ) -> SourceDocument:
        source_hash = str(inventory["sha256"]).lower()
        document = SourceDocument(
            ingestion_batch=batch,
            document_code=document_id,
            dataset_scope_code=SourceDocument.DatasetScope.MVP,
            title=inventory["source_name"],
            source_org="SK매직",
            document_type_code="OFFICIAL_MANUAL",
            official_source_url=inventory["source_url"],
            usage_terms_url=FIXED_USAGE_TERMS_URL,
            license_note=FIXED_LICENSE_NOTE,
            original_file_uri=(
                f"object://official-sources/mvp/{document_id}/{source_hash}.pdf"
            ),
            file_name=f"{source_hash}.pdf",
            mime_type="application/pdf",
            file_size_bytes=int(inventory["file_size_bytes"]),
            sha256_hash=source_hash,
            revision_label=inventory["version"],
            collected_at=reviewed_at,
            collected_by=verifier,
            status_code="APPROVED",
            parser_version="three-model-canonical-v2",
        )
        document.full_clean()
        document.save(force_insert=True)
        return document

    @staticmethod
    def _create_or_validate_page(
        *,
        document: SourceDocument,
        page_no: int,
        row: dict[str, Any],
        verifier: User,
        reviewed_at,
    ) -> tuple[DocumentPage, bool]:
        page = DocumentPage.objects.select_for_update().filter(
            document=document,
            page_no=page_no,
        ).first()
        expected = {
            "extracted_text": row["text"],
            "text_sha256": str(row["text_sha256"]).lower(),
            "parse_status_code": "PARSED",
            "review_status_code": "APPROVED",
            "is_rag_eligible": True,
            "exclusion_reason": None,
        }
        if page is None:
            page = DocumentPage(
                document=document,
                page_no=page_no,
                reviewer=verifier,
                reviewed_at=reviewed_at,
                **expected,
            )
            page.full_clean()
            page.save(force_insert=True)
            return page, True
        for field_name, expected_value in expected.items():
            if getattr(page, field_name) != expected_value:
                raise CommandError(
                    f"{document.document_code}: approved page {page_no} "
                    f"{field_name} differs."
                )
        if page.reviewer_id is None or page.reviewed_at is None:
            raise CommandError(
                f"{document.document_code}: approved page {page_no} "
                "review evidence is incomplete."
            )
        return page, False

    @staticmethod
    def _validate_existing_document(
        *,
        document: SourceDocument,
        inventory: dict[str, str],
    ) -> None:
        expected = {
            "dataset_scope_code": SourceDocument.DatasetScope.MVP,
            "title": inventory["source_name"],
            "source_org": "SK매직",
            "document_type_code": "OFFICIAL_MANUAL",
            "official_source_url": inventory["source_url"],
            "usage_terms_url": FIXED_USAGE_TERMS_URL,
            "license_note": FIXED_LICENSE_NOTE,
            "file_size_bytes": int(inventory["file_size_bytes"]),
            "sha256_hash": str(inventory["sha256"]).lower(),
            "revision_label": inventory["version"],
            "status_code": "APPROVED",
            "deleted_at": None,
        }
        for field_name, expected_value in expected.items():
            if getattr(document, field_name) != expected_value:
                raise CommandError(
                    f"{document.document_code}: existing {field_name} differs."
                )

    @staticmethod
    def _locked_product(*, model_code: str, generation_code: str) -> ProductModel:
        product = ProductModel.objects.select_for_update().filter(
            model_code=model_code
        ).first()
        if (
            product is None
            or product.generation_code != generation_code
            or not product.is_active
        ):
            raise CommandError(f"{model_code}: active ProductModel is not prepared.")
        return product

    @staticmethod
    def _runtime_source_path(environment: Mapping[str, str], *, key: str) -> Path:
        value = environment.get(key)
        if not isinstance(value, str) or not value.strip():
            raise CommandError(f"{key} must be injected into the process.")
        path = Path(value)
        if not path.is_absolute():
            raise CommandError("Official source runtime path must be absolute.")
        return path

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        try:
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot load JSONL input: {path}") from exc
        if not rows or any(not isinstance(row, dict) for row in rows):
            raise CommandError(f"JSONL input must contain objects: {path}")
        return rows

    @staticmethod
    def _verified_json(path: Path, expected_hash: str, *, label: str):
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot load {label}.") from exc
        if not isinstance(payload, dict):
            raise CommandError(f"{label} root must be an object.")
        digest = sha256(raw).hexdigest()
        if digest != ThreeModelEvidenceImporter._lower_hash(expected_hash):
            raise CommandError(f"{label} SHA-256 does not match.")
        return payload, digest

    @staticmethod
    def _verified_canonical_json(path: Path, expected_hash: str, *, label: str):
        payload, digest = ThreeModelEvidenceImporter._verified_json(
            path, expected_hash, label=label
        )
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if path.read_bytes() != canonical:
            raise CommandError(f"{label} must use canonical compact JSON bytes.")
        return payload, digest

    @staticmethod
    def _chunk_set_sha256(rows: list[dict[str, Any]]) -> str:
        canonical = [
            {
                "chunk_id": row["child_id"],
                "source_hash": str(row["source_file_sha256"]).upper(),
                "content": row["child_text"],
            }
            for row in sorted(rows, key=lambda item: str(item["child_id"]))
        ]
        return sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest().upper()

    @staticmethod
    def _parse_datetime(value: Any, *, label: str):
        parsed = parse_datetime(str(value or ""))
        if parsed is None:
            raise CommandError(f"{label} must be an ISO-8601 timestamp.")
        return parsed

    @staticmethod
    def _positive_int(value: Any, *, label: str) -> int:
        try:
            parsed = int(str(value))
        except (TypeError, ValueError) as exc:
            raise CommandError(f"{label} must be a positive integer.") from exc
        if parsed <= 0:
            raise CommandError(f"{label} must be a positive integer.")
        return parsed

    @staticmethod
    def _lower_hash(value: Any) -> str:
        if not isinstance(value, str) or len(value) != 64:
            raise CommandError("SHA-256 must contain 64 hexadecimal characters.")
        normalized = value.lower()
        if any(character not in "0123456789abcdef" for character in normalized):
            raise CommandError("SHA-256 must contain hexadecimal characters only.")
        return normalized
