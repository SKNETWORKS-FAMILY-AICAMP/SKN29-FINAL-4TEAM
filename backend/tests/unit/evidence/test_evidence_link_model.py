"""T-005 Wave 6B evidence-link schema and integrity tests."""

from __future__ import annotations

from decimal import Decimal
from importlib import import_module
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import Q
from django.db.models.deletion import PROTECT, ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AIRetrievalHit, AIRetrievalRun, AIRun
from apps.consultations.models import Consultation
from apps.evidence.models import DocumentChunk, EvidenceLink
from apps.inquiries.models import Guidance, Inquiry
from apps.visits.models import HandoffReport
from tests.unit.evidence.test_document_chunk_model import create_chunk
from tests.unit.inquiries.test_t022_models import create_inquiry


pytestmark = pytest.mark.django_db


def create_guidance(
    sequence: int,
    *,
    inquiry: Inquiry,
) -> Guidance:
    return Guidance.objects.create(
        inquiry=inquiry,
        guidance_version=1,
        title=f"Evidence guidance {sequence}",
        summary_text="Follow the reviewed safety procedure.",
        evidence_sufficiency_code="TEAM_REVIEWED",
    )


def create_consultation(
    sequence: int,
    *,
    inquiry: Inquiry,
) -> Consultation:
    return Consultation.objects.create(
        consultation_code=f"EVIDENCE-CONSULT-{sequence:04d}",
        inquiry=inquiry,
        sequence=1,
        summary="Evidence consultation fixture.",
        idempotency_key=f"evidence-consult-{sequence:04d}",
        correlation_id=uuid4(),
    )


def create_handoff(
    sequence: int,
    *,
    inquiry: Inquiry,
) -> HandoffReport:
    consultation = create_consultation(
        sequence,
        inquiry=inquiry,
    )
    return HandoffReport.objects.create(
        inquiry=inquiry,
        consultation=consultation,
        report_status_code="TEAM_REVIEW_PENDING",
        product_summary="Product summary.",
        symptom_summary="Symptom summary.",
        action_summary="Action summary.",
        risk_summary="Risk summary.",
    )


def create_verifier(
    sequence: int,
    *,
    role_code: str = User.Role.OPERATOR,
) -> User:
    employee_no = (
        f"EVIDENCE-EMP-{sequence:04d}"
        if role_code
        in {
            User.Role.CONSULTANT,
            User.Role.TECHNICIAN,
            User.Role.OPERATOR,
        }
        else None
    )
    return User.objects.create_user(
        username=f"EVIDENCE-VERIFIER-{sequence:04d}",
        password=None,
        full_name=f"Evidence verifier {sequence}",
        role_code=role_code,
        employee_no=employee_no,
    )


def create_ai_run(
    sequence: int,
    *,
    inquiry: Inquiry,
) -> AIRun:
    return AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.RETRIEVE_EVIDENCE,
        response_schema_version="1.0.0",
        input_payload={"query": "official procedure"},
        input_sha256="a" * 64,
        idempotency_key=f"evidence-ai-run-{sequence:04d}",
        correlation_id=uuid4(),
    )


def create_retrieval_run(
    sequence: int,
    *,
    ai_run: AIRun,
) -> AIRetrievalRun:
    return AIRetrievalRun.objects.create(
        ai_run=ai_run,
        inquiry=ai_run.inquiry,
        query_text="Official water-care procedure",
        query_sha256="b" * 64,
        retrieval_config_version="exact-cosine-v1",
        correlation_id=ai_run.correlation_id,
    )


def create_hit(
    sequence: int,
    *,
    retrieval_run: AIRetrievalRun,
    chunk: DocumentChunk,
    selected_for_answer: bool = True,
    applicability_status_code: str = "FUTURE_SELECTED_STATE",
) -> AIRetrievalHit:
    return AIRetrievalHit.objects.create(
        retrieval_run=retrieval_run,
        chunk=chunk,
        rank_no=1,
        vector_score=Decimal("0.875000"),
        applicability_status_code=applicability_status_code,
        selected_for_answer=selected_for_answer,
        selected_at=(
            timezone.now() if selected_for_answer else None
        ),
    )


def target_values(
    sequence: int,
    *,
    inquiry: Inquiry,
    target_kind: str,
):
    if target_kind == "guidance":
        return {
            "guidance": create_guidance(
                sequence,
                inquiry=inquiry,
            )
        }
    if target_kind == "consultation":
        return {
            "consultation": create_consultation(
                sequence,
                inquiry=inquiry,
            )
        }
    if target_kind == "handoff_report":
        return {
            "handoff_report": create_handoff(
                sequence,
                inquiry=inquiry,
            )
        }
    raise AssertionError(f"Unsupported target kind: {target_kind}")


def link_values(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
    chunk: DocumentChunk | None = None,
    target_kind: str = "guidance",
    target: object | None = None,
    **overrides,
) -> dict:
    assigned_inquiry = inquiry or create_inquiry(sequence)
    assigned_chunk = chunk or create_chunk(sequence)
    document = assigned_chunk.page.document
    if target is None:
        target_mapping = target_values(
            sequence,
            inquiry=assigned_inquiry,
            target_kind=target_kind,
        )
    else:
        target_mapping = {target_kind: target}

    values = {
        "inquiry": assigned_inquiry,
        "chunk": assigned_chunk,
        **target_mapping,
        "selection_origin_code": "MANUAL",
        "evidence_role_code": "SUPPORTING",
        "display_order": 1,
        "citation_label": (
            f"{document.title} p.{assigned_chunk.page.page_no}"
        ),
        "document_code_snapshot": document.document_code,
        "document_title_snapshot": document.title,
        "source_org_snapshot": document.source_org,
        "revision_label_snapshot": document.revision_label,
        "official_source_url_snapshot": (
            document.official_source_url
        ),
        "document_sha256_snapshot": document.sha256_hash,
        "evidence_summary": "Reviewed official evidence summary.",
        "cited_text_snapshot": assigned_chunk.chunk_text,
        "page_no_snapshot": assigned_chunk.page.page_no,
        "section_snapshot": assigned_chunk.section_path,
        "product_model_codes_snapshot": ["WPU-JAC104D"],
    }
    values.update(overrides)
    return values


def automatic_link_values(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
    chunk: DocumentChunk | None = None,
    target_kind: str = "guidance",
    **overrides,
) -> dict:
    assigned_inquiry = inquiry or create_inquiry(sequence)
    assigned_chunk = chunk or create_chunk(sequence)
    ai_run = create_ai_run(sequence, inquiry=assigned_inquiry)
    retrieval_run = create_retrieval_run(
        sequence,
        ai_run=ai_run,
    )
    retrieval_hit = create_hit(
        sequence,
        retrieval_run=retrieval_run,
        chunk=assigned_chunk,
    )
    values = link_values(
        sequence,
        inquiry=assigned_inquiry,
        chunk=assigned_chunk,
        target_kind=target_kind,
        selection_origin_code="AUTO_RETRIEVAL",
        ai_run=ai_run,
        retrieval_run=retrieval_run,
        retrieval_hit=retrieval_hit,
    )
    values.update(overrides)
    return values


def test_evidence_link_uses_target_identifiers_fields_and_defaults():
    link = EvidenceLink.objects.create(**link_values(1))
    field_names = {
        field.name for field in EvidenceLink._meta.local_fields
    }

    assert isinstance(link.pk, int)
    assert isinstance(link.public_id, UUID)
    assert link._meta.db_table == "knowledge_evidence_link"
    assert link.selection_origin_code == "MANUAL"
    assert link.evidence_role_code == "SUPPORTING"
    assert link.display_order == 1
    assert link.is_verified is False
    assert link.verified_by is None
    assert link.verified_at is None
    assert len(field_names) == 30
    assert field_names == {
        "created_at",
        "updated_at",
        "id",
        "public_id",
        "inquiry",
        "guidance",
        "consultation",
        "handoff_report",
        "ai_run",
        "chunk",
        "retrieval_hit",
        "retrieval_run",
        "selection_origin_code",
        "evidence_role_code",
        "display_order",
        "citation_label",
        "document_code_snapshot",
        "document_title_snapshot",
        "source_org_snapshot",
        "revision_label_snapshot",
        "official_source_url_snapshot",
        "document_sha256_snapshot",
        "evidence_summary",
        "cited_text_snapshot",
        "page_no_snapshot",
        "section_snapshot",
        "product_model_codes_snapshot",
        "is_verified",
        "verified_by",
        "verified_at",
    }


def test_evidence_link_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.get_model("EvidenceLink") is EvidenceLink
    assert EvidenceLink._meta.app_label == "evidence"


def test_fk_policy_and_migration_dependency():
    expected_models = {
        "inquiry": Inquiry,
        "guidance": Guidance,
        "consultation": Consultation,
        "handoff_report": HandoffReport,
        "ai_run": AIRun,
        "chunk": DocumentChunk,
        "retrieval_hit": AIRetrievalHit,
        "retrieval_run": AIRetrievalRun,
        "verified_by": User,
    }
    for field_name, expected_model in expected_models.items():
        field = EvidenceLink._meta.get_field(field_name)
        assert field.remote_field.model is expected_model
        assert field.remote_field.on_delete is PROTECT
        assert field.db_column == f"{field_name}_id"
        assert field.db_index is False

    migration = import_module(
        "apps.evidence.migrations.0008_evidencelink"
    )
    assert migration.Migration.dependencies == [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("audit", "0004_airetrievalhit"),
        ("consultations", "0001_initial"),
        ("evidence", "0007_chunkembedding"),
        ("inquiries", "0008_guidance"),
        ("visits", "0003_handoffreport"),
    ]


def test_indexes_and_constraints_match_physical_contract():
    indexes = {
        index.name: tuple(index.fields)
        for index in EvidenceLink._meta.indexes
    }
    constraints = {
        constraint.name
        for constraint in EvidenceLink._meta.constraints
    }

    assert indexes == {
        "ix_evidence_link_inquiry": ("inquiry", "created_at"),
        "ix_evidence_link_guidance": ("guidance", "inquiry"),
        "ix_evidence_link_consultation": (
            "consultation",
            "inquiry",
        ),
        "ix_evidence_link_handoff": (
            "handoff_report",
            "inquiry",
        ),
        "ix_evidence_link_chunk": ("chunk",),
        "ix_evidence_link_ai_run": ("ai_run", "inquiry"),
        "ix_evidence_link_retrieval_hit": (
            "retrieval_hit",
            "retrieval_run",
            "chunk",
        ),
    }
    assert constraints == {
        "ux_evidence_guidance_chunk",
        "ux_evidence_consultation_chunk",
        "ux_evidence_handoff_chunk",
        "ux_evidence_guidance_order",
        "ux_evidence_consultation_order",
        "ux_evidence_handoff_order",
        "ck_evidence_exactly_one_target",
        "ck_evidence_display_order",
        "ck_evidence_page_no",
        "ck_evidence_verification",
        "ck_evidence_document_hash",
        "ck_evidence_product_models",
        "ck_evidence_retrieval_bundle",
        "ck_evidence_selection_origin_nonempty",
        "ck_evidence_role_nonempty",
        "ck_evidence_required_text",
    }


def test_unapproved_code_sets_remain_open():
    origin_field = EvidenceLink._meta.get_field(
        "selection_origin_code"
    )
    role_field = EvidenceLink._meta.get_field(
        "evidence_role_code"
    )
    constraint_names = {
        constraint.name
        for constraint in EvidenceLink._meta.constraints
    }

    assert not origin_field.choices
    assert not role_field.choices
    assert "ck_evidence_selection_origin" not in constraint_names
    assert (
        "ck_knowledge_evidence_link_selection_origin_code_allowed"
        not in constraint_names
    )
    assert (
        "ck_knowledge_evidence_link_evidence_role_code_allowed"
        not in constraint_names
    )

    link = EvidenceLink.objects.create(
        **link_values(
            2,
            selection_origin_code="FUTURE_SELECTION_ORIGIN",
            evidence_role_code="FUTURE_EVIDENCE_ROLE",
        )
    )
    assert link.selection_origin_code == "FUTURE_SELECTION_ORIGIN"
    assert link.evidence_role_code == "FUTURE_EVIDENCE_ROLE"


@pytest.mark.parametrize(
    ("target_kind", "sequence"),
    [
        ("guidance", 10),
        ("consultation", 11),
        ("handoff_report", 12),
    ],
)
def test_each_single_result_target_is_valid(target_kind, sequence):
    link = EvidenceLink(**link_values(sequence, target_kind=target_kind))

    link.full_clean()
    link.save()

    assert getattr(link, f"{target_kind}_id") is not None


def test_database_requires_exactly_one_result_target():
    no_target = link_values(20)
    no_target["guidance"] = None

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(**no_target)

    two_targets = link_values(21)
    two_targets["consultation"] = create_consultation(
        21,
        inquiry=two_targets["inquiry"],
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(**two_targets)


@pytest.mark.parametrize(
    "overrides",
    [
        {"display_order": 0},
        {"page_no_snapshot": 0},
        {"document_sha256_snapshot": "A" * 64},
        {"product_model_codes_snapshot": []},
        {"product_model_codes_snapshot": {}},
        {"selection_origin_code": "\t\r\n"},
        {"evidence_role_code": "   "},
        {"citation_label": "\n"},
        {"evidence_summary": "\t"},
        {"cited_text_snapshot": " "},
    ],
)
def test_database_rejects_invalid_structural_values(overrides):
    sequence = 30 + len(str(overrides))
    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(sequence, **overrides)
        )


def test_verification_bundle_and_verifier_role_policy():
    verifier = create_verifier(50)

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                50,
                is_verified=True,
                verified_by=verifier,
                verified_at=None,
            )
        )

    verified = EvidenceLink.objects.create(
        **link_values(
            51,
            is_verified=True,
            verified_by=verifier,
            verified_at=timezone.now(),
        )
    )
    assert verified.is_verified is True

    customer = create_verifier(
        52,
        role_code=User.Role.CUSTOMER,
    )
    invalid_role = EvidenceLink(
        **link_values(
            52,
            is_verified=True,
            verified_by=customer,
            verified_at=timezone.now(),
        )
    )
    with pytest.raises(ValidationError) as exc_info:
        invalid_role.full_clean()
    assert "verified_by" in exc_info.value.message_dict


def test_complete_retrieval_context_accepts_open_applicability_code():
    link = EvidenceLink(**automatic_link_values(60))

    link.full_clean()
    link.save()

    assert link.retrieval_hit.selected_for_answer is True
    assert (
        link.retrieval_hit.applicability_status_code
        == "FUTURE_SELECTED_STATE"
    )


@pytest.mark.parametrize(
    "bundle_shape",
    [
        "hit_only",
        "run_only",
        "run_and_ai_without_hit",
    ],
)
def test_database_rejects_partial_retrieval_bundle(bundle_shape):
    sequence = {
        "hit_only": 70,
        "run_only": 71,
        "run_and_ai_without_hit": 72,
    }[bundle_shape]
    inquiry = create_inquiry(sequence)
    chunk = create_chunk(sequence)
    ai_run = create_ai_run(sequence, inquiry=inquiry)
    retrieval_run = create_retrieval_run(
        sequence,
        ai_run=ai_run,
    )
    hit = create_hit(
        sequence,
        retrieval_run=retrieval_run,
        chunk=chunk,
    )
    values = link_values(
        sequence,
        inquiry=inquiry,
        chunk=chunk,
    )
    if bundle_shape == "hit_only":
        values["retrieval_hit"] = hit
    elif bundle_shape == "run_only":
        values["retrieval_run"] = retrieval_run
    else:
        values["retrieval_run"] = retrieval_run
        values["ai_run"] = ai_run

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(**values)


def test_model_requires_retrieval_hit_selected_for_answer():
    inquiry = create_inquiry(80)
    chunk = create_chunk(80)
    ai_run = create_ai_run(80, inquiry=inquiry)
    retrieval_run = create_retrieval_run(80, ai_run=ai_run)
    hit = create_hit(
        80,
        retrieval_run=retrieval_run,
        chunk=chunk,
        selected_for_answer=False,
    )
    link = EvidenceLink(
        **link_values(
            80,
            inquiry=inquiry,
            chunk=chunk,
            selection_origin_code="FUTURE_AUTO_ORIGIN",
            ai_run=ai_run,
            retrieval_run=retrieval_run,
            retrieval_hit=hit,
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        link.full_clean()
    assert "retrieval_hit" in exc_info.value.message_dict


@pytest.mark.parametrize(
    ("target_kind", "sequence"),
    [
        ("guidance", 90),
        ("consultation", 91),
        ("handoff_report", 92),
    ],
)
def test_database_rejects_result_target_inquiry_mismatch(
    target_kind,
    sequence,
):
    target_inquiry = create_inquiry(sequence)
    link_inquiry = create_inquiry(sequence + 100)
    target = target_values(
        sequence,
        inquiry=target_inquiry,
        target_kind=target_kind,
    )[target_kind]

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                sequence,
                inquiry=link_inquiry,
                target_kind=target_kind,
                target=target,
            )
        )


def test_database_rejects_ai_run_inquiry_mismatch():
    target_inquiry = create_inquiry(100)
    ai_inquiry = create_inquiry(101)
    ai_run = create_ai_run(100, inquiry=ai_inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                100,
                inquiry=target_inquiry,
                ai_run=ai_run,
            )
        )


def test_database_rejects_retrieval_hit_run_or_chunk_mismatch():
    inquiry = create_inquiry(110)
    first_chunk = create_chunk(110)
    other_chunk = create_chunk(111)
    first_ai = create_ai_run(110, inquiry=inquiry)
    first_run = create_retrieval_run(110, ai_run=first_ai)
    hit = create_hit(
        110,
        retrieval_run=first_run,
        chunk=first_chunk,
    )
    other_ai = create_ai_run(111, inquiry=inquiry)
    other_run = create_retrieval_run(111, ai_run=other_ai)

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                110,
                inquiry=inquiry,
                chunk=first_chunk,
                ai_run=other_ai,
                retrieval_run=other_run,
                retrieval_hit=hit,
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                111,
                inquiry=inquiry,
                chunk=other_chunk,
                ai_run=first_ai,
                retrieval_run=first_run,
                retrieval_hit=hit,
            )
        )


def test_database_rejects_retrieval_run_ai_inquiry_mismatch():
    first_inquiry = create_inquiry(120)
    other_inquiry = create_inquiry(121)
    chunk = create_chunk(120)
    first_ai = create_ai_run(120, inquiry=first_inquiry)
    first_run = create_retrieval_run(120, ai_run=first_ai)
    hit = create_hit(
        120,
        retrieval_run=first_run,
        chunk=chunk,
    )
    other_ai = create_ai_run(121, inquiry=other_inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                120,
                inquiry=other_inquiry,
                chunk=chunk,
                ai_run=other_ai,
                retrieval_run=first_run,
                retrieval_hit=hit,
            )
        )


@pytest.mark.parametrize(
    ("target_kind", "sequence"),
    [
        ("guidance", 130),
        ("consultation", 131),
        ("handoff_report", 132),
    ],
)
def test_target_chunk_role_and_display_order_are_unique(
    target_kind,
    sequence,
):
    inquiry = create_inquiry(sequence)
    chunk = create_chunk(sequence)
    target = target_values(
        sequence,
        inquiry=inquiry,
        target_kind=target_kind,
    )[target_kind]
    EvidenceLink.objects.create(
        **link_values(
            sequence,
            inquiry=inquiry,
            chunk=chunk,
            target_kind=target_kind,
            target=target,
        )
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                sequence + 1000,
                inquiry=inquiry,
                chunk=chunk,
                target_kind=target_kind,
                target=target,
                display_order=2,
            )
        )

    other_chunk = create_chunk(sequence + 2000)
    with pytest.raises(IntegrityError), transaction.atomic():
        EvidenceLink.objects.create(
            **link_values(
                sequence + 2000,
                inquiry=inquiry,
                chunk=other_chunk,
                target_kind=target_kind,
                target=target,
                evidence_role_code="SECONDARY_OPEN_ROLE",
                display_order=1,
            )
        )


def test_parent_context_updates_are_blocked_bidirectionally():
    values = automatic_link_values(140)
    link = EvidenceLink.objects.create(**values)
    other_inquiry = create_inquiry(141)

    with pytest.raises(IntegrityError), transaction.atomic():
        Guidance.objects.filter(pk=link.guidance_id).update(
            inquiry=other_inquiry
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        AIRun.objects.filter(pk=link.ai_run_id).update(
            inquiry=other_inquiry
        )

    other_ai = create_ai_run(141, inquiry=link.inquiry)
    with pytest.raises(IntegrityError), transaction.atomic():
        AIRetrievalRun.objects.filter(
            pk=link.retrieval_run_id
        ).update(ai_run=other_ai)

    other_chunk = create_chunk(141)
    with pytest.raises(IntegrityError), transaction.atomic():
        AIRetrievalHit.objects.filter(
            pk=link.retrieval_hit_id
        ).update(chunk=other_chunk)

    consultation_values = link_values(
        142,
        target_kind="consultation",
    )
    consultation_link = EvidenceLink.objects.create(
        **consultation_values
    )
    other_consultation_inquiry = create_inquiry(1420)
    with pytest.raises(IntegrityError), transaction.atomic():
        Consultation.objects.filter(
            pk=consultation_link.consultation_id
        ).update(inquiry=other_consultation_inquiry)


def test_all_referenced_parent_deletions_are_protected():
    verifier = create_verifier(150)
    link = EvidenceLink.objects.create(
        **automatic_link_values(
            150,
            is_verified=True,
            verified_by=verifier,
            verified_at=timezone.now(),
        )
    )

    for parent in (
        link.guidance,
        link.inquiry,
        link.ai_run,
        link.chunk,
        link.retrieval_hit,
        link.retrieval_run,
        link.verified_by,
    ):
        with pytest.raises(ProtectedError):
            parent.delete()


def test_context_integrity_catalog_is_installed():
    migration = import_module(
        "apps.evidence.migrations.0008_evidencelink"
    )

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND name LIKE 'fk_evidence_%_context_%'
                ORDER BY name
                """
            )
            names = {row[0] for row in cursor.fetchall()}
            assert names == set(migration.SQLITE_TRIGGER_NAMES)
            assert len(names) == 18
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid =
                    'knowledge_evidence_link'::regclass
                """
            )
            names = {row[0] for row in cursor.fetchall()}
            assert {
                item[0]
                for item in migration.POSTGRES_COMPOSITE_FOREIGN_KEYS
            } <= names
            cursor.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE tgrelid IN (
                    'knowledge_evidence_link'::regclass,
                    'support_consultation'::regclass
                )
                  AND NOT tgisinternal
                """
            )
            trigger_names = {
                row[0] for row in cursor.fetchall()
            }
            assert {
                migration.POSTGRES_CONSULT_CHILD_TRIGGER,
                migration.POSTGRES_CONSULT_PARENT_TRIGGER,
            } <= trigger_names
        else:
            pytest.fail(
                f"Unsupported database vendor: {connection.vendor}"
            )


def test_partial_unique_conditions_match_target_presence():
    conditions = {
        constraint.name: constraint.condition
        for constraint in EvidenceLink._meta.constraints
        if isinstance(constraint, models.UniqueConstraint)
    }

    assert conditions["ux_evidence_guidance_chunk"] == Q(
        guidance__isnull=False
    )
    assert conditions["ux_evidence_consultation_chunk"] == Q(
        consultation__isnull=False
    )
    assert conditions["ux_evidence_handoff_chunk"] == Q(
        handoff_report__isnull=False
    )
