"""Fail-closed routing for the six reserved P1 team contracts."""

from __future__ import annotations

from typing import Any


P1_TEAM_CONSULTANT_CONTRACT_MAP = {
    "SKN-001": "SYN-P1-TEAM-CONTRACT-001",
    "SKN-002": "SYN-P1-TEAM-CONTRACT-002",
    "SKN-003": "SYN-P1-TEAM-CONTRACT-003",
    "SKN-004": "SYN-P1-TEAM-CONTRACT-004",
    "SKN-005": "SYN-P1-TEAM-CONTRACT-005",
    "SKN-006": "SYN-P1-TEAM-CONTRACT-006",
}
P1_TEAM_RESERVED_CONTRACTS = frozenset(
    P1_TEAM_CONSULTANT_CONTRACT_MAP.values()
)
P1_TEAM_CONTRACT_CONSULTANT_MAP = {
    contract_no: username
    for username, contract_no in P1_TEAM_CONSULTANT_CONTRACT_MAP.items()
}


class P1TeamConsultantRouting:
    """Keep reserved P1 work visible only to its numbered consultant."""

    @staticmethod
    def _username(actor: Any) -> str:
        return str(getattr(actor, "username", "") or "").strip().upper()

    @classmethod
    def assigned_contract(cls, actor: Any) -> str | None:
        return P1_TEAM_CONSULTANT_CONTRACT_MAP.get(cls._username(actor))

    @staticmethod
    def reserved_contracts() -> frozenset[str]:
        return P1_TEAM_RESERVED_CONTRACTS

    @classmethod
    def can_access_contract(cls, *, actor: Any, contract_no: str) -> bool:
        required_username = P1_TEAM_CONTRACT_CONSULTANT_MAP.get(
            str(contract_no).strip()
        )
        if required_username is None:
            return True
        return cls._username(actor) == required_username
