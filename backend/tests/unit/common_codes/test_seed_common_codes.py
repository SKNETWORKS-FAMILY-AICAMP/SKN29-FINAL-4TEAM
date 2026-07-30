"""확정 공통코드 계약 Seed의 반복 실행·범위 검증."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.common_codes.management.commands.seed_common_codes import (
    SEED_SPECS,
    load_contract_codes,
)
from apps.common_codes.models import CommonCode, CommonCodeGroup


pytestmark = pytest.mark.django_db


def test_seed_twice_preserves_counts_and_uuid_identifiers():
    first_output = StringIO()
    call_command("seed_common_codes", stdout=first_output)

    expected_code_count = sum(
        len(
            load_contract_codes(
                Path(__file__).resolve().parents[4]
                / "contracts"
                / "codes"
                / spec.filename
            )
        )
        for spec in SEED_SPECS
    )
    identifiers = {
        (code.group_id, code.code): (code.pk, code.public_id)
        for code in CommonCode.objects.all()
    }

    second_output = StringIO()
    call_command("seed_common_codes", stdout=second_output)

    assert CommonCodeGroup.objects.count() == len(SEED_SPECS)
    assert CommonCode.objects.count() == expected_code_count
    assert {
        (code.group_id, code.code): (code.pk, code.public_id)
        for code in CommonCode.objects.all()
    } == identifiers
    assert "BLOCKED_CONTRACT_MAPPING" in first_output.getvalue()
    assert "created=0" in second_output.getvalue()


def test_seeded_codes_match_each_allowlisted_contract():
    call_command("seed_common_codes", stdout=StringIO())
    contract_dir = (
        Path(__file__).resolve().parents[4] / "contracts" / "codes"
    )

    for spec in SEED_SPECS:
        expected = load_contract_codes(contract_dir / spec.filename)
        actual = list(
            CommonCode.objects.filter(group_id=spec.group_code)
            .order_by("display_order")
            .values_list("code", flat=True)
        )

        assert actual == expected


def test_contract_loader_blocks_current_lowercase_risk_contract():
    path = (
        Path(__file__).resolve().parents[4]
        / "contracts"
        / "codes"
        / "risk-levels.yaml"
    )

    with pytest.raises(CommandError, match="대문자 코드 형식"):
        load_contract_codes(path)


def test_seed_deactivates_removed_codes_without_deleting_them():
    call_command("seed_common_codes", stdout=StringIO())
    source_contract = "contracts/codes/user-roles.yaml"
    stale = CommonCode.objects.create(
        group_id="USER_ROLE",
        code="STALE_ROLE",
        code_name="제거된 역할",
        metadata={"source_contract": source_contract},
    )

    call_command("seed_common_codes", stdout=StringIO())

    stale.refresh_from_db()
    assert stale.is_active is False
    assert CommonCode.objects.filter(pk=stale.pk).exists()
