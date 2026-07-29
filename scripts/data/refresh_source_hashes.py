"""Refresh platform-independent hashes for Data contract source mappings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
TOOLS_ROOT = DATA_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.io import ensure_within, read_json, sha256_text_file, write_json


CONFIG_TARGETS = (
    (
        DATA_ROOT / "config/workflow/service_contract_mapping.json",
        "contract_sources",
    ),
    (
        DATA_ROOT / "config/handoff/backend_import_crosswalk.json",
        "backend_sources",
    ),
)


def refresh_config(
    config_path: Path,
    source_key: str,
    *,
    check: bool,
) -> list[dict[str, str]]:
    config = read_json(config_path)
    changes: list[dict[str, str]] = []
    for source_name, source in config[source_key].items():
        source_path = ensure_within(REPO_ROOT, REPO_ROOT / source["path"])
        actual_hash = sha256_text_file(source_path)
        if source["sha256"] == actual_hash:
            continue
        changes.append(
            {
                "source": source_name,
                "path": source["path"],
                "before": source["sha256"],
                "after": actual_hash,
            }
        )
        source["sha256"] = actual_hash
    if changes and not check:
        write_json(DATA_ROOT, config_path, config)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh LF-canonical hashes for contract source mappings."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale hashes without changing files",
    )
    args = parser.parse_args()

    changes = [
        change
        for config_path, source_key in CONFIG_TARGETS
        for change in refresh_config(config_path, source_key, check=args.check)
    ]
    if args.check:
        status = "STALE" if changes else "PASS"
    else:
        status = "UPDATED" if changes else "PASS"
    print(
        json.dumps(
            {
                "status": status,
                "changed": len(changes),
                "changes": changes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if args.check and changes else 0


if __name__ == "__main__":
    raise SystemExit(main())
