"""Cross-platform file hashing rules for reproducible AI experiments."""

from __future__ import annotations

import hashlib
from pathlib import Path


CANONICAL_TEXT_SUFFIXES = frozenset({".json", ".jsonl", ".yaml", ".yml"})


def canonical_file_bytes(path: Path) -> bytes:
    """Return canonical bytes for an experiment input or artifact.

    Git checkouts may expose text files with CRLF on Windows. Experiment
    manifests hash JSON/YAML content with LF line endings so the same commit
    has the same identity on every supported OS. Binary files remain exact.
    """

    payload = path.read_bytes()
    if path.suffix.lower() in CANONICAL_TEXT_SUFFIXES:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return payload


def file_sha256(path: Path) -> str:
    """Return the uppercase SHA-256 of a canonical experiment file."""

    return hashlib.sha256(canonical_file_bytes(path)).hexdigest().upper()
