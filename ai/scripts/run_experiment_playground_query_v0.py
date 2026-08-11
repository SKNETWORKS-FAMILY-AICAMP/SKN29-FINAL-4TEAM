"""A4 Playground v0 단일 Query 재현 CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai.app.experiments.playground import ExperimentPlaygroundEngine, REPOSITORY_ROOT


DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "ai/evaluation/reports/experiments/playground_v0/single_query_result.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="A4 Experiment Playground v0 Single Query")
    parser.add_argument("--product", default="WPUJAC104DWH")
    parser.add_argument("--query", default="정수기 밑이 축축하고 물이 새는 것 같아요.")
    parser.add_argument("--corpus", default="JAC104_IAC425_COMBINED")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-product-filter", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = ExperimentPlaygroundEngine().search(
        product_model_code=args.product,
        query=args.query,
        corpus_variant=args.corpus,
        top_k=args.top_k,
        product_filter=not args.no_product_filter,
    )
    output = args.output.resolve()
    output.relative_to(REPOSITORY_ROOT.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
