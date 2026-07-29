"""Resolve externally visible actions from the canonical PM YAML contract."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from apps.workflow.contracts.state_machine_loader import (
    load_state_machine_contract,
)


ACTION_RESPONSE_FIELDS = (
    "code",
    "label",
    "operation_id",
    "style",
    "requires_confirmation",
    "confirmation_message",
)


@lru_cache(maxsize=1)
def _contract_documents():
    return load_state_machine_contract()


class AllowedActionResolver:
    """Return only actions assigned to the current state and actor role."""

    @staticmethod
    def resolve(*, state_code: str, role_code: str) -> list[dict[str, Any]]:
        document = _contract_documents()["allowed_actions"]
        role_actions = (
            document["state_role_actions"]
            .get(state_code, {})
            .get(role_code, [])
        )
        catalog = {
            item["code"]: item
            for item in document["action_catalog"]
        }

        result = []
        for assignment in role_actions:
            action = catalog[assignment["action"]]
            result.append(
                {
                    field: action.get(field)
                    for field in ACTION_RESPONSE_FIELDS
                }
            )
        return result
