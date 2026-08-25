"""Privacy-safe display projections shared by Backend read services."""

from __future__ import annotations

import re


_SYNTHETIC_SUFFIX = re.compile(r"\s*(\([^)]*합성[^)]*\))\s*$")


def mask_person_name(value: str) -> str:
    """Keep only the first and last character of a display name."""

    normalized = str(value or "").strip()
    if not normalized:
        return ""

    suffix_match = _SYNTHETIC_SUFFIX.search(normalized)
    suffix = ""
    if suffix_match is not None:
        suffix = f" {suffix_match.group(1)}"
        normalized = normalized[: suffix_match.start()].strip()

    if not normalized:
        return suffix.strip()
    if len(normalized) == 1:
        masked = "*"
    elif len(normalized) == 2:
        masked = f"{normalized[0]}*"
    else:
        masked = (
            f"{normalized[0]}"
            f"{'*' * (len(normalized) - 2)}"
            f"{normalized[-1]}"
        )
    return f"{masked}{suffix}"


def mask_phone(value: str) -> str:
    """Expose only a Korean phone prefix and the final four digits."""

    digits = "".join(
        character for character in str(value or "") if character.isdigit()
    )
    if not digits:
        return ""
    if len(digits) == 11:
        return f"{digits[:3]}-****-{digits[-4:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-***-{digits[-4:]}"
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"
