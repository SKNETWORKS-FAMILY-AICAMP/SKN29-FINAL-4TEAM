"""S06: S04 Train 18건 중 검수용 15건을 추출한다. (학습용 최종 정답 아님)

프로젝트 루트의 Windows CMD:
  python portfolio_upgrade\\scripts\\s06_build_examples.py
  python portfolio_upgrade\\scripts\\s06_build_examples.py --write

특징: Dev/Holdout 차단; 동일 헤더 충돌 차단; 원본 행동 라벨 보존;
원문에 없는 답변/금지 조치/검색 결과를 만들어 내지 않는다.
표준 라이브러리만 사용. --write 없으면 파일을 만들지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "splits" / "s04_reviewed_pilot_split_v2.csv"
DEFAULT_SCENARIOS = ROOT.parent / "data" / "synthetic" / "candidates" / "manual_3model_candidate_scenarios.json"
DEFAULT_OUTPUT = ROOT / "data" / "training" / "examples_v0.jsonl"
STANDARD_ACTIONS = frozenset({"ANSWER", "ASK", "ESCALATE"})
ACTION_REVIEW_REQUIRED = frozenset({"ANSWER_THEN_CONFIRM", "EXPLAIN_UNSUPPORTED"})
REQUIRED_CSV_FIELDS = frozenset({
    "scenario_id", "model_code", "split", "semantic_group_id",
    "intended_oracle_action", "required_actions_from_pdf",
    "pdf_review_pages", "source_issue", "pdf_sha256_verified",
})


class SourceError(Exception):
    """입력 파일 계약 위반. 원본을 고치거나 확인하기 전 자동 생성 중단."""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_s04(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        raise SourceError(f"S04 CSV 파일 없음: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        raw = list(csv.reader(f))
    if len(raw) < 2:
        raise SourceError("S04 CSV가 비어 있거나 데이터 행이 없음")
    header = [v.strip() for v in raw[0]]
    missing = REQUIRED_CSV_FIELDS - set(header)
    if missing:
        raise SourceError("필수 CSV 열 누락: " + ", ".join(sorted(missing)))
    dup_names = sorted(name for name, count in Counter(header).items() if count > 1)
    rows = []
    for line, cells in enumerate(raw[1:], start=2):
        if len(cells) != len(header):
            raise SourceError(f"CSV {line}행 열 개수가 헤더와 다름: {len(cells)} != {len(header)}")
        row = {}
        for name in dict.fromkeys(header):
            values = [cells[i].strip() for i, h in enumerate(header) if h == name]
            if len(set(values)) > 1:
                raise SourceError(f"CSV {line}행 중복 헤더 '{name}' 값 충돌: {values}")
            row[name] = values[0]
        rows.append(row)
    if not rows:
        raise SourceError("CSV에 데이터 행이 없음")
    id_counts = Counter(row["scenario_id"] for row in rows)
    if any(not k or n != 1 for k, n in id_counts.items()):
        raise SourceError("scenario_id 공백 또는 중복")
    group_splits = defaultdict(set)
    for row in rows:
        if not row["semantic_group_id"]:
            raise SourceError(f"의미 그룹 없는 시나리오: {row['scenario_id']}")
        if row["split"].lower() not in {"train", "dev", "holdout"}:
            raise SourceError(f"미지원 분할: {row['scenario_id']} / {row['split']}")
        group_splits[row["semantic_group_id"]].add(row["split"].lower())
    crossing = {k: sorted(v) for k, v in group_splits.items() if len(v) > 1}
    if crossing:
        raise SourceError(f"의미 그룹 분할 교차: {crossing}")
    return rows, dup_names


def read_scenarios(path: Path) -> dict[str, dict]:
    if not path.is_file():
        raise SourceError(f"원본 합성 시나리오 JSON 파일 없음: {path}")
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SourceError("시나리오 JSON 최상위 구조는 배열이어야 함")
    result = {}
    for item in data:
        if not isinstance(item, dict) or not item.get("scenario_id"):
            raise SourceError("원본 시나리오에 scenario_id가 없음")
        if item["scenario_id"] in result:
            raise SourceError("원본 시나리오 ID 중복: " + item["scenario_id"])
        result[item["scenario_id"]] = item
    return result


def parse_gold_ids(value: str) -> list[str]:
    if not value or value.upper() in {"NONE", "NULL", "N/A"}:
        return []
    return list(dict.fromkeys(re.findall(r"EVD-[A-Za-z0-9_-]+", value)))


def parse_pages(value: str) -> list[int]:
    return sorted(set(int(s) for s in re.findall(r"\d+", value)))


def validate_input_pair(row: dict[str, str], source: dict) -> None:
    sid = row["scenario_id"]
    req = source.get("request")
    product = source.get("product")
    if not isinstance(req, dict) or not isinstance(product, dict):
        raise SourceError(f"{sid}: request/product 구조 누락")
    if not isinstance(req.get("raw_symptom"), str) or not req["raw_symptom"].strip():
        raise SourceError(f"{sid}: 원문 고객 발화 누락")
    model = row["model_code"]
    if req.get("model_code") != model or product.get("exact_sales_code") != model:
        raise SourceError(f"{sid}: CSV/원본 request/product 모델 코드 불일치 (자동 정정 안 함)")
    if row["intended_oracle_action"] not in STANDARD_ACTIONS | ACTION_REVIEW_REQUIRED:
        raise SourceError(f"{sid}: 미확인 원본 행동 라벨: {row['intended_oracle_action']}")


def candidate_key(row: dict[str, str], used_action: Counter, used_model: Counter) -> tuple:
    # 동일 그룹·상태에선 PDF 수정 제안이 없는 것을 먼저 보고, 행동·제품 균형을 고려.
    clean = row.get("source_issue", "NONE") == "NONE"
    pdf_reviewed = row.get("review_status", "") == "PDF_REVIEWED"
    return (-int(clean), -int(pdf_reviewed), used_action[row["intended_oracle_action"]],
            used_model[row["model_code"]], row["scenario_id"])


def select_candidates(rows: list[dict[str, str]], target_count: int = 15) -> tuple[list[dict], list[dict]]:
    train = [r for r in rows if r["split"].lower() == "train"]
    eligible = [r for r in train if r["intended_oracle_action"] in STANDARD_ACTIONS]
    excluded = [r for r in train if r["intended_oracle_action"] not in STANDARD_ACTIONS]
    if len(eligible) < target_count:
        raise SourceError(
            f"표준 3라벨 Train 후보 {len(eligible)}건 < 요청 {target_count}건. "
            "Dev/Holdout이나 미확인 원본 행동을 자동 변환해 채우지 않음."
        )
    groups = defaultdict(list)
    for row in eligible:
        groups[row["semantic_group_id"]].append(row)
    selected, seen = [], set()
    used_actions, used_models = Counter(), Counter()
    # 1차: 가능한 한 모든 의미 그룹을 포함(15건보다 그룹이 많은 경우 일부만 포함).
    # 그룹 순서는 첫 번째 시나리오 ID로 고정한다.
    for gid in sorted(groups, key=lambda g: min(r["scenario_id"] for r in groups[g])):
        if len(selected) >= target_count:
            break
        row = sorted(groups[gid], key=lambda r: candidate_key(r, used_actions, used_models))[0]
        selected.append(row)
        seen.add(row["scenario_id"])
        used_actions[row["intended_oracle_action"]] += 1
        used_models[row["model_code"]] += 1
    # 2차: 중복 그룹의 다른 제품·행동 사례로 확장한다.
    while len(selected) < target_count:
        remain = [r for r in eligible if r["scenario_id"] not in seen]
        if not remain:
            raise SourceError("15건 선정 도중 후보 소진")
        row = sorted(remain, key=lambda r: candidate_key(r, used_actions, used_models))[0]
        selected.append(row)
        seen.add(row["scenario_id"])
        used_actions[row["intended_oracle_action"]] += 1
        used_models[row["model_code"]] += 1
    return selected, excluded


def create_draft(row: dict[str, str], source: dict) -> dict:
    validate_input_pair(row, source)
    req = source["request"]
    original_action = row["intended_oracle_action"]
    if original_action not in STANDARD_ACTIONS:
        raise SourceError(f"{row['scenario_id']}: 행동 라벨 검토 필요, 자동 변환 금지")
    target_fields = (source.get("question_expectations") or {}).get("product_specific_target") or {}
    missing = [item.get("field_name") for item in target_fields.get("missing_fields", [])
               if isinstance(item, dict) and item.get("field_name")]
    if original_action == "ASK" and not missing:
        # 정보 부족인지를 문서에서 다시 확인해야 하므로, 임의 필드를 채워 넣지 않는다.
        raise SourceError(f"{row['scenario_id']}: ASK인데 missing_fields 없음. 검수 후 생성해야 함")
    proposed_gold = parse_gold_ids(row.get("suggested_gold_evidence_group_ids", ""))
    original_gold = parse_gold_ids(row.get("expected_evidence_group_ids", ""))
    issue = row.get("source_issue", "")
    if proposed_gold:
        gold, gold_source = proposed_gold, "s04_suggested_gold_evidence_group_ids"
    elif issue == "NONE":
        gold, gold_source = original_gold, "s04_expected_evidence_group_ids"
    else:
        gold, gold_source = [], "s04_review_empty_or_pending"
    action_text = (row.get("required_actions_from_pdf") or "").strip()
    sha = (row.get("pdf_sha256_verified") or "").strip()
    warnings = ["공식 PDF 직접 재대조 전; S04의 PDF 검수 기록을 재사용한 초안",
                "모델 입력용 evidence 미설정. S08에서 검색 근거 공급 조건 고정 필요",
                "assistant_message / forbidden_claims 미작성: 모델 정답 문장 생성·검수 전",
                "source_use_limit(오프라인 평가용) 확인 후 SFT 학습 사용 여부 별도 결정"]
    if issue and issue != "NONE":
        warnings.append(f"S04 라벨/근거 수정·범위 이슈: {issue}")
    if not gold:
        warnings.append("평가용 Gold 근거 ID가 비어 있음. 기능 정책/원문/인덱스 구분 필요")
    if sha and not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
        raise SourceError(f"{row['scenario_id']}: SHA256 형식 이상: {sha!r}")
    return {
        "example_id": f"S06-{row['scenario_id']}",
        "input": {
            "product_code": row["model_code"],
            "customer_message": req["raw_symptom"],
            "known_conditions": {
                "selected_symptoms": req.get("selected_symptoms") or [],
                "previous_answers": req.get("previous_answers") or [],
            },
            "evidence": [],
            "evidence_status": "not_built_retrieval_pending",
        },
        "target": {
            "action": original_action,
            "assistant_message": None,
            "missing_fields": missing if original_action == "ASK" else [],
            "required_actions": [action_text] if action_text else [],
            "forbidden_claims": None,
            "cited_evidence_ids": None,
            "tool_request": None,
        },
        "provenance": {
            "source_scenario_id": row["scenario_id"],
            "semantic_group_id": row["semantic_group_id"],
            "split": "train",
            "origin": "synthetic_manual_based",
            "manual_pages": parse_pages(row.get("pdf_review_pages", "")),
            "manual_sha256": sha or None,
            "gold_evidence_ids": gold,
            "gold_source": gold_source,
            "source_action_label": original_action,
            "source_issue": issue,
            "original_gold_evidence_ids": original_gold,
            "source_review_status": row.get("review_status", ""),
            "source_review_detail": row.get("review_status_detail", ""),
            "source_use_limit": row.get("source_use_limit", ""),
            "pdf_review_detail": row.get("pdf_review_detail", ""),
            "required_actions_from_pdf_raw": action_text,
        },
        "review": {
            "status": "needs_review",
            "notes": "S06 자동 매핑 초안. S04 PDF 검수 메모를 복사했으며 S06 원본 PDF 재검증·학습 권한 검토 전.",
            "warnings": warnings,
        }
    }


def plan(csv_path: Path, scenario_path: Path, target_count: int = 15):
    rows, dups = read_s04(csv_path)
    scenarios = read_scenarios(scenario_path)
    missing_ids = sorted(set(r["scenario_id"] for r in rows) - set(scenarios))
    if missing_ids:
        raise SourceError("시나리오 원본에서 다음 ID 누락: " + ", ".join(missing_ids))
    for row in rows:
        validate_input_pair(row, scenarios[row["scenario_id"]])
    selected, excluded = select_candidates(rows, target_count)
    drafts = [create_draft(row, scenarios[row["scenario_id"]]) for row in selected]
    selected_ids = {r["scenario_id"] for r in selected}
    inventory = []
    for row in rows:
        if row["split"].lower() != "train":
            continue
        status = "selected_draft" if row["scenario_id"] in selected_ids else (
            "action_mapping_review" if row["intended_oracle_action"] not in STANDARD_ACTIONS else "backup")
        inventory.append({
            "scenario_id": row["scenario_id"], "semantic_group_id": row["semantic_group_id"],
            "model_code": row["model_code"], "source_action": row["intended_oracle_action"],
            "source_issue": row.get("source_issue", ""), "review_status": row.get("review_status", ""),
            "selection": status,
        })
    report = {
        "status": "DRAFT_NOT_TRAIN_READY",
        "source": {
            "s04_csv": str(csv_path), "s04_csv_sha256": file_sha256(csv_path),
            "synthetic_scenarios_json": str(scenario_path),
            "synthetic_scenarios_sha256": file_sha256(scenario_path),
            "duplicate_csv_header_names_same_value": dups,
        },
        "counts": {
            "s04_all": len(rows),
            "s04_splits": dict(sorted(Counter(r["split"].lower() for r in rows).items())),
            "train": sum(r["split"].lower()=="train" for r in rows),
            "train_semantic_groups": len(set(r["semantic_group_id"] for r in rows if r["split"].lower()=="train")),
            "selected": len(selected),
            "selected_semantic_groups": len(set(r["semantic_group_id"] for r in selected)),
            "selected_source_actions": dict(sorted(Counter(r["intended_oracle_action"] for r in selected).items())),
            "mapping_review_excluded": len(excluded),
            "total_review_needed": len(selected),
        },
        "selection_policy": "Train only; standard ANSWER/ASK/ESCALATE only; group coverage then product/action diversity",
        "skipped_nonstandard_actions": [
            {"scenario_id": r["scenario_id"], "original_action": r["intended_oracle_action"]} for r in excluded
        ],
        "not_done": ["공식 PDF S06 직접 재검증", "15개 답변 본문 작성 및 금지 주장 검수",
                     "추론 근거 생성·동일 검색 조건 확정", "학습 활용 허용 여부 판단", "학습 또는 모델 성능 평가"],
    }
    return drafts, inventory, report


def write_outputs(examples: list[dict], inventory: list[dict], report: dict, output: Path) -> None:
    files = [output, output.with_name("s06_candidate_inventory.csv"), output.with_name("s06_build_report.json")]
    exists = [p for p in files if p.exists()]
    if exists:
        raise SourceError("기존 결과 덮어쓰기 차단: " + ", ".join(map(str, exists)) +
                          "\n기존 파일을 백업하거나 다른 --output 위치를 사용하세요.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with files[0].open("w", encoding="utf-8", newline="\n") as f:
        for example in examples:
            f.write(json.dumps(example, ensure_ascii=False, sort_keys=False) + "\n")
    with files[1].open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(inventory[0].keys()))
        writer.writeheader()
        writer.writerows(inventory)
    files[2].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in files:
        print("생성:", path)


def main() -> int:
    parser = argparse.ArgumentParser(description="S06 원본 기반 검수용 예시 15건 추출")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=15)
    parser.add_argument("--write", action="store_true", help="검수용 JSONL/보고서/인벤토리 실제 생성")
    args = parser.parse_args()
    try:
        if args.count < 1:
            raise SourceError("--count는 1 이상이어야 함")
        drafts, inventory, report = plan(args.csv, args.scenarios, args.count)
        print("[S06] 원본 연계 검수용 예시 추출" + (" / --write" if args.write else " / DRY RUN"))
        print("Train:", report["counts"]["train"], "선택:", report["counts"]["selected"],
              "선택 의미 그룹:", report["counts"]["selected_semantic_groups"])
        print("행동 분포:", report["counts"]["selected_source_actions"])
        print("원본 행동 별도 검수:", report["skipped_nonstandard_actions"])
        if report["source"]["duplicate_csv_header_names_same_value"]:
            print("[주의] 중복 CSV 열(모든 행 값 동일 확인):",
                  report["source"]["duplicate_csv_header_names_same_value"])
        for item in inventory:
            print(f"  {item['selection']:22} {item['scenario_id']:18} "
                  f"{item['source_action']:20} {item['source_issue']}")
        print("[주의] 출력은 PDF 직접 재검수/학습 허용 확인 전의 needs_review 초안임")
        if args.write:
            write_outputs(drafts, inventory, report, args.output)
        else:
            print("실제 파일 생성하려면 --write 옵션을 추가하세요.")
        return 0
    except (SourceError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("[S06] 중단:", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
