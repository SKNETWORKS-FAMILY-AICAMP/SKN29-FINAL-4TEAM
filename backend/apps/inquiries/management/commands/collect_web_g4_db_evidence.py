"""Collect sanitized Web G4 Backend/DB evidence without mutating the DB.

The historical r3 run can only provide a final snapshot.  A new r4 run uses
five explicit snapshots so that the first write, idempotent replay, and
stale-state conflict are not inferred from one another.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count, Q
from django.utils import timezone

from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.workflow.models import IdempotencyRecord, TransitionHistory


EVIDENCE_SCOPE = "WEB_G4_BACKEND_DB_EVIDENCE"
BACKEND_ROOT = Path(__file__).resolve().parents[4]
REPOSITORY_ROOT = BACKEND_ROOT.parent
HOLD_MIGRATION = ("visits", "0005_replace_visit_result_assignment_fk")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SOURCE_REF_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")

PHASE_FILES = {
    "r3-final": "04-r3-final-snapshot.json",
    "r4-before-first-write": "04-r4-before-first-write.json",
    "r4-after-first-write": "05-r4-after-first-write.json",
    "r4-after-replay": "06-r4-after-replay.json",
    "r4-before-conflict": "07-r4-before-conflict.json",
    "r4-after-conflict": "08-r4-after-conflict.json",
}
R4_SNAPSHOT_PHASES = tuple(
    phase for phase in PHASE_FILES if phase.startswith("r4-")
)
FIRST_PHASES = {"r3-final", "r4-before-first-write"}

FORBIDDEN_TEXT_PATTERNS = {
    "database_uri": re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb)://[^\s\"']+"
    ),
    "windows_absolute_path": re.compile(
        r"(?i)\b[A-Z]:\\(?:Users|python-src|Program Files)\\[^\r\n\"']*"
    ),
    "email": re.compile(
        r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
    ),
    "phone": re.compile(
        r"(?<![0-9A-Fa-f])01[016789][- ]?\d{3,4}[- ]?\d{4}"
        r"(?![0-9A-Fa-f])"
    ),
    "secret_assignment": re.compile(
        r"(?i)\b(?:password|secret|api[_-]?key|dsn)\s*[:=]\s*"
        r"(?!\[?redacted\]?|none|null|false|0)\S+"
    ),
}


class Command(BaseCommand):
    help = (
        "Web G4 합성 문의의 상담·상태이력·멱등·Migration·Schema 증거를 "
        "원문과 비밀값 없이 파일로 수집합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--inquiry-id",
            required=True,
            type=UUID,
            help="검증할 합성 Inquiry의 공개 UUID",
        )
        parser.add_argument(
            "--run-id",
            required=True,
            help="Web E2E 실행 식별자",
        )
        parser.add_argument(
            "--source-ref",
            required=True,
            help="실행 소스 식별자. Secret이나 로컬 경로를 넣지 않습니다.",
        )
        parser.add_argument(
            "--phase",
            required=True,
            choices=tuple(PHASE_FILES) + ("r4-compare",),
            help="r3 최종 상태 또는 r4 단계별 Snapshot/비교 단계",
        )
        parser.add_argument(
            "--output-dir",
            required=True,
            type=Path,
            help="정제된 증거 파일을 저장할 디렉토리",
        )
        parser.add_argument(
            "--require-migration-ready",
            action="store_true",
            help=(
                "visits.0005 HOLD, 예상 밖 Pending·Applied 0이 아니면 "
                "Exit 1로 종료합니다."
            ),
        )

    def handle(self, *args, **options):
        del args
        inquiry_id = options["inquiry_id"]
        run_id = _validate_run_id(options["run_id"])
        source_ref = _validate_source_ref(options["source_ref"])
        phase = options["phase"]
        output_dir = options["output_dir"]
        _prepare_output_dir(output_dir, phase=phase)
        if phase not in FIRST_PHASES:
            _validate_existing_context(
                output_dir=output_dir,
                inquiry_id=inquiry_id,
                run_id=run_id,
                source_ref=source_ref,
            )

        if phase == "r4-compare":
            result = _compare_r4_evidence(
                output_dir=output_dir,
                inquiry_id=inquiry_id,
                run_id=run_id,
                source_ref=source_ref,
            )
            _write_json_once(
                output_dir / "09-r4-diff-and-duplicates.json",
                result,
            )
            _write_schema_diff(output_dir)
            _refresh_integrity_artifacts(output_dir)
            if result["status"] != "PASS":
                raise CommandError("r4 Replay·409 DB 증거 비교가 실패했습니다.")
            self.stdout.write("WEB_G4_DB_EVIDENCE=R4_COMPARE_PASS")
            return

        snapshot = collect_inquiry_snapshot(
            inquiry_id=inquiry_id,
            run_id=run_id,
            source_ref=source_ref,
            phase=phase,
        )
        _write_json_once(output_dir / PHASE_FILES[phase], snapshot)

        if phase in {"r3-final", "r4-before-first-write"}:
            context = {
                "scope": EVIDENCE_SCOPE,
                "evidence_mode": "R3_FINAL_ONLY" if phase == "r3-final" else "R4",
                "run_id": run_id,
                "inquiry_id": str(inquiry_id),
                "source_ref": source_ref,
                "database_vendor": connection.vendor,
                "historical_replay_evidence": (
                    "NOT_CAPTURED" if phase == "r3-final" else "CAPTURE_IN_PROGRESS"
                ),
                "historical_schema_delta": (
                    "NOT_CAPTURED" if phase == "r3-final" else "CAPTURE_IN_PROGRESS"
                ),
                "raw_business_text_included": False,
                "secret_values_included": False,
                "local_environment_metadata_included": False,
            }
            _write_json_once(output_dir / "00-db-evidence-context.json", context)
            migration = collect_migration_evidence()
            _write_text_once(
                output_dir / "01-showmigrations-visits-before.txt",
                migration.pop("showmigrations_visits"),
            )
            _write_text_once(
                output_dir / "02-migrate-plan-before.txt",
                migration.pop("migrate_plan"),
            )
            _write_json_once(
                output_dir / "03-migration-gate-before.json",
                migration,
            )
            schema = collect_schema_fingerprint()
            _write_text_once(
                output_dir / "10-schema-fingerprint-before.sha256",
                f"{schema['sha256']}  schema\n",
            )
            _write_json_once(
                output_dir / "10a-schema-summary-before.json",
                schema,
            )
            if (
                options["require_migration_ready"]
                and migration["status"] != "READY"
            ):
                _refresh_integrity_artifacts(output_dir)
                raise CommandError("Migration·Schema 읽기 전용 Gate가 READY가 아닙니다.")

        if phase == "r4-after-conflict":
            migration = collect_migration_evidence()
            _write_text_once(
                output_dir / "01-showmigrations-visits-after.txt",
                migration.pop("showmigrations_visits"),
            )
            _write_text_once(
                output_dir / "02-migrate-plan-after.txt",
                migration.pop("migrate_plan"),
            )
            _write_json_once(
                output_dir / "03-migration-gate-after.json",
                migration,
            )
            schema = collect_schema_fingerprint()
            _write_text_once(
                output_dir / "11-schema-fingerprint-after.sha256",
                f"{schema['sha256']}  schema\n",
            )
            _write_json_once(
                output_dir / "11a-schema-summary-after.json",
                schema,
            )
            if (
                options["require_migration_ready"]
                and migration["status"] != "READY"
            ):
                _refresh_integrity_artifacts(output_dir)
                raise CommandError("Migration·Schema 읽기 전용 Gate가 READY가 아닙니다.")

        _refresh_integrity_artifacts(output_dir)
        self.stdout.write(f"WEB_G4_DB_EVIDENCE={phase.upper().replace('-', '_')}_SAVED")


def collect_inquiry_snapshot(
    *,
    inquiry_id: UUID,
    run_id: str,
    source_ref: str,
    phase: str,
) -> dict[str, Any]:
    """Return one inquiry-scoped snapshot in a PostgreSQL read-only transaction."""

    with _database_read_only():
        inquiry = (
            Inquiry.objects.select_related("initiated_by")
            .filter(public_id=inquiry_id)
            .first()
        )
        if inquiry is None:
            raise CommandError("지정한 합성 Inquiry를 찾을 수 없습니다.")
        if not inquiry.initiated_by.is_synthetic:
            raise CommandError("합성 Inquiry만 DB 증거로 수집할 수 있습니다.")

        consultation_values = list(
            Consultation.objects.filter(inquiry=inquiry)
            .order_by("sequence", "id")
            .values(
                "public_id",
                "sequence",
                "status",
                "outcome",
                "data_classification",
                "state_version",
                "correlation_id",
                "idempotency_key",
                "created_at",
                "updated_at",
                "started_at",
                "summary",
                "ai_draft_summary",
                "confirmed_summary",
                "consultation_note",
                "customer_guidance",
                "summary_confirmed_at",
                "completed_at",
            )
        )
        consultation_ids = [row["public_id"] for row in consultation_values]
        if any(
            row["data_classification"]
            != Consultation.DataClassification.SYNTHETIC
            for row in consultation_values
        ):
            raise CommandError("운영 Consultation은 DB 증거로 수집할 수 없습니다.")
        consultation_pks = list(
            Consultation.objects.filter(inquiry=inquiry).values_list("pk", flat=True)
        )

        histories = list(
            TransitionHistory.objects.filter(
                Q(inquiry=inquiry) | Q(consultation_id__in=consultation_pks)
            )
            .order_by("changed_at", "id")
            .values(
                "target_type_code",
                "event_code",
                "from_state",
                "to_state",
                "state_version",
                "changed_by_type_code",
                "actor__role_code",
                "correlation_id",
                "idempotency_key",
                "created_at",
                "updated_at",
                "changed_at",
            )
        )
        resource_ids = [inquiry.public_id, *consultation_ids]
        record_filter = Q(resource_public_id__in=resource_ids)
        records = list(
            IdempotencyRecord.objects.filter(record_filter)
            .order_by("created_at", "id")
            .values(
                "public_id",
                "operation_id",
                "idempotency_key",
                "response_status",
                "resource_public_id",
                "created_at",
                "updated_at",
                "completed_at",
            )
        )
        duplicate_scopes = list(
            IdempotencyRecord.objects.filter(record_filter)
            .values("actor_id", "operation_id", "idempotency_key")
            .annotate(row_count=Count("id"))
            .filter(row_count__gt=1)
        )

        safe_consultations = [
            {
                "consultation_id": str(row["public_id"]),
                "sequence": row["sequence"],
                "status": row["status"],
                "outcome": row["outcome"],
                "data_classification": row["data_classification"],
                "state_version": row["state_version"],
                "correlation_id": str(row["correlation_id"]),
                "idempotency_key_sha256": _sha256_text(row["idempotency_key"]),
                "created_at": _isoformat(row["created_at"]),
                "updated_at": _isoformat(row["updated_at"]),
                "started_at": _isoformat(row["started_at"]),
                "content_presence": {
                    "summary": bool(row["summary"]),
                    "ai_draft_summary": bool(row["ai_draft_summary"]),
                    "confirmed_summary": bool(row["confirmed_summary"]),
                    "consultation_note": bool(row["consultation_note"]),
                    "customer_guidance": bool(row["customer_guidance"]),
                },
                "summary_confirmed": row["summary_confirmed_at"] is not None,
                "completed": row["completed_at"] is not None,
                "summary_confirmed_at": _isoformat(
                    row["summary_confirmed_at"]
                ),
                "completed_at": _isoformat(row["completed_at"]),
            }
            for row in consultation_values
        ]
        safe_histories = [
            {
                "target_type_code": row["target_type_code"],
                "event_code": row["event_code"],
                "from_state": row["from_state"],
                "to_state": row["to_state"],
                "state_version": row["state_version"],
                "changed_by_type_code": row["changed_by_type_code"],
                "actor_role_code": row["actor__role_code"],
                "correlation_id": str(row["correlation_id"]),
                "idempotency_key_sha256": _sha256_text(row["idempotency_key"]),
                "created_at": _isoformat(row["created_at"]),
                "updated_at": _isoformat(row["updated_at"]),
                "changed_at": _isoformat(row["changed_at"]),
            }
            for row in histories
        ]
        safe_records = [
            {
                "record_id": str(row["public_id"]),
                "operation_id": row["operation_id"],
                "idempotency_key_sha256": _sha256_text(row["idempotency_key"]),
                "response_status": row["response_status"],
                "resource_public_id": (
                    str(row["resource_public_id"])
                    if row["resource_public_id"]
                    else None
                ),
                "completed": row["completed_at"] is not None,
                "created_at": _isoformat(row["created_at"]),
                "updated_at": _isoformat(row["updated_at"]),
                "completed_at": _isoformat(row["completed_at"]),
            }
            for row in records
        ]

        result = {
            "scope": EVIDENCE_SCOPE,
            "phase": phase,
            "captured_at": timezone.now().isoformat(),
            "run_id": run_id,
            "source_ref": source_ref,
            "database_vendor": connection.vendor,
            "inquiry": {
                "inquiry_id": str(inquiry.public_id),
                "status": inquiry.status_code,
                "state_version": inquiry.state_version,
                "created_at": _isoformat(inquiry.created_at),
                "updated_at": _isoformat(inquiry.updated_at),
            },
            "consultation": {
                "count": len(safe_consultations),
                "unexpected_additional_count": max(0, len(safe_consultations) - 1),
                "items": safe_consultations,
            },
            "workflow": {
                "history_count": len(safe_histories),
                "history_event_counts": dict(
                    sorted(Counter(row["event_code"] for row in histories).items())
                ),
                "history": safe_histories,
                "idempotency_record_count": len(safe_records),
                "idempotency_operation_counts": dict(
                    sorted(Counter(row["operation_id"] for row in records).items())
                ),
                "idempotency_records": safe_records,
                "duplicate_idempotency_scope_count": len(duplicate_scopes),
            },
            "raw_business_text_included": False,
            "secret_values_included": False,
            "local_environment_metadata_included": False,
        }
        result["snapshot_sha256"] = _database_snapshot_sha256(result)
        return result


def collect_migration_evidence() -> dict[str, Any]:
    """Collect raw Django plan plus a fail-closed migration summary."""

    with _database_read_only():
        executor = MigrationExecutor(connection)
        loader = executor.loader
        disk = set(loader.disk_migrations)
        applied = set(loader.applied_migrations)
        leaves = loader.graph.leaf_nodes()
        plan = executor.migration_plan(leaves)
        pending = sorted(
            {
                (migration.app_label, migration.name)
                for migration, backwards in plan
                if not backwards
            }
        )
        unknown_applied = sorted(applied - disk)

    showmigrations_output = StringIO()
    with _database_read_only():
        call_command(
            "showmigrations",
            "visits",
            stdout=showmigrations_output,
            verbosity=1,
            no_color=True,
        )
    migrate_plan_output = StringIO()
    with _database_read_only():
        call_command(
            "migrate",
            plan=True,
            interactive=False,
            stdout=migrate_plan_output,
            verbosity=1,
            no_color=True,
        )

    hold_on_disk = HOLD_MIGRATION in disk
    hold_applied = HOLD_MIGRATION in applied
    unexpected_pending = [item for item in pending if item != HOLD_MIGRATION]
    blockers: list[str] = []
    if not hold_on_disk:
        blockers.append("VISITS_0005_NOT_IN_SOURCE_GRAPH")
    if hold_applied:
        blockers.append("VISITS_0005_ALREADY_APPLIED")
    if unexpected_pending:
        blockers.append("UNEXPECTED_PENDING_MIGRATIONS")
    if unknown_applied:
        blockers.append("APPLIED_MIGRATIONS_NOT_IN_SOURCE_GRAPH")

    return {
        "status": "READY" if not blockers else "BLOCKED",
        "database_vendor": connection.vendor,
        "visits_0005": (
            "APPLIED_BLOCKER" if hold_applied else "NOT_APPLIED_P1_HOLD"
        ),
        "pending_migrations": [_migration_label(item) for item in pending],
        "unexpected_pending_migrations": [
            _migration_label(item) for item in unexpected_pending
        ],
        "unknown_applied_migrations": [
            _migration_label(item) for item in unknown_applied
        ],
        "blockers": blockers,
        "showmigrations_visits": showmigrations_output.getvalue(),
        "migrate_plan": migrate_plan_output.getvalue(),
    }


def collect_schema_fingerprint() -> dict[str, Any]:
    """Hash names and structural metadata only; never include table values."""

    tables: list[dict[str, Any]] = []
    with _database_read_only():
        with connection.cursor() as cursor:
            table_names = sorted(
                connection.introspection.table_names(cursor, include_views=True)
            )
            for table_name in table_names:
                columns = []
                for field in connection.introspection.get_table_description(
                    cursor,
                    table_name,
                ):
                    try:
                        field_type = connection.introspection.get_field_type(
                            field.type_code,
                            field,
                        )
                    except (AttributeError, KeyError):
                        field_type = str(field.type_code)
                    columns.append(
                        {
                            "name": field.name,
                            "type": field_type,
                            "null_ok": bool(field.null_ok),
                        }
                    )
                constraints = connection.introspection.get_constraints(
                    cursor,
                    table_name,
                )
                safe_constraints = []
                for name, value in sorted(constraints.items()):
                    foreign_key = value.get("foreign_key")
                    safe_constraints.append(
                        {
                            "name": name,
                            "columns": sorted(value.get("columns") or []),
                            "primary_key": bool(value.get("primary_key")),
                            "unique": bool(value.get("unique")),
                            "index": bool(value.get("index")),
                            "check": bool(value.get("check")),
                            "foreign_key": (
                                list(foreign_key) if foreign_key else None
                            ),
                        }
                    )
                tables.append(
                    {
                        "name": table_name,
                        "columns": columns,
                        "constraints": safe_constraints,
                    }
                )

    encoded = json.dumps(
        tables,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "table_count": len(tables),
        "column_count": sum(len(item["columns"]) for item in tables),
        "constraint_count": sum(len(item["constraints"]) for item in tables),
        "table_values_included": False,
    }


def _compare_r4_evidence(
    *,
    output_dir: Path,
    inquiry_id: UUID,
    run_id: str,
    source_ref: str,
) -> dict[str, Any]:
    snapshots = {
        phase: _load_json(output_dir / PHASE_FILES[phase])
        for phase in R4_SNAPSHOT_PHASES
    }
    blockers: list[str] = []
    expected_identity = (str(inquiry_id), run_id, source_ref)
    for phase, snapshot in snapshots.items():
        identity = (
            snapshot.get("inquiry", {}).get("inquiry_id"),
            snapshot.get("run_id"),
            snapshot.get("source_ref"),
        )
        if identity != expected_identity:
            blockers.append(f"MIXED_EVIDENCE_IDENTITY:{phase}")

    before = snapshots["r4-before-first-write"]
    after_first = snapshots["r4-after-first-write"]
    after_replay = snapshots["r4-after-replay"]
    before_conflict = snapshots["r4-before-conflict"]
    after_conflict = snapshots["r4-after-conflict"]

    first_write_delta = _snapshot_delta(before, after_first)
    replay_delta = _snapshot_delta(after_first, after_replay)
    conflict_delta = _snapshot_delta(before_conflict, after_conflict)
    expected_first_write = {
        "consultation": 0,
        "history": 1,
        "idempotency": 1,
        "state_version": 1,
    }
    if first_write_delta != expected_first_write:
        blockers.append("FIRST_WRITE_DB_DELTA_UNEXPECTED")
    if any(replay_delta.values()):
        blockers.append("REPLAY_CREATED_OR_CHANGED_ROWS")
    if any(conflict_delta.values()):
        blockers.append("STALE_STATE_409_CREATED_OR_CHANGED_ROWS")
    if after_replay["workflow"]["duplicate_idempotency_scope_count"] != 0:
        blockers.append("IDEMPOTENCY_DUPLICATE_SCOPE_EXISTS")
    if after_replay["consultation"]["unexpected_additional_count"] != 0:
        blockers.append("DUPLICATE_CONSULTATION_EXISTS")
    if before["snapshot_sha256"] == after_first["snapshot_sha256"]:
        blockers.append("FIRST_WRITE_SNAPSHOT_UNCHANGED")
    if after_first["snapshot_sha256"] != after_replay["snapshot_sha256"]:
        blockers.append("REPLAY_MUTATED_EXISTING_ROWS")
    if after_replay["snapshot_sha256"] != before_conflict["snapshot_sha256"]:
        blockers.append("CONFLICT_BASELINE_DIFFERS_FROM_REPLAY")
    if before_conflict["snapshot_sha256"] != after_conflict["snapshot_sha256"]:
        blockers.append("STALE_STATE_409_MUTATED_EXISTING_ROWS")

    before_hash = _read_hash(
        output_dir / "10-schema-fingerprint-before.sha256"
    )
    after_hash = _read_hash(
        output_dir / "11-schema-fingerprint-after.sha256"
    )
    if before_hash != after_hash:
        blockers.append("SCHEMA_CHANGED_DURING_R4")

    migration_before = _load_json(
        output_dir / "03-migration-gate-before.json"
    )
    migration_after = _load_json(
        output_dir / "03-migration-gate-after.json"
    )
    if migration_before != migration_after:
        blockers.append("MIGRATION_STATE_CHANGED_DURING_R4")

    return {
        "status": "PASS" if not blockers else "FAIL",
        "scope": EVIDENCE_SCOPE,
        "run_id": run_id,
        "inquiry_id": str(inquiry_id),
        "source_ref": source_ref,
        "first_write_delta": first_write_delta,
        "expected_first_write_delta": expected_first_write,
        "replay_additional_rows": replay_delta,
        "stale_state_409_additional_rows": conflict_delta,
        "first_write_snapshot_changed": (
            before["snapshot_sha256"] != after_first["snapshot_sha256"]
        ),
        "replay_snapshot_unchanged": (
            after_first["snapshot_sha256"] == after_replay["snapshot_sha256"]
        ),
        "stale_state_409_snapshot_unchanged": (
            before_conflict["snapshot_sha256"]
            == after_conflict["snapshot_sha256"]
        ),
        "duplicate_idempotency_scope_count": after_replay["workflow"][
            "duplicate_idempotency_scope_count"
        ],
        "duplicate_consultation_count": after_replay["consultation"][
            "unexpected_additional_count"
        ],
        "schema_unchanged": before_hash == after_hash,
        "migration_state_unchanged": migration_before == migration_after,
        "blockers": blockers,
    }


def _snapshot_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    return {
        "consultation": after["consultation"]["count"]
        - before["consultation"]["count"],
        "history": after["workflow"]["history_count"]
        - before["workflow"]["history_count"],
        "idempotency": after["workflow"]["idempotency_record_count"]
        - before["workflow"]["idempotency_record_count"],
        "state_version": after["inquiry"]["state_version"]
        - before["inquiry"]["state_version"],
    }


@contextmanager
def _database_read_only():
    """Make PostgreSQL evidence queries fail closed on accidental writes."""

    if connection.vendor == "postgresql" and not connection.get_autocommit():
        raise CommandError(
            "PostgreSQL 증거 수집은 기존 Transaction 밖에서 실행해야 합니다."
        )
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
        yield


def _prepare_output_dir(output_dir: Path, *, phase: str) -> None:
    resolved = output_dir.resolve()
    forbidden_targets = {
        Path(resolved.anchor).resolve(),
        Path.home().resolve(),
        REPOSITORY_ROOT.resolve(),
        BACKEND_ROOT.resolve(),
    }
    if resolved in forbidden_targets:
        raise CommandError("넓은 상위 경로를 증거 출력 폴더로 사용할 수 없습니다.")
    output_dir.mkdir(parents=True, exist_ok=True)
    if phase in FIRST_PHASES and any(output_dir.iterdir()):
        raise CommandError("첫 Capture 출력 디렉토리는 비어 있어야 합니다.")
    if phase not in FIRST_PHASES and not (
        output_dir / "00-db-evidence-context.json"
    ).is_file():
        raise CommandError("같은 r4 출력 디렉토리의 Context 파일이 필요합니다.")


def _validate_existing_context(
    *,
    output_dir: Path,
    inquiry_id: UUID,
    run_id: str,
    source_ref: str,
) -> None:
    context = _load_json(output_dir / "00-db-evidence-context.json")
    expected = {
        "evidence_mode": "R4",
        "inquiry_id": str(inquiry_id),
        "run_id": run_id,
        "source_ref": source_ref,
    }
    actual = {key: context.get(key) for key in expected}
    if actual != expected:
        raise CommandError(
            "같은 r4 실행의 Inquiry·run_id·source_ref가 아닙니다."
        )


def _validate_run_id(raw_value: str) -> str:
    value = raw_value.strip()
    if not RUN_ID_PATTERN.fullmatch(value):
        raise CommandError("run_id 형식이 올바르지 않습니다.")
    return value


def _validate_source_ref(raw_value: str) -> str:
    value = raw_value.strip()
    if not SOURCE_REF_PATTERN.fullmatch(value) or ":\\" in value:
        raise CommandError("source_ref에는 Commit·Branch 등 공개 식별자만 사용합니다.")
    return value


def _migration_label(value: tuple[str, str]) -> str:
    return f"{value[0]}.{value[1]}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _isoformat(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _database_snapshot_sha256(snapshot: dict[str, Any]) -> str:
    payload = {
        "inquiry": snapshot["inquiry"],
        "consultation": snapshot["consultation"],
        "workflow": snapshot["workflow"],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json_once(path: Path, value: Any) -> None:
    _write_text_once(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_text_once(path: Path, value: str) -> None:
    if path.exists():
        raise CommandError(f"기존 증거 파일을 덮어쓸 수 없습니다: {path.name}")
    path.write_text(value, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CommandError(f"필수 증거 파일이 없습니다: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_hash(path: Path) -> str:
    if not path.is_file():
        raise CommandError(f"Schema Fingerprint가 없습니다: {path.name}")
    return path.read_text(encoding="utf-8").split()[0]


def _write_schema_diff(output_dir: Path) -> None:
    before = _read_hash(output_dir / "10-schema-fingerprint-before.sha256")
    after = _read_hash(output_dir / "11-schema-fingerprint-after.sha256")
    status = "UNCHANGED" if before == after else "CHANGED"
    _write_text_once(
        output_dir / "12-schema-diff.txt",
        f"schema_status={status}\nbefore_sha256={before}\nafter_sha256={after}\n",
    )


def _refresh_integrity_artifacts(output_dir: Path) -> None:
    scan_path = output_dir / "13-backend-db-redaction-scan.json"
    manifest_path = output_dir / "SHA256SUMS.txt"
    scan_path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)

    findings = []
    for path in sorted(item for item in output_dir.iterdir() if item.is_file()):
        text = path.read_text(encoding="utf-8", errors="replace")
        for code, pattern in FORBIDDEN_TEXT_PATTERNS.items():
            if pattern.search(text):
                findings.append({"file": path.name, "finding": code})
    scan = {
        "status": "PASS" if not findings else "FAIL",
        "scanned_file_count": sum(
            1 for item in output_dir.iterdir() if item.is_file()
        ),
        "finding_count": len(findings),
        "findings": findings,
    }
    scan_path.write_text(
        json.dumps(scan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if findings:
        raise CommandError("증거 파일 정제 검사에서 민감정보 후보를 발견했습니다.")

    lines = []
    for path in sorted(item for item in output_dir.iterdir() if item.is_file()):
        if path.name == manifest_path.name:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
