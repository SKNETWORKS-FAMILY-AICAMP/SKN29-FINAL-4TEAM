#!/usr/bin/env python3
"""Classify whether a GitHub event needs the heavy Backend CI gate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ZERO_SHA = "0" * 40

RELEVANT_PREFIXES = (
    "backend/",
    "contracts/",
    "scripts/development/",
)
RELEVANT_FILES = {
    ".github/workflows/backend-ci.yml",
    "scripts/testing/classify_backend_ci_changes.py",
    "tests/deployment/test_backend_ci_workflow.py",
}

BACKEND_TEST_SHARDS = {
    "domain": {
        "preflight": True,
        "targets": (
            "tests/unit/accounts",
            "tests/unit/care",
            "tests/unit/consultations",
            "tests/unit/inquiries",
            "tests/unit/products",
            "tests/unit/questionnaires",
            "tests/unit/subscriptions",
            "tests/unit/visits",
            "tests/unit/workflow",
        ),
    },
    "platform": {
        "preflight": False,
        "targets": (
            "tests/unit/ai_integration",
            "tests/unit/audit",
            "tests/unit/common",
            "tests/unit/common_codes",
            "tests/unit/database",
            "tests/unit/evidence",
            "tests/unit/settings",
        ),
    },
    "api-integration": {
        "preflight": False,
        "targets": (
            "tests/api",
            "tests/integration",
        ),
    },
}


def normalized_path(value: str) -> str:
    normalized = PurePosixPath(value.replace("\\", "/")).as_posix()
    return normalized[2:] if normalized.startswith("./") else normalized


def is_backend_relevant(path: str) -> bool:
    normalized = normalized_path(path)
    return normalized in RELEVANT_FILES or normalized.startswith(RELEVANT_PREFIXES)


def needs_heavy_gate(paths: list[str]) -> bool:
    return any(is_backend_relevant(path) for path in paths)


def shard_matrix() -> dict[str, list[dict[str, str | bool]]]:
    return {
        "include": [
            {
                "name": name,
                "preflight": definition["preflight"],
                "targets": " ".join(definition["targets"]),
            }
            for name, definition in BACKEND_TEST_SHARDS.items()
        ]
    }


def _git_lines(*arguments: str) -> list[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_paths(
    *, event_name: str, before_sha: str, base_sha: str, head_sha: str
) -> list[str]:
    if event_name == "pull_request":
        if not base_sha or not head_sha:
            raise ValueError("pull_request requires base and head SHA values")
        return _git_lines("diff", "--name-only", f"{base_sha}...{head_sha}")

    if event_name == "push":
        if not head_sha:
            raise ValueError("push requires a head SHA value")
        if not before_sha or before_sha == ZERO_SHA:
            return _git_lines(
                "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", head_sha
            )
        return _git_lines("diff", "--name-only", f"{before_sha}..{head_sha}")

    raise ValueError(f"unsupported event for path classification: {event_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", default="")
    parser.add_argument("--before-sha", default="")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--force-full", action="store_true")
    parser.add_argument("--print-matrix", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_matrix:
        print(json.dumps(shard_matrix(), separators=(",", ":")))
        return 0

    if args.force_full or args.event_name == "workflow_dispatch":
        print("true")
        return 0

    try:
        paths = changed_paths(
            event_name=args.event_name,
            before_sha=args.before_sha,
            base_sha=args.base_sha,
            head_sha=args.head_sha,
        )
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"Backend CI path classification failed: {exc}", file=sys.stderr)
        return 2

    relevant = sorted(path for path in paths if is_backend_relevant(path))
    if relevant:
        print("Backend CI relevant paths:", file=sys.stderr)
        for path in relevant:
            print(f"- {path}", file=sys.stderr)
    else:
        print("No Backend CI relevant paths changed.", file=sys.stderr)
    print("true" if relevant else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
