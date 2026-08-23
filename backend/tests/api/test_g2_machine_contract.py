"""G2 OpenAPI 계약을 Runtime·DB 없이 정적으로 검증한다."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_DIR = REPOSITORY_ROOT / "contracts" / "api"
OPENAPI_PATH = API_DIR / "openapi.yaml"
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}

G2_OPERATIONS = {
    ("/inquiries/unassigned-consultations", "get"): (
        "listUnassignedConsultationInquiries"
    ),
    ("/inquiries/{id}/claim-consultation", "post"): (
        "claimConsultation"
    ),
    ("/inquiries", "get"): "listConsultantInquiries",
    ("/inquiries/{id}", "get"): "getConsultantInquiryDetail",
    ("/inquiries/{id}/start-consultation", "post"): (
        "startConsultation"
    ),
    ("/inquiries/{id}/consultation-summary", "patch"): (
        "updateConsultationSummary"
    ),
    ("/inquiries/{id}/consultation-summary/confirm", "post"): (
        "confirmConsultationSummary"
    ),
    ("/inquiries/{id}/complete-consultation", "post"): (
        "completeConsultation"
    ),
    ("/inquiries/{id}/visit-review", "post"): "requestVisitReview",
    ("/inquiries/{id}/visits", "post"): "createVisitRequest",
    ("/inquiries/{id}/visit-not-needed", "post"): (
        "markVisitNotNeeded"
    ),
    ("/visits/{visit_id}/schedule", "patch"): (
        "updateVisitSchedule"
    ),
    ("/visits/{visit_id}/confirm", "post"): "confirmVisit",
}

WRITE_G2_OPERATIONS = {
    key: operation_id
    for key, operation_id in G2_OPERATIONS.items()
    if key[1] != "get"
}

IMPLEMENTED_G2_OPERATIONS = set(G2_OPERATIONS)

EXAMPLE_PATHS = {
    "inquiry_list": (
        API_DIR
        / "examples"
        / "inquiries"
        / "consultant-inquiry-list-success.json"
    ),
    "inquiry_detail": (
        API_DIR
        / "examples"
        / "inquiries"
        / "consultant-inquiry-detail-success.json"
    ),
    "consultation_save": (
        API_DIR
        / "examples"
        / "consultations"
        / "save-consultation-request.json"
    ),
    "visit_create": (
        API_DIR
        / "examples"
        / "visits"
        / "create-visit-request.json"
    ),
    "visit_schedule": (
        API_DIR
        / "examples"
        / "visits"
        / "update-visit-schedule-request.json"
    ),
}

DENIED_PII_OR_INTERNAL_FIELDS = {
    "actual_address",
    "actual_customer_name",
    "actual_phone",
    "db_id",
    "email",
    "internal_pk",
    "raw_address",
    "raw_customer_name",
    "raw_phone",
    "resident_registration_number",
    "source_storage_path",
    "vector_chunk_id",
}


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_json_pointer(document: Any, fragment: str) -> Any:
    current = document
    pointer = fragment.removeprefix("/")
    if not pointer:
        return current
    for token in pointer.split("/"):
        decoded = token.replace("~1", "/").replace("~0", "~")
        current = current[decoded]
    return current


def resolve_reference(source_path: Path, reference: str):
    external_path, _, fragment = reference.partition("#")
    target_path = (
        source_path
        if not external_path
        else (source_path.parent / external_path).resolve()
    )
    assert target_path.is_file(), (
        f"{source_path.relative_to(REPOSITORY_ROOT)}: "
        f"missing $ref target {reference}"
    )
    document = load_yaml(target_path)
    target = resolve_json_pointer(document, fragment)
    return target_path, fragment, target


def load_path_item(raw_path_item: dict[str, Any]) -> dict[str, Any]:
    reference = raw_path_item.get("$ref")
    if reference is None:
        return raw_path_item
    _, _, path_item = resolve_reference(OPENAPI_PATH, reference)
    return path_item


def collect_operations() -> dict[tuple[str, str], dict[str, Any]]:
    specification = load_yaml(OPENAPI_PATH)
    operations = {}
    for api_path, raw_path_item in specification["paths"].items():
        path_item = load_path_item(raw_path_item)
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                operations[(api_path, method)] = operation
    return operations


def walk_references(
    source_path: Path,
    node: Any,
    visited: set[tuple[Path, str]],
) -> None:
    if isinstance(node, dict):
        reference = node.get("$ref")
        if reference is not None:
            target_path, fragment, target = resolve_reference(
                source_path, reference
            )
            identity = (target_path, fragment)
            if identity not in visited:
                visited.add(identity)
                walk_references(target_path, target, visited)
        for key, value in node.items():
            if key != "$ref":
                walk_references(source_path, value, visited)
    elif isinstance(node, list):
        for value in node:
            walk_references(source_path, value, visited)


def iter_property_names(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            yield from properties
        for value in node.values():
            yield from iter_property_names(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_property_names(value)


def iter_mapping_keys(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from iter_mapping_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_mapping_keys(value)


def iter_string_values(node: Any) -> Iterable[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from iter_string_values(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_string_values(value)


def normalize_rule_ids(value: str | list[str]) -> list[str]:
    return value if isinstance(value, list) else [value]


def test_g2_operation_inventory_crosswalk_and_runtime_boundary():
    root = load_yaml(OPENAPI_PATH)
    operations = collect_operations()
    crosswalk = load_yaml(API_DIR / "g2-operation-crosswalk.yaml")
    crosswalk_operations = {
        (item["path"], item["method"].lower()): item
        for item in crosswalk["operations"]
    }

    assert root["info"]["version"] == "0.9.0"
    assert len(operations) == 49
    assert len({item["operationId"] for item in operations.values()}) == 49
    assert set(crosswalk_operations) == set(G2_OPERATIONS)
    assert crosswalk["contract"]["included_decisions"] == [
        "DEC-001",
        "DEC-002",
        "DEC-003",
        "DEC-004",
        "DEC-005",
        "DEC-007",
        "DEC-009",
        "PM-20260823-CONSULTANT-CLAIM",
    ]
    assert crosswalk["contract"]["excluded_decisions"] == [
        "DEC-006",
        "DEC-008",
    ]
    assert crosswalk["contract"][
        "runtime_implementation_start_allowed"
    ] is False

    for key, operation_id in G2_OPERATIONS.items():
        operation = operations[key]
        crosswalk_item = crosswalk_operations[key]
        expected_runtime_status = (
            "IMPLEMENTED"
            if key in IMPLEMENTED_G2_OPERATIONS
            else "NOT_IMPLEMENTED"
        )
        assert operation["operationId"] == operation_id
        assert operation["x-contract-status"] == "CONFIRMED"
        assert operation["x-runtime-status"] == expected_runtime_status
        assert crosswalk_item["operation_id"] == operation_id
        assert crosswalk_item["runtime_status"] == expected_runtime_status
        assert crosswalk_item["permission_scope"] == (
            operation["x-permission-scope"]
        )

        if crosswalk_item["event"] is None:
            assert "x-state-machine" not in operation
            continue

        state_contract = operation["x-state-machine"]
        assert state_contract["event"] == crosswalk_item["event"]
        actual_rules = state_contract.get("transition_rules")
        if actual_rules is None:
            actual_rules = [state_contract["transition_rule"]]
        assert actual_rules == normalize_rule_ids(
            crosswalk_item["transition_rule"]
        )


def test_update_visit_schedule_includes_revisit_transition_tr_inq_028():
    operation = collect_operations()[
        ("/visits/{visit_id}/schedule", "patch")
    ]
    crosswalk = load_yaml(API_DIR / "g2-operation-crosswalk.yaml")
    crosswalk_item = next(
        item
        for item in crosswalk["operations"]
        if item["operation_id"] == "updateVisitSchedule"
    )
    rules = {
        item["id"]: item
        for item in load_yaml(
            REPOSITORY_ROOT
            / "contracts"
            / "state-machine"
            / "transition-rules.yaml"
        )["transitions"]
    }

    assert operation["x-state-machine"] == {
        "event": "UPDATE_VISIT_SCHEDULE",
        "transition_rules": [
            "TR-INQ-020",
            "TR-INQ-021",
            "TR-INQ-028",
        ],
        "inquiry_states": ["VISIT_SCHEDULING", "REVISIT_REQUIRED"],
        "visit_from_statuses": [
            "ASSIGNING",
            "SCHEDULING",
            "FOLLOW_UP_REQUIRED",
        ],
        "visit_to_status": "SCHEDULING",
    }
    assert crosswalk_item["transition_rule"] == [
        "TR-INQ-020",
        "TR-INQ-021",
        "TR-INQ-028",
    ]
    revisit = rules["TR-INQ-028"]
    assert revisit["from_inquiry_state"] == "REVISIT_REQUIRED"
    assert revisit["to_inquiry_state"] == "VISIT_SCHEDULING"
    assert revisit["visit"] == {
        "mode": "TRANSITION",
        "from_status": "FOLLOW_UP_REQUIRED",
        "to_status": "SCHEDULING",
    }
    assert "G-ASSIGNED-CONSULTANT" in revisit["guard_refs"]


def test_all_g2_external_references_resolve():
    root = load_yaml(OPENAPI_PATH)
    visited: set[tuple[Path, str]] = set()

    for api_path, _ in G2_OPERATIONS:
        walk_references(
            OPENAPI_PATH,
            root["paths"][api_path],
            visited,
        )

    assert visited


def test_visit_contract_is_date_only_and_server_controls_status():
    schema_dir = API_DIR / "components" / "schemas" / "visit"
    create = load_yaml(schema_dir / "CreateVisitRequest.yaml")
    update = load_yaml(schema_dir / "UpdateVisitScheduleRequest.yaml")
    confirm = load_yaml(schema_dir / "ConfirmVisitRequest.yaml")
    schedule = load_yaml(schema_dir / "VisitSchedule.yaml")

    assert create["properties"]["preferred_date"]["format"] == "date"
    assert "synthetic_technician_id" not in create["properties"]
    assert "confirmed_date" not in create["properties"]

    for field in ("preferred_date", "confirmed_date"):
        assert update["properties"][field]["format"] == "date"
        assert schedule["properties"][field]["format"] == "date"
    assert "schedule_status" not in update["properties"]
    assert set(confirm["properties"]) == {"state_version"}

    forbidden_time_fields = {
        "scheduled_at",
        "scheduled_end_at",
        "scheduled_start_at",
    }
    assert not (
        forbidden_time_fields
        & set(iter_property_names([create, update, confirm, schedule]))
    )

    create_example = load_json(EXAMPLE_PATHS["visit_create"])
    update_example = load_json(EXAMPLE_PATHS["visit_schedule"])
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    assert date_pattern.fullmatch(create_example["preferred_date"])
    assert date_pattern.fullmatch(update_example["preferred_date"])
    assert date_pattern.fullmatch(update_example["confirmed_date"])
    assert "synthetic_technician_id" not in create_example
    assert "schedule_status" not in update_example


def test_assigned_consultant_guards_and_object_concealment_are_required():
    operations = collect_operations()
    rules_document = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "transition-rules.yaml"
    )
    guards_document = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "transition-guards.yaml"
    )
    roles = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "role-permissions.yaml"
    )
    matrix = load_yaml(API_DIR / "g2-error-matrix.yaml")
    rules = {item["id"]: item for item in rules_document["transitions"]}
    assigned_guard = next(
        item
        for item in guards_document["guards"]
        if item["id"] == "G-ASSIGNED-CONSULTANT"
    )
    guards = {
        item["id"]: item for item in guards_document["guards"]
    }

    assert assigned_guard["failure"] == {
        "http_status": 404,
        "error_code": "RESOURCE_NOT_FOUND",
        "message": "문의를 찾을 수 없습니다.",
    }
    assert roles["default_policy"]["resource_access_failure_status"] == 404
    assert roles["default_policy"]["role_failure_status"] == 403
    assert matrix["object_concealment"] == {
        "wrong_role": 403,
        "missing_object": 404,
        "unassigned_object": 404,
        "inactive_assignment": 404,
    }

    for key in WRITE_G2_OPERATIONS:
        operation = operations[key]
        assert {"401", "403", "404", "409", "422", "500"} <= set(
            operation["responses"]
        )
        state_contract = operation["x-state-machine"]
        rule_ids = state_contract.get("transition_rules")
        if rule_ids is None:
            rule_ids = [state_contract["transition_rule"]]
        if key == ("/inquiries/{id}/claim-consultation", "post"):
            assert operation["x-permission-scope"] == (
                "UNASSIGNED_CONSULTATION_QUEUE"
            )
            assert rule_ids == ["TR-INQ-037"]
            assert {
                "G-ACTOR-CONSULTANT",
                "G-UNASSIGNED-CONSULTATION-CLAIMABLE",
            } <= set(rules["TR-INQ-037"]["guard_refs"])
            continue

        assert operation["x-permission-scope"] == "ASSIGNED_INQUIRIES"
        for rule_id in rule_ids:
            assert {
                "G-ACTOR-CONSULTANT",
                "G-ASSIGNED-CONSULTANT",
            } <= set(rules[rule_id]["guard_refs"])

    detail = operations[("/inquiries/{id}", "get")]
    assert "존재 여부를 숨기기 위해 404" in detail["description"]
    assert detail["responses"]["404"] == {
        "$ref": "../components/responses/NotFound.yaml"
    }
    for guard_id in (
        "G-VISIT-REVIEW-PAYLOAD-VALID",
        "G-VISIT-HANDOFF-COMPLETE",
        "G-VISIT-NOT-NEEDED-RESULT-COMPLETE",
    ):
        assert "consultation.result_code == VISIT_REQUIRED" in guards[
            guard_id
        ]["conditions"]
    assert "SET_CONSULTATION_RESULT_COMPLETED_NO_VISIT" in rules[
        "TR-INQ-034"
    ]["effects"]


def test_ai_processing_timeout_contract_is_internal_and_fail_closed():
    events_document = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "inquiry-events.yaml"
    )
    rules_document = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "transition-rules.yaml"
    )
    guards_document = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "transition-guards.yaml"
    )
    roles_document = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "role-permissions.yaml"
    )
    events = {item["code"]: item for item in events_document["events"]}
    rules = {item["id"]: item for item in rules_document["transitions"]}
    guards = {item["id"]: item for item in guards_document["guards"]}
    roles = {item["code"]: item for item in roles_document["roles"]}

    event = events["AI_PROCESSING_TIMEOUT"]
    assert event["actor_roles"] == ["SYSTEM"]
    assert event["requires_state_version"] is True
    assert event["external_action"] == {
        "exposed": False,
        "operation_id": None,
    }
    rule = rules["TR-INQ-036"]
    assert rule["event"] == "AI_PROCESSING_TIMEOUT"
    assert rule["from_inquiry_state"] == "QUESTIONNAIRE_IN_PROGRESS"
    assert rule["to_inquiry_state"] == "CONSULTATION_REQUIRED"
    assert rule["visit"] == {"mode": "REQUIRE_ABSENT"}
    assert "G-AI-PROCESSING-TIMEOUT-VALID" in rule["guard_refs"]
    assert "DO_NOT_CREATE_CONSULTATION" in rule["effects"]
    assert guards["G-AI-PROCESSING-TIMEOUT-VALID"]["failure"] == {
        "http_status": 409,
        "error_code": "AI_PROCESSING_TIMEOUT_PRECONDITION_FAILED",
        "message": "AI 처리 시간 초과 전환 조건을 충족하지 못했습니다.",
        "expose_to_external_client": False,
    }
    assert "AI_PROCESSING_TIMEOUT" in roles["SYSTEM"]["allowed_events"]


def test_error_matrix_separates_role_object_and_workflow_conflicts():
    matrix = load_yaml(API_DIR / "g2-error-matrix.yaml")
    registry = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "error-codes"
        / "error-codes.yaml"
    )
    registry_codes = {item["code"] for item in registry["errors"]}
    errors_by_status: dict[int, list[dict[str, Any]]] = {}
    for item in matrix["errors"]:
        errors_by_status.setdefault(item["http_status"], []).append(item)

    assert {item["code"] for item in errors_by_status[403]} == {
        "FORBIDDEN"
    }
    assert {item["code"] for item in errors_by_status[404]} == {
        "RESOURCE_NOT_FOUND"
    }
    assert {item["code"] for item in errors_by_status[409]} == {
        "STATE-CONFLICT-01",
        "DUPLICATE-EVENT-01",
    }
    assert {
        "FORBIDDEN",
        "RESOURCE_NOT_FOUND",
        "STATE-CONFLICT-01",
        "DUPLICATE-EVENT-01",
    } <= registry_codes
    assert matrix["workflow_conflict_wire"] == {
        "schema": "WorkflowConflictResponse",
        "state_conflict_allowed_actions_shape": "array_of_string_codes",
        "normal_success_allowed_actions_shape": (
            "array_of_AllowedAction_objects"
        ),
    }


def test_dec007_uses_closed_synthetic_projections_and_excludes_evidence():
    inquiry_schema_dir = API_DIR / "components" / "schemas" / "inquiry"
    visit_schema_dir = API_DIR / "components" / "schemas" / "visit"
    customer = load_yaml(
        inquiry_schema_dir / "ConsultantCustomerProjection.yaml"
    )
    technician = load_yaml(
        visit_schema_dir / "SyntheticTechnicianProjection.yaml"
    )
    list_item = load_yaml(
        inquiry_schema_dir / "ConsultantInquiryListItem.yaml"
    )
    detail = load_yaml(inquiry_schema_dir / "ConsultantInquiryDetail.yaml")
    operations = collect_operations()

    for projection in (customer, technician, list_item, detail):
        assert projection["additionalProperties"] is False
        assert not (
            DENIED_PII_OR_INTERNAL_FIELDS
            & set(iter_property_names(projection))
        )
    for projection in (customer, technician):
        assert projection["properties"]["is_synthetic"] == {
            "type": "boolean",
            "const": True,
        }

    assert set(customer["properties"]) == {
        "is_synthetic",
        "display_name",
        "phone",
    }
    assert "customer_display_name_masked" in list_item["properties"]
    assert "phone" not in list_item["properties"]
    assert "address" not in list_item["properties"]
    assert "evidence" not in detail["properties"]

    detail_operation = operations[("/inquiries/{id}", "get")]
    assert detail_operation["x-excluded-decisions"] == ["DEC-008"]
    detail_ref_values = {
        value
        for value in iter_string_values(detail)
        if value.startswith(("./", "../"))
        and "evidence" in value.lower()
    }
    assert not detail_ref_values


def test_dec009_excludes_server_draft_and_defers_web_runtime():
    operations = collect_operations()
    operation = operations[
        ("/inquiries/{id}/consultation-summary", "patch")
    ]
    policy = load_yaml(
        REPOSITORY_ROOT
        / "contracts"
        / "state-machine"
        / "consultation-draft-policy.yaml"
    )

    assert operation["operationId"] == "updateConsultationSummary"
    assert operation["x-dec009-boundary"] == "USER_TRIGGERED_SAVE_ONLY"
    assert operation["x-dec009-web-status"] == "DEFERRED_TO_WEB"
    assert "자동저장" in operation["description"]
    assert "서버 Draft" in operation["description"]

    assert policy["scope"]["backend_api_change_required"] is False
    assert policy["scope"]["server_persistence_required"] is False
    assert {"SERVER_DRAFT", "BACKGROUND_AUTOSAVE"} <= set(
        policy["storage"]["forbidden"]
    )
    assert policy["explicit_save_boundary"] == {
        "decision_id": "DEC-003",
        "action": "UPDATE_CONSULTATION_SUMMARY",
        "server_write_allowed": True,
        "user_initiated_only": True,
        "background_invocation": "DENY",
    }
    assert policy["implementation_gate"]["web_runtime_status"] == (
        "DEFERRED_UNTIL_CONSUMER_INTEGRATION_GATE"
    )
    assert policy["implementation_gate"]["backend_runtime_status"] == (
        "NOT_REQUIRED"
    )

    operation_ids = {
        item["operationId"].lower() for item in operations.values()
    }
    assert not any(
        marker in operation_id
        for operation_id in operation_ids
        for marker in ("autosave", "restoredraft", "serverdraft")
    )


def test_g2_code_catalogs_match_state_and_schema_enums():
    code_dir = REPOSITORY_ROOT / "contracts" / "codes"
    state_dir = REPOSITORY_ROOT / "contracts" / "state-machine"
    inquiry_schema_dir = API_DIR / "components" / "schemas" / "inquiry"
    visit_schema_dir = API_DIR / "components" / "schemas" / "visit"
    consultation_schema_dir = (
        API_DIR / "components" / "schemas" / "consultation"
    )

    states = load_yaml(state_dir / "inquiry-states.yaml")
    actions = load_yaml(state_dir / "allowed-actions.yaml")
    list_item = load_yaml(
        inquiry_schema_dir / "ConsultantInquiryListItem.yaml"
    )
    visit_schedule = load_yaml(visit_schema_dir / "VisitSchedule.yaml")
    save_consultation = load_yaml(
        consultation_schema_dir / "SaveConsultationRequest.yaml"
    )
    consultation_record = load_yaml(
        consultation_schema_dir / "ConsultationRecord.yaml"
    )
    visit_review = load_yaml(
        visit_schema_dir / "VisitReviewRequest.yaml"
    )
    visit_not_needed = load_yaml(
        visit_schema_dir / "VisitNotNeededRequest.yaml"
    )

    inquiry_codes = load_yaml(code_dir / "inquiry-statuses.yaml")["codes"]
    workflow_codes = load_yaml(code_dir / "workflow-actions.yaml")["codes"]
    visit_codes = load_yaml(code_dir / "visit-statuses.yaml")["codes"]
    priority_codes = load_yaml(code_dir / "priority-levels.yaml")["codes"]
    risk_codes = load_yaml(code_dir / "risk-levels.yaml")["codes"]
    guidance_codes = load_yaml(
        code_dir / "usage-guidance-statuses.yaml"
    )["codes"]
    consultation_result_codes = load_yaml(
        code_dir / "consultation-result-codes.yaml"
    )["codes"]
    visit_review_codes = load_yaml(
        code_dir / "visit-review-reason-codes.yaml"
    )["codes"]
    visit_not_needed_codes = load_yaml(
        code_dir / "visit-not-needed-reason-codes.yaml"
    )["codes"]

    assert inquiry_codes == [item["code"] for item in states["states"]]
    assert set(inquiry_codes) == set(
        list_item["properties"]["status"]["enum"]
    )
    list_data = load_yaml(
        inquiry_schema_dir / "ConsultantInquiryListData.yaml"
    )
    workflow_schema_dir = (
        API_DIR / "components" / "schemas" / "workflow"
    )
    transition_result = load_yaml(
        workflow_schema_dir / "StateTransitionResult.yaml"
    )
    workflow_snapshot = load_yaml(
        workflow_schema_dir / "WorkflowSnapshot.yaml"
    )
    assert set(inquiry_codes) == set(
        list_data["properties"]["status_counts"]["propertyNames"][
            "enum"
        ]
    )
    assert set(inquiry_codes) == set(
        transition_result["properties"]["status"]["enum"]
    )
    assert set(inquiry_codes) == set(
        workflow_snapshot["properties"]["status"]["enum"]
    )
    assert workflow_codes == [
        item["code"] for item in actions["action_catalog"]
    ]
    assert visit_codes == states["visit_status_codes"]
    assert set(visit_codes) == set(
        visit_schedule["properties"]["schedule_status"]["enum"]
    )
    assert set(priority_codes) == set(
        list_item["properties"]["priority"]["enum"]
    )
    assert set(risk_codes) == set(
        list_item["properties"]["risk_level"]["enum"]
    )
    assert set(guidance_codes) == set(
        save_consultation["properties"]["usage_guidance_status"][
            "enum"
        ]
    )
    assert set(consultation_result_codes) == set(
        save_consultation["properties"]["result_code"]["enum"]
    )
    assert set(consultation_result_codes) == set(
        consultation_record["properties"]["result_code"]["enum"]
    )
    assert "outcome" not in consultation_record["properties"]
    assert set(visit_review_codes) == set(
        visit_review["properties"]["reason_code"]["enum"]
    )
    assert set(visit_not_needed_codes) == set(
        visit_not_needed["properties"]["reason_code"]["enum"]
    )


def test_g2_examples_are_synthetic_parseable_and_evidence_free():
    examples = {name: load_json(path) for name, path in EXAMPLE_PATHS.items()}

    assert set(examples) == {
        "inquiry_list",
        "inquiry_detail",
        "consultation_save",
        "visit_create",
        "visit_schedule",
    }
    detail = examples["inquiry_detail"]
    customer = detail["data"]["customer"]
    assert customer["is_synthetic"] is True
    assert "합성" in customer["display_name"]
    assert customer["phone"].startswith("010-0000-")
    assert examples["inquiry_list"]["data"]["items"][0][
        "customer_display_name_masked"
    ].endswith("*")

    for example in examples.values():
        keys = set(iter_mapping_keys(example))
        assert "evidence" not in keys
        assert not (DENIED_PII_OR_INTERNAL_FIELDS & keys)
