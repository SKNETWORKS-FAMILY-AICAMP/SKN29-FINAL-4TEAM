"""Fail-closed preflight for overdue T-019/T-020/T-021 runtime work.

The audit is intentionally read-only.  It records which preparation work is
safe while public contracts and upstream runtime dependencies remain open.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
WRITE_METHODS = {"post", "put", "patch"}
TASK_IDS = ("T-019", "T-020", "T-021")


def load_yaml(relative_path: str) -> Any:
    path = REPOSITORY_ROOT / relative_path
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def source_has_fragment(relative_path: str, fragment: str) -> bool:
    source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
    return fragment in source


def operation_methods(document: Any) -> set[str]:
    methods: set[str] = set()
    if not isinstance(document, dict):
        return methods
    for api_path, path_item in document.items():
        if not str(api_path).startswith("/") or not isinstance(path_item, dict):
            continue
        methods.update(set(path_item) & HTTP_METHODS)
    return methods


def runtime_sources_ready(requirements: dict[str, str]) -> bool:
    return all(
        source_has_fragment(relative_path, fragment)
        for relative_path, fragment in requirements.items()
    )


def audit_runtime_gates() -> dict[str, Any]:
    products = load_yaml("contracts/api/paths/products.yaml")
    care_paths = load_yaml("contracts/api/paths/care.yaml")
    questionnaires_paths = load_yaml(
        "contracts/api/paths/questionnaires.yaml"
    )
    next_care_schema = load_yaml(
        "contracts/api/components/schemas/care/NextCareSchedule.yaml"
    )

    t018_write_ready = bool(operation_methods(products) & WRITE_METHODS)
    care_contract_ready = bool(care_paths)
    questionnaire_contract_ready = bool(questionnaires_paths)
    next_care_rule_ready = bool(
        isinstance(next_care_schema, dict)
        and next_care_schema.get("properties")
    )
    care_runtime_ready = runtime_sources_ready(
        {
            "backend/apps/care/api/serializers.py": "class ",
            "backend/apps/care/api/views.py": "class ",
            "backend/apps/care/api/urls.py": "urlpatterns",
            "backend/apps/care/services/care_history_service.py": "class ",
            "backend/apps/care/repositories/care_history_repository.py": (
                "class "
            ),
        }
    )
    care_schedule_runtime_ready = runtime_sources_ready(
        {
            "backend/apps/care/services/care_schedule_service.py": "class ",
            "backend/apps/care/repositories/care_schedule_repository.py": (
                "class "
            ),
        }
    )
    questionnaire_runtime_ready = runtime_sources_ready(
        {
            "backend/apps/questionnaires/api/serializers.py": "class ",
            "backend/apps/questionnaires/api/views.py": "class ",
            "backend/apps/questionnaires/api/urls.py": "urlpatterns",
            "backend/apps/questionnaires/services/questionnaire_service.py": (
                "class "
            ),
            "backend/apps/questionnaires/repositories/questionnaire_repository.py": (
                "class "
            ),
        }
    )

    t019_blockers = []
    if not t018_write_ready:
        t019_blockers.append("T018_WRITE_SCOPE_NOT_CONTRACTED")
    if not care_contract_ready:
        t019_blockers.append("CARE_API_CONTRACT_EMPTY")
    if not care_runtime_ready:
        t019_blockers.append("CARE_RUNTIME_STUBS_ONLY")

    t020_blockers = []
    if t019_blockers:
        t020_blockers.append("T019_RUNTIME_NOT_READY")
    if not next_care_rule_ready:
        t020_blockers.append("NEXT_CARE_RULE_SCHEMA_EMPTY")
    if not care_schedule_runtime_ready:
        t020_blockers.append("CARE_SCHEDULE_RUNTIME_STUBS_ONLY")

    t021_blockers = []
    if t020_blockers:
        t021_blockers.append("T020_RUNTIME_NOT_READY")
    if not questionnaire_contract_ready:
        t021_blockers.append("QUESTIONNAIRE_API_CONTRACT_EMPTY")
    if not questionnaire_runtime_ready:
        t021_blockers.append("QUESTIONNAIRE_RUNTIME_STUBS_ONLY")

    task_blockers = {
        "T-019": t019_blockers,
        "T-020": t020_blockers,
        "T-021": t021_blockers,
    }
    tasks = {
        task_id: {
            "status": "BLOCKED" if blockers else "READY",
            "runtime_change_allowed": not blockers,
            "blockers": blockers,
        }
        for task_id, blockers in task_blockers.items()
    }

    forbidden_while_blocked = []
    if t019_blockers:
        forbidden_while_blocked.append(
            "PUBLIC_CARE_ENDPOINT_IMPLEMENTATION"
        )
    if t020_blockers:
        forbidden_while_blocked.append("NEXT_CARE_DATE_CALCULATION")
    if t021_blockers:
        forbidden_while_blocked.append(
            "PUBLIC_QUESTIONNAIRE_ENDPOINT_IMPLEMENTATION"
        )
    if any(task["blockers"] for task in tasks.values()):
        forbidden_while_blocked.append(
            "DATABASE_MIGRATION_FOR_BLOCKED_RUNTIME"
        )

    return {
        "schema_version": "1.0",
        "overall_status": (
            "PREPARATION_ONLY"
            if any(task["blockers"] for task in tasks.values())
            else "RUNTIME_READY"
        ),
        "tasks": tasks,
        "safe_without_external_decision": [
            "CONTRACT_GAP_INVENTORY",
            "FAIL_CLOSED_READINESS_TESTS",
            "IMPLEMENTED_ROUTE_REGRESSION",
            "EVIDENCE_DOCUMENTATION",
        ],
        "forbidden_while_blocked": forbidden_while_blocked,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit T-019/T-020/T-021 runtime gates without writes."
    )
    parser.add_argument(
        "--require-runtime-ready",
        choices=TASK_IDS,
        help="Exit 2 unless the selected task is ready for implementation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = audit_runtime_gates()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_runtime_ready:
        selected = result["tasks"][args.require_runtime_ready]
        if not selected["runtime_change_allowed"]:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
