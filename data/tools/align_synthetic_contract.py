#!/usr/bin/env python3
"""One-time, idempotent normalization of legacy synthetic workflow fixtures."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DATA_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = DATA_ROOT / "config" / "synthetic" / "scenarios.json"
BLOCKED_SCENARIOS = {"SYN-JAC104-012", "SYN-JAC104-016"}


def _timestamp(value: str, minutes: int) -> str:
    parsed = datetime.fromisoformat(value)
    return (parsed + timedelta(minutes=minutes)).isoformat()


def _allowed_actions(step: dict[str, Any]) -> list[str]:
    status = step["to_status"]
    visit_status = step.get("visit_to_status")
    if status == "DRAFT":
        return ["SUBMIT_SYMPTOM"]
    if status == "QUESTIONNAIRE_IN_PROGRESS":
        return ["SUBMIT_ANSWERS"]
    if status == "AI_GUIDANCE":
        return ["CUSTOMER_REPORTED_SELF_RESOLVED", "REQUEST_CONSULTATION"]
    if status == "CONSULTATION_REQUIRED":
        return ["START_CONSULTATION"]
    if status == "CONSULTATION_IN_PROGRESS":
        return ["CONSULTATION_COMPLETED", "VISIT_REVIEW_REQUIRED"]
    if status == "VISIT_REVIEW_PENDING":
        return ["VISIT_NEEDED", "VISIT_NOT_NEEDED"]
    if status == "VISIT_SCHEDULING" and visit_status == "ASSIGNING":
        return ["UPDATE_VISIT_SCHEDULE"]
    if status == "VISIT_SCHEDULING":
        return ["UPDATE_VISIT_SCHEDULE", "CONFIRM_VISIT"]
    if status == "VISIT_SCHEDULED" and visit_status == "IN_PROGRESS":
        return ["VISIT_COMPLETED", "REVISIT_NEEDED"]
    if status == "VISIT_SCHEDULED":
        return ["START_VISIT"]
    if status == "COMPLETION_PENDING":
        return [
            "SUBMIT_RESOLUTION_FEEDBACK",
            "CUSTOMER_REPORTED_UNRESOLVED",
            "REQUEST_CONSULTATION",
            "FINALIZE_INQUIRY",
        ]
    if status == "REVISIT_REQUIRED":
        return ["UPDATE_VISIT_SCHEDULE"]
    if status == "REOPENED":
        return ["RESUME_CONSULTATION"]
    return []


def _normalize_workflow(workflow: dict[str, Any]) -> None:
    expanded: list[dict[str, Any]] = []
    for source in workflow["steps"]:
        step = deepcopy(source)
        if (
            step["event"] == "VISIT_NEEDED"
            and step["from_status"] == "CONSULTATION_IN_PROGRESS"
        ):
            step["event"] = "VISIT_REVIEW_REQUIRED"
            expanded.append(step)
            continue
        if (
            step["event"] == "CONFIRM_VISIT"
            and step["from_status"] == "VISIT_REVIEW_PENDING"
        ):
            visit_needed = deepcopy(step)
            visit_needed.update(
                event="VISIT_NEEDED",
                from_status="VISIT_REVIEW_PENDING",
                to_status="VISIT_SCHEDULING",
                occurred_at=_timestamp(step["occurred_at"], -20),
                idempotency_key=f"{step['idempotency_key']}-create",
                visit_from_status=None,
                visit_to_status="ASSIGNING",
                visit_state_version=1,
            )
            schedule = deepcopy(step)
            schedule.update(
                event="UPDATE_VISIT_SCHEDULE",
                from_status="VISIT_SCHEDULING",
                to_status="VISIT_SCHEDULING",
                occurred_at=_timestamp(step["occurred_at"], -10),
                idempotency_key=f"{step['idempotency_key']}-schedule",
                visit_from_status="ASSIGNING",
                visit_to_status="SCHEDULING",
                visit_state_version=2,
            )
            step.update(
                from_status="VISIT_SCHEDULING",
                to_status="VISIT_SCHEDULED",
                visit_from_status="SCHEDULING",
                visit_to_status="CONFIRMED",
                visit_state_version=3,
            )
            expanded.extend([visit_needed, schedule, step])
            continue
        if step["event"] == "START_VISIT":
            step.update(
                from_status="VISIT_SCHEDULED",
                to_status="VISIT_SCHEDULED",
                visit_from_status="CONFIRMED",
                visit_to_status="IN_PROGRESS",
                visit_state_version=4,
            )
        elif step["event"] == "VISIT_COMPLETED":
            step.update(
                from_status="VISIT_SCHEDULED",
                to_status="COMPLETION_PENDING",
                visit_from_status="IN_PROGRESS",
                visit_to_status="COMPLETED",
                visit_state_version=5,
            )
        expanded.append(step)

    for order, step in enumerate(expanded, 1):
        step["order"] = order
        step["state_version"] = order
        step["expected_allowed_actions"] = _allowed_actions(step)
    workflow["steps"] = expanded
    workflow["final_status"] = expanded[-1]["to_status"]


def _assignment(
    step: dict[str, Any],
    visit: dict[str, Any] | None,
) -> tuple[str, str | None]:
    status = step["to_status"]
    if status in {
        "CONSULTATION_IN_PROGRESS",
        "VISIT_REVIEW_PENDING",
        "VISIT_SCHEDULING",
    }:
        return "CONSULTANT", step["actor_id"]
    if status == "VISIT_SCHEDULED":
        technician_id = visit["technician_id"] if visit else step["actor_id"]
        return "TECHNICIAN", technician_id
    if status == "COMPLETION_PENDING":
        if visit:
            return "TECHNICIAN", visit["technician_id"]
        return step["actor_role"], step["actor_id"]
    if step["event"] == "FINALIZE_INQUIRY":
        return step["actor_role"], step["actor_id"]
    return "NONE", None


def _rebuild_event_records(
    config: dict[str, Any],
    workflows: list[dict[str, Any]],
    inquiries: list[dict[str, Any]],
    visits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    namespace = uuid.UUID(config["uuid_namespace"])
    inquiry_by_scenario = {row["scenario_id"]: row for row in inquiries}
    visit_by_inquiry = {row["inquiry_id"]: row for row in visits}
    histories: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []

    for workflow in workflows:
        scenario_id = workflow["scenario_id"]
        inquiry = inquiry_by_scenario[scenario_id]
        visit = visit_by_inquiry.get(inquiry["inquiry_id"])
        for step in workflow["steps"]:
            assigned_role, assigned_user_id = _assignment(step, visit)
            record_key = f"{scenario_id}:{step['order']}"
            histories.append(
                {
                    "history_id": str(
                        uuid.uuid5(namespace, f"status-history:{record_key}")
                    ),
                    "inquiry_id": inquiry["inquiry_id"],
                    "sequence": step["order"],
                    "event": step["event"],
                    "from_status": step["from_status"],
                    "to_status": step["to_status"],
                    "actor_role": step["actor_role"],
                    "actor_id": step["actor_id"],
                    "assigned_role_after": assigned_role,
                    "assigned_user_id_after": assigned_user_id,
                    "state_version": step["state_version"],
                    "idempotency_key": step["idempotency_key"],
                    "correlation_id": step["correlation_id"],
                    "changed_at": step["occurred_at"],
                    "reason": f"{scenario_id} 합성 상태 전이",
                    "data_classification": "synthetic",
                }
            )
            audits.append(
                {
                    "audit_event_id": str(
                        uuid.uuid5(namespace, f"audit-event:{record_key}")
                    ),
                    "entity_type": "INQUIRY",
                    "entity_id": inquiry["inquiry_id"],
                    "event_type": step["event"],
                    "actor_role": step["actor_role"],
                    "actor_id": step["actor_id"],
                    "state_version": step["state_version"],
                    "idempotency_key": step["idempotency_key"],
                    "correlation_id": step["correlation_id"],
                    "occurred_at": step["occurred_at"],
                    "data_classification": "synthetic",
                }
            )
    return histories, audits


def normalize(config: dict[str, Any]) -> dict[str, Any]:
    outputs = config["materialized_outputs"]
    workflows = outputs["workflow_states"]
    for workflow in workflows:
        _normalize_workflow(workflow)

    inquiry_by_scenario = {
        row["scenario_id"]: row for row in outputs["inquiries"]
    }
    workflow_by_scenario = {row["scenario_id"]: row for row in workflows}

    review_inquiry_ids = {
        inquiry_by_scenario["SYN-JAC104-008"]["inquiry_id"]
    }
    outputs["visits"] = [
        row for row in outputs["visits"] if row["inquiry_id"] not in review_inquiry_ids
    ]
    visit_versions = {
        "ASSIGNING": 1,
        "SCHEDULING": 2,
        "CONFIRMED": 3,
        "IN_PROGRESS": 4,
        "COMPLETED": 5,
        "FOLLOW_UP_REQUIRED": 5,
        "CANCELLED": 1,
    }
    for visit in outputs["visits"]:
        visit["state_version"] = visit_versions[visit["status"]]

    visit_by_inquiry = {row["inquiry_id"]: row for row in outputs["visits"]}
    histories, audits = _rebuild_event_records(
        config,
        workflows,
        outputs["inquiries"],
        outputs["visits"],
    )
    outputs["inquiry_status_histories"] = histories
    outputs["audit_events"] = audits

    for scenario_id, inquiry in inquiry_by_scenario.items():
        workflow = workflow_by_scenario[scenario_id]
        last_step = workflow["steps"][-1]
        assigned_role, assigned_user_id = _assignment(
            last_step,
            visit_by_inquiry.get(inquiry["inquiry_id"]),
        )
        inquiry["status"] = workflow["final_status"]
        inquiry["state_version"] = last_step["state_version"]
        inquiry["assigned_role"] = assigned_role
        inquiry["assigned_user_id"] = assigned_user_id
        inquiry["updated_at"] = last_step["occurred_at"]

    final_statuses = {
        scenario_id: workflow["final_status"]
        for scenario_id, workflow in workflow_by_scenario.items()
    }
    for row in config["scenario_matrix"]:
        row["current_status"] = final_statuses[row["scenario_id"]]
    for container in [
        outputs["demo_scenarios"]["scenarios"],
        *config["materialized_subsets"].values(),
    ]:
        for row in container:
            row["expected_outcome"] = final_statuses[row["scenario_id"]]

    config["outputs"]["contract_alignment_registry"] = (
        "synthetic/expected/contract_alignment_registry.json"
    )
    outputs["contract_alignment_registry"] = [
        {
            "scenario_id": row["scenario_id"],
            "contract_alignment_status": (
                "BLOCKED_DECISION"
                if row["scenario_id"] in BLOCKED_SCENARIOS
                else "ALIGNED"
            ),
            "blocker_ids": (
                ["DEC-RESOLVED-REOPEN-001"]
                if row["scenario_id"] in BLOCKED_SCENARIOS
                else []
            ),
            "include_in_contract_projection": (
                row["scenario_id"] not in BLOCKED_SCENARIOS
            ),
            "reason": (
                "RESOLVED 이후 동일 문의 재개 정책 결정 대기"
                if row["scenario_id"] in BLOCKED_SCENARIOS
                else "현행 저장소 계약에 정합화됨"
            ),
        }
        for row in config["scenario_matrix"]
    ]

    config["config_version"] = "1.4.0"
    return config


def main() -> int:
    source = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    normalized = normalize(source)
    rendered = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    CONFIG_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "PASS",
                "config_version": normalized["config_version"],
                "blocked_scenarios_preserved": sorted(BLOCKED_SCENARIOS),
                "visits": len(normalized["materialized_outputs"]["visits"]),
                "workflow_steps": sum(
                    len(row["steps"])
                    for row in normalized["materialized_outputs"]["workflow_states"]
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
