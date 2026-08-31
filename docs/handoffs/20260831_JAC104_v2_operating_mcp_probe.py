"""Readonly MCP retrieval probe in the approved running AI container.

Uses the real production facade, shared stdio manager and MCP server.
Does not call PipelineRouter.run(), Provider, Backend context or write APIs.
This is a new diagnostic-process MCP session, not the ASGI process's session.
No production source, environment file or DB row is modified.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
from time import perf_counter

SOURCE_SHA = "ce22601bf4f21b0c11d7626fb3bd1b905464d1da"
SOURCE_HASHES = {
    "ai/app/orchestration/pipeline_router.py": "af0f14dd89db627e89e055b1fb2993a8baac69447f0d1a148f01f45f2bc7f3d3",
    "ai/app/integrations/mcp/client.py": "da04772170d91f8ecac300764beb954c15bf1456253496764b08fcfdb023fcec",
    "ai/app/integrations/mcp/session_manager.py": "3c9791ed565faf4d0ed55e8195c78e4469d51ec8825a1917e9d41995aed9ebe5",
    "ai/app/integrations/mcp/search_service.py": "667f34933c5f93e091d0ef9566d1715c1698d6f23c3c2f6a6a9d9be8be444af8",
    "ai/app/integrations/mcp/server.py": "edd52aa6db11199f116f640a6b76a4cc3599a706a58d3141072395689984ec1d",
    "ai/app/integrations/mcp/tools/search_official_evidence.py": "7ce8cca939906609bde99cec8c116713eb5e4edaecf5921d18c77309827abb27",
    "ai/scripts/verify_jac104_v2_recovery.py": "cc62f6cb6ec6dcea99a4fdec7e33af6acea8fa2bd3f1275419bb0bc48f1826ab",
    "ai/app/retrieval/runtime_profile.py": "da2e89df19396162f5cc390892cdc7c73bc0fa907a8de2811b5d00d3cdcc49f3",
    "ai/app/retrieval/verification/index_readiness.py": "18fefb9ff62057d90391f6fc4af1c525fd760ea74243a57373aba17f79148c37",
    "ai/configs/index_manifest_3model.json": "3fa0f26c0c2c2628f9d4410c061ff17dd8d6ce9c6e0b76358cbb0bb0a9c28a1e",
    "ai/configs/canonical_evidence_identity_3model.json": "ab98aa6cfe839366cb13ecc3839d72ee0ae99419af85f702f0c2f1d05bdca169"
}
EXPECTED_ENV = {
    "AI_RAG_RUNTIME_PROFILE": "jac104_v2_recovery",
    "AI_PIPELINE_RUNTIME": "multi_agent",
    "AI_RETRIEVAL_TRANSPORT": "mcp",
    "AI_VECTOR_TABLE_NAME": "backend_ai_rag_chunks_v1",
    "AI_EMBEDDING_REVISION": "5617a9f61b028005a4858fdac845db406aefb181",
    "AI_HANDOFF_BACKEND_ENABLED": "false",
}


class GateError(RuntimeError):
    pass


def require(condition, reason):
    if not condition:
        raise GateError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def own_mcp_children():
    if not Path("/proc/self/task").is_dir():
        return []
    children = set()
    for task in Path("/proc/self/task").iterdir():
        try:
            children.update(int(pid) for pid in (task / "children").read_text().split())
        except (FileNotFoundError, ProcessLookupError):
            pass
    matches = []
    for pid in children:
        try:
            arguments = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, ProcessLookupError):
            continue
        if b"ai.app.integrations.mcp.server" in arguments:
            matches.append(pid)
    return sorted(matches)


def evidence_checks(references, canonical, parent_ids, required_ids):
    metrics = dict.fromkeys((
        "cross_model_hits", "direct_parent_hits", "noncanonical_hits",
        "unverified_hits", "ineligible_hits", "content_hash_mismatches",
        "page_mismatches",
    ), 0)
    ids = []
    for evidence in references:
        chunk_id = evidence["chunk_id"]
        ids.append(chunk_id)
        expected = canonical.get(chunk_id)
        metrics["cross_model_hits"] += int(
            evidence["model_code"] != "WPUJAC104DWH"
            or evidence["product_generation"] != "D"
        )
        metrics["direct_parent_hits"] += int(chunk_id in parent_ids)
        metrics["noncanonical_hits"] += int(expected is None)
        metrics["unverified_hits"] += int(
            evidence["verification_status"] != "official_verified"
        )
        metrics["ineligible_hits"] += int(
            evidence["allowed_use"] is not True
            or evidence["runtime_eligible"] is not True
        )
        if expected is not None:
            metrics["content_hash_mismatches"] += int(
                hashlib.sha256(evidence["summary"].encode("utf-8")).hexdigest().upper()
                != expected["chunk_text_sha256"].upper()
            )
            metrics["page_mismatches"] += int(
                evidence["page_refs"] != expected["page_refs"]
            )
    expected_hit = bool(set(ids).intersection(required_ids))
    return {
        "pass": 1 <= len(ids) <= 5 and len(set(ids)) == len(ids)
        and expected_hit and all(value == 0 for value in metrics.values()),
        "hit_count": len(ids),
        "expected_evidence_hit": expected_hit,
        "evidence_ids_in_returned_order": ids,
        **metrics,
    }


def chunk_reference(chunk):
    return {
        "chunk_id": chunk.chunk_id, "model_code": chunk.model_code,
        "product_generation": chunk.product_generation,
        "verification_status": chunk.verification_status,
        "allowed_use": chunk.allowed_use, "runtime_eligible": chunk.runtime_eligible,
        "summary": chunk.content, "page_refs": chunk.page_refs,
    }


def main():
    report = {
        "status": "BLOCKED", "scope": "RUNNING_CONTAINER_MCP_RETRIEVAL_ONLY",
        "source_sha": SOURCE_SHA, "started_at_utc": now(), "probe_pid": os.getpid(),
        "full_analysis_pipeline_executed": False,
        "asgi_process_existing_session_used": False,
        "guidance_provider_calls": 0, "backend_context_calls": 0,
        "backend_writes": 0, "ddl_executed": False,
        "zero_call_basis": "Only readonly index inspection and MCP evidence/health/warmup methods are called",
        "three_model_public_activation": "HOLD", "provider_canary_executed": False,
        "cases": [],
    }
    stage = "ENVIRONMENT"
    manager = None
    def deadline(_signum, _frame):
        raise GateError("PROBE_WALL_TIME_BUDGET_EXCEEDED")
    alarm_supported = hasattr(signal, "SIGALRM")
    if alarm_supported:
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(150)
    try:
        require(platform.python_version() == "3.13.13", "PYTHON_VERSION_MISMATCH")
        require(platform.system() == "Linux", "LINUX_PROCESS_SCOPE_REQUIRED")
        import resource
        require(all(os.getenv(key) == value for key, value in EXPECTED_ENV.items()),
                "DEPLOYED_RUNTIME_ENVIRONMENT_MISMATCH")
        require(not os.getenv("OPENAI_API_KEY") and not os.getenv("AI_HANDOFF_INTERNAL_TOKEN"),
                "DIAGNOSTIC_SECRET_SUPPRESSION_REQUIRED")
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        available_kib = int(memory["MemAvailable"].split()[0])
        require(available_kib >= 4 * 1024 * 1024, "INSUFFICIENT_HOST_MEMORY_HEADROOM")
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
        os.nice(10)
        resource.setrlimit(resource.RLIMIT_CPU, (90, 100))
        report.update(python_version=platform.python_version(),
                      runtime_environment=dict(EXPECTED_ENV),
                      host_memory_available_kib_at_start=available_kib,
                      diagnostic_cpu_affinity=sorted(os.sched_getaffinity(0)),
                      diagnostic_nice=10, cpu_time_limit_seconds=90)
        stage = "PINNED_SOURCE_IDENTITY"
        for path, digest in SOURCE_HASHES.items():
            require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest,
                    "PINNED_IMAGE_SOURCE_HASH_MISMATCH")
        report["image_source_files_verified"] = len(SOURCE_HASHES)

        from ai.scripts.verify_jac104_v2_recovery import PROBES, _read_index_rows
        from ai.app.retrieval.runtime_profile import resolve_rag_runtime_profile
        from ai.app.retrieval.indexing.index_manifest import IndexManifest
        from ai.app.retrieval.verification.index_readiness import validate_readonly_index
        from ai.app.retrieval.models.retrieval_query import RetrievalQuery
        from ai.app.orchestration.pipeline_router import _create_mcp_evidence_search_service
        from ai.app.integrations.mcp.client import WaterBridgeMCPClient
        from ai.app.integrations.mcp.session_manager import get_shared_mcp_session_manager

        profile = resolve_rag_runtime_profile()
        manifest = IndexManifest.load_manifest(str(profile.manifest_path))
        identity = json.loads(Path("ai/configs/canonical_evidence_identity_3model.json").read_text())
        canonical = {item["chunk_id"]: item for item in identity["chunks"]}
        def snapshot():
            rows = _read_index_rows(os.environ["AI_VECTOR_DSN"], maximum_rows=54)
            index = validate_readonly_index(profile, manifest, identity, rows)
            digest = hashlib.sha256(json.dumps(
                [asdict(row) for row in rows], sort_keys=True, separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")).hexdigest()
            return rows, index, digest

        stage = "READONLY_CANONICAL_BEFORE"
        rows, index, before_hash = snapshot()
        parent_ids = {row.metadata["parent_id"] for row in rows}
        report["index_before"] = index
        report["readonly_metadata_sha256_before"] = before_hash
        stage = "REAL_MCP_FACTORY"
        facade = _create_mcp_evidence_search_service()
        require(facade._client_factory is WaterBridgeMCPClient,
                "REAL_PRODUCTION_MCP_CLIENT_REQUIRED")
        server_env = WaterBridgeMCPClient._server_environment()
        require(all(server_env.get(key) == os.environ[key] for key in (
            "AI_VECTOR_DSN", "AI_VECTOR_TABLE_NAME", "AI_EMBEDDING_REVISION",
            "AI_RAG_RUNTIME_PROFILE",
        )), "MCP_SERVER_ENVIRONMENT_PARITY_FAILED")
        require(not server_env.get("OPENAI_API_KEY")
                and not server_env.get("AI_HANDOFF_INTERNAL_TOKEN"),
                "MCP_SERVER_PROVIDER_HANDOFF_KEYS_PRESENT")
        report["mcp_server_core_environment_matches_parent"] = True
        report["factory"] = "ai.app.orchestration.pipeline_router._create_mcp_evidence_search_service"
        report["facade_type"] = type(facade).__name__
        manager = get_shared_mcp_session_manager()
        stage = "MCP_HEALTH"
        health = manager.call_tool("health_check", {}, timeout_seconds=15)
        health_payload = getattr(health, "structuredContent", None)
        if health_payload is None:
            health_payload = json.loads(health.content[0].text)
        require(not getattr(health, "isError", False)
                and health_payload.get("status") == "ok", "MCP_HEALTH_FAILED")
        report["mcp_health"] = health_payload
        stage = "MCP_WARMUP"
        started = perf_counter()
        require(manager.warmup_search_runtime(timeout_seconds=90), "MCP_WARMUP_FAILED")
        report["mcp_warmup_seconds"] = round(perf_counter() - started, 6)
        session_pids = own_mcp_children()
        require(len(session_pids) == 1, "MCP_CHILD_PROCESS_NOT_UNIQUE")
        report["mcp_server_process_ids"] = session_pids

        all_cases = [
            (probe_id, text, "WPUJAC104DWH", "D", expected)
            for probe_id, text, expected in PROBES
        ] + [
            ("BLOCK_IAC425", PROBES[0][1], "WPUIAC425SNW", "IAC425", None),
            ("BLOCK_IAC606", PROBES[0][1], "WPUIAC606SNW", "IAC606", None),
        ]
        for probe_id, query_text, model_code, generation, expected in all_cases:
            stage = probe_id
            query = RetrievalQuery(query_text=query_text, model_code=model_code,
                                   product_generation=generation, top_k=5)
            started = perf_counter()
            result = manager.call_tool("search_official_evidence",
                                       facade._tool_arguments(query), timeout_seconds=15)
            output = facade._parse_output(result)
            raw_seconds = perf_counter() - started
            started = perf_counter()
            chunks = facade.search(query)
            facade_seconds = perf_counter() - started
            case = {
                "probe_id": probe_id, "model_code": model_code,
                "policy_execution_path": output.policy_execution_path,
                "policy_blocked": output.policy_blocked,
                "vector_search_executed": output.vector_search_executed,
                "search_result_found": output.search_result_found,
                "evidence_found": output.evidence_found,
                "raw_tool_seconds": round(raw_seconds, 6),
                "production_facade_seconds": round(facade_seconds, 6),
                "search_tool_calls": 2,
            }
            if expected is not None:
                raw_check = evidence_checks(
                    [item.model_dump() for item in output.evidence_references],
                    canonical, parent_ids, expected,
                )
                facade_check = evidence_checks(
                    [chunk_reference(chunk) for chunk in chunks],
                    canonical, parent_ids, expected,
                )
                case["raw_evidence"] = raw_check
                case["production_facade_evidence"] = facade_check
                case["pass"] = all((
                    output.policy_execution_path == "PGVECTOR_QUERY",
                    output.vector_search_executed, output.evidence_found,
                    output.search_result_found, not output.policy_blocked,
                    raw_check["pass"], facade_check["pass"],
                    set(raw_check["evidence_ids_in_returned_order"])
                    == set(facade_check["evidence_ids_in_returned_order"]),
                ))
            else:
                case["pass"] = all((
                    output.policy_execution_path == "POLICY_BLOCK_UNSUPPORTED_MODEL",
                    output.policy_blocked, not output.vector_search_executed,
                    not output.search_result_found, not output.evidence_found,
                    not output.evidence_references, not chunks,
                ))
                case["evidence_count"] = len(output.evidence_references)
                case["facade_evidence_count"] = len(chunks)
            case["same_mcp_server_process"] = own_mcp_children() == session_pids
            case["pass"] = case["pass"] and case["same_mcp_server_process"]
            report["cases"].append(case)
            require(case["pass"], "MCP_RETRIEVAL_CASE_FAILED")

        stage = "READONLY_CANONICAL_AFTER"
        _rows, after_index, after_hash = snapshot()
        report["index_after"] = after_index
        report["readonly_metadata_sha256_after"] = after_hash
        require(after_hash == before_hash, "READONLY_INDEX_METADATA_CHANGED")
        report["readonly_canonical_before_after"] = "PASS"
        report["positive_pass_count"] = 3
        report["blocked_product_pass_count"] = 2
        report["search_tool_call_count"] = 10
        report["persistent_mcp_process_reused"] = True
        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "BLOCKED"
        report["failure_stage"] = stage
        report["error_type"] = type(exc).__name__
        report["reason_code"] = (
            str(exc) if isinstance(exc, GateError)
            else getattr(exc, "reason_code", "MCP_PROBE_REQUIREMENTS_NOT_MET")
        )
        kind = getattr(exc, "kind", None)
        if kind is not None:
            report["mcp_failure_kind"] = getattr(kind, "value", type(kind).__name__)
    finally:
        if alarm_supported:
            signal.alarm(0)
        try:
            if manager is not None:
                manager.close(timeout_seconds=5)
            report["diagnostic_mcp_session_closed"] = not own_mcp_children()
        except Exception as exc:
            report["status"] = "BLOCKED"
            report["cleanup_error_type"] = type(exc).__name__
        remaining = own_mcp_children()
        if remaining:
            report["status"] = "BLOCKED"
            report["diagnostic_mcp_children_terminated"] = remaining
            for pid in remaining:
                # Only exact MCP-module children of this diagnostic process.
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        report["finished_at_utc"] = now()
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
