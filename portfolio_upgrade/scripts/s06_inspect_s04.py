"""S06 준비: S04 검수 CSV 구조와 분할 현황을 읽기 전용으로 확인한다.

Windows CMD (저장소 루트에서):
    python portfolio_upgrade\\scripts\\s06_inspect_s04.py

표준 라이브러리만 사용한다. 파일 생성, 모델 호출, CSV 수정 없음.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_CSV = (
    Path(__file__).resolve().parents[1]
    / "data" / "splits" / "s04_reviewed_pilot_split_v2.csv"
)
PREVIEW_FIELDS = (
    "scenario_id",
    "model_code",
    "semantic_group_id",
    "split",
    "intended_oracle_action",
    "manual_answerable",
    "source_issue",
    "pdf_review_pages",
    "pdf_sha256_verified",
    "required_actions_from_pdf",
    "expected_evidence_group_ids",
    "suggested_gold_evidence_group_ids",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="S04 CSV 읽기 전용 점검")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="검수 분할 CSV 경로")
    parser.add_argument("--preview", type=int, default=3, help="Train 미리보기 행 수")
    args = parser.parse_args()

    if not args.csv.is_file():
        print(f"[S06] 파일을 찾지 못했습니다: {args.csv}")
        print("원본 CSV의 실제 위치를 확인하세요. 가짜 데이터를 생성하지 않습니다.")
        return 2
    with args.csv.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = reader.fieldnames or []
        rows = list(reader)
    if not columns:
        print("[S06] CSV 헤더가 없습니다.")
        return 2

    print("[S06] 읽기 전용 S04 데이터 점검")
    print("파일:", args.csv)
    print("전체 행:", len(rows))
    print("CSV 열:", ", ".join(columns))

    absent = [name for name in ("scenario_id", "split", "semantic_group_id") if name not in columns]
    if absent:
        print("[주의] 필수로 예상한 열이 없습니다:", ", ".join(absent))
        print("기존 CSV 스키마를 확인한 뒤 실제 열 이름에 맞춰 수정하세요.")
        return 1

    by_split = Counter((row.get("split") or "(empty)").strip().lower() for row in rows)
    print("분할별 사례 수:", dict(sorted(by_split.items())))
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        group = (row.get("semantic_group_id") or "").strip()
        split = (row.get("split") or "").strip().lower()
        if group and split:
            group_splits[group].add(split)
    crossing = {group: sorted(splits) for group, splits in group_splits.items() if len(splits) > 1}
    print("선언된 의미 그룹 수:", len(group_splits))
    print("분할을 가로지르는 의미 그룹 수:", len(crossing))
    if crossing:
        print("[주의] 분할 교차 그룹:", crossing)

    train = [row for row in rows if (row.get("split") or "").strip().lower() == "train"]
    print(f"Train 후보: {len(train)}건 (S06 목표: 원문 검수된 15건)")
    if len(train) < 15:
        print("[주의] Train 사례가 15건 미만입니다. Dev/Holdout으로 메우면 안 됩니다.")
    for number, row in enumerate(train[: max(0, args.preview)], start=1):
        print(f"\n--- Train 예시 {number} (읽기 전용) ---")
        for field in PREVIEW_FIELDS:
            if field in columns:
                value = (row.get(field) or "").replace("\n", " ")
                if len(value) > 180:
                    value = value[:177] + "..."
                print(f"{field}: {value}")
    print("\n[S06] 이 출력은 파일 구조 확인이며 예시 정답의 PDF 검수가 아닙니다.")
    return 1 if crossing else 0


if __name__ == "__main__":
    raise SystemExit(main())
