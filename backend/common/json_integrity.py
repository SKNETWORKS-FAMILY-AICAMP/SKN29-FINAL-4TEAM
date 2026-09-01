"""Canonical JSON integrity helpers shared by contract consumers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_sha256(payload: Any) -> str:
    """Return the contract SHA-256 for one JSON-compatible value."""

    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = ["canonical_json_sha256"]
