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


def test_runtime_gates_reflect_t019_t020_and_t021_ready():
    result = load_module().audit_runtime_gates()

    assert result["overall_status"] == "RUNTIME_READY"
    assert result["tasks"] == {
        "T-019": {
            "status": "READY",
            "runtime_change_allowed": True,
            "blockers": [],
        },
        "T-020": {
            "status": "READY",
            "runtime_change_allowed": True,
            "blockers": [],
        },
        "T-021": {
            "status": "READY",
            "runtime_change_allowed": True,
            "blockers": [],
        },
    }


def test_preflight_allows_all_three_ready_scopes():
    result = load_module().audit_runtime_gates()

    assert "IMPLEMENTED_ROUTE_REGRESSION" in result[
        "safe_without_external_decision"
    ]
    assert "EVIDENCE_DOCUMENTATION" in result[
        "safe_without_external_decision"
    ]
    assert "PUBLIC_CARE_ENDPOINT_IMPLEMENTATION" not in result[
        "forbidden_while_blocked"
    ]
    assert "NEXT_CARE_DATE_CALCULATION" not in result[
        "forbidden_while_blocked"
    ]
    assert "PUBLIC_QUESTIONNAIRE_ENDPOINT_IMPLEMENTATION" not in result[
        "forbidden_while_blocked"
    ]
    assert result["forbidden_while_blocked"] == []


def test_require_runtime_ready_passes_t019_t020_and_t021(capsys):
    module = load_module()

    assert module.main(["--require-runtime-ready", "T-019"]) == 0
    assert module.main(["--require-runtime-ready", "T-020"]) == 0
    assert module.main(["--require-runtime-ready", "T-021"]) == 0
    assert '"overall_status": "RUNTIME_READY"' in capsys.readouterr().out
