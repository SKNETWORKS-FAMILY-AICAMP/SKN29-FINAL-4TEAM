"""Remove non-P1 customer runtime rows from an explicitly isolated database."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any, Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import (
    CustomerAccountLink,
    CustomerProfile,
    P1AuthChallengeRateBucket,
    P1AuthEmailOutbox,
    P1AuthIdempotencyLock,
    P1AuthLoginRateBucket,
    P1AuthOperationReceipt,
    P1AuthOtpChallenge,
    P1AuthRateLimitEvent,
    P1AuthTicket,
    User,
)
from apps.inquiries.models import Inquiry
from apps.workflow.models import IdempotencyRecord


ISOLATED_DATABASE_NAME = "waterbridge_p1_team_isolated"
PRESERVE_PREFIX = "SYN-P1-TEAM-CUSTOMER-"
EXPECTED_PRESERVE_NUMBERS = tuple(
    f"{PRESERVE_PREFIX}{index:03d}" for index in range(1, 7)
)
ALLOWED_KNOWLEDGE_DELETE_TABLES = {"knowledge_evidence_link"}


def _single_column_keys(cursor, constraint_type: str) -> dict[str, str]:
    cursor.execute(
        """
        SELECT constraint_row.conrelid::regclass::text, attribute.attname
        FROM pg_constraint AS constraint_row
        JOIN pg_attribute AS attribute
          ON attribute.attrelid = constraint_row.conrelid
         AND attribute.attnum = constraint_row.conkey[1]
        WHERE constraint_row.contype = %s
          AND cardinality(constraint_row.conkey) = 1
        """,
        [constraint_type],
    )
    return {table: column for table, column in cursor.fetchall()}


def _foreign_keys(cursor) -> list[tuple[str, str, str, str]]:
    cursor.execute(
        """
        SELECT
          constraint_row.conrelid::regclass::text,
          child_attribute.attname,
          constraint_row.confrelid::regclass::text,
          parent_attribute.attname
        FROM pg_constraint AS constraint_row
        JOIN pg_attribute AS child_attribute
          ON child_attribute.attrelid = constraint_row.conrelid
         AND child_attribute.attnum = constraint_row.conkey[1]
        JOIN pg_attribute AS parent_attribute
          ON parent_attribute.attrelid = constraint_row.confrelid
         AND parent_attribute.attnum = constraint_row.confkey[1]
        WHERE constraint_row.contype = 'f'
          AND cardinality(constraint_row.conkey) = 1
          AND cardinality(constraint_row.confkey) = 1
        """
    )
    return list(cursor.fetchall())


def _table_edges(cursor) -> set[tuple[str, str]]:
    cursor.execute(
        """
        SELECT DISTINCT
          constraint_row.confrelid::regclass::text,
          constraint_row.conrelid::regclass::text
        FROM pg_constraint AS constraint_row
        WHERE constraint_row.contype = 'f'
          AND constraint_row.confrelid <> constraint_row.conrelid
        """
    )
    return set(cursor.fetchall())


def _table_count(cursor, table: str) -> int:
    quoted = connection.ops.quote_name(table)
    cursor.execute(f"SELECT COUNT(*) FROM {quoted}")
    return int(cursor.fetchone()[0])


def _protected_reference_counts(cursor) -> dict[str, int]:
    cursor.execute(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = current_schema()
          AND (
            tablename LIKE 'knowledge_%'
            OR tablename LIKE 'products_%'
          )
        ORDER BY tablename
        """
    )
    return {
        table: _table_count(cursor, table)
        for (table,) in cursor.fetchall()
        if table not in ALLOWED_KNOWLEDGE_DELETE_TABLES
    }


def _select_related_ids(
    cursor,
    *,
    child_table: str,
    child_pk: str,
    child_fk: str,
    parent_ids: Iterable[Any],
) -> set[Any]:
    values = list(parent_ids)
    if not values:
        return set()
    table = connection.ops.quote_name(child_table)
    pk = connection.ops.quote_name(child_pk)
    fk = connection.ops.quote_name(child_fk)
    cursor.execute(f"SELECT {pk} FROM {table} WHERE {fk} = ANY(%s)", [values])
    return {row[0] for row in cursor.fetchall()}


def _delete_order(
    target_tables: set[str],
    edges: set[tuple[str, str]],
) -> list[str]:
    children: dict[str, set[str]] = defaultdict(set)
    indegree = {table: 0 for table in target_tables}
    for parent, child in edges:
        if parent not in target_tables or child not in target_tables:
            continue
        if child in children[parent]:
            continue
        children[parent].add(child)
        indegree[child] += 1

    queue = deque(sorted(table for table, degree in indegree.items() if degree == 0))
    ordered: list[str] = []
    while queue:
        table = queue.popleft()
        ordered.append(table)
        for child in sorted(children[table]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(ordered) != len(target_tables):
        cyclic = sorted(set(target_tables) - set(ordered))
        raise CommandError(
            "삭제 후보 FK 순환을 안전하게 해소할 수 없습니다: "
            + ",".join(cyclic)
        )
    return list(reversed(ordered))


class Command(BaseCommand):
    help = (
        "정확히 waterbridge_p1_team_isolated DB에서만 P1 고객 6명과 "
        "상담사·공식 근거를 보존하고 기존 고객·문의 Runtime을 정리합니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm-isolated", action="store_true")
        parser.add_argument("--json", action="store_true")

    def _collect_targets(self, cursor) -> tuple[dict[str, set[Any]], list[str]]:
        preserve = CustomerProfile.objects.filter(
            customer_no__startswith=PRESERVE_PREFIX,
        ).order_by("customer_no")
        preserve_numbers = tuple(preserve.values_list("customer_no", flat=True))
        if preserve_numbers != EXPECTED_PRESERVE_NUMBERS:
            raise CommandError("P1 팀 보존 고객이 정확히 001~006 여섯 명이 아닙니다.")
        if preserve.filter(is_synthetic=False).exists():
            raise CommandError("P1 팀 보존 고객에 비합성 데이터가 포함되어 있습니다.")

        preserve_customer_ids = set(preserve.values_list("id", flat=True))
        preserve_user_ids = set(
            preserve.exclude(user_id=None).values_list("user_id", flat=True)
        )
        preserve_user_ids.update(
            CustomerAccountLink.objects.filter(
                customer_id__in=preserve_customer_ids,
                is_active=True,
            ).values_list("user_id", flat=True)
        )
        preserve_consultant_ids = set(
            User.objects.filter(
                role_code=User.Role.CONSULTANT,
                is_active=True,
            ).values_list("id", flat=True)
        )

        remove_customers = CustomerProfile.objects.exclude(
            id__in=preserve_customer_ids,
        )
        if remove_customers.filter(is_synthetic=False).exists():
            raise CommandError("삭제 후보에 비합성 고객이 포함되어 적용을 중단합니다.")

        targets: dict[str, set[Any]] = defaultdict(set)
        targets[CustomerProfile._meta.db_table].update(
            remove_customers.values_list("id", flat=True)
        )
        targets[Inquiry._meta.db_table].update(
            Inquiry.objects.values_list("id", flat=True)
        )
        targets[User._meta.db_table].update(
            User.objects.filter(
                role_code=User.Role.CUSTOMER,
                is_synthetic=True,
            )
            .exclude(id__in=preserve_user_ids)
            .values_list("id", flat=True)
        )

        for model in (
            P1AuthChallengeRateBucket,
            P1AuthEmailOutbox,
            P1AuthIdempotencyLock,
            P1AuthLoginRateBucket,
            P1AuthOperationReceipt,
            P1AuthOtpChallenge,
            P1AuthRateLimitEvent,
            P1AuthTicket,
            IdempotencyRecord,
        ):
            targets[model._meta.db_table].update(
                model.objects.values_list(model._meta.pk.attname, flat=True)
            )

        primary_keys = _single_column_keys(cursor, "p")
        foreign_keys = _foreign_keys(cursor)
        changed = True
        while changed:
            changed = False
            for child_table, child_fk, parent_table, parent_column in foreign_keys:
                if not targets.get(parent_table):
                    continue
                if primary_keys.get(parent_table) != parent_column:
                    continue
                child_pk = primary_keys.get(child_table)
                if child_pk is None:
                    continue
                related = _select_related_ids(
                    cursor,
                    child_table=child_table,
                    child_pk=child_pk,
                    child_fk=child_fk,
                    parent_ids=targets[parent_table],
                )
                if child_table == CustomerProfile._meta.db_table:
                    related.difference_update(preserve_customer_ids)
                if child_table == User._meta.db_table:
                    related.difference_update(preserve_user_ids)
                    related.difference_update(preserve_consultant_ids)
                new_ids = related - targets[child_table]
                if new_ids:
                    targets[child_table].update(new_ids)
                    changed = True

        protected_customer_overlap = (
            targets[CustomerProfile._meta.db_table] & preserve_customer_ids
        )
        protected_user_overlap = targets[User._meta.db_table] & (
            preserve_user_ids | preserve_consultant_ids
        )
        if protected_customer_overlap or protected_user_overlap:
            raise CommandError("보존 고객 또는 상담사가 삭제 후보에 포함됐습니다.")

        forbidden_knowledge = sorted(
            table
            for table, ids in targets.items()
            if ids
            and table.startswith("knowledge_")
            and table not in ALLOWED_KNOWLEDGE_DELETE_TABLES
        )
        if forbidden_knowledge:
            raise CommandError(
                "공식 근거 테이블이 삭제 후보에 포함되어 중단합니다: "
                + ",".join(forbidden_knowledge)
            )

        return targets, list(preserve_numbers)

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        del args
        if connection.vendor != "postgresql":
            raise CommandError("이 정리 명령은 PostgreSQL 격리 DB에서만 실행됩니다.")
        database_name = str(connection.settings_dict.get("NAME") or "")
        apply_requested = bool(options["apply"])
        if apply_requested and (
            not options["confirm_isolated"]
            or database_name != ISOLATED_DATABASE_NAME
        ):
            raise CommandError(
                "Apply는 --confirm-isolated와 정확한 격리 DB 이름에서만 허용됩니다."
            )

        with connection.cursor() as cursor:
            protected_before = _protected_reference_counts(cursor)
            consultant_count_before = User.objects.filter(
                role_code=User.Role.CONSULTANT,
                is_active=True,
            ).count()
            targets, preserve_numbers = self._collect_targets(cursor)
            target_counts = {
                table: len(ids)
                for table, ids in sorted(targets.items())
                if ids
            }
            deleted_counts: dict[str, int] = {}

            if apply_requested:
                primary_keys = _single_column_keys(cursor, "p")
                order = _delete_order(set(target_counts), _table_edges(cursor))
                for table in order:
                    ids = list(targets[table])
                    if not ids:
                        continue
                    quoted_table = connection.ops.quote_name(table)
                    quoted_pk = connection.ops.quote_name(primary_keys[table])
                    cursor.execute(
                        f"DELETE FROM {quoted_table} WHERE {quoted_pk} = ANY(%s)",
                        [ids],
                    )
                    deleted_counts[table] = cursor.rowcount

                actual_numbers = tuple(
                    CustomerProfile.objects.order_by("customer_no").values_list(
                        "customer_no", flat=True
                    )
                )
                if actual_numbers != EXPECTED_PRESERVE_NUMBERS:
                    raise CommandError("적용 후 P1 고객 6명 보존 검증에 실패했습니다.")
                if Inquiry.objects.exists():
                    raise CommandError("적용 후 문의 0건 검증에 실패했습니다.")
                consultant_count_after = User.objects.filter(
                    role_code=User.Role.CONSULTANT,
                    is_active=True,
                ).count()
                if consultant_count_after != consultant_count_before:
                    raise CommandError("상담사 보존 수량 검증에 실패했습니다.")
                protected_after = _protected_reference_counts(cursor)
                if protected_after != protected_before:
                    raise CommandError("제품·공식 근거 테이블 무변경 검증에 실패했습니다.")
            else:
                consultant_count_after = consultant_count_before
                protected_after = protected_before

        result = {
            "mode": "APPLIED" if apply_requested else "PLAN_ONLY",
            "database_name": database_name,
            "preserve_customer_numbers": preserve_numbers,
            "preserve_consultants": consultant_count_after,
            "target_counts": target_counts,
            "deleted_counts": deleted_counts,
            "inquiry_count_after": Inquiry.objects.count(),
            "protected_reference_counts_unchanged": (
                protected_after == protected_before
            ),
        }
        payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        if options["json"]:
            self.stdout.write(payload)
        else:
            self.stdout.write(self.style.SUCCESS(payload))
