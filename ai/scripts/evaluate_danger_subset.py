"""Diagnose the danger subset with every Provider and retrieval call forbidden.

This is an offline diagnostic, never the final 45-case Provider evaluation.
Expected labels select the subset only; runtime_request excludes the Oracle.
"""

import argparse
from collections import Counter
import json
import os
from pathlib import Path

from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.evaluation.release_evidence import (
    execution_blockers, execution_provenance, execution_source_changed, write_report,
)
from ai.evaluation.runners.reference_scenario_runner import evaluate_cases, load_reference_catalog


class ForbiddenDependencies:
    def __init__(self):
        self.attempts = Counter()

    def _reject(self, dependency):
        self.attempts[dependency] += 1
        raise AssertionError("OFFLINE_SAFETY_EXTERNAL_CALL_FORBIDDEN")

    def search(self, *args, **kwargs):
        self._reject("retrieval")

    def structure_symptom(self, *args, **kwargs):
        self._reject("symptom_provider")

    def generate_followup_wording(self, *args, **kwargs):
        self._reject("followup_provider")

    def generate_guidance(self, *args, **kwargs):
        self._reject("guidance_provider")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    os.environ.update(
        AI_RAG_RUNTIME_PROFILE="three_model_integration", AI_RETRIEVAL_TRANSPORT="direct",
        AI_HANDOFF_BACKEND_ENABLED="false", OTEL_SDK_DISABLED="true",
        AI_VECTOR_DSN="", OPENAI_API_KEY="",
    )
    source = execution_provenance()
    if source["python_version"] != "3.13.13":
        raise RuntimeError("PYTHON_VERSION_MISMATCH")
    cases, dataset = load_reference_catalog()
    danger_cases = [case for case in cases if case["risk_level"] == "danger"]
    assert len(danger_cases) == 15
    assert set(Counter(case["exact_model_code"] for case in danger_cases).values()) == {5}
    runs = {}
    for runtime in ("single_rag", "multi_agent"):
        dependency = ForbiddenDependencies()
        router = PipelineRouter(
            search_service=dependency, symptom_llm_client=dependency,
            followup_llm_client=dependency, llm_client=dependency, mcp_context_service=None,
        )
        run = evaluate_cases(danger_cases, router, runtime=runtime, provider_events=[])
        run["external_dependency_attempts"] = dict(dependency.attempts)
        if dependency.attempts:
            run["status"] = "CANDIDATE_FAIL"
        runs[runtime] = run
    after = execution_provenance()
    report = {
        "scope": "OFFLINE_DANGER_15_SUBSET_TWO_PIPELINES_ONLY",
        "status": "PASS" if all(run["status"] == "CANDIDATE_PASS" for run in runs.values()) else "FAIL",
        "provenance": source, "end_provenance": after, "dataset": dataset, "subset_count": 15,
        "final_sha_blockers": execution_blockers(source, args.expected_sha),
        "source_changed_during_execution": execution_source_changed(source, after),
        "provider_requests": 0, "database_queries": 0, "rds_writes": 0,
        "model": None, "prompt": None,
        "execution_mode": "DETERMINISTIC_SAFETY_WITH_FORBIDDEN_EXTERNAL_DEPENDENCIES",
        "full_reference_45_provider_evaluation": "NOT_RUN",
        "backend_customer_publication_check": "NOT_RUN", "independent_qa": "NOT_RUN",
        "final_sha_eligible": False, "public_runtime_activation": "HOLD", "runs": runs,
    }
    if report["source_changed_during_execution"]:
        report["status"] = "HOLD"
    write_report(args.output, report)
    print(json.dumps({
        "scope": report["scope"], "status": report["status"],
        "runs": {name: {key: value for key, value in run.items() if key != "case_results"}
                 for name, run in runs.items()},
    }, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
