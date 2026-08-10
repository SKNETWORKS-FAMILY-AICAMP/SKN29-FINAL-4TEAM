"""T-005 inquiry follow-up QA model and database integrity tests."""

from uuid import UUID, uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models.deletion import PROTECT, ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AIRun
from apps.inquiries.models import FollowUpAnswer, Inquiry, InquiryQA
from tests.unit.inquiries.test_t022_models import create_inquiry


pytestmark = pytest.mark.django_db


def qa_values(
    sequence: int,
    *,
    inquiry: Inquiry | None = None,
    **overrides,
):
    values = {
        "inquiry": inquiry or create_inquiry(sequence),
        "sequence_no": 1,
        "question_code": f"RULE-QUESTION-{sequence:04d}",
        "question_text": "When did the symptom begin?",
        "answer_type_code": "FREE_TEXT",
        "asked_by_type_code": "RULE",
    }
    values.update(overrides)
    return values


def create_passed_question_run(
    sequence: int,
    inquiry: Inquiry,
) -> AIRun:
    now = timezone.now()
    return AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.GENERATE_QUESTIONS,
        response_schema_version="1.0.0",
        model_provider="local",
        model_name="contract-test-model",
        prompt_version="question-prompt-v1",
        input_payload={"inquiry_id": str(inquiry.public_id)},
        input_sha256="b" * 64,
        idempotency_key=f"inquiry-qa-ai-run-{sequence:04d}",
        raw_output_text='{"questions": []}',
        validated_output_payload={"questions": []},
        schema_validation_status_code=(
            AIRun.SchemaValidationStatus.PASSED
        ),
        status_code=AIRun.Status.SUCCEEDED,
        started_at=now,
        completed_at=now,
        correlation_id=uuid4(),
    )


def test_inquiry_qa_uses_contract_identifiers_fields_and_defaults():
    entry = InquiryQA.objects.create(**qa_values(1))

    assert isinstance(entry.pk, int)
    assert isinstance(entry.public_id, UUID)
    assert entry._meta.db_table == "support_inquiry_qa"
    assert entry.sequence_no == 1
    assert entry.answer_type_code == "FREE_TEXT"
    assert entry.asked_by_type_code == "RULE"
    assert entry.question_options == []
    assert entry.target_field is None
    assert entry.answer_text is None
    assert entry.answer_payload is None
    assert entry.answered_by is None
    assert entry.answered_at is None
    assert entry.created_at is not None
    assert entry.updated_at is not None
    assert entry.inquiry.qa_entries.get() == entry


def test_unapproved_answer_and_origin_code_sets_remain_open():
    answer_type_field = InquiryQA._meta.get_field(
        "answer_type_code"
    )
    origin_field = InquiryQA._meta.get_field(
        "asked_by_type_code"
    )
    constraint_names = {
        constraint.name for constraint in InquiryQA._meta.constraints
    }

    assert not answer_type_field.choices
    assert not origin_field.choices
    assert (
        "ck_support_inquiry_qa_answer_type_code_allowed"
        not in constraint_names
    )
    assert (
        "ck_support_inquiry_qa_asked_by_type_code_allowed"
        not in constraint_names
    )

    entry = InquiryQA.objects.create(
        **qa_values(
            2,
            answer_type_code="FUTURE_ANSWER_TYPE",
            asked_by_type_code="FUTURE_ORIGIN",
        )
    )
    assert entry.answer_type_code == "FUTURE_ANSWER_TYPE"
    assert entry.asked_by_type_code == "FUTURE_ORIGIN"


def test_inquiry_qa_declares_historical_constraints_and_indexes():
    constraint_names = {
        constraint.name for constraint in InquiryQA._meta.constraints
    }
    index_names = {
        index.name for index in InquiryQA._meta.indexes
    }

    assert constraint_names == {
        "ux_inquiry_qa_sequence",
        "ux_inquiry_qa_question",
        "ck_inquiry_qa_answer_consistency",
        "ck_inquiry_qa_sequence",
        "ck_inquiry_qa_ai_origin",
    }
    assert index_names == {
        "ix_inquiry_qa_answered",
        "ix_inquiry_qa_ai_run",
    }


def test_database_rejects_nonpositive_sequence():
    with pytest.raises(IntegrityError), transaction.atomic():
        InquiryQA.objects.create(
            **qa_values(10, sequence_no=0)
        )


def test_database_rejects_incomplete_answer_metadata():
    inquiry = create_inquiry(11)
    question = InquiryQA.objects.create(
        **qa_values(11, inquiry=inquiry)
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        FollowUpAnswer.objects.create(
            question=question,
            answered_by=inquiry.initiated_by,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        FollowUpAnswer.objects.create(
            question=question,
            answered_by=inquiry.initiated_by,
            answer_text="Yesterday.",
            answer_payload={"selected_option": "Yesterday."},
        )


def test_database_enforces_ai_origin_pair():
    inquiry = create_inquiry(13)
    run = create_passed_question_run(13, inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        InquiryQA.objects.create(
            **qa_values(
                13,
                inquiry=inquiry,
                asked_by_type_code="AI",
            )
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        InquiryQA.objects.create(
            **qa_values(
                14,
                inquiry=inquiry,
                asked_by_type_code="RULE",
                source_ai_run=run,
            )
        )


def test_sequence_is_unique_per_inquiry():
    inquiry = create_inquiry(20)
    InquiryQA.objects.create(
        **qa_values(20, inquiry=inquiry)
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        InquiryQA.objects.create(
            **qa_values(
                21,
                inquiry=inquiry,
                question_code="RULE-QUESTION-0021",
            )
        )


def test_question_code_is_conditionally_unique_and_null_is_repeatable():
    inquiry = create_inquiry(22)
    InquiryQA.objects.create(
        **qa_values(22, inquiry=inquiry)
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        InquiryQA.objects.create(
            **qa_values(
                23,
                inquiry=inquiry,
                sequence_no=2,
                question_code="RULE-QUESTION-0022",
            )
        )

    InquiryQA.objects.create(
        **qa_values(
            24,
            inquiry=inquiry,
            sequence_no=2,
            question_code=None,
        )
    )
    InquiryQA.objects.create(
        **qa_values(
            25,
            inquiry=inquiry,
            sequence_no=3,
            question_code=None,
        )
    )

    assert inquiry.qa_entries.filter(question_code__isnull=True).count() == 2


def test_valid_answer_uses_separate_text_or_structured_answer_rows():
    inquiry = create_inquiry(30)
    answered_at = timezone.now()
    answerer = inquiry.initiated_by

    text_question = InquiryQA.objects.create(
        **qa_values(
            30,
            inquiry=inquiry,
        )
    )
    payload_question = InquiryQA.objects.create(
        **qa_values(
            31,
            inquiry=inquiry,
            sequence_no=2,
            answer_type_code="SINGLE_CHOICE",
            answer_payload={"question_options": ["cold", "ambient"]},
        )
    )
    text_entry = FollowUpAnswer.objects.create(
        question=text_question,
        answer_text="Two days ago.",
        answered_by=answerer,
        answered_at=answered_at,
    )
    payload_entry = FollowUpAnswer.objects.create(
        question=payload_question,
        answer_payload={"selected_option": "cold"},
        answered_by=answerer,
        answered_at=answered_at,
    )

    assert text_entry.answer_text == "Two days ago."
    assert payload_entry.answer_payload == {"selected_option": "cold"}
    assert text_question.customer_answer == text_entry
    assert payload_question.customer_answer == payload_entry


def test_full_clean_preserves_legacy_non_metadata_payload_keys():
    inquiry = create_inquiry(32)
    entry = InquiryQA(
        **qa_values(
            32,
            inquiry=inquiry,
            answer_type_code="SINGLE_CHOICE",
            answer_payload={
                "question_options": [" YES "],
                "target_field": "legacy_target",
                "selected_option": "YES",
                "legacy_raw": {"source": "v3"},
            },
        )
    )

    entry.full_clean()

    assert entry.answer_payload == {
        "question_options": ["YES"],
        "target_field": "legacy_target",
        "selected_option": "YES",
        "legacy_raw": {"source": "v3"},
    }


def test_ai_question_accepts_validated_generation_run():
    inquiry = create_inquiry(40)
    run = create_passed_question_run(40, inquiry)
    entry = InquiryQA(
        **qa_values(
            40,
            inquiry=inquiry,
            asked_by_type_code="AI",
            source_ai_run=run,
        )
    )

    entry.full_clean()
    entry.save()

    assert entry.source_ai_run == run


def test_model_rejects_unvalidated_or_wrong_task_ai_run():
    inquiry = create_inquiry(41)
    run = AIRun.objects.create(
        inquiry=inquiry,
        task_type_code=AIRun.TaskType.STRUCTURE_SYMPTOM,
        response_schema_version="1.0.0",
        input_payload={},
        input_sha256="c" * 64,
        idempotency_key="inquiry-qa-ai-run-0041",
        correlation_id=uuid4(),
    )
    entry = InquiryQA(
        **qa_values(
            41,
            inquiry=inquiry,
            asked_by_type_code="AI",
            source_ai_run=run,
        )
    )

    with pytest.raises(ValidationError) as exc_info:
        entry.full_clean()

    assert "source_ai_run" in exc_info.value.message_dict


def test_database_enforces_ai_run_and_question_same_inquiry():
    first_inquiry = create_inquiry(50)
    other_inquiry = create_inquiry(51)
    run = create_passed_question_run(50, first_inquiry)

    with pytest.raises(IntegrityError), transaction.atomic():
        InquiryQA.objects.create(
            **qa_values(
                50,
                inquiry=other_inquiry,
                asked_by_type_code="AI",
                source_ai_run=run,
            )
        )


def test_database_blocks_ai_run_parent_context_change():
    inquiry = create_inquiry(60)
    other_inquiry = create_inquiry(61)
    run = create_passed_question_run(60, inquiry)
    InquiryQA.objects.create(
        **qa_values(
            60,
            inquiry=inquiry,
            asked_by_type_code="AI",
            source_ai_run=run,
        )
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        AIRun.objects.filter(pk=run.pk).update(
            inquiry=other_inquiry
        )


def test_composite_integrity_ddl_is_installed_for_current_database():
    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND name LIKE 'fk_inquiry_qa_context_%'
                ORDER BY name
                """
            )
            names = {row[0] for row in cursor.fetchall()}
            assert names == {
                "fk_inquiry_qa_context_child_insert",
                "fk_inquiry_qa_context_child_update",
                "fk_inquiry_qa_context_parent_update",
            }
        elif connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'support_inquiry_qa'::regclass
                  AND conname = 'fk_inquiry_qa_ai_run_inquiry'
                """
            )
            assert cursor.fetchone() == (
                "fk_inquiry_qa_ai_run_inquiry",
            )
        else:
            pytest.fail(
                f"Unsupported database vendor: {connection.vendor}"
            )


def test_parent_deletions_are_protected():
    inquiry = create_inquiry(70)
    run = create_passed_question_run(70, inquiry)
    answerer = User.objects.create_user(
        username="INQUIRY-QA-ANSWERER-0070",
        password=None,
        full_name="Inquiry QA answerer 70",
        role_code=User.Role.CUSTOMER,
    )
    question = InquiryQA.objects.create(
        **qa_values(
            70,
            inquiry=inquiry,
            asked_by_type_code="AI",
            source_ai_run=run,
        )
    )
    FollowUpAnswer.objects.create(
        question=question,
        answer_text="Today.",
        answered_by=answerer,
        answered_at=timezone.now(),
    )

    with pytest.raises(ProtectedError):
        run.delete()
    with pytest.raises(ProtectedError):
        answerer.delete()

    assert (
        InquiryQA._meta.get_field("inquiry").remote_field.on_delete
        is PROTECT
    )
