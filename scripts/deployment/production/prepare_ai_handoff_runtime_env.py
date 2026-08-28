#!/usr/bin/env python3
"""Atomically install fail-closed AI Handoff runtime defaults.

Only non-secret, production-canonical values are written. Existing environment
values and the internal token are never printed.
"""

from __future__ import annotations

import argparse
import os
import stat
import tempfile
from pathlib import Path


CANONICAL_VALUES = {
    "AI_HANDOFF_BACKEND_ENABLED": "false",
    "AI_BACKEND_BASE_URL": "http://backend:8000",
    "AI_HANDOFF_TIMEOUT_SECONDS": "2.0",
}
REQUIRED_SECRET_KEY = "AI_HANDOFF_INTERNAL_TOKEN"


class RuntimeEnvironmentError(RuntimeError):
    """Raised when the protected runtime file is unsafe or ambiguous."""


def _parse_assignments(lines: list[str]) -> dict[str, list[int]]:
    assignments: dict[str, list[int]] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _ = stripped.split("=", 1)
        normalized = key.strip()
        assignments.setdefault(normalized, []).append(index)
    return assignments


def prepare_runtime_env(path: Path, *, require_root: bool = True) -> None:
    if require_root and hasattr(os, "geteuid") and os.geteuid() != 0:
        raise RuntimeEnvironmentError("root privileges are required")
    if not path.is_file() or path.is_symlink():
        raise RuntimeEnvironmentError("AI environment must be one regular file")

    metadata = path.stat()
    if os.name == "posix" and stat.S_IMODE(metadata.st_mode) & 0o077:
        raise RuntimeEnvironmentError(
            "AI environment permissions grant group or other access"
        )

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    assignments = _parse_assignments(lines)
    protected_keys = (*CANONICAL_VALUES, REQUIRED_SECRET_KEY)
    for key in protected_keys:
        if len(assignments.get(key, [])) > 1:
            raise RuntimeEnvironmentError(f"duplicate protected key: {key}")

    secret_indexes = assignments.get(REQUIRED_SECRET_KEY, [])
    if len(secret_indexes) != 1:
        raise RuntimeEnvironmentError("AI Handoff internal token key is missing")
    _, secret_value = lines[secret_indexes[0]].strip().split("=", 1)
    if not secret_value.strip():
        raise RuntimeEnvironmentError("AI Handoff internal token is empty")

    for key, value in CANONICAL_VALUES.items():
        indexes = assignments.get(key, [])
        replacement = f"{key}={value}\n"
        if indexes:
            index = indexes[0]
            ending = "\n" if lines[index].endswith("\n") else ""
            lines[index] = f"{key}={value}{ending}"
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(replacement)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), stat.S_IMODE(metadata.st_mode))
            if hasattr(os, "fchown"):
                os.fchown(temporary.fileno(), metadata.st_uid, metadata.st_gid)
            temporary.writelines(lines)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        if os.name == "posix":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai-env-file", type=Path, required=True)
    args = parser.parse_args()
    prepare_runtime_env(args.ai_env_file)
    print("AI_HANDOFF_RUNTIME_ENV_PREPARED")
    print("ai_handoff_enabled=false")
    print("secret_values_printed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
