"""Atomic, insert-only persistence for validated reference scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from local_apps.reference_cases.catalog import LoadedReferenceCatalog
from local_apps.reference_cases.models import ReferenceScenario


@dataclass(frozen=True)
class ReferenceScenarioImportResult:
    """Counts for one dry-run or applied import."""

    records: int
    created: int
    unchanged: int


class ReferenceScenarioImportConflict(ValueError):
    """Raised when an existing versioned scenario differs from its source."""


class ReferenceScenarioImporter:
    """Create new rows and reject in-place mutation of versioned rows."""

    @staticmethod
    def _values(
        catalog: LoadedReferenceCatalog,
        row: dict,
    ) -> dict:
        fields = {
            key: row[key]
            for key in (
                "exact_model_code",
                "model_family",
                "risk_level",
                "title",
                "customer_utterance",
                "topic_code",
                "context_facts",
                "source_document_id",
                "source_policy",
                "manual_page_refs",
                "evidence_group_ids",
                "evidence_readiness",
                "expected_route",
                "expected_requires_consultation",
                "expected_publication_gate",
                "expected_usage_guidance_status",
                "expected_reason",
                "response_outline",
            )
        }
        fields.update(
            {
                "runtime_use": "REFERENCE_ONLY",
                "training_use": "PROHIBITED",
                "curation_status": "CANDIDATE",
                "is_runtime_enabled": False,
                "data_classification": "synthetic",
                "source_record_sha256": catalog.record_sha256[
                    row["scenario_id"]
                ],
                "source_catalog_sha256": catalog.catalog_sha256,
            }
        )
        return fields

    @classmethod
    @transaction.atomic
    def persist(
        cls,
        catalog: LoadedReferenceCatalog,
    ) -> ReferenceScenarioImportResult:
        created = 0
        unchanged = 0
        for row in catalog.rows:
            scenario_id = row["scenario_id"]
            existing = (
                ReferenceScenario.objects.select_for_update()
                .filter(
                    catalog_version=catalog.catalog_version,
                    scenario_id=scenario_id,
                )
                .first()
            )
            values = cls._values(catalog, row)
            if existing is not None:
                drifted = [
                    field
                    for field, expected in values.items()
                    if getattr(existing, field) != expected
                ]
                if drifted:
                    raise ReferenceScenarioImportConflict(
                        f"immutable scenario drift: {scenario_id} "
                        f"fields={','.join(sorted(drifted))}"
                    )
                unchanged += 1
                continue

            scenario = ReferenceScenario(
                scenario_id=scenario_id,
                catalog_version=catalog.catalog_version,
                **values,
            )
            try:
                scenario.full_clean(validate_unique=True)
            except ValidationError as exc:
                raise ReferenceScenarioImportConflict(
                    f"scenario model validation failed: {scenario_id}"
                ) from exc
            scenario.save(force_insert=True)
            created += 1

        return ReferenceScenarioImportResult(
            records=len(catalog.rows),
            created=created,
            unchanged=unchanged,
        )
