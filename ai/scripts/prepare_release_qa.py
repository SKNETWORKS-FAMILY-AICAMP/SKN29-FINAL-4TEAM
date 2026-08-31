"""Validate release evaluation inputs without a DB, Provider or deployment."""

import argparse
from collections import Counter
import json
from pathlib import Path

from ai.app.retrieval.indexing import load_rag_handoff_profile
from ai.app.retrieval.runtime_profile import resolve_rag_runtime_profile
from ai.evaluation.release_evidence import execution_blockers, execution_provenance, write_report
from ai.evaluation.runners.reference_scenario_runner import load_reference_catalog
from ai.evaluation.three_model_rag import load_three_model_evaluation_inputs
from ai.scripts.verify_three_model_readonly_runtime import _load_identity_and_manifest


def prepare(expected_sha: str) -> dict:
    source = execution_provenance()
    blockers = execution_blockers(source, expected_sha)
    report = {
        "status": "HOLD", "scope": "OFFLINE_QA_PREPARATION_ONLY",
        "provenance": source, "final_sha_blockers": blockers,
        "final_sha_eligible": False, "database_queries": 0,
        "provider_requests": 0, "executed_45_cases": 0, "executed_50_cases": 0,
        "public_runtime_activation": "HOLD", "rds_writes": 0,
        "independent_qa": "NOT_RUN", "ledger_implementation": "HOLD_PENDING_ADDITIONAL_CONTRACT",
    }
    stage = "REFERENCE_45_INPUTS"
    try:
        reference_cases, reference_identity = load_reference_catalog()
        report["reference_45"] = {**reference_identity, "declared_case_count": len(reference_cases)}
        stage = "READONLY_50_INPUTS"
        cases, groups, chunks = load_three_model_evaluation_inputs(load_rag_handoff_profile("rag-expansion"))
        case_types = dict(Counter(case["case_type"] for case in cases))
        model_counts = dict(Counter(chunk.model_code for chunk in chunks))
        if len(reference_cases) != 45 or case_types != {"POSITIVE": 43, "NEGATIVE": 7}:
            raise ValueError("EVALUATION_COUNTS_MISMATCH")
        if len(groups) != 43 or model_counts != {"WPUJAC104DWH": 15, "WPUIAC425SNW": 19, "WPUIAC606SNW": 19}:
            raise ValueError("EVIDENCE_COUNTS_MISMATCH")
        stage = "CANONICAL_INDEX_IDENTITY"
        identity, manifest = _load_identity_and_manifest(resolve_rag_runtime_profile("three_model_integration"))
        if {chunk.chunk_id for chunk in chunks} != {row["chunk_id"] for row in identity["chunks"]}:
            raise ValueError("CANONICAL_CHILD_SET_MISMATCH")
        report["readonly_50"] = {
            "declared_case_count": len(cases), "case_types": case_types,
            "evidence_group_count": len(groups), "child_count": len(chunks),
            "model_counts": model_counts, "index_version": manifest.index_version,
            "chunk_set_sha256": manifest.chunk_set_sha256,
            "embedding_model": manifest.model_name, "embedding_revision": manifest.model_revision,
            "runtime_profile": "three_model_integration", "transport": "direct",
            "view": "backend_ai_rag_chunks_v1",
        }
        report["status"] = "QA_INPUTS_READY"
        report["clean_source_ready_for_candidate_run"] = not blockers
    except Exception as exc:
        report.update(failure_stage=stage, error_type=type(exc).__name__)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.expected_sha)
    write_report(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "provenance"}, ensure_ascii=False))
    return 0 if report["status"] == "QA_INPUTS_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
