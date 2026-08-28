#!/usr/bin/env python3
"""Install the fail-closed Canary Nginx include in one exact server block."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path


INCLUDE_DIRECTIVE = "include /etc/nginx/waterbridge-server.d/*.conf;"
SOURCE_MARKER = re.compile(r"^# configuration file (.+):$")


class NginxPreparationError(RuntimeError):
    """Raised when the active Nginx configuration is unsafe or ambiguous."""


def _server_blocks(lines: list[str]) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    start: int | None = None
    depth = 0
    collected: list[str] = []
    for index, raw_line in enumerate(lines):
        line = raw_line.split("#", 1)[0]
        if start is None:
            if re.match(r"^\s*server\s*\{", line):
                start = index
                collected = [line]
                depth = line.count("{") - line.count("}")
            continue
        collected.append(line)
        depth += line.count("{") - line.count("}")
        if depth == 0:
            blocks.append((start, index, "\n".join(collected)))
            start = None
            collected = []
    if start is not None:
        raise NginxPreparationError("unterminated Nginx server block")
    return blocks


def _dump_sources(dump: str) -> dict[Path, list[str]]:
    sources: dict[Path, list[str]] = {}
    current: Path | None = None
    for line in dump.splitlines(keepends=True):
        marker = SOURCE_MARKER.match(line.rstrip("\r\n"))
        if marker:
            current = Path(marker.group(1))
            if current in sources:
                raise NginxPreparationError("duplicate Nginx source marker")
            sources[current] = []
            continue
        if current is not None:
            sources[current].append(line)
    if not sources:
        raise NginxPreparationError("Nginx source markers are unavailable")
    return sources


def _atomic_write(path: Path, content: bytes, metadata: os.stat_result) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), stat.S_IMODE(metadata.st_mode))
            if hasattr(os, "fchown"):
                os.fchown(temporary.fileno(), metadata.st_uid, metadata.st_gid)
            temporary.write(content)
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


def _run_checked(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    return runner(command, check=True, capture_output=True, text=True)


def prepare_nginx(
    *,
    domain: str,
    upstream: str,
    dropin_dir: Path,
    backup_dir: Path,
    allowed_root: Path = Path("/etc/nginx"),
    require_root: bool = True,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    if require_root and hasattr(os, "geteuid") and os.geteuid() != 0:
        raise NginxPreparationError("root privileges are required")
    if domain != "waterbridge.site" or upstream != "127.0.0.1:18080":
        raise NginxPreparationError("non-canonical Canary Nginx target")

    dump = _run_checked(runner, ["nginx", "-T"]).stdout
    sources = _dump_sources(dump)
    domain_pattern = re.compile(
        rf"server_name\s+[^;]*\b{re.escape(domain)}\b[^;]*;"
    )
    candidates: list[Path] = []
    for source, lines in sources.items():
        for _, _, block in _server_blocks(lines):
            if domain_pattern.search(block) and upstream in block:
                candidates.append(source)
    if len(candidates) != 1:
        raise NginxPreparationError("expected exactly one Canary server block")

    allowed = allowed_root.resolve(strict=True)
    if (
        dropin_dir.name != "waterbridge-server.d"
        or dropin_dir.parent.resolve(strict=True) != allowed
    ):
        raise NginxPreparationError("non-canonical Canary drop-in directory")
    target = candidates[0].resolve(strict=True)
    try:
        target.relative_to(allowed)
    except ValueError as exc:
        raise NginxPreparationError("Nginx target is outside the allowed root") from exc
    if not target.is_file() or target.is_symlink():
        raise NginxPreparationError("Nginx target must resolve to one regular file")

    original = target.read_bytes()
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NginxPreparationError("Nginx target is not UTF-8") from exc
    lines = text.splitlines(keepends=True)
    blocks = [
        (start, end, block)
        for start, end, block in _server_blocks(lines)
        if domain_pattern.search(block) and upstream in block
    ]
    if len(blocks) != 1:
        raise NginxPreparationError("active dump and source server blocks differ")
    if INCLUDE_DIRECTIVE in text and INCLUDE_DIRECTIVE not in blocks[0][2]:
        raise NginxPreparationError("Canary include exists outside the target block")

    dropin_dir.mkdir(parents=True, exist_ok=True)
    if dropin_dir.is_symlink() or dropin_dir.resolve(strict=True) != (
        allowed / "waterbridge-server.d"
    ):
        raise NginxPreparationError("Canary drop-in directory is unsafe")
    dropin_dir.chmod(0o755)
    if INCLUDE_DIRECTIVE in blocks[0][2]:
        _run_checked(runner, ["nginx", "-t"])
        return "already_configured"

    metadata = target.stat()
    checksum = hashlib.sha256(original).hexdigest()
    backup_dir.mkdir(parents=True, exist_ok=True)
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        raise NginxPreparationError("Nginx backup directory is unsafe")
    backup_dir.chmod(0o700)
    backup = backup_dir / f"{checksum}.conf"
    if backup.exists():
        if backup.is_symlink() or backup.read_bytes() != original:
            raise NginxPreparationError("Nginx backup checksum collision")
    else:
        with backup.open("xb") as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        backup.chmod(0o600)

    _, end, _ = blocks[0]
    ending = "\r\n" if "\r\n" in text else "\n"
    updated_lines = list(lines)
    updated_lines.insert(end, f"    {INCLUDE_DIRECTIVE}{ending}")
    updated = "".join(updated_lines).encode("utf-8")
    _atomic_write(target, updated, metadata)
    try:
        _run_checked(runner, ["nginx", "-t"])
        _run_checked(runner, ["systemctl", "reload", "nginx"])
    except Exception as exc:
        _atomic_write(target, original, metadata)
        try:
            _run_checked(runner, ["nginx", "-t"])
            _run_checked(runner, ["systemctl", "reload", "nginx"])
        except Exception as restore_exc:
            raise NginxPreparationError(
                "Nginx preparation and restoration both failed"
            ) from restore_exc
        raise NginxPreparationError("Nginx preparation failed and was restored") from exc
    return checksum


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dropin-dir", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    result = prepare_nginx(
        domain="waterbridge.site",
        upstream="127.0.0.1:18080",
        dropin_dir=args.dropin_dir,
        backup_dir=args.backup_dir,
    )
    print("AI_HANDOFF_NGINX_PREPARED")
    print("nginx_backup_sha256=" + result)
    print("secret_values_printed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
