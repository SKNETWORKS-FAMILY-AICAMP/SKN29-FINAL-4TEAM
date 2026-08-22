"""Install and verify the Linux CI lock in a clean target container."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from generate_linux_ci_lock import (
    PYPI_INDEX_URL,
    PYTORCH_CPU_INDEX_URL,
    _assert_cpu_only_lock,
    _assert_generation_environment,
    _repository_root,
)


def _run(*args: str, capture_output: bool = False) -> str:
    completed = subprocess.run(
        [sys.executable, *args],
        check=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.STDOUT if capture_output else None,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout if capture_output else ""


def main() -> None:
    _assert_generation_environment()
    root = _repository_root()
    lock_path = root / "ai" / "requirements-linux.lock"
    if not lock_path.is_file():
        raise FileNotFoundError(f"Linux CI Lock이 없습니다: {lock_path}")

    _run(
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-deps",
        "--only-binary=:all:",
        "--index-url",
        PYPI_INDEX_URL,
        "--extra-index-url",
        PYTORCH_CPU_INDEX_URL,
        "--requirement",
        str(lock_path),
    )

    pip_check = _run("-m", "pip", "check", capture_output=True).strip()
    print(f"pip_check={pip_check}")

    frozen = _run("-m", "pip", "freeze", "--local", capture_output=True)
    requirement_lines = sorted(
        line.strip()
        for line in frozen.splitlines()
        if line.strip() and not line.startswith("pip==")
    )
    _assert_cpu_only_lock(requirement_lines)

    _run(
        "-m",
        "pytest",
        str(Path("ai") / "tests" / "unit"),
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp=ai/tests/.linux-pytest-root/basetemp",
    )
    print("linux_lock_verification=PASS")


if __name__ == "__main__":
    main()
