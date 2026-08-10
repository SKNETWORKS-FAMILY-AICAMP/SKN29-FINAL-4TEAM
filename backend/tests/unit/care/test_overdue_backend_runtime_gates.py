"""Regression tests for the T-019/T-020/T-021 fail-closed preflight."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (
    REPOSITORY_ROOT
    / "scripts"
    / "contracts"
    / "audit_overdue_backend_runtime_gates.py"
)


def load_module():
    spec = spec_from_file_location("overdue_backend_runtime_gates", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overdue_tasks_are_fail_closed_at_current_contract_baseline():
    result = load_module().audit_runtime_gates()

    assert result["overall_status"] == "PREPARATION_ONLY"
    assert result["tasks"] == {
        "T-019": {
            "status": "BLOCKED",
            "runtime_change_allowed": False,
            "blockers": [
                "T018_WRITE_SCOPE_NOT_CONTRACTED",
                "CARE_API_CONTRACT_EMPTY",
                "CARE_RUNTIME_STUBS_ONLY",
            ],
        },
        "T-020": {
            "status": "BLOCKED",
            "runtime_change_allowed": False,
            "blockers": [
                "T019_RUNTIME_NOT_READY",
                "NEXT_CARE_RULE_SCHEMA_EMPTY",
                "CARE_SCHEDULE_RUNTIME_STUBS_ONLY",
            ],
        },
        "T-021": {
            "status": "BLOCKED",
            "runtime_change_allowed": False,
            "blockers": [
                "T020_RUNTIME_NOT_READY",
                "QUESTIONNAIRE_API_CONTRACT_EMPTY",
                "QUESTIONNAIRE_RUNTIME_STUBS_ONLY",
            ],
        },
    }


def test_preflight_allows_evidence_work_but_not_blocked_runtime_changes():
    result = load_module().audit_runtime_gates()

    assert "IMPLEMENTED_ROUTE_REGRESSION" in result[
        "safe_without_external_decision"
    ]
    assert "EVIDENCE_DOCUMENTATION" in result[
        "safe_without_external_decision"
    ]
    assert "PUBLIC_CARE_ENDPOINT_IMPLEMENTATION" in result[
        "forbidden_while_blocked"
    ]
    assert "NEXT_CARE_DATE_CALCULATION" in result[
        "forbidden_while_blocked"
    ]


def test_require_runtime_ready_returns_two_for_each_blocked_task(capsys):
    module = load_module()

    for task_id in module.TASK_IDS:
        assert module.main(["--require-runtime-ready", task_id]) == 2
    assert '"overall_status": "PREPARATION_ONLY"' in capsys.readouterr().out
