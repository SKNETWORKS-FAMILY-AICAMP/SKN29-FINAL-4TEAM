#!/usr/bin/env python3
"""WaterBridge Backend 로컬 가상환경을 재현한다.

이 스크립트는 Python 표준 라이브러리만 사용한다. 비밀값이나 .env를
생성·수정하지 않으며 Docker, Migration, Seed도 자동 실행하지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
VENV_ROOT = BACKEND_ROOT / ".venv"
RUNTIME_ROOT = BACKEND_ROOT / ".runtime"
VERSION_FILE = BACKEND_ROOT / ".python-version"
LOCAL_REQUIREMENTS = BACKEND_ROOT / "requirements" / "local.txt"
BASE_REQUIREMENTS = BACKEND_ROOT / "requirements" / "base.txt"
CONSTRAINTS = BACKEND_ROOT / "requirements" / "constraints-py313.txt"
STATE_FILE_NAME = ".waterbridge-environment.json"
# 기존 가상환경을 재설치하지 않고 읽기 위한 전환기 호환 파일명이다.
LEGACY_STATE_FILE_NAME = ".watercare-environment.json"
PIP_VERSION = "26.0.1"


class BootstrapError(RuntimeError):
    """사용자가 조치할 수 있는 환경 재현 오류."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service",
        choices=("backend",),
        default="backend",
        help="현재 자동화 대상 서비스(현재 backend만 지원)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="기존 backend/.venv를 백업한 뒤 최종 경로에 새로 생성",
    )
    return parser.parse_args()


def required_python_version() -> str:
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not value:
        raise BootstrapError(f"Python 버전 파일이 비어 있습니다: {VERSION_FILE}")
    return value


def ensure_under(path: Path, parent: Path) -> Path:
    resolved_path = path.resolve(strict=False)
    resolved_parent = parent.resolve(strict=True)
    try:
        resolved_path.relative_to(resolved_parent)
    except ValueError as exc:
        raise BootstrapError(f"보호 경로 밖을 사용할 수 없습니다: {resolved_path}") from exc
    return resolved_path


def venv_python(venv_root: Path = VENV_ROOT) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def command_text(command: list[str | os.PathLike[str]]) -> str:
    return shlex.join(str(part) for part in command)


def run(
    command: list[str | os.PathLike[str]],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print(f"+ {command_text(command)}")
    return subprocess.run(
        [str(part) for part in command],
        cwd=cwd,
        env=env,
        text=True,
        check=True,
        capture_output=capture,
    )


def environment_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (VERSION_FILE, BASE_REQUIREMENTS, LOCAL_REQUIREMENTS, CONSTRAINTS):
        digest.update(path.relative_to(REPO_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(f"pip=={PIP_VERSION}".encode("ascii"))
    return digest.hexdigest()


def canonical_package_name(value: str) -> str:
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
        result[canonical_package_name(name)] = (name, version)
    return result


def installed_python_version(python: Path) -> str:
    result = run(
        [python, "-c", "import platform; print(platform.python_version())"],
        capture=True,
    )
    return result.stdout.strip()


def pip_version(python: Path) -> str:
    result = run([python, "-m", "pip", "--version"], capture=True)
    parts = result.stdout.split()
    return parts[1] if len(parts) >= 2 else ""


def remove_tree(path: Path) -> None:
    safe_path = ensure_under(path, BACKEND_ROOT)
    if not safe_path.exists():
        return

    def handle_readonly(function, target, _error) -> None:
        os.chmod(target, stat.S_IWRITE)
        function(target)

    shutil.rmtree(safe_path, onexc=handle_readonly)


def create_isolated_environment(python: Path) -> None:
    ensure_under(VENV_ROOT, BACKEND_ROOT)
    temp_root = ensure_under(RUNTIME_ROOT / "tmp" / "bootstrap", BACKEND_ROOT)
    temp_root.mkdir(parents=True, exist_ok=True)
    child_env = os.environ.copy()
    child_env["TEMP"] = str(temp_root)
    child_env["TMP"] = str(temp_root)

    try:
        run([sys.executable, "-m", "venv", VENV_ROOT], env=child_env)
    except subprocess.CalledProcessError:
        print("ensurepip 생성이 실패해 host pip 방식으로 한 번 재시도합니다.")
        remove_tree(VENV_ROOT)
        run(
            [sys.executable, "-m", "venv", "--without-pip", VENV_ROOT],
            env=child_env,
        )
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "--python",
                python,
                "install",
                "--disable-pip-version-check",
                f"pip=={PIP_VERSION}",
            ],
            env=child_env,
        )

    run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            f"pip=={PIP_VERSION}",
        ],
        env=child_env,
    )


def install_dependencies(python: Path) -> None:
    run(
        [
            python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--constraint",
            CONSTRAINTS,
            "--requirement",
            LOCAL_REQUIREMENTS,
        ]
    )


def validate_environment(python: Path) -> None:
    expected_python = required_python_version()
    actual_python = installed_python_version(python)
    if actual_python != expected_python:
        raise BootstrapError(
            f"가상환경 Python 불일치: expected={expected_python}, actual={actual_python}"
        )

    actual_pip = pip_version(python)
    if actual_pip != PIP_VERSION:
        raise BootstrapError(
            f"가상환경 pip 불일치: expected={PIP_VERSION}, actual={actual_pip}"
        )

    package_result = run(
        [python, "-m", "pip", "list", "--format=json"],
        capture=True,
    )
    installed = {
        canonical_package_name(item["name"]): item["version"]
        for item in json.loads(package_result.stdout)
    }
    mismatches = []
    for key, (display_name, expected_version) in expected_packages().items():
        actual_version = installed.get(key)
        if actual_version != expected_version:
            mismatches.append(
                f"{display_name}: expected={expected_version}, actual={actual_version}"
            )
    allowed = set(expected_packages()) | {"pip"}
    extras = sorted(name for name in installed if name not in allowed)
    if mismatches or extras:
        details = "; ".join(mismatches)
        if extras:
            details = f"{details}; extra={','.join(extras)}".strip("; ")
        raise BootstrapError(f"constraints와 설치 패키지가 다릅니다: {details}")

    run([python, "-m", "pip", "check"])
    check_env = os.environ.copy()
    check_env["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    run([python, "manage.py", "check"], cwd=BACKEND_ROOT, env=check_env)


def write_state(python: Path) -> None:
    state = {
        "service": "backend",
        "python": required_python_version(),
        "pip": PIP_VERSION,
        "fingerprint": environment_fingerprint(),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "requirements": [
            BASE_REQUIREMENTS.relative_to(REPO_ROOT).as_posix(),
            LOCAL_REQUIREMENTS.relative_to(REPO_ROOT).as_posix(),
            CONSTRAINTS.relative_to(REPO_ROOT).as_posix(),
        ],
        "interpreter": str(python),
    }
    (VENV_ROOT / STATE_FILE_NAME).write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def state_matches() -> bool:
    for state_file_name in (STATE_FILE_NAME, LEGACY_STATE_FILE_NAME):
        state_file = VENV_ROOT / state_file_name
        if not state_file.is_file():
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        return state.get("fingerprint") == environment_fingerprint()
    return False


def backup_existing_environment() -> Path | None:
    if not VENV_ROOT.exists():
        return None
    running_python = Path(sys.executable).resolve(strict=True)
    try:
        running_python.relative_to(VENV_ROOT.resolve(strict=True))
    except ValueError:
        pass
    else:
        raise BootstrapError(
            "--recreate는 교체 대상 backend/.venv 밖의 Python으로 실행해야 합니다."
        )

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ensure_under(
        RUNTIME_ROOT / "venv-backups" / stamp / ".venv",
        BACKEND_ROOT,
    )
    backup.parent.mkdir(parents=True, exist_ok=False)
    print(f"기존 환경 백업: {backup}")
    shutil.move(str(VENV_ROOT), str(backup))
    return backup


def restore_backup(backup: Path | None) -> None:
    if backup is None:
        return
    if VENV_ROOT.exists():
        remove_tree(VENV_ROOT)
    print(f"환경 생성 실패로 백업 복원: {backup} -> {VENV_ROOT}")
    shutil.move(str(backup), str(VENV_ROOT))


def main() -> int:
    args = parse_args()
    expected_python = required_python_version()
    actual_host_python = platform.python_version()
    if actual_host_python != expected_python:
        raise BootstrapError(
            "이 스크립트는 backend/.python-version과 같은 Python으로 실행해야 "
            f"합니다: expected={expected_python}, actual={actual_host_python}, "
            f"executable={sys.executable}"
        )

    python = venv_python()
    backup: Path | None = None
    created_environment = False
    try:
        if args.recreate:
            backup = backup_existing_environment()

        if not python.is_file():
            if VENV_ROOT.exists():
                remove_tree(VENV_ROOT)
            print(f"Backend 가상환경 생성: {VENV_ROOT}")
            created_environment = True
            create_isolated_environment(python)
            install_dependencies(python)
        else:
            actual_python = installed_python_version(python)
            if actual_python != expected_python:
                raise BootstrapError(
                    "기존 backend/.venv의 Python이 기준과 다릅니다. "
                    f"expected={expected_python}, actual={actual_python}. "
                    "기반 Python을 확인한 뒤 --recreate를 사용하세요."
                )
            if state_matches():
                print("requirements fingerprint가 같아 설치를 생략합니다.")
            else:
                print("requirements fingerprint가 달라 의존성을 동기화합니다.")
                run(
                    [
                        python,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        f"pip=={PIP_VERSION}",
                    ]
                )
                install_dependencies(python)

        validate_environment(python)
        write_state(python)
    except (BootstrapError, OSError, subprocess.CalledProcessError) as exc:
        if backup is None and created_environment and VENV_ROOT.exists():
            remove_tree(VENV_ROOT)
        restore_backup(backup)
        print(f"[FAIL] Backend 환경 재현 실패: {exc}", file=sys.stderr)
        return 1

    print("[PASS] Backend 환경 재현 및 경량 검증 완료")
    print(f"interpreter={python}")
    print(f"python={expected_python}")
    print(f"pip={PIP_VERSION}")
    print(f"fingerprint={environment_fingerprint()}")
    if backup is not None:
        print(f"rollback_backup={backup}")
        print("전체 검증 후 필요 없을 때만 위 백업을 삭제하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
