"""Separate AI question metadata from customer follow-up answers."""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


METADATA_KEYS = {"question_options", "target_field"}
CONSTRAINT_NAME = "fk_inquiry_qa_ai_run_inquiry"
QA_TABLE = "support_inquiry_qa"
AI_RUN_TABLE = "aiops_ai_run"
SQLITE_TRIGGER_NAMES = (
    "fk_inquiry_qa_context_child_insert",
    "fk_inquiry_qa_context_child_update",
    "fk_inquiry_qa_context_parent_update",
)


def add_inquiry_qa_context_constraint(apps, schema_editor):
    """Restore the vendor-specific same-inquiry integrity rule."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            ALTER TABLE {QA_TABLE}
            ADD CONSTRAINT {CONSTRAINT_NAME}
            FOREIGN KEY (source_ai_run_id, inquiry_id)
            REFERENCES {AI_RUN_TABLE} (id, inquiry_id)
            MATCH SIMPLE
            ON DELETE RESTRICT
            """
        )
        return
    if vendor == "sqlite":
        child_insert, child_update, parent_update = SQLITE_TRIGGER_NAMES
        schema_editor.execute(
            f"""
            CREATE TRIGGER {child_insert}
            BEFORE INSERT ON {QA_TABLE}
            FOR EACH ROW
            WHEN NEW.source_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1 FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.source_ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(ABORT, '{CONSTRAINT_NAME}');
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {child_update}
            BEFORE UPDATE OF source_ai_run_id, inquiry_id ON {QA_TABLE}
            FOR EACH ROW
            WHEN NEW.source_ai_run_id IS NOT NULL
             AND NOT EXISTS (
                SELECT 1 FROM {AI_RUN_TABLE} parent
                WHERE parent.id = NEW.source_ai_run_id
                  AND parent.inquiry_id = NEW.inquiry_id
            )
            BEGIN
                SELECT RAISE(ABORT, '{CONSTRAINT_NAME}');
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {parent_update}
            BEFORE UPDATE OF id, inquiry_id ON {AI_RUN_TABLE}
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1 FROM {QA_TABLE} child
                WHERE child.source_ai_run_id = OLD.id
                  AND (
                      child.source_ai_run_id <> NEW.id
                      OR child.inquiry_id <> NEW.inquiry_id
                  )
            )
            BEGIN
                SELECT RAISE(ABORT, '{CONSTRAINT_NAME}');
            END
            """
        )
        return
    raise RuntimeError(
        "InquiryQA context migration supports PostgreSQL and SQLite "
        f"only, not {vendor!r}."
    )


def remove_inquiry_qa_context_constraint(apps, schema_editor):
    """Temporarily remove integrity objects before SQLite table remake."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"ALTER TABLE {QA_TABLE} "
            f"DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
        )
        return
    if vendor == "sqlite":
        for trigger_name in SQLITE_TRIGGER_NAMES:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")
        return
    raise RuntimeError(
        "InquiryQA context migration supports PostgreSQL and SQLite "
        f"only, not {vendor!r}."
    )


def split_question_metadata_and_answers(apps, schema_editor):
    """Copy legacy answers while keeping question metadata in place."""

    InquiryQA = apps.get_model("inquiries", "InquiryQA")
    FollowUpAnswer = apps.get_model("inquiries", "FollowUpAnswer")
    using = schema_editor.connection.alias

    for question in InquiryQA.objects.using(using).all().iterator():
        raw_payload = question.answer_payload
        answer_payload = raw_payload
        if isinstance(raw_payload, dict):
            answer_payload = {
                key: value
                for key, value in raw_payload.items()
                if key not in METADATA_KEYS
            } or None
        answer_text = question.answer_text
        if isinstance(answer_text, str):
            answer_text = answer_text.strip() or None
        if not (
            question.answered_at
            and question.answered_by_id
            and (answer_text is not None or answer_payload is not None)
        ):
            continue

        # Historical rows could contain both. Preserve the explicit text as
        # the canonical public answer and leave metadata in the question.
        if answer_text is not None:
            answer_payload = None
        FollowUpAnswer.objects.using(using).create(
            question_id=question.pk,
            answered_by_id=question.answered_by_id,
            answer_text=answer_text,
            answer_payload=answer_payload,
            answered_at=question.answered_at,
        )


def restore_legacy_answer_columns(apps, schema_editor):
    """Backfill only post-0011 answers when rolling back the new table."""

    InquiryQA = apps.get_model("inquiries", "InquiryQA")
    FollowUpAnswer = apps.get_model("inquiries", "FollowUpAnswer")
    using = schema_editor.connection.alias

    answers = {
        answer.question_id: answer
        for answer in FollowUpAnswer.objects.using(using).all().iterator()
    }
    for question in InquiryQA.objects.using(using).all().iterator():
        raw_payload = question.answer_payload
        raw_non_metadata = (
            {
                key: value
                for key, value in raw_payload.items()
                if key not in METADATA_KEYS
            }
            if isinstance(raw_payload, dict)
            else raw_payload
        )
        # Pre-0011 answer values were retained in place. Metadata-only rows
        # can still receive a post-0011 answer during reverse backfill.
        if (
            question.answer_text is not None
            or raw_non_metadata not in (None, {})
            or question.answered_by_id is not None
            or question.answered_at is not None
        ):
            continue
        metadata = (
            {
                key: value
                for key, value in raw_payload.items()
                if key in METADATA_KEYS
            }
            if isinstance(raw_payload, dict)
            else {}
        )

        answer = answers.get(question.pk)
        if answer is not None:
            question.answer_text = answer.answer_text
            question.answered_by_id = answer.answered_by_id
            question.answered_at = answer.answered_at
            if answer.answer_payload is not None:
                if isinstance(answer.answer_payload, dict):
                    question.answer_payload = {
                        **metadata,
                        **answer.answer_payload,
                    }
                else:
                    question.answer_payload = answer.answer_payload
            else:
                question.answer_payload = metadata or None
        else:
            continue
        question.save(
            using=using,
            update_fields=[
                "answer_text",
                "answer_payload",
                "answered_by",
                "answered_at",
            ],
        )


class Migration(migrations.Migration):

    # PostgreSQL cannot add the restored composite FK in the same transaction
    # that just backfilled legacy rows because pending trigger events remain.
    # Keep the data copy atomic while letting each DDL boundary commit first.
    atomic = False

    dependencies = [
        ("inquiries", "0010_customeractionresult"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            remove_inquiry_qa_context_constraint,
            reverse_code=add_inquiry_qa_context_constraint,
        ),
        migrations.CreateModel(
            name="FollowUpAnswer",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.BigAutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "public_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                (
                    "answer_text",
                    models.TextField(blank=True, null=True),
                ),
                (
                    "answer_payload",
                    models.JSONField(blank=True, null=True),
                ),
                (
                    "accepted_state_version",
                    models.PositiveBigIntegerField(
                        blank=True,
                        help_text=(
                            "SUBMIT_ANSWERS 요청이 수락될 때의 Inquiry "
                            "state_version; 0011 이전 이관 데이터는 "
                            "알 수 없어 null"
                        ),
                        null=True,
                    ),
                ),
                (
                    "answered_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "answered_by",
                    models.ForeignKey(
                        db_column="answered_by_id",
                        db_index=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="submitted_followup_answers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "question",
                    models.OneToOneField(
                        db_column="question_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="customer_answer",
                        to="inquiries.inquiryqa",
                    ),
                ),
            ],
            options={
                "db_table": "support_followup_answer",
                "indexes": [
                    models.Index(
                        fields=["answered_by", "answered_at"],
                        name="ix_followup_answer_actor",
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            models.Q(
                                answer_payload__isnull=True,
                                answer_text__isnull=False,
                            )
                            | models.Q(
                                answer_payload__isnull=False,
                                answer_text__isnull=True,
                            )
                        ),
                        name="ck_followup_answer_value_xor",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(accepted_state_version__isnull=True)
                            | models.Q(accepted_state_version__gt=0)
                        ),
                        name="ck_followup_answer_version",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            split_question_metadata_and_answers,
            reverse_code=restore_legacy_answer_columns,
            atomic=True,
        ),
        # The original answer columns, consistency constraint, and answered
        # index belong to the immutable T-005 32-table contract. Keep them in
        # place while new Runtime writes use support_followup_answer.
        migrations.RunPython(
            add_inquiry_qa_context_constraint,
            reverse_code=remove_inquiry_qa_context_constraint,
        ),
    ]
