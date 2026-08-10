"""Data-preservation proof for the InquiryQA compatibility migration."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
import pytest

from tests.api.test_t022_submit_symptom import create_inquiry, create_user


OLD_TARGET = [("inquiries", "0010_customeractionresult")]
NEW_TARGET = [
    ("inquiries", "0011_split_followup_question_metadata_and_answers")
]


@pytest.mark.django_db(transaction=True)
def test_0010_to_0011_preserves_metadata_text_and_structured_answers():
    owner = create_user(901)
    _client, inquiry, _subscription = create_inquiry(owner, 901)
    answered_at = timezone.now()

    try:
        executor = MigrationExecutor(connection)
        executor.migrate(OLD_TARGET)
        old_apps = executor.loader.project_state(OLD_TARGET).apps
        OldInquiryQA = old_apps.get_model("inquiries", "InquiryQA")

        metadata = OldInquiryQA.objects.create(
            inquiry_id=inquiry.pk,
            sequence_no=1,
            question_code="MIG-META",
            question_text="Metadata only",
            answer_type_code="SINGLE_CHOICE",
            answer_payload={
                "question_options": ["YES", "NO"],
                "target_field": "filter_changed",
            },
            asked_by_type_code="RULE",
        )
        text = OldInquiryQA.objects.create(
            inquiry_id=inquiry.pk,
            sequence_no=2,
            question_code="MIG-TEXT",
            question_text="Text answer",
            answer_type_code="FREE_TEXT",
            answer_text="  two days ago  ",
            answer_payload={
                "target_field": "occurrence_time",
                "legacy_raw": {"selected_option": "YESTERDAY"},
            },
            asked_by_type_code="RULE",
            answered_by_id=owner.pk,
            answered_at=answered_at,
        )
        structured = OldInquiryQA.objects.create(
            inquiry_id=inquiry.pk,
            sequence_no=3,
            question_code="MIG-CHOICE",
            question_text="Choice answer",
            answer_type_code="SINGLE_CHOICE",
            answer_payload={
                "question_options": ["YES", "NO"],
                "target_field": "filter_changed",
                "selected_option": "YES",
            },
            asked_by_type_code="RULE",
            answered_by_id=owner.pk,
            answered_at=answered_at,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(NEW_TARGET)
        new_apps = executor.loader.project_state(NEW_TARGET).apps
        NewInquiryQA = new_apps.get_model("inquiries", "InquiryQA")
        FollowUpAnswer = new_apps.get_model(
            "inquiries", "FollowUpAnswer"
        )

        migrated_metadata = NewInquiryQA.objects.get(pk=metadata.pk)
        migrated_text = NewInquiryQA.objects.get(pk=text.pk)
        migrated_structured = NewInquiryQA.objects.get(pk=structured.pk)

        assert migrated_metadata.answer_payload == {
            "question_options": ["YES", "NO"],
            "target_field": "filter_changed",
        }
        # The immutable T-005 columns remain physically available.
        assert migrated_text.answer_text == "  two days ago  "
        assert migrated_text.answer_payload == {
            "target_field": "occurrence_time",
            "legacy_raw": {"selected_option": "YESTERDAY"},
        }
        assert migrated_structured.answer_payload["selected_option"] == "YES"

        assert not FollowUpAnswer.objects.filter(
            question_id=metadata.pk
        ).exists()
        text_answer = FollowUpAnswer.objects.get(question_id=text.pk)
        choice_answer = FollowUpAnswer.objects.get(
            question_id=structured.pk
        )
        assert text_answer.answer_text == "two days ago"
        assert text_answer.answer_payload is None
        assert choice_answer.answer_text is None
        assert choice_answer.answer_payload == {"selected_option": "YES"}
        assert text_answer.answered_by_id == owner.pk
        assert text_answer.accepted_state_version is None
        assert choice_answer.accepted_state_version is None

        post_migration_question = NewInquiryQA.objects.create(
            inquiry_id=inquiry.pk,
            sequence_no=4,
            question_code="MIG-POST-0011",
            question_text="Created after 0011",
            answer_type_code="FREE_TEXT",
            answer_payload={
                "question_options": [],
                "target_field": "post_migration_field",
            },
            asked_by_type_code="RULE",
        )
        FollowUpAnswer.objects.create(
            question_id=post_migration_question.pk,
            answered_by_id=owner.pk,
            answer_text="new answer",
            accepted_state_version=2,
            answered_at=answered_at,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(OLD_TARGET)
        reversed_apps = executor.loader.project_state(OLD_TARGET).apps
        ReversedInquiryQA = reversed_apps.get_model(
            "inquiries", "InquiryQA"
        )
        assert ReversedInquiryQA.objects.get(pk=text.pk).answer_text == (
            "  two days ago  "
        )
        assert ReversedInquiryQA.objects.get(pk=text.pk).answer_payload == {
            "target_field": "occurrence_time",
            "legacy_raw": {"selected_option": "YESTERDAY"},
        }
        assert ReversedInquiryQA.objects.get(
            pk=structured.pk
        ).answer_payload == {
            "question_options": ["YES", "NO"],
            "target_field": "filter_changed",
            "selected_option": "YES",
        }
        reversed_new = ReversedInquiryQA.objects.get(
            pk=post_migration_question.pk
        )
        assert reversed_new.answer_text == "new answer"
        assert reversed_new.answer_payload == {
            "question_options": [],
            "target_field": "post_migration_field"
        }
        assert reversed_new.answered_by_id == owner.pk
    finally:
        MigrationExecutor(connection).migrate(NEW_TARGET)
