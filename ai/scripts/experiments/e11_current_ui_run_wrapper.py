"""Run the repository-native E11 isolated workflow without source patching."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = REPO_ROOT / "web"
INNER_RUNNER = (
    REPO_ROOT
    / "ai"
    / "scripts"
    / "experiments"
    / "e11_isolated_setup_and_run.py"
)


def assert_native_specs() -> None:
    consultation = (
        WEB_ROOT / "e2e" / "specs" / "consultation-workflow.spec.ts"
    ).read_text(encoding="utf-8")
    technician = (
        WEB_ROOT / "e2e" / "specs" / "technician-selection.spec.ts"
    ).read_text(encoding="utf-8")

    checks = {
        "product_section_contract": (
            "toContainText(expected.productModel)" in consultation
            and "toContainText(expected.productModelName)" in consultation
        ),
        "consultation_step_navigation": (
            consultation.count('name: "상담 3단계: 상담 진행"') >= 2
        ),
        "consultation_current_summary_label": (
            'getByLabel("상담 내용 수정본"' in consultation
        ),
        "consultation_history_portal": (
            consultation.count('name: "이전 상담 기록·처리 이력"') >= 2
        ),
        "technician_step_navigation": (
            technician.count('name: "상담 3단계: 상담 진행"') >= 2
        ),
        "technician_current_summary_label": (
            'getByLabel("상담 내용 수정본"' in technician
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(
            "Repository-native E11 specs are not aligned: "
            f"{checks}"
        )


def main() -> int:
    if not INNER_RUNNER.exists():
        print("[E11-UI] BLOCKED: inner isolated runner missing")
        return 2

    try:
        assert_native_specs()
    except (OSError, UnicodeError, RuntimeError) as exc:
        print("[E11-UI] NATIVE_SPEC_BLOCKED")
        print(str(exc))
        return 2

    print(
        "[E11-UI] Repository-native current UI specs: PASS "
        "(runtime patch 없음)"
    )
    result = subprocess.run(
        [sys.executable, str(INNER_RUNNER)],
        cwd=REPO_ROOT,
    )
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
