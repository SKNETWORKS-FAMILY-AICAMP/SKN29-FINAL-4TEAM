"""AI canonical chunk Crosswalk, View, and runtime Verifier tests."""

from __future__ import annotations

import json
from datetime import date
from importlib import import_module
from uuid import UUID, uuid4

import httpx
import pytest
from django.core.management.base import CommandError
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.audit.models import AIRun
from apps.evidence.models import (
    AIChunkCrosswalk,
    AIChunkCrosswalkPage,
    ChunkEmbedding,
    DataQualityIssue,
    DocumentChunk,
    DocumentModelScope,
    DocumentPage,
    EvidenceLink,
    IngestionBatch,
    SourceDocument,
)
from apps.evidence.services import EvidenceReferenceVerifier
from apps.inquiries.models import Guidance, Inquiry
from apps.inquiries.services.inquiry_ai_service import InquiryAIService
from apps.products.models import ProductModel
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.models import TransitionHistory
from integrations.ai.client import AIClient
from integrations.ai.schema_validator import DEFAULT_CONTRACT_ROOT, AIContractValidator


pytestmark = pytest.mark.django_db


def create_verified_mapping(sequence: int = 1):
    operator = User.objects.create_user(
        username=f"AI-XWALK-OP-{sequence}",
        password=None,
        full_name=f"AI Crosswalk operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"AI-XWALK-EMP-{sequence}",
        is_synthetic=True,
    )
    customer_user = User.objects.create_user(
        username=f"AI-XWALK-CUSTOMER-{sequence}",
        password=None,
        full_name=f"AI Crosswalk customer {sequence}",
        role_code=User.Role.CUSTOMER,
        is_synthetic=True,
    )
    profile = CustomerProfile.objects.create(
        user=customer_user,
        customer_no=f"AI-XWALK-CUS-{sequence}",
        customer_name=f"AI Crosswalk customer {sequence}",
        is_synthetic=True,
    )
    product = ProductModel.objects.create(
        model_code=f"AI-XWALK-MODEL-{sequence}",
        model_name=f"AI Crosswalk model {sequence}",
        generation_code="D",
        is_supported_mvp=True,
        is_active=True,
    )
    subscription = CustomerSubscription.objects.create(
        contract_no=f"AI-XWALK-SUB-{sequence}",
        customer=profile,
        product_model=product,
        serial_no=f"AI-XWALK-SERIAL-{sequence}",
        started_on=date(2026, 8, 1),
    )
    inquiry = Inquiry.objects.create(
        subscription=subscription,
        initiated_by=customer_user,
        channel_code=Inquiry.Channel.WEB,
        raw_text="Synthetic crosswalk verification inquiry.",
        status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
        state_version=2,
    )
    batch = IngestionBatch.objects.create(
        batch_no=f"AI-XWALK-BATCH-{sequence}",
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"ai-xwalk-batch-{sequence}",
        correlation_id=uuid4(),
        pipeline_version="ai-xwalk-test-v1",
        status_code=IngestionBatch.Status.SUCCEEDED,
        started_at=timezone.now(),
        completed_at=timezone.now(),
        total_count=1,
        success_count=1,
    )
    source_hash = f"{sequence + 100:064x}"
    chunk_hash = f"{sequence + 200:064x}"
    document = SourceDocument.objects.create(
        ingestion_batch=batch,
        document_code=f"AI-XWALK-DOC-{sequence}",
        title=f"AI Crosswalk document {sequence}",
        source_org="Official test organization",
        document_type_code="OFFICIAL_GUIDE",
        official_source_url=f"https://example.test/ai-xwalk/{sequence}",
        usage_terms_url=f"https://example.test/ai-xwalk/terms/{sequence}",
        license_note="Synthetic test fixture.",
        original_file_uri=f"object://ai-xwalk/{sequence}.pdf",
        sha256_hash=source_hash,
        revision_label="REV-1",
        collected_by=operator,
        status_code="APPROVED",
    )
    page = DocumentPage.objects.create(
        document=document,
        page_no=37,
        extracted_text="Approved synthetic page.",
        text_sha256=f"{sequence + 300:064x}",
        parse_status_code="PARSED",
        review_status_code="APPROVED",
        is_rag_eligible=True,
        reviewer=operator,
        reviewed_at=timezone.now(),
    )
    chunk = DocumentChunk.objects.create(
        page=page,
        chunk_no=1,
        chunk_text="Approved synthetic evidence chunk.",
        chunk_text_sha256=chunk_hash,
        metadata={
            "safe_actions": ["STOP_AND_CONTACT"],
            "evidence_summary": "Approved customer-safe evidence summary.",
        },
        chunking_version="ai-xwalk-v1",
    )
    scope = DocumentModelScope.objects.create(
        document=document,
        product_model=product,
        is_verified=True,
        verified_by=operator,
        verified_at=timezone.now(),
    )
    ChunkEmbedding.objects.create(
        chunk=chunk,
        embedding_model="BAAI/bge-m3",
        embedding_model_version=(
            "5617a9f61b028005a4858fdac845db406aefb181"
        ),
        embedding_dimension=1024,
        source_text_sha256=chunk_hash,
        embedding=[0.0] * 1024,
        is_active=True,
    )
    mapping = AIChunkCrosswalk(
        canonical_chunk_id=f"RAG-AI-XWALK-{sequence}",
        chunk=chunk,
        model_scope=scope,
        manifest_schema_version="1.0.0",
        identity_manifest_sha256=f"{sequence + 400:064x}",
        canonical_verification_status="TEXT_AND_VISUAL_VERIFIED",
        source_file_sha256=source_hash,
        chunk_text_sha256=chunk_hash,
        embedding_model="BAAI/bge-m3",
        embedding_model_version=(
            "5617a9f61b028005a4858fdac845db406aefb181"
        ),
        index_version="1.0.0",
        chunk_set_sha256=f"{sequence + 500:064x}",
        is_verified=True,
        verified_by=operator,
        verified_at=timezone.now(),
        is_active=True,
    )
    mapping.full_clean()
    mapping.save()
    page_mapping = AIChunkCrosswalkPage(
        crosswalk=mapping,
        page=page,
        display_order=1,
    )
    page_mapping.full_clean()
    page_mapping.save()
    return mapping, inquiry


def evidence_reference(mapping: AIChunkCrosswalk) -> dict:
    document = mapping.chunk.page.document
    return {
        "document_title": document.title,
        "document_version": document.revision_label,
        "page": mapping.chunk.page.page_no,
        "page_refs": [mapping.chunk.page.page_no],
        "chunk_id": mapping.canonical_chunk_id,
        "official_url": document.official_source_url,
        "summary": "Synthetic approved evidence.",
        "similarity_score": 0.9,
        "verification_status": "official_verified",
    }


def test_crosswalk_uses_public_uuid_and_one_to_one_backend_chunk():
    mapping, _inquiry = create_verified_mapping()

    assert isinstance(mapping.public_id, UUID)
    assert mapping._meta.db_table == "knowledge_ai_chunk_crosswalk"
    assert mapping.chunk.ai_crosswalk == mapping
    assert list(mapping.source_pages.values_list("page__page_no", flat=True)) == [37]


def test_crosswalk_rejects_uppercase_hash_and_unverified_active_mapping():
    mapping, _inquiry = create_verified_mapping()
    mapping.identity_manifest_sha256 = "A" * 64
    mapping.is_verified = False
    mapping.verified_by = None
    mapping.verified_at = None

    with pytest.raises(ValidationError) as exc_info:
        mapping.full_clean()

    assert "identity_manifest_sha256" in exc_info.value.message_dict
    assert "is_active" in exc_info.value.message_dict


def test_verifier_returns_backend_public_id_for_fully_approved_mapping():
    mapping, inquiry = create_verified_mapping()

    result = EvidenceReferenceVerifier.verify(
        [evidence_reference(mapping)],
        inquiry,
    )

    assert result == [str(mapping.chunk.public_id)]
    assert mapping.canonical_chunk_id not in result


@pytest.mark.parametrize(
    "mutator",
    [
        lambda reference: reference.update(chunk_id="RAG-UNKNOWN-999"),
        lambda reference: reference.update(verification_status="team_verified"),
        lambda reference: reference.update(document_title="Forged title"),
        lambda reference: reference.update(page_refs=[99]),
    ],
)
def test_verifier_rejects_unknown_or_mismatched_reference(mutator):
    mapping, inquiry = create_verified_mapping()
    reference = evidence_reference(mapping)
    mutator(reference)

    assert EvidenceReferenceVerifier.verify([reference], inquiry) == []


def test_verifier_rejects_mixed_valid_and_invalid_references_as_one_unit():
    mapping, inquiry = create_verified_mapping()
    valid = evidence_reference(mapping)
    invalid = {**valid, "chunk_id": "RAG-UNKNOWN-999"}

    assert EvidenceReferenceVerifier.verify([valid, invalid], inquiry) == []


def test_verifier_rejects_open_data_quality_issue():
    mapping, inquiry = create_verified_mapping()
    DataQualityIssue.objects.create(
        document=mapping.chunk.page.document,
        issue_type_code="SOURCE_REVIEW_REQUIRED",
        issue_message="Synthetic unresolved source review issue.",
    )

    assert EvidenceReferenceVerifier.verify(
        [evidence_reference(mapping)],
        inquiry,
    ) == []


def test_postgresql_view_contract_is_read_only_and_does_not_expose_public_uuid():
    migration = import_module(
        "apps.evidence.migrations.0010_backend_ai_rag_chunks_view"
    )
    sql = migration.CREATE_VIEW_SQL

    assert migration.VIEW_NAME == "backend_ai_rag_chunks_v1"
    assert "security_barrier = true" in sql
    assert "knowledge_ai_chunk_crosswalk" in sql
    assert "knowledge_chunk_embedding" in sql
    assert "ingestion.status_code = 'SUCCEEDED'" in sql
    assert "document.status_code = 'APPROVED'" in sql
    assert (
        "crosswalk.canonical_verification_status = "
        "'TEXT_AND_VISUAL_VERIFIED'"
    ) in sql
    assert "knowledge_data_quality_issue" in sql
    assert "model_scope.applicable_to" in sql
    assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'" in sql
    assert "vector_dims(embedding.embedding) = 1024" in sql
    assert "AS chunk_id" in sql
    assert "public_id" not in sql
    assert "original_file_uri" not in sql
    assert "INSERT" not in sql
    assert "UPDATE" not in sql
    assert "DELETE" not in sql


def test_sync_command_plan_validates_then_applies_exactly_seven_rows():
    command_module = import_module(
        "apps.evidence.management.commands.sync_ai_canonical_crosswalk"
    )
    fixtures = [create_verified_mapping(sequence) for sequence in range(10, 17)]
    original_mappings = [fixture[0] for fixture in fixtures]
    verifier = original_mappings[0].verified_by
    chunks = []
    document_hashes = {}
    for mapping in original_mappings:
        document = mapping.chunk.page.document
        product = mapping.model_scope.product_model
        document_hashes[document.document_code] = document.sha256_hash.upper()
        chunks.append(
            {
                "chunk_id": mapping.canonical_chunk_id,
                "document_id": document.document_code,
                "page_refs": [mapping.chunk.page.page_no],
                "model_code": product.model_code,
                "product_generation": product.generation_code,
                "verification_status": "TEXT_AND_VISUAL_VERIFIED",
                "source_file_sha256": document.sha256_hash.upper(),
                "chunk_text_sha256": mapping.chunk.chunk_text_sha256,
            }
        )
    chunk_set_hash = "a" * 64
    identity = {
        "schema_version": "1.0.0",
        "status": "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING",
        "index_version": "1.0.0",
        "chunk_set_sha256": chunk_set_hash.upper(),
        "chunks": chunks,
    }
    index = {
        "model_name": "BAAI/bge-m3",
        "model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "dimension": 1024,
        "index_type": "exact_search",
        "index_version": "1.0.0",
        "chunk_count": 7,
        "chunk_set_sha256": chunk_set_hash,
        "document_hashes": document_hashes,
    }
    command = command_module.Command()
    plan = command._build_plan(identity=identity, index=index)

    assert len(plan) == 7
    stale_mapping, _stale_inquiry = create_verified_mapping(sequence=99)
    with transaction.atomic():
        first_result = command._apply_plan(
            plan=plan,
            identity=identity,
            index=index,
            manifest_digest="b" * 64,
            verifier=verifier,
        )

    assert first_result == {"created": 0, "updated": 7, "unchanged": 0}

    assert AIChunkCrosswalk.objects.filter(
        is_active=True,
        is_verified=True,
    ).count() == 7
    stale_mapping.refresh_from_db()
    assert stale_mapping.is_active is False
    assert AIChunkCrosswalkPage.objects.filter(
        crosswalk__is_active=True
    ).count() == 7
    assert set(
        AIChunkCrosswalk.objects.filter(is_active=True).values_list(
            "canonical_chunk_id",
            flat=True,
        )
    ) == {item["chunk_id"] for item in chunks}
    mapping_snapshot = list(
        AIChunkCrosswalk.objects.filter(is_active=True)
        .order_by("canonical_chunk_id")
        .values_list("id", "verified_at", "created_at", "updated_at")
    )
    page_snapshot = list(
        AIChunkCrosswalkPage.objects.filter(crosswalk__is_active=True)
        .order_by("crosswalk_id", "display_order")
        .values_list("id", "crosswalk_id", "page_id", "display_order")
    )

    with transaction.atomic():
        replay_result = command._apply_plan(
            plan=plan,
            identity=identity,
            index=index,
            manifest_digest="b" * 64,
            verifier=verifier,
        )

    assert replay_result == {"created": 0, "updated": 0, "unchanged": 7}
    assert mapping_snapshot == list(
        AIChunkCrosswalk.objects.filter(is_active=True)
        .order_by("canonical_chunk_id")
        .values_list("id", "verified_at", "created_at", "updated_at")
    )
    assert page_snapshot == list(
        AIChunkCrosswalkPage.objects.filter(crosswalk__is_active=True)
        .order_by("crosswalk_id", "display_order")
        .values_list("id", "crosswalk_id", "page_id", "display_order")
    )


def test_sync_command_rejects_identity_index_version_mismatch():
    command_module = import_module(
        "apps.evidence.management.commands.sync_ai_canonical_crosswalk"
    )
    command = command_module.Command()

    with pytest.raises(
        CommandError,
        match="Identity and index versions do not match",
    ):
        command._build_plan(
            identity={
                "status": "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING",
                "schema_version": "1.0.0",
                "index_version": "2.0.0",
            },
            index={"index_version": "1.0.0"},
        )


@pytest.mark.parametrize(
    "field, value, expected_message",
    [
        ("model_name", "other/model", "embedding model"),
        ("model_revision", "floating-main", "embedding revision"),
        ("index_type", "approximate", "search type"),
    ],
)
def test_sync_command_rejects_nonapproved_embedding_baseline(
    field,
    value,
    expected_message,
):
    command_module = import_module(
        "apps.evidence.management.commands.sync_ai_canonical_crosswalk"
    )
    index = {
        "model_name": "BAAI/bge-m3",
        "model_revision": "5617a9f61b028005a4858fdac845db406aefb181",
        "index_type": "exact_search",
        "index_version": "1.0.0",
    }
    index[field] = value

    with pytest.raises(CommandError, match=expected_message):
        command_module.Command()._build_plan(
            identity={
                "status": "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING",
                "schema_version": "1.0.0",
                "index_version": "1.0.0",
            },
            index=index,
        )


def test_default_verifier_persists_evidence_link_and_applies_safe_event():
    mapping, inquiry = create_verified_mapping(sequence=120)
    correlation_id = uuid4()
    ai_request_id = uuid4()
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        request_payload = json.loads(request.content.decode("utf-8"))
        example_path = (
            DEFAULT_CONTRACT_ROOT
            / "examples"
            / "symptom-analysis"
            / "general-guidance.json"
        )
        response = json.loads(example_path.read_text(encoding="utf-8"))["response"]
        for field in (
            "inquiry_id",
            "correlation_id",
            "ai_request_id",
            "state_version",
        ):
            response[field] = request_payload[field]
        response["evidence_references"] = [evidence_reference(mapping)]
        return httpx.Response(200, json=response)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = AIClient(
        base_url="http://ai.test",
        mode="local",
        http_client=http_client,
    )
    outcome = InquiryAIService.analyze_inquiry(
        inquiry_public_id=inquiry.public_id,
        correlation_id=correlation_id,
        ai_request_id=ai_request_id,
        client=client,
    )

    assert len(calls) == 1
    assert outcome.event_applied == "SAFE_GUIDANCE_READY"
    inquiry.refresh_from_db()
    assert inquiry.status_code == Inquiry.Status.AI_GUIDANCE
    assert inquiry.evidence_ids == [str(mapping.chunk.public_id)]
    guidance = Guidance.objects.get(inquiry=inquiry)
    run = AIRun.objects.get(inquiry=inquiry)
    link = EvidenceLink.objects.get(inquiry=inquiry)
    assert link.guidance == guidance
    assert link.ai_run == run
    assert link.chunk == mapping.chunk
    assert link.evidence_summary == "Approved customer-safe evidence summary."
    assert link.cited_text_snapshot == mapping.chunk.chunk_text
    assert link.is_verified is True
    assert TransitionHistory.objects.get(inquiry=inquiry).event_code == (
        "SAFE_GUIDANCE_READY"
    )

    replay = InquiryAIService._replay_or_conflict(
        run,
        input_digest=run.input_sha256,
        request_payload=run.input_payload,
        validator=AIContractValidator(),
    )
    assert replay.idempotent_replay is True
    assert EvidenceLink.objects.filter(inquiry=inquiry).count() == 1
    http_client.close()
