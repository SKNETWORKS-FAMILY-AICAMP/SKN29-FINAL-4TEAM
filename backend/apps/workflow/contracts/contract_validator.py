"""상태 머신 YAML 계약의 rich schema와 교차 참조를 검증한다."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


DOCUMENT_NAMES = (
    "states",
    "events",
    "transitions",
    "guards",
    "allowed_actions",
    "role_permissions",
)
CONTRACT_NAMES = {
    "states": "inquiry-states",
    "events": "inquiry-events",
    "transitions": "transition-rules",
    "guards": "transition-guards",
    "allowed_actions": "allowed-actions",
    "role_permissions": "role-permissions",
}


class StateMachineContractValidationError(ValueError):
    """계약 오류를 한 번에 반환하는 fail-closed 예외."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(errors)
        message = "상태 머신 계약 검증에 실패했습니다."
        if self.errors:
            message = f"{message}\n- " + "\n- ".join(self.errors)
        super().__init__(message)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _duplicate_values(values: Sequence[str]) -> list[str]:
    return sorted(
        value for value, count in Counter(values).items() if count > 1
    )


def _string_list(
    value: Any,
    *,
    path: str,
    errors: list[str],
    require_nonempty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{path}: list여야 합니다.")
        return []
    if require_nonempty and not value:
        errors.append(f"{path}: 하나 이상의 값이 필요합니다.")
        return []

    result: list[str] = []
    for index, item in enumerate(value):
        if not _is_nonempty_string(item):
            errors.append(
                f"{path}[{index}]: 비어 있지 않은 문자열이어야 합니다."
            )
            continue
        result.append(item.strip())

    for duplicate in _duplicate_values(result):
        errors.append(f"{path}: 중복 값 {duplicate!r}이 있습니다.")
    return result


def _required_string(
    entry: Mapping[str, Any],
    key: str,
    *,
    path: str,
    errors: list[str],
) -> str | None:
    value = entry.get(key)
    if not _is_nonempty_string(value):
        errors.append(f"{path}.{key}: 비어 있지 않은 문자열이어야 합니다.")
        return None
    return value.strip()


def _required_mapping(
    value: Any,
    *,
    path: str,
    errors: list[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        errors.append(f"{path}: 비어 있지 않은 mapping이어야 합니다.")
        return {}
    return value


def _mapping_entries(
    value: Any,
    *,
    path: str,
    errors: list[str],
    require_nonempty: bool = True,
) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{path}: list여야 합니다.")
        return []
    if require_nonempty and not value:
        errors.append(f"{path}: 하나 이상의 항목이 필요합니다.")
        return []

    entries: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or not item:
            errors.append(
                f"{path}[{index}]: 비어 있지 않은 mapping이어야 합니다."
            )
            continue
        entries.append(item)
    return entries


def _document(
    documents: Mapping[str, Any],
    name: str,
    errors: list[str],
) -> Mapping[str, Any]:
    value = documents.get(name)
    if not isinstance(value, Mapping) or not value:
        errors.append(f"{name}: 비어 있지 않은 mapping 계약이어야 합니다.")
        return {}
    return value


def _validate_contract_header(
    document: Mapping[str, Any],
    document_name: str,
    errors: list[str],
) -> None:
    header = _required_mapping(
        document.get("contract"),
        path=f"{document_name}.contract",
        errors=errors,
    )
    if not header:
        return

    contract_name = _required_string(
        header,
        "name",
        path=f"{document_name}.contract",
        errors=errors,
    )
    expected_name = CONTRACT_NAMES[document_name]
    if contract_name is not None and contract_name != expected_name:
        errors.append(
            f"{document_name}.contract.name: "
            f"{expected_name!r}이어야 합니다."
        )
    for key in ("version", "status", "owner"):
        _required_string(
            header,
            key,
            path=f"{document_name}.contract",
            errors=errors,
        )


def _code_index(
    entries: list[Mapping[str, Any]],
    *,
    path: str,
    errors: list[str],
    key: str = "code",
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for index, entry in enumerate(entries):
        entry_path = f"{path}[{index}]"
        code = _required_string(entry, key, path=entry_path, errors=errors)
        if code is None:
            continue
        if code in result:
            errors.append(f"{path}: {key} {code!r}가 중복됩니다.")
            continue
        result[code] = entry
    return result


def _validate_reference(
    value: str | None,
    registry: set[str],
    *,
    path: str,
    registry_name: str,
    errors: list[str],
) -> None:
    if value is not None and value not in registry:
        errors.append(
            f"{path}: 등록되지 않은 {registry_name} {value!r}입니다."
        )


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _freeze(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _validate_states(
    document: Mapping[str, Any],
    errors: list[str],
) -> tuple[dict[str, Mapping[str, Any]], set[str], set[str]]:
    entries = _mapping_entries(
        document.get("states"),
        path="states.states",
        errors=errors,
    )
    state_by_code = _code_index(
        entries,
        path="states.states",
        errors=errors,
    )
    state_codes = set(state_by_code)
    owner_types = set(
        _string_list(
            document.get("owner_types"),
            path="states.owner_types",
            errors=errors,
        )
    )
    visit_statuses = set(
        _string_list(
            document.get("visit_status_codes"),
            path="states.visit_status_codes",
            errors=errors,
        )
    )
    terminal_states = set(
        _string_list(
            document.get("terminal_states"),
            path="states.terminal_states",
            errors=errors,
        )
    )
    initial_state = (
        document.get("initial_state").strip()
        if _is_nonempty_string(document.get("initial_state"))
        else None
    )
    if initial_state is None:
        errors.append(
            "states.initial_state: 비어 있지 않은 문자열이어야 합니다."
        )
    _validate_reference(
        initial_state,
        state_codes,
        path="states.initial_state",
        registry_name="state",
        errors=errors,
    )
    for terminal in sorted(terminal_states):
        _validate_reference(
            terminal,
            state_codes,
            path="states.terminal_states",
            registry_name="state",
            errors=errors,
        )

    terminal_flags: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"states.states[{index}]"
        code = entry.get("code")
        owner_type = _required_string(
            entry,
            "owner_type",
            path=path,
            errors=errors,
        )
        _validate_reference(
            owner_type,
            owner_types,
            path=f"{path}.owner_type",
            registry_name="owner_type",
            errors=errors,
        )
        terminal = entry.get("terminal")
        if not isinstance(terminal, bool):
            errors.append(f"{path}.terminal: boolean이어야 합니다.")
        elif terminal and _is_nonempty_string(code):
            terminal_flags.add(code.strip())

        allowed_visit_statuses = _string_list(
            entry.get("allowed_visit_statuses"),
            path=f"{path}.allowed_visit_statuses",
            errors=errors,
            require_nonempty=False,
        )
        for visit_status in allowed_visit_statuses:
            _validate_reference(
                visit_status,
                visit_statuses,
                path=f"{path}.allowed_visit_statuses",
                registry_name="visit status",
                errors=errors,
            )

    for missing in sorted(terminal_states - terminal_flags):
        errors.append(
            f"states.terminal_states: {missing!r}의 terminal 플래그가 "
            "true가 아닙니다."
        )
    for extra in sorted(terminal_flags - terminal_states):
        errors.append(
            f"states.states: terminal=true인 {extra!r}가 "
            "terminal_states에 없습니다."
        )
    return state_by_code, terminal_states, visit_statuses


def _validate_events(
    document: Mapping[str, Any],
    errors: list[str],
) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    categories = set(
        _string_list(
            document.get("categories"),
            path="events.categories",
            errors=errors,
        )
    )
    scopes = set(
        _string_list(
            document.get("scopes"),
            path="events.scopes",
            errors=errors,
        )
    )
    actor_role_codes = set(
        _string_list(
            document.get("actor_roles"),
            path="events.actor_roles",
            errors=errors,
        )
    )
    entries = _mapping_entries(
        document.get("events"),
        path="events.events",
        errors=errors,
    )
    event_by_code = _code_index(
        entries,
        path="events.events",
        errors=errors,
    )

    for index, entry in enumerate(entries):
        path = f"events.events[{index}]"
        category = _required_string(
            entry,
            "category",
            path=path,
            errors=errors,
        )
        scope = _required_string(entry, "scope", path=path, errors=errors)
        _validate_reference(
            category,
            categories,
            path=f"{path}.category",
            registry_name="event category",
            errors=errors,
        )
        _validate_reference(
            scope,
            scopes,
            path=f"{path}.scope",
            registry_name="event scope",
            errors=errors,
        )
        actor_roles = _string_list(
            entry.get("actor_roles"),
            path=f"{path}.actor_roles",
            errors=errors,
        )
        for role in actor_roles:
            _validate_reference(
                role,
                actor_role_codes,
                path=f"{path}.actor_roles",
                registry_name="actor role",
                errors=errors,
            )

        for key in (
            "changes_inquiry_state",
            "changes_visit_state",
            "requires_idempotency_key",
            "requires_state_version",
        ):
            if not isinstance(entry.get(key), bool):
                errors.append(f"{path}.{key}: boolean이어야 합니다.")

        external_action = _required_mapping(
            entry.get("external_action"),
            path=f"{path}.external_action",
            errors=errors,
        )
        if not external_action:
            continue
        exposed = external_action.get("exposed")
        operation_id = external_action.get("operation_id")
        if not isinstance(exposed, bool):
            errors.append(
                f"{path}.external_action.exposed: boolean이어야 합니다."
            )
        elif exposed and not _is_nonempty_string(operation_id):
            errors.append(
                f"{path}.external_action.operation_id: "
                "외부 행동에는 operation_id가 필요합니다."
            )
        elif not exposed and operation_id is not None:
            errors.append(
                f"{path}.external_action.operation_id: "
                "내부 이벤트에서는 null이어야 합니다."
            )

    return event_by_code, actor_role_codes


def _validate_guards(
    document: Mapping[str, Any],
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    categories = set(
        _string_list(
            document.get("guard_categories"),
            path="guards.guard_categories",
            errors=errors,
        )
    )
    entries = _mapping_entries(
        document.get("guards"),
        path="guards.guards",
        errors=errors,
    )
    guard_by_id = _code_index(
        entries,
        path="guards.guards",
        errors=errors,
        key="id",
    )

    for index, entry in enumerate(entries):
        path = f"guards.guards[{index}]"
        category = _required_string(
            entry,
            "category",
            path=path,
            errors=errors,
        )
        _validate_reference(
            category,
            categories,
            path=f"{path}.category",
            registry_name="guard category",
            errors=errors,
        )
        conditions = entry.get("conditions")
        if isinstance(conditions, Mapping):
            combiner = _required_string(
                conditions,
                "combiner",
                path=f"{path}.conditions",
                errors=errors,
            )
            if combiner not in {"ALL", "ANY"}:
                errors.append(
                    f"{path}.conditions.combiner: 'ALL' 또는 "
                    "'ANY'여야 합니다."
                )
            _string_list(
                conditions.get("items"),
                path=f"{path}.conditions.items",
                errors=errors,
            )
        else:
            _string_list(
                conditions,
                path=f"{path}.conditions",
                errors=errors,
            )
        failure = _required_mapping(
            entry.get("failure"),
            path=f"{path}.failure",
            errors=errors,
        )
        if not failure:
            continue
        status = failure.get("http_status")
        if not isinstance(status, int) or isinstance(status, bool):
            errors.append(f"{path}.failure.http_status: 정수여야 합니다.")
        elif not 400 <= status <= 599:
            errors.append(
                f"{path}.failure.http_status: 400~599 범위여야 합니다."
            )
        for key in ("error_code", "message"):
            _required_string(
                failure,
                key,
                path=f"{path}.failure",
                errors=errors,
            )

    return guard_by_id


def _validate_transitions(
    document: Mapping[str, Any],
    *,
    state_codes: set[str],
    terminal_states: set[str],
    visit_statuses: set[str],
    event_by_code: Mapping[str, Mapping[str, Any]],
    guard_ids: set[str],
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    entries = _mapping_entries(
        document.get("transitions"),
        path="transitions.transitions",
        errors=errors,
    )
    transition_by_id = _code_index(
        entries,
        path="transitions.transitions",
        errors=errors,
        key="id",
    )
    rule_semantics = _required_mapping(
        document.get("rule_semantics"),
        path="transitions.rule_semantics",
        errors=errors,
    )
    visit_modes_value = (
        rule_semantics.get("visit_modes") if rule_semantics else None
    )
    visit_modes = (
        set(visit_modes_value)
        if isinstance(visit_modes_value, Mapping)
        else set()
    )
    if not visit_modes:
        errors.append(
            "transitions.rule_semantics.visit_modes: "
            "비어 있지 않은 mapping이어야 합니다."
        )
    version_actions_value = (
        rule_semantics.get("version_actions") if rule_semantics else None
    )
    version_actions = (
        set(version_actions_value)
        if isinstance(version_actions_value, Mapping)
        else set()
    )
    if not version_actions:
        errors.append(
            "transitions.rule_semantics.version_actions: "
            "비어 있지 않은 mapping이어야 합니다."
        )

    seen_combinations: set[tuple[Any, ...]] = set()
    transition_event_codes: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"transitions.transitions[{index}]"
        event = _required_string(
            entry,
            "event",
            path=path,
            errors=errors,
        )
        _validate_reference(
            event,
            set(event_by_code),
            path=f"{path}.event",
            registry_name="event",
            errors=errors,
        )
        if event is not None:
            transition_event_codes.add(event)

        if "from_inquiry_state" not in entry:
            errors.append(f"{path}.from_inquiry_state: 필수 키가 없습니다.")
            from_state = None
        else:
            raw_from_state = entry.get("from_inquiry_state")
            if raw_from_state is None:
                from_state = None
            elif _is_nonempty_string(raw_from_state):
                from_state = raw_from_state.strip()
                _validate_reference(
                    from_state,
                    state_codes,
                    path=f"{path}.from_inquiry_state",
                    registry_name="state",
                    errors=errors,
                )
            else:
                from_state = None
                errors.append(
                    f"{path}.from_inquiry_state: null 또는 "
                    "비어 있지 않은 문자열이어야 합니다."
                )
        to_state = _required_string(
            entry,
            "to_inquiry_state",
            path=path,
            errors=errors,
        )
        _validate_reference(
            to_state,
            state_codes,
            path=f"{path}.to_inquiry_state",
            registry_name="state",
            errors=errors,
        )

        if event == "START_INQUIRY":
            if from_state is not None:
                errors.append(
                    f"{path}.from_inquiry_state: START_INQUIRY는 "
                    "null이어야 합니다."
                )
        elif from_state is None:
            errors.append(
                f"{path}.from_inquiry_state: START_INQUIRY 외 전이에는 "
                "기존 상태가 필요합니다."
            )
        if from_state in terminal_states:
            errors.append(
                f"{path}: terminal state {from_state!r}에서 "
                "후속 전이를 정의할 수 없습니다."
            )

        visit = _required_mapping(
            entry.get("visit"),
            path=f"{path}.visit",
            errors=errors,
        )
        visit_mode = None
        if visit:
            visit_mode = _required_string(
                visit,
                "mode",
                path=f"{path}.visit",
                errors=errors,
            )
            _validate_reference(
                visit_mode,
                visit_modes,
                path=f"{path}.visit.mode",
                registry_name="visit mode",
                errors=errors,
            )
            for key in ("from_status", "to_status", "required_status"):
                if key not in visit or visit.get(key) is None:
                    continue
                status = _required_string(
                    visit,
                    key,
                    path=f"{path}.visit",
                    errors=errors,
                )
                _validate_reference(
                    status,
                    visit_statuses,
                    path=f"{path}.visit.{key}",
                    registry_name="visit status",
                    errors=errors,
                )

        if event is not None:
            combination = (from_state, event, _freeze(visit))
            if combination in seen_combinations:
                errors.append(
                    f"{path}: from state/event/Visit 조건 조합이 "
                    "중복됩니다."
                )
            seen_combinations.add(combination)

        guard_refs = _string_list(
            entry.get("guard_refs"),
            path=f"{path}.guard_refs",
            errors=errors,
        )
        for guard in guard_refs:
            _validate_reference(
                guard,
                guard_ids,
                path=f"{path}.guard_refs",
                registry_name="guard",
                errors=errors,
            )
        if event != "START_INQUIRY" and "G-STATE-VERSION" not in guard_refs:
            errors.append(
                f"{path}.guard_refs: START_INQUIRY 외 전이는 "
                "G-STATE-VERSION을 포함해야 합니다."
            )
        event_contract = event_by_code.get(event, {})
        if (
            event_contract.get("requires_idempotency_key") is True
            and "G-IDEMPOTENCY-KEY" not in guard_refs
        ):
            errors.append(
                f"{path}.guard_refs: requires_idempotency_key=true인 "
                "이벤트는 G-IDEMPOTENCY-KEY를 포함해야 합니다."
            )

        history = _required_mapping(
            entry.get("history"),
            path=f"{path}.history",
            errors=errors,
        )
        if history:
            for key in (
                "record_inquiry_state_history",
                "record_visit_state_history",
                "record_business_event",
            ):
                if not isinstance(history.get(key), bool):
                    errors.append(f"{path}.history.{key}: boolean이어야 합니다.")
            if (
                from_state != to_state
                and history.get("record_inquiry_state_history") is not True
            ):
                errors.append(
                    f"{path}.history.record_inquiry_state_history: "
                    "상태 변경 전이는 true여야 합니다."
                )
            visit_changes = (
                visit_mode == "CREATE"
                or (
                    visit_mode == "TRANSITION"
                    and visit.get("from_status") != visit.get("to_status")
                )
            )
            if (
                visit_changes
                and history.get("record_visit_state_history") is not True
            ):
                errors.append(
                    f"{path}.history.record_visit_state_history: "
                    "Visit 생성·상태 변경 전이는 true여야 합니다."
                )

        version_action = entry.get("version_action")
        if version_action is not None:
            if not _is_nonempty_string(version_action):
                errors.append(
                    f"{path}.version_action: 비어 있지 않은 "
                    "문자열이어야 합니다."
                )
            else:
                _validate_reference(
                    version_action.strip(),
                    version_actions,
                    path=f"{path}.version_action",
                    registry_name="version action",
                    errors=errors,
                )

    excluded_entries = _mapping_entries(
        document.get("excluded_events"),
        path="transitions.excluded_events",
        errors=errors,
        require_nonempty=False,
    )
    excluded_event_codes: set[str] = set()
    for index, entry in enumerate(excluded_entries):
        path = f"transitions.excluded_events[{index}]"
        event = _required_string(
            entry,
            "event",
            path=path,
            errors=errors,
        )
        _validate_reference(
            event,
            set(event_by_code),
            path=f"{path}.event",
            registry_name="event",
            errors=errors,
        )
        if event is not None:
            if event in excluded_event_codes:
                errors.append(
                    f"transitions.excluded_events: event {event!r}가 "
                    "중복됩니다."
                )
            excluded_event_codes.add(event)

    for event in sorted(transition_event_codes & excluded_event_codes):
        errors.append(
            f"transitions: event {event!r}가 전이와 제외 목록에 "
            "동시에 있습니다."
        )
    for event in sorted(
        set(event_by_code) - transition_event_codes - excluded_event_codes
    ):
        errors.append(
            f"transitions: event {event!r}가 전이 또는 제외 목록에 없습니다."
        )
    return transition_by_id


def _validate_role_permissions(
    document: Mapping[str, Any],
    *,
    event_by_code: Mapping[str, Mapping[str, Any]],
    actor_role_codes: set[str],
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    entries = _mapping_entries(
        document.get("roles"),
        path="role_permissions.roles",
        errors=errors,
    )
    role_by_code = _code_index(
        entries,
        path="role_permissions.roles",
        errors=errors,
    )
    event_role_pairs: set[tuple[str, str]] = set()
    for event_code, event in event_by_code.items():
        for role in event.get("actor_roles", []):
            if _is_nonempty_string(role):
                event_role_pairs.add((event_code, role.strip()))

    permission_pairs: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        path = f"role_permissions.roles[{index}]"
        role = entry.get("code")
        normalized_role = role.strip() if _is_nonempty_string(role) else None
        _validate_reference(
            normalized_role,
            actor_role_codes,
            path=f"{path}.code",
            registry_name="actor role",
            errors=errors,
        )
        allowed_events = _string_list(
            entry.get("allowed_events"),
            path=f"{path}.allowed_events",
            errors=errors,
        )
        for event in allowed_events:
            _validate_reference(
                event,
                set(event_by_code),
                path=f"{path}.allowed_events",
                registry_name="event",
                errors=errors,
            )
            if normalized_role is not None:
                permission_pairs.add((event, normalized_role))

        required_permissions = entry.get("required_permissions")
        if required_permissions is not None:
            if not isinstance(required_permissions, Mapping):
                errors.append(
                    f"{path}.required_permissions: mapping이어야 합니다."
                )
            else:
                for event, permissions in required_permissions.items():
                    if event not in allowed_events:
                        errors.append(
                            f"{path}.required_permissions.{event}: "
                            "allowed_events에 없는 이벤트입니다."
                        )
                    _string_list(
                        permissions,
                        path=f"{path}.required_permissions.{event}",
                        errors=errors,
                    )

    for event, role in sorted(event_role_pairs - permission_pairs):
        errors.append(
            f"role_permissions.roles: event {event!r}의 actor role "
            f"{role!r}에 대응하는 권한이 없습니다."
        )
    for event, role in sorted(permission_pairs - event_role_pairs):
        errors.append(
            f"role_permissions.roles: role {role!r}의 event {event!r}가 "
            "inquiry-events.actor_roles와 일치하지 않습니다."
        )

    for event_code, event in event_by_code.items():
        if event.get("category") == "SYSTEM_EVENT":
            roles = {
                role.strip()
                for role in event.get("actor_roles", [])
                if _is_nonempty_string(role)
            }
            if roles != {"SYSTEM"}:
                errors.append(
                    f"events.events.{event_code}: SYSTEM_EVENT는 "
                    "SYSTEM 역할에만 허용되어야 합니다."
                )
    finalize = event_by_code.get("FINALIZE_INQUIRY")
    if finalize is not None:
        finalize_roles = {
            role.strip()
            for role in finalize.get("actor_roles", [])
            if _is_nonempty_string(role)
        }
        if finalize_roles != {"CONSULTANT", "TECHNICIAN"}:
            errors.append(
                "events.events.FINALIZE_INQUIRY: CONSULTANT와 "
                "TECHNICIAN에게만 허용되어야 합니다."
            )
    return role_by_code


def _validate_allowed_actions(
    document: Mapping[str, Any],
    *,
    state_codes: set[str],
    terminal_states: set[str],
    event_by_code: Mapping[str, Mapping[str, Any]],
    role_codes: set[str],
    transition_by_id: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    styles = set(
        _string_list(
            document.get("styles"),
            path="allowed_actions.styles",
            errors=errors,
        )
    )
    entries = _mapping_entries(
        document.get("action_catalog"),
        path="allowed_actions.action_catalog",
        errors=errors,
    )
    action_by_code = _code_index(
        entries,
        path="allowed_actions.action_catalog",
        errors=errors,
    )

    for index, entry in enumerate(entries):
        path = f"allowed_actions.action_catalog[{index}]"
        action = entry.get("code")
        action_code = action.strip() if _is_nonempty_string(action) else None
        event = event_by_code.get(action_code) if action_code else None
        if event is None and action_code is not None:
            errors.append(
                f"{path}.code: 등록되지 않은 event {action_code!r}입니다."
            )
        elif event is not None:
            external_action = event.get("external_action")
            exposed = (
                external_action.get("exposed")
                if isinstance(external_action, Mapping)
                else None
            )
            event_operation_id = (
                external_action.get("operation_id")
                if isinstance(external_action, Mapping)
                else None
            )
            if exposed is not True or event.get("category") == "SYSTEM_EVENT":
                errors.append(
                    f"{path}.code: 외부 공개 이벤트만 action catalog에 "
                    "포함할 수 있습니다."
                )
            if entry.get("operation_id") != event_operation_id:
                errors.append(
                    f"{path}.operation_id: inquiry-events의 operation_id와 "
                    "일치해야 합니다."
                )
        style = _required_string(
            entry,
            "style",
            path=path,
            errors=errors,
        )
        _validate_reference(
            style,
            styles,
            path=f"{path}.style",
            registry_name="action style",
            errors=errors,
        )
        if not isinstance(entry.get("requires_confirmation"), bool):
            errors.append(f"{path}.requires_confirmation: boolean이어야 합니다.")

    state_role_actions = document.get("state_role_actions")
    if not isinstance(state_role_actions, Mapping):
        errors.append("allowed_actions.state_role_actions: mapping이어야 합니다.")
        state_role_actions = {}
    actual_states = {
        state.strip()
        for state in state_role_actions
        if _is_nonempty_string(state)
    }
    for missing in sorted(state_codes - actual_states):
        errors.append(
            f"allowed_actions.state_role_actions: state {missing!r}가 "
            "누락되었습니다."
        )
    for extra in sorted(actual_states - state_codes):
        errors.append(
            f"allowed_actions.state_role_actions: 등록되지 않은 state "
            f"{extra!r}가 있습니다."
        )

    for state, role_map in state_role_actions.items():
        if not _is_nonempty_string(state):
            errors.append(
                "allowed_actions.state_role_actions: state 키는 "
                "비어 있지 않은 문자열이어야 합니다."
            )
            continue
        normalized_state = state.strip()
        if not isinstance(role_map, Mapping):
            errors.append(
                f"allowed_actions.state_role_actions.{normalized_state}: "
                "mapping이어야 합니다."
            )
            continue
        if normalized_state in terminal_states and role_map:
            errors.append(
                f"allowed_actions.state_role_actions.{normalized_state}: "
                "terminal state의 외부 행동은 비어 있어야 합니다."
            )
        for role, action_entries_value in role_map.items():
            path = (
                "allowed_actions.state_role_actions."
                f"{normalized_state}.{role}"
            )
            normalized_role = role.strip() if _is_nonempty_string(role) else None
            _validate_reference(
                normalized_role,
                role_codes,
                path=path,
                registry_name="role",
                errors=errors,
            )
            action_entries = _mapping_entries(
                action_entries_value,
                path=path,
                errors=errors,
            )
            seen_actions: set[str] = set()
            for index, action_entry in enumerate(action_entries):
                entry_path = f"{path}[{index}]"
                action = _required_string(
                    action_entry,
                    "action",
                    path=entry_path,
                    errors=errors,
                )
                _validate_reference(
                    action,
                    set(action_by_code),
                    path=f"{entry_path}.action",
                    registry_name="action",
                    errors=errors,
                )
                if action is not None:
                    if action in seen_actions:
                        errors.append(
                            f"{path}: action {action!r}이 중복됩니다."
                        )
                    seen_actions.add(action)
                    event = event_by_code.get(action)
                    actor_roles = (
                        event.get("actor_roles", [])
                        if event is not None
                        else []
                    )
                    if normalized_role not in actor_roles:
                        errors.append(
                            f"{entry_path}.action: role {normalized_role!r}이 "
                            "이벤트 actor_roles에 없습니다."
                        )
                    if event is not None and event.get("category") == (
                        "SYSTEM_EVENT"
                    ):
                        errors.append(
                            f"{entry_path}.action: SYSTEM_EVENT는 외부 행동에 "
                            "포함할 수 없습니다."
                        )

                rule_ids = _string_list(
                    action_entry.get("transition_rule_ids"),
                    path=f"{entry_path}.transition_rule_ids",
                    errors=errors,
                )
                for rule_id in rule_ids:
                    rule = transition_by_id.get(rule_id)
                    if rule is None:
                        errors.append(
                            f"{entry_path}.transition_rule_ids: 등록되지 않은 "
                            f"transition rule {rule_id!r}입니다."
                        )
                        continue
                    if action is not None and rule.get("event") != action:
                        errors.append(
                            f"{entry_path}.transition_rule_ids: rule "
                            f"{rule_id!r}의 event가 action과 다릅니다."
                        )
                    if rule.get("from_inquiry_state") != normalized_state:
                        errors.append(
                            f"{entry_path}.transition_rule_ids: rule "
                            f"{rule_id!r}의 from_inquiry_state가 상위 "
                            "state와 다릅니다."
                        )

    internal_events = document.get("internal_events_by_state")
    if not isinstance(internal_events, Mapping):
        errors.append(
            "allowed_actions.internal_events_by_state: mapping이어야 합니다."
        )
        internal_events = {}
    internal_states = {
        state.strip()
        for state in internal_events
        if _is_nonempty_string(state)
    }
    for missing in sorted(state_codes - internal_states):
        errors.append(
            f"allowed_actions.internal_events_by_state: state {missing!r}가 "
            "누락되었습니다."
        )
    for extra in sorted(internal_states - state_codes):
        errors.append(
            "allowed_actions.internal_events_by_state: 등록되지 않은 state "
            f"{extra!r}가 있습니다."
        )

    actual_internal_pairs: set[tuple[str, str]] = set()
    for state, values in internal_events.items():
        if not _is_nonempty_string(state):
            continue
        normalized_state = state.strip()
        events = _string_list(
            values,
            path=(
                "allowed_actions.internal_events_by_state."
                f"{normalized_state}"
            ),
            errors=errors,
            require_nonempty=False,
        )
        for event_code in events:
            event = event_by_code.get(event_code)
            if event is None:
                errors.append(
                    "allowed_actions.internal_events_by_state."
                    f"{normalized_state}: 등록되지 않은 event "
                    f"{event_code!r}입니다."
                )
                continue
            if event.get("category") != "SYSTEM_EVENT":
                errors.append(
                    "allowed_actions.internal_events_by_state."
                    f"{normalized_state}: {event_code!r}는 "
                    "SYSTEM_EVENT가 아닙니다."
                )
            actual_internal_pairs.add((normalized_state, event_code))

    expected_internal_pairs = {
        (rule.get("from_inquiry_state"), rule.get("event"))
        for rule in transition_by_id.values()
        if rule.get("from_inquiry_state") is not None
        and (
            event_by_code.get(rule.get("event"), {}).get("category")
            == "SYSTEM_EVENT"
        )
    }
    for state, event in sorted(
        expected_internal_pairs - actual_internal_pairs
    ):
        errors.append(
            "allowed_actions.internal_events_by_state: "
            f"{state!r}의 SYSTEM_EVENT {event!r}가 누락되었습니다."
        )
    for state, event in sorted(
        actual_internal_pairs - expected_internal_pairs
    ):
        errors.append(
            "allowed_actions.internal_events_by_state: "
            f"{state!r}의 event {event!r}에 대응하는 전이가 없습니다."
        )
    return action_by_code


def collect_contract_errors(
    documents: Mapping[str, Any],
) -> tuple[str, ...]:
    """계약 오류를 결정적인 순서로 모은다."""

    errors: list[str] = []
    if not isinstance(documents, Mapping):
        return ("contracts: mapping이어야 합니다.",)

    document_map = {
        name: _document(documents, name, errors) for name in DOCUMENT_NAMES
    }
    for name, document in document_map.items():
        if document:
            _validate_contract_header(document, name, errors)

    state_by_code, terminal_states, visit_statuses = _validate_states(
        document_map["states"],
        errors,
    )
    event_by_code, actor_role_codes = _validate_events(
        document_map["events"],
        errors,
    )
    guard_by_id = _validate_guards(document_map["guards"], errors)
    transition_by_id = _validate_transitions(
        document_map["transitions"],
        state_codes=set(state_by_code),
        terminal_states=terminal_states,
        visit_statuses=visit_statuses,
        event_by_code=event_by_code,
        guard_ids=set(guard_by_id),
        errors=errors,
    )
    role_by_code = _validate_role_permissions(
        document_map["role_permissions"],
        event_by_code=event_by_code,
        actor_role_codes=actor_role_codes,
        errors=errors,
    )
    _validate_allowed_actions(
        document_map["allowed_actions"],
        state_codes=set(state_by_code),
        terminal_states=terminal_states,
        event_by_code=event_by_code,
        role_codes=set(role_by_code),
        transition_by_id=transition_by_id,
        errors=errors,
    )
    return tuple(errors)


def validate_contract_documents(
    documents: Mapping[str, Any],
) -> None:
    """오류가 하나라도 있으면 전체 계약 사용을 차단한다."""

    errors = collect_contract_errors(documents)
    if errors:
        raise StateMachineContractValidationError(errors)
