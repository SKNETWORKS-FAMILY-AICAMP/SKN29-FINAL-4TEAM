# Generated from the active T-005 Wave 6B contract on 2026-07-30.

import uuid

import apps.evidence.models.evidence_link
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


EVIDENCE_TABLE = "knowledge_evidence_link"
CONSULTATION_TABLE = "support_consultation"
CONSULTATION_CONTEXT_NAME = "fk_evidence_consultation_inquiry"
POSTGRES_CONSULT_CHILD_TRIGGER = (
    "trg_evidence_consult_context_child"
)
POSTGRES_CONSULT_PARENT_TRIGGER = (
    "trg_evidence_consult_context_parent"
)
POSTGRES_CONSULT_CHILD_FUNCTION = (
    "check_evidence_consultation_inquiry"
)
POSTGRES_CONSULT_PARENT_FUNCTION = (
    "protect_evidence_consultation_inquiry"
)

POSTGRES_COMPOSITE_FOREIGN_KEYS = (
    (
        "fk_evidence_guidance_inquiry",
        ("guidance_id", "inquiry_id"),
        "support_guidance",
        ("id", "inquiry_id"),
    ),
    (
        "fk_evidence_handoff_inquiry",
        ("handoff_report_id", "inquiry_id"),
        "support_handoff_report",
        ("id", "inquiry_id"),
    ),
    (
        "fk_evidence_ai_run_inquiry",
        ("ai_run_id", "inquiry_id"),
        "aiops_ai_run",
        ("id", "inquiry_id"),
    ),
    (
        "fk_evidence_retrieval_hit_context",
        (
            "retrieval_hit_id",
            "retrieval_run_id",
            "chunk_id",
        ),
        "aiops_retrieval_hit",
        ("id", "retrieval_run_id", "chunk_id"),
    ),
    (
        "fk_evidence_retrieval_run_context",
        ("retrieval_run_id", "ai_run_id", "inquiry_id"),
        "aiops_retrieval_run",
        ("id", "ai_run_id", "inquiry_id"),
    ),
)

# constraint, label, child optional FK, parent table, child-to-parent
# column mappings. Each SQLite context receives child INSERT/UPDATE and
# parent UPDATE triggers, matching the bidirectional PostgreSQL behavior.
SQLITE_CONTEXTS = (
    (
        "fk_evidence_guidance_inquiry",
        "guidance",
        "guidance_id",
        "support_guidance",
        (
            ("guidance_id", "id"),
            ("inquiry_id", "inquiry_id"),
        ),
    ),
    (
        CONSULTATION_CONTEXT_NAME,
        "consultation",
        "consultation_id",
        CONSULTATION_TABLE,
        (
            ("consultation_id", "id"),
            ("inquiry_id", "inquiry_id"),
        ),
    ),
    (
        "fk_evidence_handoff_inquiry",
        "handoff",
        "handoff_report_id",
        "support_handoff_report",
        (
            ("handoff_report_id", "id"),
            ("inquiry_id", "inquiry_id"),
        ),
    ),
    (
        "fk_evidence_ai_run_inquiry",
        "ai_run",
        "ai_run_id",
        "aiops_ai_run",
        (
            ("ai_run_id", "id"),
            ("inquiry_id", "inquiry_id"),
        ),
    ),
    (
        "fk_evidence_retrieval_hit_context",
        "retrieval_hit",
        "retrieval_hit_id",
        "aiops_retrieval_hit",
        (
            ("retrieval_hit_id", "id"),
            ("retrieval_run_id", "retrieval_run_id"),
            ("chunk_id", "chunk_id"),
        ),
    ),
    (
        "fk_evidence_retrieval_run_context",
        "retrieval_run",
        "retrieval_run_id",
        "aiops_retrieval_run",
        (
            ("retrieval_run_id", "id"),
            ("ai_run_id", "ai_run_id"),
            ("inquiry_id", "inquiry_id"),
        ),
    ),
)


def _sqlite_trigger_names(label):
    return (
        f"fk_evidence_{label}_context_child_insert",
        f"fk_evidence_{label}_context_child_update",
        f"fk_evidence_{label}_context_parent_update",
    )


SQLITE_TRIGGER_NAMES = tuple(
    trigger_name
    for _, label, _, _, _ in SQLITE_CONTEXTS
    for trigger_name in _sqlite_trigger_names(label)
)


def _add_postgresql_integrity(schema_editor):
    for (
        constraint_name,
        child_columns,
        parent_table,
        parent_columns,
    ) in POSTGRES_COMPOSITE_FOREIGN_KEYS:
        schema_editor.execute(
            f"""
            ALTER TABLE {EVIDENCE_TABLE}
            ADD CONSTRAINT {constraint_name}
            FOREIGN KEY ({", ".join(child_columns)})
            REFERENCES {parent_table} ({", ".join(parent_columns)})
            MATCH SIMPLE
            ON DELETE RESTRICT
            """
        )

    # Consultation currently has no UNIQUE(id, inquiry_id) candidate key.
    # A child trigger and a parent trigger provide the same bidirectional
    # context guarantee without changing a migration owned by another app.
    schema_editor.execute(
        f"""
        CREATE FUNCTION {POSTGRES_CONSULT_CHILD_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.consultation_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1
                   FROM {CONSULTATION_TABLE} parent
                   WHERE parent.id = NEW.consultation_id
                     AND parent.inquiry_id = NEW.inquiry_id
               )
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = '{CONSULTATION_CONTEXT_NAME}',
                    CONSTRAINT = '{CONSULTATION_CONTEXT_NAME}';
            END IF;
            RETURN NEW;
        END
        $function$
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {POSTGRES_CONSULT_CHILD_TRIGGER}
        BEFORE INSERT OR UPDATE OF consultation_id, inquiry_id
        ON {EVIDENCE_TABLE}
        FOR EACH ROW
        EXECUTE FUNCTION {POSTGRES_CONSULT_CHILD_FUNCTION}()
        """
    )
    schema_editor.execute(
        f"""
        CREATE FUNCTION {POSTGRES_CONSULT_PARENT_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF NEW.inquiry_id IS DISTINCT FROM OLD.inquiry_id
               AND EXISTS (
                   SELECT 1
                   FROM {EVIDENCE_TABLE} child
                   WHERE child.consultation_id = OLD.id
                     AND child.inquiry_id IS DISTINCT
                         FROM NEW.inquiry_id
               )
            THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = '{CONSULTATION_CONTEXT_NAME}',
                    CONSTRAINT = '{CONSULTATION_CONTEXT_NAME}';
            END IF;
            RETURN NEW;
        END
        $function$
        """
    )
    schema_editor.execute(
        f"""
        CREATE TRIGGER {POSTGRES_CONSULT_PARENT_TRIGGER}
        BEFORE UPDATE OF inquiry_id
        ON {CONSULTATION_TABLE}
        FOR EACH ROW
        EXECUTE FUNCTION {POSTGRES_CONSULT_PARENT_FUNCTION}()
        """
    )


def _add_sqlite_integrity(schema_editor):
    for (
        constraint_name,
        label,
        optional_child_column,
        parent_table,
        mappings,
    ) in SQLITE_CONTEXTS:
        (
            child_insert,
            child_update,
            parent_update,
        ) = _sqlite_trigger_names(label)
        parent_predicate = "\n                  AND ".join(
            f"parent.{parent_column} = NEW.{child_column}"
            for child_column, parent_column in mappings
        )
        child_columns = ", ".join(
            child_column for child_column, _ in mappings
        )
        parent_context_columns = tuple(
            parent_column
            for _, parent_column in mappings
            if parent_column != "id"
        )
        parent_columns = ", ".join(parent_context_columns)
        parent_mismatch = "\n               OR ".join(
            f"child.{child_column} IS NOT NEW.{parent_column}"
            for child_column, parent_column in mappings
            if parent_column != "id"
        )

        schema_editor.execute(
            f"""
            CREATE TRIGGER {child_insert}
            BEFORE INSERT ON {EVIDENCE_TABLE}
            FOR EACH ROW
            WHEN NEW.{optional_child_column} IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {parent_table} parent
                WHERE {parent_predicate}
            )
            BEGIN
                SELECT RAISE(ABORT, '{constraint_name}');
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {child_update}
            BEFORE UPDATE OF {child_columns}
            ON {EVIDENCE_TABLE}
            FOR EACH ROW
            WHEN NEW.{optional_child_column} IS NOT NULL
             AND NOT EXISTS (
                SELECT 1
                FROM {parent_table} parent
                WHERE {parent_predicate}
            )
            BEGIN
                SELECT RAISE(ABORT, '{constraint_name}');
            END
            """
        )
        schema_editor.execute(
            f"""
            CREATE TRIGGER {parent_update}
            BEFORE UPDATE OF {parent_columns}
            ON {parent_table}
            FOR EACH ROW
            WHEN EXISTS (
                SELECT 1
                FROM {EVIDENCE_TABLE} child
                WHERE child.{optional_child_column} = OLD.id
                  AND ({parent_mismatch})
            )
            BEGIN
                SELECT RAISE(ABORT, '{constraint_name}');
            END
            """
        )


def add_evidence_context_integrity(apps, schema_editor):
    """Enforce every EvidenceLink parent context on supported databases."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        _add_postgresql_integrity(schema_editor)
        return
    if vendor == "sqlite":
        _add_sqlite_integrity(schema_editor)
        return
    raise RuntimeError(
        "EvidenceLink context migration supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


def remove_evidence_context_integrity(apps, schema_editor):
    """Drop vendor-specific context enforcement before table rollback."""

    del apps
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            f"""
            DROP TRIGGER IF EXISTS {POSTGRES_CONSULT_PARENT_TRIGGER}
            ON {CONSULTATION_TABLE}
            """
        )
        schema_editor.execute(
            f"""
            DROP TRIGGER IF EXISTS {POSTGRES_CONSULT_CHILD_TRIGGER}
            ON {EVIDENCE_TABLE}
            """
        )
        schema_editor.execute(
            f"""
            DROP FUNCTION IF EXISTS
            {POSTGRES_CONSULT_PARENT_FUNCTION}()
            """
        )
        schema_editor.execute(
            f"""
            DROP FUNCTION IF EXISTS
            {POSTGRES_CONSULT_CHILD_FUNCTION}()
            """
        )
        for (
            constraint_name,
            _,
            _,
            _,
        ) in reversed(POSTGRES_COMPOSITE_FOREIGN_KEYS):
            schema_editor.execute(
                f"""
                ALTER TABLE {EVIDENCE_TABLE}
                DROP CONSTRAINT IF EXISTS {constraint_name}
                """
            )
        return
    if vendor == "sqlite":
        for trigger_name in SQLITE_TRIGGER_NAMES:
            schema_editor.execute(
                f"DROP TRIGGER IF EXISTS {trigger_name}"
            )
        return
    raise RuntimeError(
        "EvidenceLink context rollback supports PostgreSQL and "
        f"SQLite only, not {vendor!r}."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("audit", "0004_airetrievalhit"),
        ("consultations", "0001_initial"),
        ("evidence", "0007_chunkembedding"),
        ("inquiries", "0008_guidance"),
        ("visits", "0003_handoffreport"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvidenceLink",
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
                    "selection_origin_code",
                    models.CharField(
                        default="AUTO_RETRIEVAL",
                        max_length=40,
                    ),
                ),
                (
                    "evidence_role_code",
                    models.CharField(
                        default="SUPPORTING",
                        max_length=40,
                    ),
                ),
                (
                    "display_order",
                    models.SmallIntegerField(default=1),
                ),
                (
                    "citation_label",
                    models.CharField(max_length=200),
                ),
                (
                    "document_code_snapshot",
                    models.CharField(max_length=80),
                ),
                (
                    "document_title_snapshot",
                    models.CharField(max_length=300),
                ),
                (
                    "source_org_snapshot",
                    models.CharField(max_length=150),
                ),
                (
                    "revision_label_snapshot",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "official_source_url_snapshot",
                    models.CharField(max_length=1000),
                ),
                (
                    "document_sha256_snapshot",
                    models.CharField(max_length=64),
                ),
                ("evidence_summary", models.TextField()),
                ("cited_text_snapshot", models.TextField()),
                ("page_no_snapshot", models.IntegerField()),
                (
                    "section_snapshot",
                    models.CharField(
                        blank=True,
                        max_length=500,
                        null=True,
                    ),
                ),
                (
                    "product_model_codes_snapshot",
                    models.JSONField(),
                ),
                (
                    "is_verified",
                    models.BooleanField(default=False),
                ),
                (
                    "verified_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "ai_run",
                    models.ForeignKey(
                        blank=True,
                        db_column="ai_run_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="audit.airun",
                    ),
                ),
                (
                    "chunk",
                    models.ForeignKey(
                        db_column="chunk_id",
                        db_index=False,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="evidence.documentchunk",
                    ),
                ),
                (
                    "consultation",
                    models.ForeignKey(
                        blank=True,
                        db_column="consultation_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="consultations.consultation",
                    ),
                ),
                (
                    "guidance",
                    models.ForeignKey(
                        blank=True,
                        db_column="guidance_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="inquiries.guidance",
                    ),
                ),
                (
                    "handoff_report",
                    models.ForeignKey(
                        blank=True,
                        db_column="handoff_report_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="visits.handoffreport",
                    ),
                ),
                (
                    "inquiry",
                    models.ForeignKey(
                        db_column="inquiry_id",
                        db_index=False,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="inquiries.inquiry",
                    ),
                ),
                (
                    "retrieval_hit",
                    models.ForeignKey(
                        blank=True,
                        db_column="retrieval_hit_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="audit.airetrievalhit",
                    ),
                ),
                (
                    "retrieval_run",
                    models.ForeignKey(
                        blank=True,
                        db_column="retrieval_run_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="evidence_links",
                        to="audit.airetrievalrun",
                    ),
                ),
                (
                    "verified_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="verified_by_id",
                        db_index=False,
                        null=True,
                        on_delete=(
                            django.db.models.deletion.PROTECT
                        ),
                        related_name="verified_evidence_links",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "knowledge_evidence_link",
                "indexes": [
                    models.Index(
                        fields=["inquiry", "created_at"],
                        name="ix_evidence_link_inquiry",
                    ),
                    models.Index(
                        fields=["guidance", "inquiry"],
                        name="ix_evidence_link_guidance",
                    ),
                    models.Index(
                        fields=["consultation", "inquiry"],
                        name="ix_evidence_link_consultation",
                    ),
                    models.Index(
                        fields=["handoff_report", "inquiry"],
                        name="ix_evidence_link_handoff",
                    ),
                    models.Index(
                        fields=["chunk"],
                        name="ix_evidence_link_chunk",
                    ),
                    models.Index(
                        fields=["ai_run", "inquiry"],
                        name="ix_evidence_link_ai_run",
                    ),
                    models.Index(
                        fields=[
                            "retrieval_hit",
                            "retrieval_run",
                            "chunk",
                        ],
                        name="ix_evidence_link_retrieval_hit",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("guidance__isnull", False)
                        ),
                        fields=(
                            "guidance",
                            "chunk",
                            "evidence_role_code",
                        ),
                        name="ux_evidence_guidance_chunk",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("consultation__isnull", False)
                        ),
                        fields=(
                            "consultation",
                            "chunk",
                            "evidence_role_code",
                        ),
                        name="ux_evidence_consultation_chunk",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("handoff_report__isnull", False)
                        ),
                        fields=(
                            "handoff_report",
                            "chunk",
                            "evidence_role_code",
                        ),
                        name="ux_evidence_handoff_chunk",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("guidance__isnull", False)
                        ),
                        fields=("guidance", "display_order"),
                        name="ux_evidence_guidance_order",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("consultation__isnull", False)
                        ),
                        fields=("consultation", "display_order"),
                        name="ux_evidence_consultation_order",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(
                            ("handoff_report__isnull", False)
                        ),
                        fields=("handoff_report", "display_order"),
                        name="ux_evidence_handoff_order",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("consultation__isnull", True),
                                ("guidance__isnull", False),
                                ("handoff_report__isnull", True),
                            ),
                            models.Q(
                                ("consultation__isnull", False),
                                ("guidance__isnull", True),
                                ("handoff_report__isnull", True),
                            ),
                            models.Q(
                                ("consultation__isnull", True),
                                ("guidance__isnull", True),
                                ("handoff_report__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="ck_evidence_exactly_one_target",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("display_order__gt", 0)
                        ),
                        name="ck_evidence_display_order",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("page_no_snapshot__gt", 0)
                        ),
                        name="ck_evidence_page_no",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("is_verified", True),
                                ("verified_at__isnull", False),
                                ("verified_by__isnull", False),
                            ),
                            models.Q(
                                ("is_verified", False),
                                ("verified_at__isnull", True),
                                ("verified_by__isnull", True),
                            ),
                            _connector="OR",
                        ),
                        name="ck_evidence_verification",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "document_sha256_snapshot__regex",
                                "^[0-9a-f]{64}$",
                            )
                        ),
                        name="ck_evidence_document_hash",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            apps.evidence.models.evidence_link
                            .IsNonEmptyJSONArray(
                                models.F(
                                    "product_model_codes_snapshot"
                                )
                            )
                        ),
                        name="ck_evidence_product_models",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("retrieval_hit__isnull", True),
                                ("retrieval_run__isnull", True),
                            ),
                            models.Q(
                                ("ai_run__isnull", False),
                                ("retrieval_hit__isnull", False),
                                ("retrieval_run__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="ck_evidence_retrieval_bundle",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "selection_origin_code__regex",
                                ".*\\S.*",
                            )
                        ),
                        name=(
                            "ck_evidence_selection_origin_nonempty"
                        ),
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "evidence_role_code__regex",
                                ".*\\S.*",
                            )
                        ),
                        name="ck_evidence_role_nonempty",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "citation_label__regex",
                                ".*\\S.*",
                            ),
                            (
                                "document_code_snapshot__regex",
                                ".*\\S.*",
                            ),
                            (
                                "document_title_snapshot__regex",
                                ".*\\S.*",
                            ),
                            (
                                "source_org_snapshot__regex",
                                ".*\\S.*",
                            ),
                            (
                                "official_source_url_snapshot__regex",
                                ".*\\S.*",
                            ),
                            (
                                "evidence_summary__regex",
                                ".*\\S.*",
                            ),
                            (
                                "cited_text_snapshot__regex",
                                ".*\\S.*",
                            ),
                        ),
                        name="ck_evidence_required_text",
                    ),
                ],
            },
        ),
        migrations.RunPython(
            add_evidence_context_integrity,
            remove_evidence_context_integrity,
        ),
    ]
