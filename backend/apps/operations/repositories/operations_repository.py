"""Strict persistence primitives for the synthetic handoff importer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils import timezone

from apps.operations.models import (
    SyntheticImportBatch,
    SyntheticImportItem,
)


class SyntheticImportConflict(ValueError):
    """Raised when public and business identifiers resolve inconsistently."""


@dataclass(frozen=True)
class PersistResult:
    """Persistence result excluding operational ledger writes."""

    instance: models.Model
    action: str


@dataclass(frozen=True)
class LedgerItem:
    """Source-row outcome ready to be persisted after verification."""

    source_dataset: str
    source_public_id: UUID
    source_business_key: str
    source_sha256: str
    action: str
    target_model: str
    target_public_id: UUID
    target_business_key: str


class SyntheticImportRepository:
    """Resolve by public UUID first and mutate only dirty model fields."""

    def persist(
        self,
        model: type[models.Model],
        *,
        public_id: UUID,
        business_lookup: dict[str, Any],
        values: dict[str, Any],
        immutable_values: dict[str, Any] | None = None,
        prepare_new: Callable[[models.Model], None] | None = None,
        source_created_at: datetime | None = None,
        source_updated_at: datetime | None = None,
    ) -> PersistResult:
        """Create, update, or leave one target through explicit resolution.

        A row found only by its business key has a different public UUID and is
        therefore a hard conflict. A row found by public UUID must retain the
        requested business and immutable relationship fields.
        """

        immutable_values = immutable_values or {}
        public_object = model.objects.filter(public_id=public_id).first()
        business_object = model.objects.filter(**business_lookup).first()

        if (
            public_object is not None
            and business_object is not None
            and public_object.pk != business_object.pk
        ):
            raise SyntheticImportConflict(
                f"{model._meta.label} identifier split: "
                f"public_id={public_id}, business={business_lookup}"
            )

        if public_object is None and business_object is not None:
            raise SyntheticImportConflict(
                f"{model._meta.label} public UUID mismatch: "
                f"business={business_lookup}, "
                f"database_public_id={business_object.public_id}, "
                f"source_public_id={public_id}"
            )

        instance = public_object
        if instance is not None:
            self._assert_values(
                instance,
                business_lookup,
                label="business key",
            )
            self._assert_values(
                instance,
                immutable_values,
                label="immutable field",
            )

        if instance is None:
            initial_values = {
                "public_id": public_id,
                **business_lookup,
                **immutable_values,
                **values,
            }
            instance = model(**initial_values)
            if prepare_new is not None:
                prepare_new(instance)
            instance.full_clean()
            instance.save(force_insert=True)
            self._apply_source_timestamps(
                instance,
                source_created_at=source_created_at,
                source_updated_at=source_updated_at,
            )
            return PersistResult(
                instance=instance,
                action=SyntheticImportItem.Action.CREATED,
            )

        dirty_fields: list[str] = []
        for field_name, desired_value in values.items():
            if self._value(instance, field_name) == self._comparable(
                desired_value
            ):
                continue
            setattr(instance, field_name, desired_value)
            dirty_fields.append(field_name)

        timestamp_dirty = self._timestamps_differ(
            instance,
            source_created_at=source_created_at,
            source_updated_at=source_updated_at,
        )
        if dirty_fields:
            instance.full_clean()
            update_fields = list(dirty_fields)
            if self._has_auto_updated_at(instance):
                update_fields.append("updated_at")
            instance.save(update_fields=update_fields)

        if dirty_fields or timestamp_dirty:
            self._apply_source_timestamps(
                instance,
                source_created_at=source_created_at,
                source_updated_at=source_updated_at,
            )
            return PersistResult(
                instance=instance,
                action=SyntheticImportItem.Action.UPDATED,
            )

        return PersistResult(
            instance=instance,
            action=SyntheticImportItem.Action.UNCHANGED,
        )

    def record_ledger(
        self,
        *,
        profile: str,
        dataset_version: str,
        mapping_version: str,
        fixture_set_sha256: str,
        items: list[LedgerItem],
    ) -> SyntheticImportBatch:
        """Persist a completed batch and every source-row result."""

        counts = {
            action: sum(item.action == action for item in items)
            for action in SyntheticImportItem.Action.values
        }
        batch = SyntheticImportBatch(
            profile=profile,
            status=SyntheticImportBatch.Status.COMPLETED,
            dataset_version=dataset_version,
            mapping_version=mapping_version,
            fixture_set_sha256=fixture_set_sha256,
            source_count=len(items),
            created_count=counts[SyntheticImportItem.Action.CREATED],
            updated_count=counts[SyntheticImportItem.Action.UPDATED],
            unchanged_count=counts[
                SyntheticImportItem.Action.UNCHANGED
            ],
            projected_count=counts[
                SyntheticImportItem.Action.PROJECTED
            ],
            completed_at=timezone.now(),
        )
        batch.full_clean()
        batch.save(force_insert=True)

        for outcome in items:
            item = SyntheticImportItem(
                batch=batch,
                source_dataset=outcome.source_dataset,
                source_public_id=outcome.source_public_id,
                source_business_key=outcome.source_business_key,
                source_sha256=outcome.source_sha256,
                action=outcome.action,
                target_model=outcome.target_model,
                target_public_id=outcome.target_public_id,
                target_business_key=outcome.target_business_key,
            )
            item.full_clean()
            item.save(force_insert=True)
        return batch

    def _assert_values(
        self,
        instance: models.Model,
        expected: dict[str, Any],
        *,
        label: str,
    ) -> None:
        for field_name, expected_value in expected.items():
            if self._value(instance, field_name) == self._comparable(
                expected_value
            ):
                continue
            raise SyntheticImportConflict(
                f"{instance._meta.label} {label} conflict: "
                f"public_id={instance.public_id}, field={field_name}"
            )

    @staticmethod
    def _comparable(value: Any) -> Any:
        if isinstance(value, models.Model):
            return value.pk
        return value

    @staticmethod
    def _value(instance: models.Model, field_name: str) -> Any:
        field = instance._meta.get_field(field_name)
        if field.is_relation and (
            field.many_to_one or field.one_to_one
        ):
            return getattr(instance, field.attname)
        return getattr(instance, field_name)

    @staticmethod
    def _has_auto_updated_at(instance: models.Model) -> bool:
        try:
            field = instance._meta.get_field("updated_at")
        except FieldDoesNotExist:
            return False
        return bool(getattr(field, "auto_now", False))

    def _timestamps_differ(
        self,
        instance: models.Model,
        *,
        source_created_at: datetime | None,
        source_updated_at: datetime | None,
    ) -> bool:
        values = self._timestamp_values(
            instance,
            source_created_at=source_created_at,
            source_updated_at=source_updated_at,
        )
        return any(
            getattr(instance, field_name) != value
            for field_name, value in values.items()
        )

    def _apply_source_timestamps(
        self,
        instance: models.Model,
        *,
        source_created_at: datetime | None,
        source_updated_at: datetime | None,
    ) -> None:
        values = self._timestamp_values(
            instance,
            source_created_at=source_created_at,
            source_updated_at=source_updated_at,
        )
        if not values:
            return
        instance.__class__.objects.filter(pk=instance.pk).update(**values)
        for field_name, value in values.items():
            setattr(instance, field_name, value)
        instance.full_clean()

    @staticmethod
    def _timestamp_values(
        instance: models.Model,
        *,
        source_created_at: datetime | None,
        source_updated_at: datetime | None,
    ) -> dict[str, datetime]:
        values: dict[str, datetime] = {}
        field_names = {
            field.name for field in instance._meta.concrete_fields
        }
        if source_created_at is not None and "created_at" in field_names:
            values["created_at"] = source_created_at
        if source_updated_at is not None and "updated_at" in field_names:
            values["updated_at"] = source_updated_at
        elif source_created_at is not None and "updated_at" in field_names:
            values["updated_at"] = source_created_at
        return values
