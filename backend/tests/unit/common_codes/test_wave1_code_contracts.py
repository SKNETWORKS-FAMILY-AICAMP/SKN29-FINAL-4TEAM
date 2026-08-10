"""Wave 1 AI·지식수집 코드의 YAML·Runtime·Seed parity 검증."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command

from apps.audit.models import AIRun
from apps.common_codes.models import CommonCode, CommonCodeGroup
from apps.evidence.models import IngestionBatch


pytestmark = pytest.mark.django_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_DIR = REPOSITORY_ROOT / "contracts" / "codes"

WAVE1_CODE_CONTRACTS = (
    (
        "ai-task-types.yaml",
        "AI_TASK_TYPE",
        AIRun.TaskType,
    ),
    (
        "ai-schema-validation-statuses.yaml",
        "AI_SCHEMA_VALIDATION_STATUS",
        AIRun.SchemaValidationStatus,
    ),
    (
        "ai-run-statuses.yaml",
        "AI_RUN_STATUS",
        AIRun.Status,
    ),
    (
        "dataset-scopes.yaml",
        "DATASET_SCOPE",
        IngestionBatch.DatasetScope,
    ),
    (
        "ingestion-source-types.yaml",
        "INGESTION_SOURCE_TYPE",
        IngestionBatch.SourceType,
    ),
    (
        "ingestion-statuses.yaml",
        "INGESTION_STATUS",
        IngestionBatch.Status,
    ),
)


def load_contract(filename: str) -> dict:
    return yaml.safe_load(
        (CONTRACT_DIR / filename).read_text(encoding="utf-8")
    )


def test_wave1_yaml_textchoices_and_seed_are_equal():
    call_command("seed_common_codes", stdout=StringIO())

    for filename, group_code, text_choices in WAVE1_CODE_CONTRACTS:
        contract = load_contract(filename)
        yaml_codes = contract["codes"]
        seeded_codes = list(
            CommonCode.objects.filter(group_id=group_code)
            .order_by("display_order")
            .values_list("code", flat=True)
        )
        source_contract = f"contracts/codes/{filename}"
        source_values = set(
            CommonCode.objects.filter(group_id=group_code)
            .values_list("metadata__source_contract", flat=True)
        )

        assert contract["status"] == "OWNER_BASELINE"
        assert yaml_codes == list(text_choices.values)
        assert seeded_codes == yaml_codes
        assert source_values == {source_contract}


def test_wave1_seed_twice_preserves_rows_and_identifiers():
    first_output = StringIO()
    call_command("seed_common_codes", stdout=first_output)

    group_codes = {
        group_code
        for _, group_code, _ in WAVE1_CODE_CONTRACTS
    }
    first_groups = {
        group.group_code: group.pk
        for group in CommonCodeGroup.objects.filter(
            group_code__in=group_codes
        )
    }
    first_codes = {
        (code.group_id, code.code): (code.pk, code.public_id)
        for code in CommonCode.objects.filter(
            group_id__in=group_codes
        )
    }

    second_output = StringIO()
    call_command("seed_common_codes", stdout=second_output)

    expected_code_count = sum(
        len(load_contract(filename)["codes"])
        for filename, _, _ in WAVE1_CODE_CONTRACTS
    )
    assert len(first_groups) == len(WAVE1_CODE_CONTRACTS)
    assert len(first_codes) == expected_code_count
    assert {
        group.group_code: group.pk
        for group in CommonCodeGroup.objects.filter(
            group_code__in=group_codes
        )
    } == first_groups
    assert {
        (code.group_id, code.code): (code.pk, code.public_id)
        for code in CommonCode.objects.filter(
            group_id__in=group_codes
        )
    } == first_codes
    assert "groups: created=0, updated=16" in second_output.getvalue()
    assert "codes: created=0" in second_output.getvalue()
