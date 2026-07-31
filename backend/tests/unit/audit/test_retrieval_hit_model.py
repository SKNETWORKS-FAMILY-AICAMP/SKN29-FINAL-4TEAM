"""T-005 Wave 5A retrieval-hit model and persistence tests."""

from decimal import Decimal
from importlib import import_module
from uuid import UUID

import pytest
from django.apps import apps
from django.db import IntegrityError, models, transaction
from django.db.models import Q
from django.db.models.deletion import PROTECT, ProtectedError
from django.utils import timezone

from apps.audit.models import AIRetrievalHit, AIRetrievalRun
from apps.evidence.models import DocumentChunk
from tests.unit.audit.test_retrieval_run_model import (
    retrieval_values,
)
from tests.unit.evidence.test_document_chunk_model import (
    create_chunk,
)


pytestmark = pytest.mark.django_db


def create_retrieval_run(sequence: int) -> AIRetrievalRun:
    return AIRetrievalRun.objects.create(
        **retrieval_values(sequence)
    )


def hit_values(
    sequence: int,
    *,
    retrieval_run: AIRetrievalRun | None = None,
    chunk: DocumentChunk | None = None,
    **overrides,
) -> dict:
    values = {
        "retrieval_run": (
            retrieval_run or create_retrieval_run(sequence)
        ),
        "chunk": chunk or create_chunk(sequence),
        "rank_no": 1,
        "vector_score": Decimal("0.875000"),
    }
    values.update(overrides)
    return values


def create_hit(sequence: int, **overrides) -> AIRetrievalHit:
    return AIRetrievalHit.objects.create(
        **hit_values(sequence, **overrides)
    )


def test_retrieval_hit_uses_target_identifiers_fields_and_defaults():
    hit = create_hit(1)
    field_names = {
        field.name for field in AIRetrievalHit._meta.local_fields
    }

    assert isinstance(hit.pk, int)
    assert isinstance(hit.public_id, UUID)
    assert hit._meta.db_table == "aiops_retrieval_hit"
    assert hit.applicability_status_code == "PENDING"
    assert hit.applicability_reason is None
    assert hit.selected_for_answer is False
    assert hit.selected_at is None
    assert hit.keyword_score is None
    assert hit.hybrid_score is None
    assert hit.rerank_score is None
    assert hit.retrieval_run.hits.get() == hit
    assert hit.chunk.retrieval_hits.get() == hit
    assert len(field_names) == 15


def test_retrieval_hit_is_exported_and_runtime_registered():
    config = apps.get_app_config("audit")

    assert config.get_model("AIRetrievalHit") is AIRetrievalHit
    assert AIRetrievalHit._meta.app_label == "audit"


def test_fk_policy_and_migration_dependency():
    retrieval_run = AIRetrievalHit._meta.get_field(
        "retrieval_run"
    )
    chunk = AIRetrievalHit._meta.get_field("chunk")

    assert retrieval_run.remote_field.model is AIRetrievalRun
    assert retrieval_run.remote_field.on_delete is PROTECT
    assert retrieval_run.db_column == "retrieval_run_id"
    assert retrieval_run.db_index is False
    assert chunk.remote_field.model is DocumentChunk
    assert chunk.remote_field.on_delete is PROTECT
    assert chunk.db_column == "chunk_id"
    assert chunk.db_index is False

    migration = import_module(
        "apps.audit.migrations.0004_airetrievalhit"
    )
    assert migration.Migration.dependencies == [
        ("audit", "0003_airetrievalrun"),
        ("evidence", "0005_documentchunk"),
    ]


def test_decimal_precision_and_exact_search_default_shape():
    for field_name in (
        "vector_score",
        "keyword_score",
        "hybrid_score",
        "rerank_score",
    ):
        field = AIRetrievalHit._meta.get_field(field_name)
        assert isinstance(field, models.DecimalField)
        assert field.max_digits == 10
        assert field.decimal_places == 6
        assert field.null is True

    hit = create_hit(2)
    hit.refresh_from_db()

    assert hit.vector_score == Decimal("0.875000")
    assert hit.keyword_score is None
    assert hit.hybrid_score is None
    assert hit.rerank_score is None


def test_open_applicability_code_and_deferred_contracts():
    field = AIRetrievalHit._meta.get_field(
        "applicability_status_code"
    )
    constraint_names = {
        constraint.name
        for constraint in AIRetrievalHit._meta.constraints
    }

    assert not field.choices
    assert (
        "ck_aiops_retrieval_hit_applicability_status_code_allowed"
        not in constraint_names
    )
    assert (
        "ck_retrieval_hit_applicability_reason"
        not in constraint_names
    )

    hit = create_hit(
        3,
        applicability_status_code="FUTURE_REVIEW_STATE",
    )
    assert (
        hit.applicability_status_code
        == "FUTURE_REVIEW_STATE"
    )


def test_indexes_and_constraints_match_active_contract():
    indexes = {
        index.name: index for index in AIRetrievalHit._meta.indexes
    }
    constraints = {
        constraint.name
        for constraint in AIRetrievalHit._meta.constraints
    }

    assert set(indexes) == {
        "ix_retrieval_hit_selected",
        "ix_retrieval_hit_chunk",
    }
    assert indexes["ix_retrieval_hit_selected"].condition == Q(
        selected_for_answer=True
    )
    assert constraints == {
        "ux_retrieval_hit_rank",
        "ux_retrieval_hit_chunk",
        "ux_retrieval_hit_id_chunk",
        "ux_retrieval_hit_id_run_chunk",
        "ck_retrieval_hit_rank",
        "ck_retrieval_hit_score",
        "ck_retrieval_hit_selected",
        "ck_retrieval_hit_applicability_nonempty",
    }


def test_rank_and_chunk_are_unique_within_retrieval_run():
    run = create_retrieval_run(10)
    first_chunk = create_chunk(10)
    second_chunk = create_chunk(11)
    create_hit(
        10,
        retrieval_run=run,
        chunk=first_chunk,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(
            11,
            retrieval_run=run,
            chunk=second_chunk,
            rank_no=1,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(
            12,
            retrieval_run=run,
            chunk=first_chunk,
            rank_no=2,
        )

    other_run_hit = create_hit(
        13,
        chunk=first_chunk,
        rank_no=1,
    )
    assert other_run_hit.chunk == first_chunk


def test_database_rejects_nonpositive_rank():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(20, rank_no=0)


def test_database_requires_at_least_one_score():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(
            21,
            vector_score=None,
            keyword_score=None,
            hybrid_score=None,
            rerank_score=None,
        )


@pytest.mark.parametrize(
    "score_field",
    [
        "vector_score",
        "keyword_score",
        "hybrid_score",
        "rerank_score",
    ],
)
def test_each_single_score_satisfies_structural_score_check(
    score_field,
):
    values = {
        "vector_score": None,
        "keyword_score": None,
        "hybrid_score": None,
        "rerank_score": None,
        score_field: Decimal("-0.125000"),
    }
    hit = create_hit(
        30,
        **values,
    )

    assert getattr(hit, score_field) == Decimal("-0.125000")


def test_selected_boolean_and_timestamp_are_a_pair():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(
            40,
            selected_for_answer=True,
            selected_at=None,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(
            41,
            selected_for_answer=False,
            selected_at=timezone.now(),
        )

    selected = create_hit(
        42,
        applicability_status_code="FUTURE_SELECTED_STATE",
        selected_for_answer=True,
        selected_at=timezone.now(),
    )
    assert selected.selected_for_answer is True


@pytest.mark.parametrize(
    "status_code",
    ["PARTIAL", "NOT_APPLICABLE"],
)
def test_unapproved_reason_policy_is_deferred(status_code):
    hit = create_hit(
        50,
        applicability_status_code=status_code,
        applicability_reason=None,
    )

    assert hit.applicability_reason is None


def test_database_rejects_whitespace_only_required_code():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(
            60,
            applicability_status_code="\t\r\n",
        )


def test_public_id_is_unique_and_parent_deletions_are_protected():
    hit = create_hit(70)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_hit(71, public_id=hit.public_id)

    with pytest.raises(ProtectedError):
        hit.retrieval_run.delete()
    with pytest.raises(ProtectedError):
        hit.chunk.delete()
