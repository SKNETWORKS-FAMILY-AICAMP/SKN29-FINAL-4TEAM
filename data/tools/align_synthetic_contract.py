#!/usr/bin/env python3
"""Normalize synthetic source data to the accepted T-005 data contract.

The script only rewrites the declarative synthetic configuration. Canonical
fixtures and release metadata are materialized by ``data/tools/pipeline.py``.
"""

from __future__ import annotations

import hashlib
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
    """Expand legacy compound steps and preserve one request key per event."""
    expanded: list[dict[str, Any]] = []
    for source in workflow["steps"]:
        step = deepcopy(source)
        if "actor_id" in step:
            step["actor_public_id"] = step.pop("actor_id")
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
        elif step["event"] == "REVISIT_NEEDED":
            step.update(
                visit_from_status=step.get("visit_from_status", "IN_PROGRESS"),
                visit_to_status="FOLLOW_UP_REQUIRED",
                visit_state_version=step.get("visit_state_version"),
            )
        expanded.append(step)

    for order, step in enumerate(expanded, 1):
        step["order"] = order
        step["state_version"] = order
        step["expected_allowed_actions"] = _allowed_actions(step)
    workflow["steps"] = expanded
    workflow["final_status"] = expanded[-1]["to_status"]


def _identity_rows(
    rows: list[dict[str, Any]],
    legacy_id: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    normalized: list[dict[str, Any]] = []
    public_to_internal: dict[str, int] = {}
    for internal_id, source in enumerate(rows, 1):
        row = dict(source)
        public_id = str(row.pop(legacy_id, row.pop("public_id", "")))
        if not public_id:
            raise ValueError(f"{legacy_id} public identifier is missing")
        public_to_internal[public_id] = internal_id
        row.pop("id", None)
        normalized.append(
            {
                "id": internal_id,
                "public_id": public_id,
                **row,
            }
        )
    return normalized, public_to_internal


def _fk(value: Any, mapping: dict[str, int]) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return mapping[str(value)]


def _actor_internal_id(
    step: dict[str, Any],
    user_ids: dict[str, int],
) -> int | None:
    public_id = step.get("actor_public_id")
    return None if public_id is None else user_ids[str(public_id)]


def _assignment(
    step: dict[str, Any],
    visit: dict[str, Any] | None,
    user_ids: dict[str, int],
) -> tuple[str, int | None]:
    status = step["to_status"]
    if status in {
        "CONSULTATION_IN_PROGRESS",
        "VISIT_REVIEW_PENDING",
        "VISIT_SCHEDULING",
    }:
        return "CONSULTANT", _actor_internal_id(step, user_ids)
    if status == "VISIT_SCHEDULED":
        technician_id = visit["technician_id"] if visit else _actor_internal_id(
            step, user_ids
        )
        return "TECHNICIAN", technician_id
    if status == "COMPLETION_PENDING":
        if visit:
            return "TECHNICIAN", visit["technician_id"]
        return step["actor_role"], _actor_internal_id(step, user_ids)
    if step["event"] == "FINALIZE_INQUIRY":
        return step["actor_role"], _actor_internal_id(step, user_ids)
    return "NONE", None


def _history_row(
    *,
    namespace: uuid.UUID,
    internal_id: int,
    scenario_id: str,
    target_type: str,
    target_id: int,
    step: dict[str, Any],
    state_version: int,
    from_status: str | None,
    to_status: str,
    user_ids: dict[str, int],
) -> dict[str, Any]:
    target_label = target_type.lower()
    history_public_id = str(
        uuid.uuid5(
            namespace,
            f"status-history:{target_label}:{target_id}:{state_version}",
        )
    )
    target_fks = {
        "questionnaire_session_id": None,
        "inquiry_id": None,
        "consultation_id": None,
        "visit_id": None,
    }
    target_fks[f"{target_label}_id"] = target_id
    actor_id = _actor_internal_id(step, user_ids)
    return {
        "id": internal_id,
        "public_id": history_public_id,
        "status_history_number": (
            f"SYN-HIST-{target_type}-{scenario_id.rsplit('-', 1)[-1]}-"
            f"{state_version:03d}"
        ),
        **target_fks,
        "target_type_code": target_type,
        "event_code": step["event"],
        "from_status_code": from_status,
        "to_status_code": to_status,
        "state_version": state_version,
        "change_reason": f"{scenario_id} 합성 상태 전이",
        "changed_by_id": actor_id,
        "changed_by_type_code": "SYSTEM" if actor_id is None else "USER",
        "correlation_id": step["correlation_id"],
        "idempotency_key": step["idempotency_key"],
        "changed_at": step["occurred_at"],
        "data_classification": "synthetic",
    }


def _audit_row(
    *,
    namespace: uuid.UUID,
    internal_id: int,
    scenario_id: str,
    history: dict[str, Any],
    step: dict[str, Any],
    user_ids: dict[str, int],
) -> dict[str, Any]:
    target_type = history["target_type_code"]
    target_id = history[f"{target_type.lower()}_id"]
    public_id = str(
        uuid.uuid5(
            namespace,
            f"audit-event:{target_type.lower()}:{target_id}:"
            f"{history['state_version']}",
        )
    )
    return {
        "id": internal_id,
        "public_id": public_id,
        "audit_record_number": (
            f"SYN-AUDIT-{target_type}-{scenario_id.rsplit('-', 1)[-1]}-"
            f"{history['state_version']:03d}"
        ),
        "entity_type": target_type,
        "entity_id": target_id,
        "event_type": step["event"],
        "actor_role": step["actor_role"],
        "actor_id": _actor_internal_id(step, user_ids),
        "state_version": history["state_version"],
        "idempotency_key": step["idempotency_key"],
        "correlation_id": step["correlation_id"],
        "occurred_at": step["occurred_at"],
        "data_classification": "synthetic",
    }


def _rebuild_event_records(
    config: dict[str, Any],
    workflows: list[dict[str, Any]],
    inquiries: list[dict[str, Any]],
    visits: list[dict[str, Any]],
    user_ids: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    namespace = uuid.UUID(config["uuid_namespace"])
    inquiry_by_scenario = {row["scenario_id"]: row for row in inquiries}
    visit_by_inquiry = {row["inquiry_id"]: row for row in visits}
    histories: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []

    def append_history(
        scenario_id: str,
        target_type: str,
        target_id: int,
        step: dict[str, Any],
        state_version: int,
        from_status: str | None,
        to_status: str,
    ) -> None:
        history = _history_row(
            namespace=namespace,
            internal_id=len(histories) + 1,
            scenario_id=scenario_id,
            target_type=target_type,
            target_id=target_id,
            step=step,
            state_version=state_version,
            from_status=from_status,
            to_status=to_status,
            user_ids=user_ids,
        )
        histories.append(history)
        audits.append(
            _audit_row(
                namespace=namespace,
                internal_id=len(audits) + 1,
                scenario_id=scenario_id,
                history=history,
                step=step,
                user_ids=user_ids,
            )
        )

    for workflow in workflows:
        scenario_id = workflow["scenario_id"]
        inquiry = inquiry_by_scenario[scenario_id]
        visit = visit_by_inquiry.get(inquiry["id"])
        for step in workflow["steps"]:
            append_history(
                scenario_id,
                "INQUIRY",
                inquiry["id"],
                step,
                step["state_version"],
                step["from_status"],
                step["to_status"],
            )
            if step.get("visit_to_status") is not None:
                if visit is None:
                    raise ValueError(
                        f"{scenario_id}:{step['event']} has no visit target"
                    )
                append_history(
                    scenario_id,
                    "VISIT",
                    visit["id"],
                    step,
                    step["visit_state_version"],
                    step.get("visit_from_status"),
                    step["visit_to_status"],
                )
    return histories, audits


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _api_idempotency_cases(
    workflows: list[dict[str, Any]],
    inquiries: list[dict[str, Any]],
    visits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    workflow = next(
        row for row in workflows if row["scenario_id"] == "SYN-JAC104-002"
    )
    inquiry = next(
        row for row in inquiries if row["scenario_id"] == "SYN-JAC104-002"
    )
    visit = next(row for row in visits if row["inquiry_id"] == inquiry["id"])
    step = next(row for row in workflow["steps"] if row["event"] == "CONFIRM_VISIT")
    payload = {
        "inquiry_public_id": inquiry["public_id"],
        "visit_public_id": visit["public_id"],
        "state_version": step["state_version"],
        "visit_state_version": step["visit_state_version"],
        "confirmed_at": step["occurred_at"],
    }
    changed_payload = {**payload, "confirmed_at": _timestamp(step["occurred_at"], 5)}
    response = {
        "http_status": 200,
        "response_body_sha256": _canonical_hash(
            {
                "inquiry_public_id": inquiry["public_id"],
                "visit_public_id": visit["public_id"],
                "inquiry_status": step["to_status"],
                "visit_status": step["visit_to_status"],
            }
        ),
        "resource_public_id": inquiry["public_id"],
    }
    common = {
        "scenario_id": "SYN-JAC104-002",
        "actor": {
            "public_id": step["actor_public_id"],
            "role_code": step["actor_role"],
        },
        "operation_id": "confirmVisit",
        "idempotency_key": step["idempotency_key"],
        "first_result": response,
    }
    return [
        {
            "case_id": "SYN-IDEMPOTENCY-CONFIRM-VISIT-FIRST",
            **common,
            "request_payload_sha256": _canonical_hash(payload),
            "replay": False,
            "expected_outcome": "PROCESSED",
            "internal_conflict_code": None,
            "expected_api_error_code": None,
            "expected_history_rows_created": 2,
        },
        {
            "case_id": "SYN-IDEMPOTENCY-CONFIRM-VISIT-REPLAY",
            **common,
            "request_payload_sha256": _canonical_hash(payload),
            "replay": True,
            "expected_outcome": "REPLAY",
            "internal_conflict_code": None,
            "expected_api_error_code": None,
            "expected_history_rows_created": 0,
        },
        {
            "case_id": "SYN-IDEMPOTENCY-CONFIRM-VISIT-CONFLICT",
            **common,
            "request_payload_sha256": _canonical_hash(changed_payload),
            "replay": False,
            "expected_outcome": "CONFLICT",
            "internal_conflict_code": "IDEMPOTENCY_KEY_REUSE_CONFLICT",
            "expected_api_error_code": "DUPLICATE-EVENT-01",
            "expected_history_rows_created": 0,
        },
    ]


def _rename_expected_inquiry_id(row: dict[str, Any]) -> None:
    if "inquiry_id" in row:
        row["inquiry_public_id"] = row.pop("inquiry_id")


def normalize(config: dict[str, Any]) -> dict[str, Any]:
    outputs = config["materialized_outputs"]
    workflows = outputs["workflow_states"]
    for workflow in workflows:
        _normalize_workflow(workflow)

    # Remove the legacy review-only visit before identifiers are converted.
    legacy_inquiries = {
        row["scenario_id"]: row for row in outputs["inquiries"]
    }
    review = legacy_inquiries["SYN-JAC104-008"]
    review_public_id = review.get("public_id", review.get("inquiry_id"))
    outputs["visits"] = [
        row
        for row in outputs["visits"]
        if row.get("inquiry_id") != review_public_id
        and row.get("inquiry_id") != review.get("id")
    ]

    identities = {
        "users": "user_id",
        "products": "product_id",
        "customer_products": "customer_product_id",
        "subscriptions": "subscription_id",
        "inquiries": "inquiry_id",
        "consultations": "consultation_id",
        "visits": "visit_id",
        "care_histories": "care_history_id",
        "followup_confirmations": "followup_id",
    }
    id_maps: dict[str, dict[str, int]] = {}
    for name, legacy_id in identities.items():
        outputs[name], id_maps[name] = _identity_rows(outputs[name], legacy_id)

    namespace = uuid.UUID(config["uuid_namespace"])
    customer_users = [
        row for row in outputs["users"] if row["role"] == "CUSTOMER"
    ]
    outputs["customer_profiles"] = [
        {
            "id": index,
            "public_id": str(
                uuid.uuid5(
                    namespace,
                    f"customer-profile:{user['public_id']}",
                )
            ),
            "customer_profile_number": f"SYN-CUSTOMER-{index:03d}",
            "user_id": user["id"],
            "customer_name": user["display_name"],
            "is_synthetic": True,
            "data_classification": "synthetic",
            "created_at": user["created_at"],
        }
        for index, user in enumerate(customer_users, 1)
    ]
    user_to_profile = {
        row["user_id"]: row["id"] for row in outputs["customer_profiles"]
    }

    for row in outputs["customer_products"]:
        row["customer_id"] = _fk(row["customer_id"], id_maps["users"])
        row["product_id"] = _fk(row["product_id"], id_maps["products"])
    for row in outputs["subscriptions"]:
        if "customer_id" in row:
            customer_id = _fk(row.pop("customer_id"), id_maps["users"])
            row["customer_profile_id"] = user_to_profile[customer_id]
        row["customer_product_id"] = _fk(
            row["customer_product_id"], id_maps["customer_products"]
        )
    for row in outputs["inquiries"]:
        row["customer_id"] = _fk(row["customer_id"], id_maps["users"])
        row["subscription_id"] = _fk(
            row["subscription_id"], id_maps["subscriptions"]
        )
        row["assigned_user_id"] = _fk(
            row.get("assigned_user_id"), id_maps["users"]
        )
    for row in outputs["consultations"]:
        row["inquiry_id"] = _fk(row["inquiry_id"], id_maps["inquiries"])
        row["consultant_id"] = _fk(
            row.get("consultant_id"), id_maps["users"]
        )
    for row in outputs["visits"]:
        row["inquiry_id"] = _fk(row["inquiry_id"], id_maps["inquiries"])
        row["technician_id"] = _fk(
            row.get("technician_id"), id_maps["users"]
        )
    for index, row in enumerate(outputs["care_histories"], 1):
        row["care_history_number"] = row.get(
            "care_history_number", f"SYN-CARE-{index:04d}"
        )
        row["customer_product_id"] = _fk(
            row["customer_product_id"], id_maps["customer_products"]
        )
        row["inquiry_id"] = _fk(
            row.get("inquiry_id"), id_maps["inquiries"]
        )
        row["visit_id"] = _fk(row.get("visit_id"), id_maps["visits"])
    for index, row in enumerate(outputs["followup_confirmations"], 1):
        row["followup_number"] = row.get(
            "followup_number", f"SYN-FOLLOWUP-{index:04d}"
        )
        row["inquiry_id"] = _fk(row["inquiry_id"], id_maps["inquiries"])
        row["consultation_id"] = _fk(
            row.get("consultation_id"), id_maps["consultations"]
        )
        row["visit_id"] = _fk(row.get("visit_id"), id_maps["visits"])

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

    inquiry_by_scenario = {
        row["scenario_id"]: row for row in outputs["inquiries"]
    }
    workflow_by_scenario = {row["scenario_id"]: row for row in workflows}
    visit_by_inquiry = {row["inquiry_id"]: row for row in outputs["visits"]}
    histories, audits = _rebuild_event_records(
        config,
        workflows,
        outputs["inquiries"],
        outputs["visits"],
        id_maps["users"],
    )
    outputs["inquiry_status_histories"] = histories
    outputs["audit_events"] = audits

    for scenario_id, inquiry in inquiry_by_scenario.items():
        workflow = workflow_by_scenario[scenario_id]
        last_step = workflow["steps"][-1]
        assigned_role, assigned_user_id = _assignment(
            last_step,
            visit_by_inquiry.get(inquiry["id"]),
            id_maps["users"],
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

    for row in outputs["demo_scenarios"]["scenarios"]:
        _rename_expected_inquiry_id(row)
        row["expected_outcome"] = final_statuses[row["scenario_id"]]
    for container in config["materialized_subsets"].values():
        for row in container:
            _rename_expected_inquiry_id(row)
            row["expected_outcome"] = final_statuses[row["scenario_id"]]
    for name in ("evidence_references", "safety_assessments", "role_handoffs"):
        for row in outputs[name]:
            _rename_expected_inquiry_id(row)

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

    config["outputs"]["api_idempotency_cases"] = (
        "synthetic/expected/api_idempotency_cases.json"
    )
    config["outputs"]["customer_profiles"] = (
        "synthetic/fixtures/customer_profiles.json"
    )
    outputs["api_idempotency_cases"] = _api_idempotency_cases(
        workflows,
        outputs["inquiries"],
        outputs["visits"],
    )
    config["config_version"] = "2.0.0"
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
                "source_scenarios": len(normalized["scenario_matrix"]),
                "active_projection_scenarios": (
                    len(normalized["scenario_matrix"]) - len(BLOCKED_SCENARIOS)
                ),
                "source_status_histories": len(
                    normalized["materialized_outputs"][
                        "inquiry_status_histories"
                    ]
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
