#!/usr/bin/env python3
"""WaterCare Backend 가상환경의 재현 상태를 읽기 전용으로 점검한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
VENV_ROOT = BACKEND_ROOT / ".venv"
VERSION_FILE = BACKEND_ROOT / ".python-version"
BASE_REQUIREMENTS = BACKEND_ROOT / "requirements" / "base.txt"
LOCAL_REQUIREMENTS = BACKEND_ROOT / "requirements" / "local.txt"
CONSTRAINTS = BACKEND_ROOT / "requirements" / "constraints-py313.txt"
STATE_FILE = VENV_ROOT / ".watercare-environment.json"
PIP_VERSION = "26.0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", choices=("backend",), default="backend")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Migration drift, 전체 pytest, Git 추적 여부까지 확인",
    )
    parser.add_argument(
        "--postgresql",
        action="store_true",
        help="현재 backend/.env 기준 PostgreSQL 연결과 적용 Migration 확인",
    )
    return parser.parse_args()


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_ROOT / "Scripts" / "python.exe"
    return VENV_ROOT / "bin" / "python"


def canonical_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def expected_packages() -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for raw_line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = line.split(";", maxsplit=1)[0].strip()
        if "==" not in requirement:
            continue
        name, version = requirement.split("==", maxsplit=1)
        result[canonical_name(name)] = (name, version)
    return result


def fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (VERSION_FILE, BASE_REQUIREMENTS, LOCAL_REQUIREMENTS, CONSTRAINTS):
        digest.update(path.relative_to(REPO_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(f"pip=={PIP_VERSION}".encode("ascii"))
    return digest.hexdigest()


class Reporter:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def passed(self, message: str) -> None:
        print(f"[PASS] {message}")

    def failed(self, message: str) -> None:
        self.failures.append(message)
        print(f"[FAIL] {message}")

    def warned(self, message: str) -> None:
        self.warnings.append(message)
        print(f"[WARN] {message}")


def capture(command: list[str | Path], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def run_visible(
    reporter: Reporter,
    label: str,
    command: list[str | Path],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
) -> None:
    print(f"\n--- {label} ---")
    result = subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
    )
    if result.returncode == 0:
        reporter.passed(label)
    else:
        reporter.failed(f"{label} (exit={result.returncode})")


def check_pyvenv_config(reporter: Reporter) -> None:
    config = VENV_ROOT / "pyvenv.cfg"
    if not config.is_file():
        reporter.failed(f"pyvenv.cfg 없음: {config}")
        return
    values: dict[str, str] = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", maxsplit=1)
            values[key.strip().lower()] = value.strip()
    if values.get("include-system-site-packages", "").lower() == "false":
        reporter.passed("system site-packages 격리")
    else:
        reporter.failed("include-system-site-packages가 false가 아님")


def check_versions(reporter: Reporter, python: Path) -> None:
    expected_python = VERSION_FILE.read_text(encoding="utf-8").strip()
    result = capture(
        [python, "-c", "import platform; print(platform.python_version())"]
    )
    if result.returncode != 0:
        reporter.failed(f"가상환경 Python 실행 실패: {result.stderr.strip()}")
        return
    actual_python = result.stdout.strip()
    if actual_python == expected_python:
        reporter.passed(f"Python {actual_python}")
    else:
        reporter.failed(
            f"Python 불일치: expected={expected_python}, actual={actual_python}"
        )

    result = capture([python, "-m", "pip", "--version"])
    parts = result.stdout.split()
    actual_pip = parts[1] if result.returncode == 0 and len(parts) >= 2 else ""
    if actual_pip == PIP_VERSION:
        reporter.passed(f"pip {actual_pip}")
    else:
        reporter.failed(f"pip 불일치: expected={PIP_VERSION}, actual={actual_pip}")


def check_packages(reporter: Reporter, python: Path) -> None:
    result = capture([python, "-m", "pip", "list", "--format=json"])
    if result.returncode != 0:
        reporter.failed(f"설치 패키지 조회 실패: {result.stderr.strip()}")
        return
    installed = {
        canonical_name(item["name"]): item["version"]
        for item in json.loads(result.stdout)
    }
    mismatches: list[str] = []
    for key, (display_name, expected_version) in expected_packages().items():
        actual_version = installed.get(key)
        if actual_version != expected_version:
            mismatches.append(
                f"{display_name}: expected={expected_version}, actual={actual_version}"
            )
    if mismatches:
        for mismatch in mismatches:
            reporter.failed(mismatch)
    else:
        reporter.passed(f"constraints 고정 패키지 {len(expected_packages())}개")

    allowed = set(expected_packages()) | {"pip"}
    extras = sorted(name for name in installed if name not in allowed)
    if extras:
        reporter.warned("constraints 밖 추가 패키지: " + ", ".join(extras))
    else:
        reporter.passed("constraints 밖 추가 패키지 0개")


def check_state(reporter: Reporter) -> None:
    if not STATE_FILE.is_file():
        reporter.failed(
            "환경 fingerprint 상태파일 없음. bootstrap.py를 한 번 실행하세요."
        )
        return
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        reporter.failed(f"환경 fingerprint 상태파일 오류: {exc}")
        return
    current = fingerprint()
    if state.get("fingerprint") == current:
        reporter.passed(f"requirements fingerprint {current}")
    else:
        reporter.failed("requirements fingerprint 불일치. bootstrap.py를 실행하세요.")


def check_git_exclusion(reporter: Reporter) -> None:
    result = capture(["git", "ls-files", "--", "backend/.venv"])
    tracked = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode != 0:
        reporter.failed(f"Git 추적 검사 실패: {result.stderr.strip()}")
    elif tracked:
        reporter.failed(f"backend/.venv Git 추적 파일 {len(tracked)}개")
    else:
        reporter.passed("backend/.venv Git 추적 파일 0개")

    ignore_probe = VENV_ROOT / "pyvenv.cfg"
    result = capture(["git", "check-ignore", "-q", str(ignore_probe)])
    if result.returncode == 0:
        reporter.passed("backend/.venv Git 제외 규칙")
    else:
        reporter.failed("backend/.venv가 Git 제외 규칙에 포함되지 않음")


def main() -> int:
    args = parse_args()
    reporter = Reporter()
    python = venv_python()
    if not python.is_file():
        reporter.failed(f"Backend 가상환경 없음: {python}")
        print("실행: python scripts/development/bootstrap.py --service backend")
        return 1

    check_pyvenv_config(reporter)
    check_versions(reporter, python)
    check_packages(reporter, python)
    check_state(reporter)
    run_visible(reporter, "pip check", [python, "-m", "pip", "check"])

    test_env = os.environ.copy()
    test_env["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    run_visible(
        reporter,
        "Django system check",
        [python, "manage.py", "check"],
        cwd=BACKEND_ROOT,
        env=test_env,
    )

    if args.full:
        run_visible(
            reporter,
            "Migration drift check",
            [python, "manage.py", "makemigrations", "--check", "--dry-run"],
            cwd=BACKEND_ROOT,
            env=test_env,
        )
        run_visible(
            reporter,
            "Backend 전체 pytest",
            [python, "-m", "pytest", "-q"],
            cwd=BACKEND_ROOT,
            env=test_env,
        )
        check_git_exclusion(reporter)

    if args.postgresql:
        local_env = os.environ.copy()
        local_env["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
        run_visible(
            reporter,
            "PostgreSQL read-only connection",
            [python, REPO_ROOT / "scripts" / "database" / "check_postgresql_connection.py"],
            cwd=BACKEND_ROOT,
            env=local_env,
        )
        run_visible(
            reporter,
            "Applied Migration check",
            [python, "manage.py", "migrate", "--check"],
            cwd=BACKEND_ROOT,
            env=local_env,
        )

    print("\n=== Backend 환경 점검 요약 ===")
    print(f"failures={len(reporter.failures)}")
    print(f"warnings={len(reporter.warnings)}")
    if reporter.failures:
        return 1
    print("[PASS] 요청한 환경 점검 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
