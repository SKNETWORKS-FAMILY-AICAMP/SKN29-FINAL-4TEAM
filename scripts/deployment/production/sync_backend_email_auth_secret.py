"""Safely sync the approved NONPROD email delivery gate without logging secrets."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SECRET_ID_PATTERN = re.compile(r"^waterbridge/[A-Za-z0-9/_+=.@-]{1,480}$")
REGION_PATTERN = re.compile(r"^[a-z]{2}-[a-z]+-[0-9]+$")
HMAC_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ENV_DEFINITION_PATTERN = re.compile(
    r"^[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*="
)

EXISTING_EMAIL_AUTH_KEYS = frozenset(
    {
        "CONTRACT_EMAIL_ENCRYPTION_KEY",
        "CONTRACT_EMAIL_HMAC_KEY",
        "CONTRACT_EMAIL_KEY_VERSION",
        "DJANGO_DEFAULT_FROM_EMAIL",
        "DJANGO_EMAIL_BACKEND",
        "DJANGO_EMAIL_HOST",
        "DJANGO_EMAIL_HOST_PASSWORD",
        "DJANGO_EMAIL_HOST_USER",
        "P1_AUTH_EMAIL_REDIRECT_TO",
        "P1_AUTH_HMAC_SECRET",
        "P1_AUTH_OTP_ENCRYPTION_KEY",
    }
)
ALLOWLIST_KEY = "P1_AUTH_APPROVED_TEST_RECIPIENT_ALLOWLIST_HMACS"
SECRET_KEYS = EXISTING_EMAIL_AUTH_KEYS | {ALLOWLIST_KEY}
RUNTIME_ENV_KEY = "P1_AUTH_RUNTIME_ENVIRONMENT"
DELIVERY_ENABLED_KEY = (
    "P1_AUTH_APPROVED_TEST_RECIPIENT_DELIVERY_ENABLED"
)
TARGET_ENV_KEYS = (
    RUNTIME_ENV_KEY,
    DELIVERY_ENABLED_KEY,
    ALLOWLIST_KEY,
)


class SafeSyncError(RuntimeError):
    """Expected validation failure with a non-sensitive reason code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_secret_id(value: str) -> str:
    if not SECRET_ID_PATTERN.fullmatch(value):
        raise SafeSyncError("SECRET_ID_INVALID")
    return value


def validate_region(value: str) -> str:
    if not REGION_PATTERN.fullmatch(value):
        raise SafeSyncError("AWS_REGION_INVALID")
    return value


def decode_json_documents(raw: str) -> tuple[dict[str, str], int]:
    """Decode one or two concatenated JSON objects without echoing input."""

    decoder = json.JSONDecoder()
    offset = 0
    documents: list[dict[str, Any]] = []
    while True:
        while offset < len(raw) and raw[offset].isspace():
            offset += 1
        if offset >= len(raw):
            break
        try:
            document, offset = decoder.raw_decode(raw, offset)
        except json.JSONDecodeError as exc:
            raise SafeSyncError("SECRET_JSON_INVALID") from exc
        if not isinstance(document, dict):
            raise SafeSyncError("SECRET_DOCUMENT_NOT_OBJECT")
        documents.append(document)
        if len(documents) > 2:
            raise SafeSyncError("SECRET_DOCUMENT_COUNT_INVALID")

    if not documents:
        raise SafeSyncError("SECRET_DOCUMENT_COUNT_INVALID")

    merged: dict[str, str] = {}
    for document in documents:
        if document == {"": ""}:
            continue
        for key, value in document.items():
            if key not in SECRET_KEYS:
                raise SafeSyncError("SECRET_KEY_UNKNOWN")
            if key in merged:
                raise SafeSyncError("SECRET_KEY_DUPLICATED")
            if not isinstance(value, str) or not value:
                raise SafeSyncError("SECRET_VALUE_EMPTY_OR_INVALID")
            if "\x00" in value or "\n" in value or "\r" in value:
                raise SafeSyncError("SECRET_VALUE_MULTILINE_FORBIDDEN")
            merged[key] = value

    missing = SECRET_KEYS.difference(merged)
    if missing:
        raise SafeSyncError("SECRET_REQUIRED_KEY_MISSING")
    return merged, len(documents)


def canonicalize_allowlist(value: str) -> str:
    hashes = [item.strip() for item in value.split(",")]
    if len(hashes) != 6 or any(not item for item in hashes):
        raise SafeSyncError("ALLOWLIST_COUNT_INVALID")
    if any(not HMAC_PATTERN.fullmatch(item) for item in hashes):
        raise SafeSyncError("ALLOWLIST_FORMAT_INVALID")
    if len(set(hashes)) != len(hashes):
        raise SafeSyncError("ALLOWLIST_DUPLICATED")
    return ",".join(hashes)


def fetch_secret_string(*, secret_id: str, region: str) -> str:
    completed = subprocess.run(
        [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            secret_id,
            "--region",
            region,
            "--query",
            "SecretString",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise SafeSyncError("SECRET_FETCH_FAILED")
    try:
        secret_string = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SafeSyncError("SECRET_RESPONSE_INVALID") from exc
    if not isinstance(secret_string, str) or not secret_string:
        raise SafeSyncError("SECRET_STRING_MISSING")
    return secret_string


def _validate_env_file(path: Path, *, enforce_root: bool) -> os.stat_result:
    if not path.is_absolute():
        raise SafeSyncError("BACKEND_ENV_PATH_NOT_ABSOLUTE")
    try:
        resolved = path.resolve(strict=True)
        if enforce_root:
            resolved.relative_to(Path("/etc/waterbridge"))
        details = path.lstat()
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise SafeSyncError("BACKEND_ENV_PATH_INVALID") from exc
    if resolved != path or stat.S_ISLNK(details.st_mode):
        raise SafeSyncError("BACKEND_ENV_SYMLINK_FORBIDDEN")
    if not stat.S_ISREG(details.st_mode):
        raise SafeSyncError("BACKEND_ENV_NOT_REGULAR_FILE")
    if enforce_root:
        if stat.S_IMODE(details.st_mode) & 0o077:
            raise SafeSyncError("BACKEND_ENV_PERMISSION_INVALID")
        if details.st_uid != 0 or details.st_gid != 0:
            raise SafeSyncError("BACKEND_ENV_OWNER_INVALID")
    return details


def update_backend_env(
    path: Path,
    *,
    canonical_allowlist: str,
    enforce_root: bool = True,
) -> None:
    details = _validate_env_file(path, enforce_root=enforce_root)
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SafeSyncError("BACKEND_ENV_READ_FAILED") from exc

    definitions: dict[str, int] = {}
    lines = original.splitlines()
    for index, line in enumerate(lines):
        matched = ENV_DEFINITION_PATTERN.match(line)
        if matched is None:
            continue
        key = matched.group(1)
        if key in definitions:
            if key in SECRET_KEYS or key in TARGET_ENV_KEYS:
                raise SafeSyncError("BACKEND_ENV_KEY_DUPLICATED")
            continue
        definitions[key] = index

    if not EXISTING_EMAIL_AUTH_KEYS.issubset(definitions):
        raise SafeSyncError("BACKEND_ENV_EXISTING_KEY_MISSING")

    replacements = {
        RUNTIME_ENV_KEY: "AWS_NONPROD",
        DELIVERY_ENABLED_KEY: "true",
        ALLOWLIST_KEY: canonical_allowlist,
    }
    for key in TARGET_ENV_KEYS:
        line = f"{key}={replacements[key]}"
        if key in definitions:
            lines[definitions[key]] = line
        else:
            lines.append(line)

    updated = "\n".join(lines) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=".backend.env.",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(updated)
            temporary.flush()
            os.fsync(temporary.fileno())
            if enforce_root:
                os.fchmod(temporary.fileno(), 0o600)
                os.fchown(temporary.fileno(), 0, 0)
        os.replace(temporary_path, path)
        if enforce_root:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OSError as exc:
        raise SafeSyncError("BACKEND_ENV_ATOMIC_WRITE_FAILED") from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--backend-env-file", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    stage = "INPUT"
    try:
        args = parse_args()
        secret_id = validate_secret_id(args.secret_id)
        region = validate_region(args.region)
        stage = "SECRET_FETCH"
        secret_string = fetch_secret_string(secret_id=secret_id, region=region)
        stage = "SECRET_PARSE"
        values, document_count = decode_json_documents(secret_string)
        canonical_allowlist = canonicalize_allowlist(values[ALLOWLIST_KEY])
        stage = "BACKEND_ENV_UPDATE"
        update_backend_env(
            args.backend_env_file,
            canonical_allowlist=canonical_allowlist,
        )
    except SafeSyncError as exc:
        print(
            "BACKEND_EMAIL_AUTH_SECRET_SYNC_FAILED "
            f"stage={stage} reason={exc.reason}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            "BACKEND_EMAIL_AUTH_SECRET_SYNC_FAILED "
            f"stage={stage} error_type={type(exc).__name__}",
            file=sys.stderr,
        )
        return 1

    print("BACKEND_EMAIL_AUTH_SECRET_SYNC_PASS")
    print(f"secret_document_count={document_count}")
    print("approved_hmac_count=6")
    print("backend_env=protected")
    print("secret_values_printed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
