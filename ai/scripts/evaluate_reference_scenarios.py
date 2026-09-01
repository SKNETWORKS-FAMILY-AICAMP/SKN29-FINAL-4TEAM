"""Prepare or execute the 45-case candidate evaluation without activating Runtime."""

import argparse
import json
import os
from pathlib import Path

from ai.app.integrations.llm.llm_client import OpenAIResponsesLLMClient
from ai.app.integrations.llm.natural_language_client import (
    OpenAIResponsesFollowUpWordingClient, OpenAIResponsesSymptomStructuringClient,
)
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval.runtime_profile import resolve_rag_runtime_profile
from ai.app.retrieval.verification.index_readiness import validate_readonly_index
from ai.evaluation.release_evidence import execution_blockers, execution_provenance, execution_source_changed, write_report
from ai.evaluation.readonly_environment import read_database_versions
from ai.evaluation.runners.reference_scenario_runner import AuditedProvider, evaluate_cases, load_reference_catalog
from ai.scripts.verify_jac104_v2_recovery import _read_index_rows
from ai.scripts.verify_three_model_readonly_runtime import EXPECTED_TABLE, _load_identity_and_manifest


def main(*, output: Path, expected_sha: str | None, execute: bool = False,
         runtime: str = "single_rag") -> int:
    provenance = execution_provenance()
    blockers = execution_blockers(provenance, expected_sha)
    report = {
        "status": "HOLD", "provenance": provenance, "final_sha_blockers": blockers,
        "executed_case_count": 0, "runtime": runtime,
        "ledger_contract": "V1_APPROVED_CONTRACT_IMPLEMENTED_ACTIVATION_HOLD",
        "independent_qa": "NOT_RUN", "merge_approval": "PENDING_PM",
        "public_runtime_activation": "HOLD", "backend_writes": 0,
        "backend_customer_publication_check": "NOT_RUN",
    }
    stage = "DATASET_PREFLIGHT"
    try:
        cases, identity = load_reference_catalog()
        report.update(identity)
        if not execute:
            report["reason_code"] = "EXECUTION_NOT_REQUESTED"
        elif blockers:
            report["reason_code"] = "FINAL_EXECUTION_PROVENANCE_NOT_READY"
        else:
            stage = "READONLY_INDEX_IDENTITY"
            profile = resolve_rag_runtime_profile()
            if profile.name != "three_model_integration" or os.getenv("AI_VECTOR_TABLE_NAME") != EXPECTED_TABLE:
                raise ValueError("Integration profile and approved readonly View required")
            if os.getenv("AI_RETRIEVAL_TRANSPORT", "direct").strip().lower() != "direct":
                raise ValueError("This runner verifies direct transport only")
            identity, manifest = _load_identity_and_manifest(profile)
            if os.getenv("AI_EMBEDDING_REVISION") != manifest.model_revision:
                raise ValueError("Pinned embedding revision required")
            rows = _read_index_rows(os.environ["AI_VECTOR_DSN"], maximum_rows=manifest.chunk_count + 1)
            report["index_identity"] = validate_readonly_index(profile, manifest, identity, rows)
            report["database_versions"] = read_database_versions(os.environ["AI_VECTOR_DSN"])
            stage = "PROVIDER_CONFIGURATION_AND_WARMUP"
            events = []
            router = PipelineRouter(
                symptom_llm_client=AuditedProvider(OpenAIResponsesSymptomStructuringClient.from_environment(), "symptom_structuring", events),
                followup_llm_client=AuditedProvider(OpenAIResponsesFollowUpWordingClient.from_environment(), "followup_question", events),
                llm_client=AuditedProvider(OpenAIResponsesLLMClient.from_environment(), "customer_guidance", events),
                mcp_context_service=None,
            )
            if router.search_service is None:
                raise ValueError("Configured readonly search service required")
            router.search_service.embedding_client.warmup()
            stage = "EVALUATION"
            report.update(evaluate_cases(cases, router, runtime=runtime, provider_events=events))
            after = execution_provenance()
            report["end_provenance"] = after
            report["end_final_sha_blockers"] = execution_blockers(after, expected_sha)
            if report["end_final_sha_blockers"] or execution_source_changed(provenance, after):
                report.update(status="HOLD", reason_code="EXECUTION_SOURCE_CHANGED")
    except Exception as exc:
        report.update(status="HOLD", reason_code="REFERENCE_EVALUATION_REQUIREMENTS_NOT_MET",
                      failure_stage=stage, error_type=type(exc).__name__)
    write_report(output, report)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"case_results", "provenance", "end_provenance"}}, ensure_ascii=False))
    return 0 if report["status"] == "CANDIDATE_PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--runtime", choices=("single_rag", "multi_agent"), default="single_rag")
    args = parser.parse_args()
    raise SystemExit(main(output=args.output, expected_sha=args.expected_sha, execute=args.execute, runtime=args.runtime))
