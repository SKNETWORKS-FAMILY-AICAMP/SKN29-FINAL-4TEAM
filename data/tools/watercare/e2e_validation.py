"""Representative E2E cross-document and fixture invariants."""

from __future__ import annotations

import re
from typing import Any

from .config import PipelineConfig
from .io import read_json, read_jsonl


def _markdown_section(text: str, heading: str) -> str | None:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        return None
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6})\s", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def validate_representative_e2e(
    config: PipelineConfig,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = contract or config.config("e2e")
    synthetic = config.config("synthetic")
    outputs = {
        key: read_json(config.data_root / path)
        for key, path in synthetic["outputs"].items()
    }
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "name": name,
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
            }
        )

    documents = set()
    repo_root = config.data_root.parent.resolve()
    for assertion in spec["document_sections"]:
        relative = assertion["path"]
        path = (repo_root / relative).resolve()
        documents.add(relative)
        safe = path.is_relative_to(repo_root)
        section = (
            _markdown_section(path.read_text(encoding="utf-8"), assertion["heading"])
            if safe and path.is_file()
            else None
        )
        missing = [
            token
            for token in assertion["required_tokens"]
            if section is None or token not in section
        ]
        add(
            f"document_section:{relative}:{assertion['heading']}",
            safe and path.is_file() and section is not None and not missing,
            f"missing_tokens={missing}",
        )

    representatives = [
        row
        for row in outputs["inquiries"]
        if row["scenario_id"] == spec["scenario_id"]
        or row["inquiry_number"] == spec["inquiry_number"]
    ]
    identity_ok = (
        len(representatives) == 1
        and representatives[0]["scenario_id"] == spec["scenario_id"]
        and representatives[0]["inquiry_number"] == spec["inquiry_number"]
    )
    add("representative_identity", identity_ok, f"matches={len(representatives)}")
    if not identity_ok:
        errors = [
            f"representative_e2e:{item['name']}"
            for item in checks
            if item["status"] == "FAIL"
        ]
        return {
            "status": "FAIL",
            "generated_at": config.generated_at,
            "summary": {
                "checks": len(checks),
                "passed": len(checks) - len(errors),
                "failed": len(errors),
                "documents_checked": len(documents),
            },
            "checks": checks,
            "errors": errors,
        }

    inquiry = representatives[0]
    subscriptions = {
        row["subscription_id"]: row for row in outputs["subscriptions"]
    }
    customer_products = {
        row["customer_product_id"]: row for row in outputs["customer_products"]
    }
    products = {row["product_id"]: row for row in outputs["products"]}
    subscription = subscriptions.get(inquiry["subscription_id"])
    customer_product = (
        customer_products.get(subscription["customer_product_id"])
        if subscription
        else None
    )
    product = products.get(customer_product["product_id"]) if customer_product else None
    configured_scenario = next(
        (
            row
            for row in synthetic["scenario_matrix"]
            if row["scenario_id"] == spec["scenario_id"]
        ),
        None,
    )
    add(
        "representative_business_values",
        inquiry["topic_code"] == spec["topic_code"]
        and inquiry["risk_level"] == spec["risk_level"]
        and inquiry["usage_guidance_status"] == spec["usage_guidance_status"]
        and inquiry["status"] == spec["final_status"]
        and inquiry["state_version"] == spec["final_state_version"]
        and configured_scenario is not None
        and configured_scenario["current_status"] == spec["final_status"],
        (
            f"topic={inquiry['topic_code']},risk={inquiry['risk_level']},"
            f"usage={inquiry['usage_guidance_status']},status={inquiry['status']},"
            f"state_version={inquiry['state_version']}"
        ),
    )
    add(
        "representative_product_lineage",
        product is not None and product["product_code"] == spec["product_code"],
        f"product_code={product['product_code'] if product else None}",
    )

    evidence_rows = [
        row
        for row in read_jsonl(config.path("evidence_output"))
        if row["evidence_id"] == spec["evidence_id"]
    ]
    rag_rows = [
        row
        for row in read_jsonl(config.path("rag_output"))
        if row["chunk_id"] == spec["rag_chunk_id"]
    ]
    evidence_ok = (
        inquiry["evidence_ids"] == [spec["evidence_id"]]
        and len(evidence_rows) == 1
        and len(rag_rows) == 1
        and evidence_rows[0]["source_id"] == spec["rag_chunk_id"]
        and evidence_rows[0]["document_id"] == spec["document_id"]
        and evidence_rows[0]["exact_sales_code"] == spec["product_code"]
        and evidence_rows[0]["topic_code"] == spec["topic_code"]
        and evidence_rows[0]["page_refs"] == [spec["manual_page"]]
        and rag_rows[0]["evidence_id"] == spec["evidence_id"]
        and rag_rows[0]["document_id"] == spec["document_id"]
        and rag_rows[0]["page_refs"] == [spec["manual_page"]]
    )
    add(
        "representative_evidence_lineage",
        evidence_ok,
        f"evidence_rows={len(evidence_rows)},rag_rows={len(rag_rows)}",
    )

    workflow = next(
        row
        for row in outputs["workflow_states"]
        if row["scenario_id"] == spec["scenario_id"]
    )
    histories = sorted(
        (
            row
            for row in outputs["inquiry_status_histories"]
            if row["inquiry_id"] == inquiry["inquiry_id"]
        ),
        key=lambda row: row["sequence"],
    )
    audits = sorted(
        (
            row
            for row in outputs["audit_events"]
            if row["entity_id"] == inquiry["inquiry_id"]
        ),
        key=lambda row: row["state_version"],
    )
    expected_events = spec["expected_events"]
    workflow_events = [row["event"] for row in workflow["steps"]]
    add(
        "representative_workflow_sequence",
        workflow_events == expected_events
        and workflow["final_status"] == spec["final_status"],
        f"events={workflow_events}",
    )
    add(
        "history_audit_sequence",
        [row["event"] for row in histories] == expected_events
        and [row["event_type"] for row in audits] == expected_events
        and [row["state_version"] for row in histories]
        == list(range(1, spec["final_state_version"] + 1)),
        f"histories={len(histories)},audits={len(audits)}",
    )

    transition_text = (
        repo_root / "contracts" / "state-machine" / "transition-rules.yaml"
    ).read_text(encoding="utf-8")
    contract_transitions = {
        (None if source == "null" else source, event, target)
        for source, event, target in re.findall(
            r"\{from: (null|[A-Z_]+), event: ([A-Z_]+), to: ([A-Z_]+)\}",
            transition_text,
        )
    }
    workflow_transitions = {
        (row["from_status"], row["event"], row["to_status"])
        for row in workflow["steps"]
    }
    add(
        "workflow_transitions_in_contract",
        workflow_transitions <= contract_transitions,
        f"missing={sorted(workflow_transitions - contract_transitions, key=str)}",
    )

    consultations = [
        row
        for row in outputs["consultations"]
        if row["inquiry_id"] == inquiry["inquiry_id"]
    ]
    visits = [
        row for row in outputs["visits"] if row["inquiry_id"] == inquiry["inquiry_id"]
    ]
    followups = [
        row
        for row in outputs["followup_confirmations"]
        if row["inquiry_id"] == inquiry["inquiry_id"]
    ]
    care_histories = [
        row
        for row in outputs["care_histories"]
        if row.get("inquiry_id") == inquiry["inquiry_id"]
    ]
    chain_ok = (
        len(consultations) == len(visits) == len(followups) == len(care_histories) == 1
        and visits[0]["status"] == "COMPLETED"
        and followups[0]["consultation_id"] == consultations[0]["consultation_id"]
        and followups[0]["visit_id"] == visits[0]["visit_id"]
        and followups[0]["resolution_status_code"] == spec["final_status"]
        and care_histories[0]["visit_id"] == visits[0]["visit_id"]
        and care_histories[0]["result"] == "ISSUE_RESOLVED"
    )
    add(
        "consultation_visit_followup_care_chain",
        chain_ok,
        (
            f"consultations={len(consultations)},visits={len(visits)},"
            f"followups={len(followups)},care_histories={len(care_histories)}"
        ),
    )
    completion_policy = (
        repo_root / "contracts" / "state-machine" / "completion-policy.yaml"
    ).read_text(encoding="utf-8")
    add(
        "visit_completion_actor",
        workflow["steps"][-1]["actor_role"] == spec["final_actor_role"]
        and inquiry["assigned_role"] == spec["final_actor_role"]
        and len(visits) == 1
        and workflow["steps"][-1]["actor_id"] == visits[0]["technician_id"]
        and "visit_path: SNAPSHOT_TECHNICIAN" in completion_policy,
        (
            f"actor_role={workflow['steps'][-1]['actor_role']},"
            f"assigned_role={inquiry['assigned_role']}"
        ),
    )
    correlation_ids = {
        inquiry["correlation_id"],
        *(row["correlation_id"] for row in consultations),
        *(row["correlation_id"] for row in visits),
        *(row["correlation_id"] for row in histories),
        *(row["correlation_id"] for row in audits),
    }
    add(
        "correlation_id_continuity",
        len(correlation_ids) == 1,
        f"correlation_ids={sorted(correlation_ids)}",
    )

    actual_counts = {
        key: len(outputs[key])
        for key in spec["expected_counts"]
        if key != "representative_steps"
    }
    actual_counts["representative_steps"] = len(workflow["steps"])
    add(
        "representative_dataset_counts",
        actual_counts == spec["expected_counts"],
        f"actual={actual_counts}",
    )
    manifest_counts = read_json(config.path("dataset_manifest"))["counts"]
    manifest_keys = {
        "inquiries": "synthetic_inquiries",
        "consultations": "synthetic_consultations",
        "visits": "synthetic_visits",
        "care_histories": "synthetic_care_histories",
        "followup_confirmations": "synthetic_followup_confirmations",
        "inquiry_status_histories": "synthetic_status_histories",
        "audit_events": "synthetic_audit_events",
    }
    add(
        "manifest_counts_match_e2e_contract",
        all(
            manifest_counts.get(manifest_key) == spec["expected_counts"][output_key]
            for output_key, manifest_key in manifest_keys.items()
        ),
        "dataset manifest synthetic counts",
    )

    errors = [
        f"representative_e2e:{item['name']}"
        for item in checks
        if item["status"] == "FAIL"
    ]
    return {
        "status": "PASS" if not errors else "FAIL",
        "generated_at": config.generated_at,
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(errors),
            "failed": len(errors),
            "documents_checked": len(documents),
        },
        "checks": checks,
        "errors": errors,
    }
