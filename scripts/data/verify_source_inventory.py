"""Verify externally retained source files against the Data inventory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = REPO_ROOT / "data/processed/metadata/source_inventory.csv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF page verification requires pypdf; install the team-approved "
            "runtime dependency or use --skip-page-count."
        ) from exc
    return len(PdfReader(str(path)).pages)


def verify(
    inventory_path: Path,
    external_root: Path,
    *,
    skip_page_count: bool,
) -> dict[str, object]:
    rows = list(
        csv.DictReader(inventory_path.read_text(encoding="utf-8-sig").splitlines())
    )
    checks: list[dict[str, object]] = []
    errors: list[str] = []
    for row in rows:
        if not row["local_path"] or not row["sha256"]:
            checks.append(
                {
                    "data_id": row["data_id"],
                    "status": "EXPECTED_MISSING",
                    "path": row["local_path"],
                }
            )
            continue
        path = (external_root / Path(row["local_path"])).resolve()
        if not path.is_file():
            errors.append(f"missing:{row['data_id']}:{path}")
            checks.append(
                {
                    "data_id": row["data_id"],
                    "status": "MISSING",
                    "path": str(path),
                }
            )
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        expected_size = int(row["file_size_bytes"])
        row_errors: list[str] = []
        if actual_size != expected_size:
            row_errors.append(f"size:{actual_size}!={expected_size}")
        if actual_hash != row["sha256"]:
            row_errors.append(f"sha256:{actual_hash}!={row['sha256']}")
        expected_pages = int(row["page_count"]) if row["page_count"] else None
        actual_pages = None
        if (
            expected_pages is not None
            and path.suffix.lower() == ".pdf"
            and not skip_page_count
        ):
            actual_pages = pdf_page_count(path)
            if actual_pages != expected_pages:
                row_errors.append(f"pages:{actual_pages}!={expected_pages}")
        errors.extend(f"{row['data_id']}:{detail}" for detail in row_errors)
        checks.append(
            {
                "data_id": row["data_id"],
                "status": "PASS" if not row_errors else "FAIL",
                "path": str(path),
                "size_bytes": actual_size,
                "sha256": actual_hash,
                "page_count": actual_pages,
            }
        )
    return {
        "status": "PASS" if not errors else "FAIL",
        "inventory": str(inventory_path),
        "external_root": str(external_root),
        "checks": checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify external source size, SHA-256, and PDF page count."
    )
    parser.add_argument(
        "--external-root",
        type=Path,
        required=True,
        help="Root directory to which inventory local_path values are relative.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
    )
    parser.add_argument(
        "--skip-page-count",
        action="store_true",
        help="Verify only file size and SHA-256.",
    )
    args = parser.parse_args()
    report = verify(
        args.inventory.resolve(),
        args.external_root.resolve(),
        skip_page_count=args.skip_page_count,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
