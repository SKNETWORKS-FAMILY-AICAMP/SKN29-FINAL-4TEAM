#!/usr/bin/env python3
"""Install fail-closed Backend-to-AI Resume runtime values.

The Resume credential is a domain-separated HMAC derived from the existing
protected AI Handoff credential.  The source and derived values are never
printed.  Both protected environment files are validated before either file
is replaced, and both Resume switches always start disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path


SOURCE_TOKEN_KEY = "AI_HANDOFF_INTERNAL_TOKEN"
RESUME_ENABLED_KEY = "AI_HUMAN_REVIEW_RESUME_ENABLED"
RESUME_TOKEN_KEY = "AI_HUMAN_REVIEW_RESUME_TOKEN"
DERIVATION_CONTEXT = b"waterbridge/backend-to-ai/human-review-resume/v1"
MINIMUM_TOKEN_BYTES = 32


class ResumeRuntimeEnvironmentError(RuntimeError):
    """Raised when protected Resume runtime preparation is unsafe."""


@dataclass(frozen=True)
class _EnvironmentDocument:
    path: Path
    metadata: os.stat_result
    lines: list[str]
    assignments: dict[str, list[int]]
    values: dict[str, str]


def _parse_assignments(lines: list[str]) -> tuple[dict[str, list[int]], dict[str, str]]:
    assignments: dict[str, list[int]] = {}
    values: dict[str, str] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        normalized = key.strip()
        assignments.setdefault(normalized, []).append(index)
        if normalized not in values:
            values[normalized] = value.strip()
    return assignments, values


def _load_document(
    path: Path,
    *,
    label: str,
    require_root: bool,
) -> _EnvironmentDocument:
    if require_root and hasattr(os, "geteuid") and os.geteuid() != 0:
        raise ResumeRuntimeEnvironmentError("root privileges are required")
    if not path.is_file() or path.is_symlink():
        raise ResumeRuntimeEnvironmentError(
            f"{label} environment must be one regular file"
        )
    metadata = path.stat()
    if os.name == "posix" and stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ResumeRuntimeEnvironmentError(
            f"{label} environment grants group or other access"
        )
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    assignments, values = _parse_assignments(lines)
    for key in (SOURCE_TOKEN_KEY, RESUME_ENABLED_KEY, RESUME_TOKEN_KEY):
        if len(assignments.get(key, [])) > 1:
            raise ResumeRuntimeEnvironmentError(
                f"duplicate protected key in {label}: {key}"
            )
    source = values.get(SOURCE_TOKEN_KEY, "")
    if len(source.encode("utf-8")) < MINIMUM_TOKEN_BYTES:
        raise ResumeRuntimeEnvironmentError(
            f"{label} Handoff source token is missing or too short"
        )
    return _EnvironmentDocument(path, metadata, lines, assignments, values)


def _render(document: _EnvironmentDocument, updates: dict[str, str]) -> str:
    lines = list(document.lines)
    for key, value in updates.items():
        indexes = document.assignments.get(key, [])
        if indexes:
            index = indexes[0]
            ending = "\n" if lines[index].endswith("\n") else ""
            lines[index] = f"{key}={value}{ending}"
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"{key}={value}\n")
    return "".join(lines)


def _atomic_replace(
    document: _EnvironmentDocument,
    rendered: str,
) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=document.path.parent,
            prefix=f".{document.path.name}.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            requested_mode = stat.S_IMODE(document.metadata.st_mode)
            if hasattr(os, "fchmod"):
                os.fchmod(temporary.fileno(), requested_mode)
            else:
                os.chmod(temporary.name, requested_mode)
            if hasattr(os, "fchown"):
                os.fchown(
                    temporary.fileno(),
                    document.metadata.st_uid,
                    document.metadata.st_gid,
                )
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, document.path)
        temporary_path = None
        if os.name == "posix":
            directory_fd = os.open(document.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def prepare_resume_runtime_envs(
    backend_path: Path,
    ai_path: Path,
    *,
    require_root: bool = True,
) -> None:
    backend = _load_document(
        backend_path,
        label="Backend",
        require_root=require_root,
    )
    ai = _load_document(
        ai_path,
        label="AI",
        require_root=require_root,
    )
    backend_source = backend.values[SOURCE_TOKEN_KEY]
    ai_source = ai.values[SOURCE_TOKEN_KEY]
    if not hmac.compare_digest(backend_source, ai_source):
        raise ResumeRuntimeEnvironmentError(
            "Backend and AI Handoff source tokens do not match"
        )

    resume_token = hmac.new(
        backend_source.encode("utf-8"),
        DERIVATION_CONTEXT,
        hashlib.sha256,
    ).hexdigest()
    updates = {
        RESUME_ENABLED_KEY: "false",
        RESUME_TOKEN_KEY: resume_token,
    }
    rendered_backend = _render(backend, updates)
    rendered_ai = _render(ai, updates)
    original_backend = "".join(backend.lines)

    _atomic_replace(backend, rendered_backend)
    try:
        _atomic_replace(ai, rendered_ai)
    except Exception:
        # The services have not been recreated yet. Restore the first file so
        # deployment cannot leave a mixed credential pair on disk.
        restored_backend = _load_document(
            backend_path,
            label="Backend",
            require_root=require_root,
        )
        _atomic_replace(restored_backend, original_backend)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-env-file", type=Path, required=True)
    parser.add_argument("--ai-env-file", type=Path, required=True)
    args = parser.parse_args()
    prepare_resume_runtime_envs(args.backend_env_file, args.ai_env_file)
    print("AI_RESUME_RUNTIME_ENV_PREPARED")
    print("backend_resume_enabled=false")
    print("ai_resume_enabled=false")
    print("resume_token_source=DOMAIN_SEPARATED_DERIVATION")
    print("secret_values_printed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
