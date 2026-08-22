"""Generate the pinned Ubuntu 24.04 x86_64 CPU-only AI CI lock."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys


EXPECTED_OS_ID = "ubuntu"
EXPECTED_OS_VERSION = "24.04"
EXPECTED_ARCHITECTURE = "x86_64"
EXPECTED_PYTHON_VERSION = "3.13.13"
EXPECTED_PIP_VERSION = "26.1.2"
PYPI_INDEX_URL = "https://pypi.org/simple"
PYTORCH_CPU_INDEX_URL = "https://download.pytorch.org/whl/cpu"
FORBIDDEN_PACKAGE_PREFIXES = (
    "cuda-",
    "cupy-",
    "nvidia-",
    "pytorch-triton",
    "torchtriton",
)
FORBIDDEN_PACKAGE_NAMES = {"pywin32", "triton"}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        if not raw_line or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _run(*args: str) -> str:
    completed = subprocess.run(
        [sys.executable, *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _assert_generation_environment() -> None:
    os_release = _os_release()
    actual = {
        "os_id": os_release.get("ID"),
        "os_version": os_release.get("VERSION_ID"),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }
    expected = {
        "os_id": EXPECTED_OS_ID,
        "os_version": EXPECTED_OS_VERSION,
        "architecture": EXPECTED_ARCHITECTURE,
        "python_version": EXPECTED_PYTHON_VERSION,
    }
    if actual != expected:
        raise RuntimeError(
            "Linux CI Lock 생성 환경이 고정 기준과 다릅니다: "
            f"actual={json.dumps(actual, sort_keys=True)}"
        )

    pip_version = _run("-m", "pip", "--version").split()[1]
    if pip_version != EXPECTED_PIP_VERSION:
        raise RuntimeError(
            f"pip 버전은 {EXPECTED_PIP_VERSION}이어야 합니다: actual={pip_version}"
        )


def _normalized_name(requirement_line: str) -> str:
    return requirement_line.split("==", 1)[0].strip().lower().replace("_", "-")


def _assert_cpu_only_lock(requirement_lines: list[str]) -> None:
    normalized_names = {_normalized_name(line) for line in requirement_lines}
    forbidden = sorted(
        name
        for name in normalized_names
        if name in FORBIDDEN_PACKAGE_NAMES
        or name.startswith(FORBIDDEN_PACKAGE_PREFIXES)
    )
    if forbidden:
        raise RuntimeError(f"GPU/CUDA Package가 Linux CI Lock에 포함됐습니다: {forbidden}")

    torch_lines = [line for line in requirement_lines if _normalized_name(line) == "torch"]
    if torch_lines != ["torch==2.13.0+cpu"]:
        raise RuntimeError(f"CPU-only torch Pin이 올바르지 않습니다: {torch_lines}")

    import torch

    if torch.__version__ != "2.13.0+cpu" or torch.version.cuda is not None:
        raise RuntimeError(
            "설치된 torch가 CPU-only Build가 아닙니다: "
            f"version={torch.__version__}, cuda={torch.version.cuda}"
        )


def main() -> None:
    _assert_generation_environment()
    root = _repository_root()
    input_path = root / "ai" / "requirements-linux.in"
    output_path = root / "ai" / "requirements-linux.lock"

    _run(
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--only-binary=:all:",
        "--index-url",
        PYPI_INDEX_URL,
        "--extra-index-url",
        PYTORCH_CPU_INDEX_URL,
        "--requirement",
        str(input_path),
    )
    frozen = _run("-m", "pip", "freeze", "--local")
    requirement_lines = sorted(
        line.strip()
        for line in frozen.splitlines()
        if line.strip() and not line.startswith("pip==")
    )
    _assert_cpu_only_lock(requirement_lines)

    header = [
        "# Runtime: Ubuntu 24.04 LTS / x86_64 / CPython 3.13.13 / CPU-only.",
        "# Resolver: pip 26.1.2. Exact versions are pinned without package hashes.",
        "# Input: ai/requirements-linux.in with the official PyTorch CPU wheel index.",
        "# Scope: GitHub Actions Required Gate candidate; production reuse is NOT_VERIFIED.",
    ]
    output_text = "\n".join([*header, *requirement_lines, ""])
    output_path.write_text(output_text, encoding="utf-8", newline="\n")
    digest = sha256(output_text.encode("utf-8")).hexdigest()
    print(f"lock_path={output_path.relative_to(root).as_posix()}")
    print(f"lock_sha256={digest}")
    print(f"pip_version={EXPECTED_PIP_VERSION}")
    print("torch_version=2.13.0+cpu")
    print("torch_cuda_version=None")


if __name__ == "__main__":
    main()
