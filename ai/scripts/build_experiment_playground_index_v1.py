"""A4 Playground v0용 BGE-M3 문서 Index 생성 CLI."""

from __future__ import annotations

import argparse
import json

from ai.app.experiments.playground import (
    DEFAULT_INDEX,
    DEFAULT_INDEX_MANIFEST,
    DEFAULT_PROFILE,
    build_playground_index,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="A4 Experiment Playground v0 Index Builder")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--manifest", default=DEFAULT_INDEX_MANIFEST)
    args = parser.parse_args()
    result = build_playground_index(args.profile, args.index, args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
