"""Numbered consultant-to-contract routing boundaries."""

from types import SimpleNamespace

import pytest

from apps.inquiries.p1_team_routing import P1TeamConsultantRouting


@pytest.mark.parametrize(
    ("username", "contract_no"),
    [
        ("SKN-001", "SYN-P1-TEAM-CONTRACT-001"),
        ("SKN-002", "SYN-P1-TEAM-CONTRACT-002"),
        ("SKN-003", "SYN-P1-TEAM-CONTRACT-003"),
        ("SKN-004", "SYN-P1-TEAM-CONTRACT-004"),
        ("SKN-005", "SYN-P1-TEAM-CONTRACT-005"),
        ("SKN-006", "SYN-P1-TEAM-CONTRACT-006"),
        ("SKN-007", "SYN-P1-EXTRA-CONTRACT-001"),
    ],
)
def test_numbered_consultant_can_access_only_matching_reserved_contract(
    username,
    contract_no,
):
    actor = SimpleNamespace(username=username.lower())

    assert P1TeamConsultantRouting.assigned_contract(actor) == contract_no
    assert P1TeamConsultantRouting.is_exact_reserved_pair(
        actor=actor,
        contract_no=contract_no,
    )
    assert P1TeamConsultantRouting.can_access_contract(
        actor=actor,
        contract_no=contract_no,
    )
    other_contract = (
        "SYN-P1-TEAM-CONTRACT-001"
        if contract_no != "SYN-P1-TEAM-CONTRACT-001"
        else "SYN-P1-TEAM-CONTRACT-002"
    )
    assert not P1TeamConsultantRouting.is_exact_reserved_pair(
        actor=actor,
        contract_no=other_contract,
    )
    assert not P1TeamConsultantRouting.can_access_contract(
        actor=actor,
        contract_no=other_contract,
    )


def test_nonreserved_contract_keeps_existing_public_claim_flow():
    actor = SimpleNamespace(username="OTHER-CONSULTANT")

    assert P1TeamConsultantRouting.assigned_contract(actor) is None
    assert not P1TeamConsultantRouting.is_exact_reserved_pair(
        actor=actor,
        contract_no="PUBLIC-CONTRACT-001",
    )
    assert P1TeamConsultantRouting.can_access_contract(
        actor=actor,
        contract_no="PUBLIC-CONTRACT-001",
    )
