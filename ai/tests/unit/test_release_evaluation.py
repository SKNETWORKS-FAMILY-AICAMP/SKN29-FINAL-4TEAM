"""Release evaluation fails closed and cannot feed the Oracle into Runtime."""

import json
from hashlib import sha1
import subprocess
from types import SimpleNamespace

import pytest

from ai.app.integrations.llm import LLMUsage
from ai.app.schemas import StructuredSymptom, SymptomAnalysisResult
from ai.app.structuring.llm_contracts import SymptomStructuringLLMResponse, SymptomStructuringRequest
from ai.app.validation.routing import ResponseRoutingDisposition
from ai.evaluation import release_evidence
from ai.evaluation.release_evidence import execution_blockers, execution_source_changed, json_sha256, write_report
from ai.evaluation.runners import reference_scenario_runner as runner
from ai.scripts import evaluate_reference_scenarios as script
from ai.scripts import prepare_release_qa
from ai.scripts import verify_three_model_readonly_runtime as readonly_script


def test_reference_catalog_is_frozen_and_excluded_from_runtime():
    cases, identity = runner.load_reference_catalog()
    assert len(cases) == 45 and len(identity["dataset_sha256"]) == 64
    assert identity["curation_status"] == "CANDIDATE"
    for directory in (runner.REPOSITORY_ROOT / "ai/app", runner.REPOSITORY_ROOT / "ai/prompts"):
        for path in directory.rglob("*"):
            if path.suffix in {".py", ".txt", ".yaml"}:
                content = path.read_text(encoding="utf-8")
                assert "three_model_reference_scenarios" not in content
                assert "REF-JAC104-" not in content and "REF-IAC425-" not in content and "REF-IAC606-" not in content


def test_oracle_annotations_cannot_change_runtime_request():
    first = {"customer_utterance": "현재 고객 입력", "exact_model_code": "WPUJAC104DWH"}
    other = {**first, "risk_level": "danger", "context_facts": ["ORACLE_SENTINEL"],
             "topic_code": "ORACLE_TOPIC", "evidence_group_ids": ["ORACLE_EVIDENCE"],
             "expected_reason": "ORACLE_REASON", "response_outline": ["ORACLE_ANSWER"]}
    a, b = runner.runtime_request(first), runner.runtime_request(other)
    for field in ("inquiry_id", "correlation_id", "ai_request_id"):
        a.pop(field)
        b.pop(field)
    assert a == b
    assert "ORACLE" not in json.dumps(b)
    assert b["previous_answers"] == [] and b["selected_symptoms"] == []


def test_audited_provider_supports_dataclass_request_and_hashes_without_raw_text():
    class Client:
        model_name = "test-model"
        prompt_version = "symptom_structuring/v1"
        def structure_symptom(self, request, **kwargs):
            return SymptomStructuringLLMResponse(
                output=StructuredSymptom(symptom_type="온도 이상"), model_name=self.model_name,
                prompt_version=self.prompt_version, usage=LLMUsage(), latency_ms=1,
            )
    events = []
    provider = runner.AuditedProvider(Client(), "symptom_structuring", events)
    result = provider.structure_symptom(SymptomStructuringRequest(
        raw_symptom="PRIVATE_RAW_SENTINEL", selected_symptoms=(), previous_answers=(),
    ), timeout_seconds=1)
    assert result.output.symptom_type == "온도 이상"
    assert events[0]["status"] == "RETURNED" and len(events[0]["output_sha256"]) == 64
    assert "PRIVATE_RAW_SENTINEL" not in json.dumps(events)


def test_inappropriate_auto_guidance_is_measured_against_expected_risk():
    data = json.loads((runner.REPOSITORY_ROOT / "contracts/ai/examples/symptom-analysis/general-guidance.json").read_text(encoding="utf-8"))
    response = SymptomAnalysisResult.model_validate(data["response"])
    class Router:
        def run_pipeline(self, **kwargs):
            assert "risk_level" not in kwargs and "expected_route" not in kwargs
            return SimpleNamespace(
                to_analysis_result=lambda: response,
                routing_disposition=ResponseRoutingDisposition.AUTO_GUIDANCE,
                context=SimpleNamespace(evidence_selection_reasons=[]),
            )
    case = {"scenario_id": "synthetic-evaluator-test", "customer_utterance": "고객 입력",
            "exact_model_code": "WPUJAC104DWH", "risk_level": "caution",
            "expected_requires_consultation": False, "expected_route": "HUMAN_REVIEW",
            "expected_publication_gate": "HUMAN_APPROVAL_REQUIRED", "expected_usage_guidance_status": "PARTIAL_STOP"}
    report = runner.evaluate_cases([case], Router(), runtime="single_rag", provider_events=[])
    assert report["status"] == "CANDIDATE_FAIL"
    assert report["caution_auto_route_count"] == report["inappropriate_auto_guidance_count"] == 1
    assert report["backend_customer_publication_check"] == "NOT_RUN"


def test_report_checksum_and_clean_sha_requirements(tmp_path):
    report = {"status": "HOLD", "executed_case_count": 0}
    output = tmp_path / "result.json"
    write_report(output, report)
    assert json.loads(output.read_text())["artifact_payload_sha256"] == json_sha256(report)
    assert execution_blockers({"python_version": "3.13.13", "commit_sha": "a" * 40, "dirty": False, "git_metadata_verified": True}, "a" * 40) == []
    assert "CLEAN_EXECUTION_TREE_REQUIRED" in execution_blockers({"python_version": "3.13.13", "commit_sha": "a" * 40, "dirty": True}, "a" * 40)


def test_reference_eval_db_failure_never_runs_provider_or_leaks_driver_text(monkeypatch, tmp_path):
    monkeypatch.setattr(script, "execution_provenance", lambda: {"python_version": "3.13.13", "commit_sha": "a" * 40, "dirty": False, "git_metadata_verified": True})
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "three_model_integration")
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", "backend_ai_rag_chunks_v1")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", "5617a9f61b028005a4858fdac845db406aefb181")
    monkeypatch.setenv("AI_VECTOR_DSN", "PRIVATE_DSN_SENTINEL")
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_DRIVER_SENTINEL")
    def provider_forbidden(*args, **kwargs):
        raise AssertionError("Provider cannot run before readonly identity is verified")
    monkeypatch.setattr(script, "_read_index_rows", fail)
    monkeypatch.setattr(script, "PipelineRouter", provider_forbidden)
    output = tmp_path / "reference.json"
    assert script.main(output=output, expected_sha="a" * 40, execute=True) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "HOLD" and report["executed_case_count"] == 0
    assert report["failure_stage"] == "READONLY_INDEX_IDENTITY"
    assert "PRIVATE" not in output.read_text(encoding="utf-8")


def test_readonly_50_checks_entire_index_before_embedding(monkeypatch):
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "three_model_integration")
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", "backend_ai_rag_chunks_v1")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", "5617a9f61b028005a4858fdac845db406aefb181")
    monkeypatch.setenv("AI_VECTOR_DSN", "unused")
    monkeypatch.setattr(readonly_script, "_read_index_rows", lambda *args, **kwargs: [])
    def embedding_forbidden(*args, **kwargs):
        raise AssertionError("Embedding cannot run before readonly identity is verified")
    monkeypatch.setattr(readonly_script, "BgeM3EmbeddingClient", embedding_forbidden)
    with pytest.raises(Exception, match="VIEW_ROW_COUNT_MISMATCH"):
        readonly_script._verify_runtime()


@pytest.mark.parametrize("source_changed", [False, True])
def test_readonly_50_cannot_certify_a_source_changed_during_execution(monkeypatch, tmp_path, source_changed):
    before = {"python_version": "3.13.13", "commit_sha": "a" * 40,
              "dirty": False, "runtime_source_sha256": "b" * 64, "git_metadata_verified": True}
    after = {**before, "dirty": source_changed,
             "runtime_source_sha256": "c" * 64 if source_changed else "b" * 64}
    snapshots = iter([before, after])
    monkeypatch.setattr(readonly_script, "execution_provenance", lambda: next(snapshots))
    monkeypatch.setattr(readonly_script, "_verify_runtime", lambda: {"status": "PASS", "case_count": 50})
    output = tmp_path / "readonly.json"
    assert readonly_script.main(output, expected_sha="a" * 40) == int(source_changed)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["final_sha_eligible"] is not source_changed
    if source_changed:
        assert report["status"] == "HOLD"
        assert report["reason_code"] == "EXECUTION_SOURCE_CHANGED"


def test_fixed_sha_and_clean_strings_without_a_commit_object_are_not_evidence(monkeypatch, tmp_path):
    def metadata_only(command, **kwargs):
        if command[1:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(stdout="a" * 40)
        if command[1:] == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(stdout=str(tmp_path))
        raise subprocess.CalledProcessError(64, command, stderr="PRIVATE_DRIVER_TEXT")
    monkeypatch.setattr(release_evidence.subprocess, "run", metadata_only)
    result = release_evidence.execution_provenance(tmp_path)
    assert result["git_metadata_verified"] is False
    assert result["commit_sha"] is None and result["dirty"] is None
    assert "VERIFIED_GIT_COMMIT_REQUIRED" in execution_blockers(result, "a" * 40)
    assert "PRIVATE_DRIVER_TEXT" not in json.dumps(result)


def test_reported_sha_must_match_the_actual_commit_object(monkeypatch, tmp_path):
    commit = b"tree " + b"b" * 40 + b"\n\nsynthetic provenance test\n"
    actual_sha = sha1(f"commit {len(commit)}\0".encode() + commit, usedforsecurity=False).hexdigest()
    def actual_object(command, **kwargs):
        values = {
            ("rev-parse", "HEAD"): actual_sha,
            ("rev-parse", "--show-toplevel"): str(tmp_path),
            ("cat-file", "commit", actual_sha): commit,
            ("branch", "--show-current"): "",
            ("status", "--porcelain"): "",
        }
        return SimpleNamespace(stdout=values[tuple(command[1:])])
    monkeypatch.setattr(release_evidence.subprocess, "run", actual_object)
    result = release_evidence.execution_provenance(tmp_path)
    assert result["git_metadata_verified"] is True and result["commit_sha"] == actual_sha
    commit += b"tampered"
    result = release_evidence.execution_provenance(tmp_path)
    assert result["git_metadata_verified"] is False and result["commit_sha"] is None


@pytest.mark.parametrize("field", ["input_file_sha256", "evaluation_source_sha256", "git_metadata_verified"])
def test_prompt_or_oracle_or_evaluator_change_invalidates_the_same_runtime_sha(field):
    before = {"commit_sha": "a" * 40, "dirty": False, "runtime_source_sha256": "b" * 64,
              "input_file_sha256": {"oracle": "c" * 64},
              "evaluation_source_sha256": "d" * 64, "git_metadata_verified": True}
    after = {**before, field: "changed"}
    assert execution_source_changed(before, after)


def test_missing_dataset_is_not_a_final_sha_candidate():
    source = {"python_version": "3.13.13", "commit_sha": "a" * 40,
              "dirty": False, "git_metadata_verified": True,
              "missing_identity_files": ["data/config/rag/three_model_evaluation_cases.json"]}
    assert "RELEASE_IDENTITY_INPUTS_MISSING" in execution_blockers(source, "a" * 40)


def test_offline_qa_preparation_does_not_run_a_db_or_provider(monkeypatch):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("Offline preparation cannot contact an external service")
    monkeypatch.setattr(readonly_script, "_read_index_rows", network_forbidden)
    monkeypatch.setattr(script, "PipelineRouter", network_forbidden)
    report = prepare_release_qa.prepare("a" * 40)
    assert report["status"] == "QA_INPUTS_READY"
    assert report["reference_45"]["declared_case_count"] == 45
    assert report["readonly_50"]["case_types"] == {"POSITIVE": 43, "NEGATIVE": 7}
    assert report["executed_45_cases"] == report["executed_50_cases"] == 0
    assert report["database_queries"] == report["provider_requests"] == 0
    assert report["clean_source_ready_for_candidate_run"] is False
    assert report["final_sha_eligible"] is False


def test_offline_qa_preparation_reports_missing_data_without_private_paths(monkeypatch):
    def missing(*args):
        raise FileNotFoundError("PRIVATE_DATA_SOURCE_PATH")
    monkeypatch.setattr(prepare_release_qa, "load_three_model_evaluation_inputs", missing)
    report = prepare_release_qa.prepare("a" * 40)
    assert report["status"] == "HOLD"
    assert report["failure_stage"] == "READONLY_50_INPUTS"
    assert "PRIVATE_DATA_SOURCE_PATH" not in json.dumps(report)
