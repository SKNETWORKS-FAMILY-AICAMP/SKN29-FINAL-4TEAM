"""Scoped, replay-safe synchronization for consultant notices only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from django.db import transaction

from apps.operations.models import DashboardNotice
from apps.operations.repositories import (
    SyntheticImportConflict,
    SyntheticImportRepository,
)
from apps.operations.services.consultant_dashboard_seed_service import (
    NOTICE_FIXTURES,
    SEED_PREFIX,
)


SyncMode = Literal["plan", "dry-run", "apply"]
NOTICE_VALUE_FIELDS = (
    "category_code",
    "title",
    "body",
    "department_name",
    "published_on",
    "display_order",
    "is_published",
    "is_synthetic",
)


@dataclass(frozen=True)
class ConsultantNoticeSyncItem:
    """One notice outcome without exposing its body in command output."""

    notice_code: str
    action: str


@dataclass(frozen=True)
class ConsultantNoticeSyncResult:
    """Deterministic notice-only synchronization evidence."""

    mode: SyncMode
    target_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    before_sha256: str
    after_sha256: str
    items: tuple[ConsultantNoticeSyncItem, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["items"] = [asdict(item) for item in self.items]
        return payload


class ConsultantNoticeSyncService:
    """Plan or synchronize exactly the six namespaced notice rows."""

    def __init__(self) -> None:
        self.repository = SyntheticImportRepository()

    def run(self, *, mode: SyncMode = "plan") -> ConsultantNoticeSyncResult:
        if mode not in {"plan", "dry-run", "apply"}:
            raise ValueError(f"Unsupported notice sync mode: {mode}")

        expected = self._expected_rows()
        target_codes = tuple(row["notice_code"] for row in expected)

        with transaction.atomic():
            queryset = DashboardNotice.objects.filter(
                notice_code__in=target_codes
            )
            if mode != "plan":
                queryset = queryset.select_for_update()
            existing = {
                notice.notice_code: notice
                for notice in queryset.order_by("notice_code")
            }
            before_sha256 = self._snapshot_sha256(
                target_codes=target_codes,
                rows=existing,
            )
            items = tuple(
                self._plan_item(row=row, existing=existing)
                for row in expected
            )

            if mode != "plan":
                items = tuple(self._persist(row=row) for row in expected)
                verified = self._verified_rows(expected)
                after_sha256 = self._snapshot_sha256(
                    target_codes=target_codes,
                    rows=verified,
                )
                if mode == "dry-run":
                    transaction.set_rollback(True)
            else:
                after_sha256 = self._desired_sha256(expected)

            return ConsultantNoticeSyncResult(
                mode=mode,
                target_count=len(expected),
                created_count=sum(item.action == "CREATED" for item in items),
                updated_count=sum(item.action == "UPDATED" for item in items),
                unchanged_count=sum(
                    item.action == "UNCHANGED" for item in items
                ),
                before_sha256=before_sha256,
                after_sha256=after_sha256,
                items=items,
            )

    def _plan_item(
        self,
        *,
        row: dict[str, Any],
        existing: dict[str, DashboardNotice],
    ) -> ConsultantNoticeSyncItem:
        notice = existing.get(row["notice_code"])
        public_match = DashboardNotice.objects.filter(
            public_id=row["public_id"]
        ).first()
        if notice is None:
            if public_match is not None:
                raise SyntheticImportConflict(
                    "DashboardNotice public UUID is already bound to "
                    f"notice_code={public_match.notice_code}."
                )
            action = "CREATED"
        else:
            if notice.public_id != row["public_id"]:
                raise SyntheticImportConflict(
                    "DashboardNotice public UUID mismatch: "
                    f"notice_code={notice.notice_code}."
                )
            action = (
                "UPDATED"
                if any(
                    getattr(notice, field_name) != row[field_name]
                    for field_name in NOTICE_VALUE_FIELDS
                )
                else "UNCHANGED"
            )
        return ConsultantNoticeSyncItem(
            notice_code=row["notice_code"],
            action=action,
        )

    def _persist(self, *, row: dict[str, Any]) -> ConsultantNoticeSyncItem:
        result = self.repository.persist(
            DashboardNotice,
            public_id=row["public_id"],
            business_lookup={"notice_code": row["notice_code"]},
            values={
                field_name: row[field_name]
                for field_name in NOTICE_VALUE_FIELDS
            },
        )
        return ConsultantNoticeSyncItem(
            notice_code=row["notice_code"],
            action=result.action,
        )

    @staticmethod
    def _expected_rows() -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        for sequence, fixture in enumerate(NOTICE_FIXTURES, start=1):
            category, title, body, department, published_on = fixture
            rows.append(
                {
                    "public_id": ConsultantNoticeSyncService._uuid(
                        f"notice/{sequence}"
                    ),
                    "notice_code": f"{SEED_PREFIX}-NOTICE-{sequence:03d}",
                    "category_code": category,
                    "title": title,
                    "body": body,
                    "department_name": department,
                    "published_on": published_on,
                    "display_order": sequence,
                    "is_published": True,
                    "is_synthetic": True,
                }
            )
        return tuple(rows)

    @staticmethod
    def _verified_rows(
        expected: tuple[dict[str, Any], ...]
    ) -> dict[str, DashboardNotice]:
        target_codes = tuple(row["notice_code"] for row in expected)
        rows = {
            notice.notice_code: notice
            for notice in DashboardNotice.objects.filter(
                notice_code__in=target_codes
            )
        }
        if len(rows) != len(expected):
            raise SyntheticImportConflict(
                "Consultant notice sync verification count mismatch."
            )
        for desired in expected:
            notice = rows[desired["notice_code"]]
            if notice.public_id != desired["public_id"] or any(
                getattr(notice, field_name) != desired[field_name]
                for field_name in NOTICE_VALUE_FIELDS
            ):
                raise SyntheticImportConflict(
                    "Consultant notice sync verification mismatch: "
                    f"notice_code={notice.notice_code}."
                )
        return rows

    @staticmethod
    def _snapshot_sha256(
        *,
        target_codes: tuple[str, ...],
        rows: dict[str, DashboardNotice],
    ) -> str:
        payload = []
        for notice_code in sorted(target_codes):
            notice = rows.get(notice_code)
            payload.append(
                None
                if notice is None
                else {
                    "public_id": str(notice.public_id),
                    "notice_code": notice.notice_code,
                    **{
                        field_name: ConsultantNoticeSyncService._json_value(
                            getattr(notice, field_name)
                        )
                        for field_name in NOTICE_VALUE_FIELDS
                    },
                }
            )
        return ConsultantNoticeSyncService._sha256(payload)

    @staticmethod
    def _desired_sha256(expected: tuple[dict[str, Any], ...]) -> str:
        payload = [
            {
                key: ConsultantNoticeSyncService._json_value(value)
                for key, value in row.items()
            }
            for row in sorted(expected, key=lambda item: item["notice_code"])
        ]
        return ConsultantNoticeSyncService._sha256(payload)

    @staticmethod
    def _sha256(payload: Any) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    @staticmethod
    def _uuid(key: str) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            f"https://waterbridge.example/{SEED_PREFIX.lower()}/{key}",
        )
