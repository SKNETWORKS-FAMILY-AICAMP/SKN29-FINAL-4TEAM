"""외부 Runtime 없이 구조화·Safety 품질 Gate를 실행한다."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ai.evaluation.runners.safety_runner import SafetyEvaluationRunner
from ai.evaluation.runners.structuring_runner import StructuringEvaluationRunner


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def build_deterministic_report(
    *,
    safety_dataset_path: str | Path | None = None,
) -> dict[str, object]:
    """네트워크·DB·Provider를 호출하지 않는 품질 리포트를 조립한다."""

    safety_report = SafetyEvaluationRunner(safety_dataset_path).run()
    structuring_report = StructuringEvaluationRunner().run()
    statuses = [safety_report["status"], structuring_report["status"]]
    runtime_identity = json.loads(
        (REPOSITORY_ROOT / "ai" / "configs" / "runtime_identity.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": (
            "PASS" if all(item == "PASS" for item in statuses) else "FAIL"
        ),
        "evaluation_scope": "DETERMINISTIC_AI_QUALITY_WITHOUT_EXTERNAL_RUNTIME",
        "execution": {
            "git_sha": _git_output("rev-parse", "HEAD"),
            "git_dirty": bool(_git_output("status", "--porcelain")),
            "python_version": platform.python_version(),
            "contract_version": runtime_identity["contract_version"],
            "runtime_profile": os.getenv(
                "AI_RAG_RUNTIME_PROFILE",
                "NOT_CONFIGURED",
            ),
        },
        "external_runtime": {
            "backend": "NOT_RUN",
            "mcp": "NOT_RUN",
            "vector_store": "NOT_RUN",
            "provider": "NOT_RUN",
        },
        "safety_evaluation": safety_report,
        "structuring_evaluation": structuring_report,
        "retrieval_evaluation": {
            "status": "NOT_RUN",
            "reason": (
                "승인된 pgvector Runtime이 이 결정적 평가 범위에 포함되지 않았습니다."
            ),
        },
        "generation_evaluation": {
            "status": "NOT_RUN",
            "reason": "실제 Provider 호출은 별도 승인·Runtime Gate에서 수행합니다.",
        },
        "secret_values_printed": False,
        "raw_customer_text_printed": False,
    }


def _write_report(report: dict[str, object], output_path: str | Path) -> None:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="외부 Runtime 없는 AI Safety·Structuring 품질 Gate"
    )
    parser.add_argument(
        "--safety-dataset",
        help="기본 Candidate 대신 사용할 Safety 평가셋 경로",
    )
    parser.add_argument(
        "--output",
        help="정제된 JSON 리포트 저장 경로. 생략하면 파일을 쓰지 않습니다.",
    )
    args = parser.parse_args()

    report = build_deterministic_report(
        safety_dataset_path=args.safety_dataset,
    )
    if args.output:
        _write_report(report, args.output)
    print(
        json.dumps(
            {
                "overall_status": report["overall_status"],
                "safety_summary": report["safety_evaluation"]["summary"],
                "structuring_summary": report["structuring_evaluation"]["summary"],
                "external_runtime": report["external_runtime"],
            },
            ensure_ascii=False,
        )
    )
    if report["overall_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
