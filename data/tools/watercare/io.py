"""Safe deterministic I/O helpers for data-only pipeline work."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable


def ensure_within(root: Path, path: Path) -> Path:
    root = root.resolve()
    path = path.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes data root: {path}")
    return path


def data_path(data_root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ValueError(f"absolute paths are not allowed: {relative}")
    return ensure_within(data_root, data_root / relative)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
    return rows


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    ).encode("utf-8")


def write_bytes(data_root: Path, path: Path, content: bytes) -> None:
    path = ensure_within(data_root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(3):
            try:
                os.replace(temp_path, path)
                temp_path = None
                return
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def write_json(data_root: Path, path: Path, value: Any) -> None:
    write_bytes(data_root, path, json_bytes(value))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_lf_bytes(path: Path) -> bytes:
    """Read text source bytes with platform-independent LF line endings."""
    content = path.read_bytes()
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_text_file(path: Path) -> str:
    """Hash text source bytes with platform-independent LF line endings."""
    return sha256_bytes(read_lf_bytes(path))


def replace_tokens(value: Any, tokens: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: replace_tokens(item, tokens) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_tokens(item, tokens) for item in value]
    if isinstance(value, str):
        for key, replacement in tokens.items():
            value = value.replace(f"${{{key}}}", replacement)
    return value
