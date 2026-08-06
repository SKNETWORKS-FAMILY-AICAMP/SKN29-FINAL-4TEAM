#!/usr/bin/env python3
"""Generate Mermaid and optional SVG/PNG from State Machine YAML contracts.

YAML under ``contracts/state-machine`` remains the source of truth.

YAML 파일들을 mmd로 변환하는 명령어:
    python scripts/contracts/render_state_machine.py
    
mmd로 변환하면서 state machine 이미지까지 생성하는 명령어:
    python scripts/contracts/render_state_machine.py --compact --state-labels both --image-output contracts/state-machine/diagrams/inquiry-state-machine.svg
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML이 필요합니다. `python -m pip install PyYAML`로 설치해 주세요."
    ) from exc


SM_DIR = Path("contracts/state-machine")
DEFAULT_OUTPUT = SM_DIR / "diagrams/inquiry-state-machine.mmd"


class ContractError(ValueError):
    """Raised when YAML contracts are missing or inconsistent."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="State Machine YAML 계약으로 Mermaid 상태도를 생성합니다."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="저장소 루트. 기본값은 스크립트 위치를 기준으로 자동 탐색합니다.",
    )
    parser.add_argument("--states", type=Path, default=SM_DIR / "inquiry-states.yaml")
    parser.add_argument("--events", type=Path, default=SM_DIR / "inquiry-events.yaml")
    parser.add_argument(
        "--transitions", type=Path, default=SM_DIR / "transition-rules.yaml"
    )
    parser.add_argument("--guards", type=Path, default=SM_DIR / "transition-guards.yaml")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--direction",
        choices=("TB", "LR"),
        default="TB",
        help="상태도 방향: TB(위→아래), LR(왼쪽→오른쪽)",
    )
    parser.add_argument(
        "--state-labels",
        choices=("code", "display", "both"),
        default="code",
        help="상태 노드 표시 방식",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="출발·도착 상태가 같은 병렬 전이를 한 화살표로 병합합니다.",
    )
    parser.add_argument(
        "--show-guards",
        action="store_true",
        help="전이 라벨에 Guard ID를 표시합니다.",
    )
    parser.add_argument(
        "--image-output",
        type=Path,
        help="선택 사항: Mermaid CLI(mmdc)로 만들 .svg 또는 .png 경로",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="파일을 수정하지 않고 Mermaid가 YAML과 일치하는지 검사합니다.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="생성 결과를 표준 출력에도 표시합니다.",
    )
    return parser.parse_args()


def resolve_from_root(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"계약 파일을 찾을 수 없습니다: {path}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"YAML 문법 오류: {path}\n{exc}") from exc
    if not isinstance(loaded, dict):
        raise ContractError(f"YAML 최상위 값은 객체여야 합니다: {path}")
    return loaded


def require_list(document: dict[str, Any], key: str, source: Path) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list):
        raise ContractError(f"`{key}`는 배열이어야 합니다: {source}")
    return value


def unique_index(
    items: Iterable[dict[str, Any]], key: str, item_name: str
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ContractError(f"{item_name} 항목은 객체여야 합니다: {item!r}")
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ContractError(f"{item_name}에 유효한 `{key}`가 없습니다: {item!r}")
        if value in index:
            raise ContractError(f"중복된 {item_name} `{value}`가 있습니다.")
        index[value] = item
    return index


def escape_mermaid_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", " ")
        .replace("\n", " ")
    )


def validate_contracts(
    states_doc: dict[str, Any],
    events_doc: dict[str, Any],
    transitions_doc: dict[str, Any],
    guards_doc: dict[str, Any],
    source_paths: tuple[Path, Path, Path, Path],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    states_path, events_path, transitions_path, guards_path = source_paths
    states = require_list(states_doc, "states", states_path)
    events = require_list(events_doc, "events", events_path)
    transitions = require_list(transitions_doc, "transitions", transitions_path)
    guards = require_list(guards_doc, "guards", guards_path)

    state_by_code = unique_index(states, "code", "상태")
    event_by_code = unique_index(events, "code", "이벤트")
    guard_by_id = unique_index(guards, "id", "Guard")
    unique_index(transitions, "id", "전이 규칙")

    initial_state = states_doc.get("initial_state")
    if initial_state not in state_by_code:
        raise ContractError(
            f"initial_state `{initial_state}`가 상태 목록에 정의되지 않았습니다."
        )

    terminal_states = states_doc.get("terminal_states", [])
    if not isinstance(terminal_states, list):
        raise ContractError("terminal_states는 배열이어야 합니다.")
    for state in terminal_states:
        if state not in state_by_code:
            raise ContractError(f"종료 상태 `{state}`가 상태 목록에 없습니다.")

    for transition in transitions:
        rule_id = transition["id"]
        event = transition.get("event")
        from_state = transition.get("from_inquiry_state")
        to_state = transition.get("to_inquiry_state")
        guard_refs = transition.get("guard_refs", [])

        if event not in event_by_code:
            raise ContractError(f"{rule_id}: 미정의 이벤트 `{event}`를 참조합니다.")
        if from_state is not None and from_state not in state_by_code:
            raise ContractError(f"{rule_id}: 미정의 출발 상태 `{from_state}`입니다.")
        if to_state not in state_by_code:
            raise ContractError(f"{rule_id}: 미정의 도착 상태 `{to_state}`입니다.")
        if not isinstance(guard_refs, list):
            raise ContractError(f"{rule_id}: guard_refs는 배열이어야 합니다.")
        for guard_ref in guard_refs:
            if guard_ref not in guard_by_id:
                raise ContractError(
                    f"{rule_id}: 미정의 Guard `{guard_ref}`를 참조합니다."
                )

    initial_transitions = [
        item for item in transitions if item.get("from_inquiry_state") is None
    ]
    if initial_transitions and not any(
        item.get("to_inquiry_state") == initial_state for item in initial_transitions
    ):
        raise ContractError(
            "출발 상태가 null인 초기 전이 중 initial_state로 향하는 규칙이 없습니다."
        )

    return state_by_code, transitions


def contract_version(document: dict[str, Any]) -> str:
    contract = document.get("contract")
    if isinstance(contract, dict) and isinstance(contract.get("version"), str):
        return contract["version"]
    return "unknown"


def state_declarations(
    state_by_code: dict[str, dict[str, Any]], label_mode: str
) -> list[str]:
    if label_mode == "code":
        return []

    lines: list[str] = []
    for code, state in state_by_code.items():
        display = state.get("display_name")
        if not isinstance(display, str) or not display.strip():
            display = code
        label = display if label_mode == "display" else f"{display} ({code})"
        lines.append(f'    state "{escape_mermaid_text(label)}" as {code}')
    return lines


def transition_label(transition: dict[str, Any], show_guards: bool) -> str:
    event = str(transition["event"])
    guards = transition.get("guard_refs", [])
    if not show_guards or not guards:
        return event
    return f"{event}<br/>[{', '.join(str(item) for item in guards)}]"


def transition_lines(
    transitions: list[dict[str, Any]], compact: bool, show_guards: bool
) -> list[str]:
    normal = [
        item for item in transitions if item.get("from_inquiry_state") is not None
    ]
    if not compact:
        return [
            f"    {item['from_inquiry_state']} --> {item['to_inquiry_state']}: "
            f"{transition_label(item, show_guards)}"
            for item in normal
        ]

    grouped: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
    for item in normal:
        edge = (str(item["from_inquiry_state"]), str(item["to_inquiry_state"]))
        grouped.setdefault(edge, []).append(item)

    lines: list[str] = []
    for (from_state, to_state), items in grouped.items():
        labels: list[str] = []
        seen: set[str] = set()
        for item in items:
            label = transition_label(item, show_guards)
            if label not in seen:
                labels.append(label)
                seen.add(label)
        separator = "<br/>/ " if show_guards else " / "
        lines.append(
            f"    {from_state} --> {to_state}: {separator.join(labels)}"
        )
    return lines


def generate_mermaid(
    *,
    states_doc: dict[str, Any],
    events_doc: dict[str, Any],
    transitions_doc: dict[str, Any],
    guards_doc: dict[str, Any],
    state_by_code: dict[str, dict[str, Any]],
    transitions: list[dict[str, Any]],
    direction: str,
    label_mode: str,
    compact: bool,
    show_guards: bool,
    source_paths: tuple[Path, Path, Path, Path],
    repo_root: Path,
) -> str:
    def display_path(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    input_digest = hashlib.sha256()
    for path in source_paths:
        input_digest.update(display_path(path).encode("utf-8"))
        input_digest.update(b"\0")
        input_digest.update(path.read_bytes())
        input_digest.update(b"\0")

    states_path, events_path, transitions_path, guards_path = source_paths
    lines = [
        "%% AUTO-GENERATED FILE. DO NOT EDIT DIRECTLY.",
        "%% Generated by scripts/contracts/render_state_machine.py",
        "%% Command: python scripts/contracts/render_state_machine.py",
        "%% Sources: "
        + ", ".join(display_path(path) for path in source_paths),
        "%% Input SHA-256 (ordered source paths and bytes): "
        + input_digest.hexdigest(),
        "%% Versions: "
        f"states={contract_version(states_doc)}, "
        f"events={contract_version(events_doc)}, "
        f"transitions={contract_version(transitions_doc)}, "
        f"guards={contract_version(guards_doc)}",
        "stateDiagram-v2",
        f"    direction {direction}",
    ]

    declarations = state_declarations(state_by_code, label_mode)
    if declarations:
        lines.append("")
        lines.extend(declarations)

    initial = [
        item for item in transitions if item.get("from_inquiry_state") is None
    ]
    lines.append("")
    if initial:
        for item in initial:
            lines.append(
                f"    [*] --> {item['to_inquiry_state']}: "
                f"{transition_label(item, show_guards)}"
            )
    else:
        lines.append(f"    [*] --> {states_doc['initial_state']}")

    normal_lines = transition_lines(transitions, compact, show_guards)
    if normal_lines:
        lines.append("")
        lines.extend(normal_lines)

    terminal_states = states_doc.get("terminal_states", [])
    if terminal_states:
        lines.append("")
        for state in terminal_states:
            lines.append(f"    {state} --> [*]")

    return "\n".join(lines) + "\n"


def write_or_check(output: Path, content: str, check: bool) -> None:
    if check:
        if not output.is_file():
            raise ContractError(f"검사할 Mermaid 파일이 없습니다: {output}")
        if output.read_text(encoding="utf-8") != content:
            raise ContractError(
                "Mermaid 파일이 YAML 계약과 일치하지 않습니다. "
                "`python scripts/contracts/render_state_machine.py`로 갱신해 주세요."
            )
        print(f"State Machine Mermaid check PASSED: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")
    print(f"Generated Mermaid: {output}")


def render_image(mermaid_path: Path, image_path: Path) -> None:
    if image_path.suffix.lower() not in {".svg", ".png"}:
        raise ContractError("--image-output은 .svg 또는 .png여야 합니다.")

    mmdc = shutil.which("mmdc")
    if mmdc is None:
        raise ContractError(
            "Mermaid CLI `mmdc`를 찾을 수 없습니다. "
            "`npm install -g @mermaid-js/mermaid-cli`로 설치해 주세요."
        )

    image_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [mmdc, "-i", str(mermaid_path), "-o", str(image_path)],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise ContractError(f"Mermaid 이미지 렌더링 실패:\n{details}")
    print(f"Rendered image: {image_path}")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()

    source_paths = tuple(
        resolve_from_root(repo_root, path).resolve()
        for path in (args.states, args.events, args.transitions, args.guards)
    )
    output = resolve_from_root(repo_root, args.output).resolve()

    try:
        states_doc, events_doc, transitions_doc, guards_doc = (
            load_yaml(path) for path in source_paths
        )
        state_by_code, transitions = validate_contracts(
            states_doc,
            events_doc,
            transitions_doc,
            guards_doc,
            source_paths,
        )
        content = generate_mermaid(
            states_doc=states_doc,
            events_doc=events_doc,
            transitions_doc=transitions_doc,
            guards_doc=guards_doc,
            state_by_code=state_by_code,
            transitions=transitions,
            direction=args.direction,
            label_mode=args.state_labels,
            compact=args.compact,
            show_guards=args.show_guards,
            source_paths=source_paths,
            repo_root=repo_root,
        )

        if args.stdout:
            print(content, end="")

        write_or_check(output, content, args.check)

        if args.image_output is not None:
            if args.check:
                raise ContractError("--check와 --image-output은 함께 쓸 수 없습니다.")
            image_output = resolve_from_root(repo_root, args.image_output).resolve()
            render_image(output, image_output)

    except ContractError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print(
        "State Machine render PASSED "
        f"(states={len(state_by_code)}, transitions={len(transitions)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
