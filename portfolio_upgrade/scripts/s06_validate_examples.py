"""S06 검수용 15건 구조/출처/분할 확인. PDF의 진위를 자동 입증하지 않는다.

Windows CMD:
  python portfolio_upgrade\\scripts\\s06_validate_examples.py
  python portfolio_upgrade\\scripts\\s06_validate_examples.py --require-verified

첫 실행은 '초안 구조 검증'용이다. --require-verified는 수동 검수 완료 전 실패가 정상.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from s06_build_examples import (
    DEFAULT_CSV, DEFAULT_OUTPUT, DEFAULT_SCENARIOS, STANDARD_ACTIONS,
    SourceError, read_s04, read_scenarios,
)


def validate(examples: list[dict], split_rows: list[dict[str, str]],
             scenarios: dict, require_verified: bool = False) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    by_id = {r["scenario_id"]: r for r in split_rows}
    train = {r["scenario_id"]: r for r in split_rows if r["split"].lower() == "train"}
    nontrain_groups = {r["semantic_group_id"] for r in split_rows if r["split"].lower() != "train"}
    seen = set()
    for i, x in enumerate(examples, start=1):
        src = x.get("provenance") or {}
        inp = x.get("input") or {}
        trg = x.get("target") or {}
        review = x.get("review") or {}
        sid = src.get("source_scenario_id")
        tag = f"예시 {i} ({sid})"
        if sid in seen:
            errors.append(f"{tag}: 중복 ID")
        seen.add(sid)
        if sid not in train:
            errors.append(f"{tag}: Train 원본이 아님 (Dev/Holdout/미등록 차단)")
            continue
        row = train[sid]
        original = scenarios.get(sid)
        if not original:
            errors.append(f"{tag}: 원본 합성 시나리오 없음")
            continue
        if src.get("split") != "train":
            errors.append(f"{tag}: provenance.split이 train이 아님")
        if src.get("semantic_group_id") != row["semantic_group_id"]:
            errors.append(f"{tag}: 의미 그룹이 S04 원본과 다름")
        if row["semantic_group_id"] in nontrain_groups:
            errors.append(f"{tag}: 의미 그룹이 Dev/Holdout과 교차")
        if inp.get("product_code") != row["model_code"]:
            errors.append(f"{tag}: 제품 코드가 S04와 다름")
        if inp.get("customer_message") != original["request"].get("raw_symptom"):
            errors.append(f"{tag}: 고객 원문이 합성 원본과 다름")
        if trg.get("action") not in STANDARD_ACTIONS:
            errors.append(f"{tag}: 미정의 행동을 자동 변환했거나 누락함")
        if src.get("source_action_label") != row["intended_oracle_action"]:
            errors.append(f"{tag}: 원본 행동 라벨 덮어쓰기")
        if trg.get("action") != row["intended_oracle_action"]:
            errors.append(f"{tag}: 원본 행동과 다른 target.action은 수동 검수 기록 필요")
        if x.get("example_id") != f"S06-{sid}":
            errors.append(f"{tag}: example_id 규칙 불일치")
        if (trg.get("action") == "ASK" and not trg.get("missing_fields")):
            errors.append(f"{tag}: ASK지만 missing_fields 없음")
        if inp.get("evidence") and not isinstance(inp.get("evidence"), list):
            errors.append(f"{tag}: evidence는 배열이어야 함")
        if src.get("gold_evidence_ids") and not isinstance(src.get("gold_evidence_ids"), list):
            errors.append(f"{tag}: gold_evidence_ids는 배열이어야 함")
        # 검수용 초안이 검수됐다고 잘못 보이거나 입력에 정답 필드가 들어가는 것을 막는다.
        for reserved in ("gold_evidence_ids", "expected_action", "required_actions", "forbidden_claims"):
            if reserved in inp:
                errors.append(f"{tag}: 정답 감사 전용 '{reserved}'가 모델 입력에 들어감")
        if require_verified:
            if review.get("status") != "verified":
                errors.append(f"{tag}: 사람의 원문 검수 verified 아님")
            if not isinstance(trg.get("assistant_message"), str) or not trg["assistant_message"].strip():
                errors.append(f"{tag}: 검수된 답변 본문이 없음")
            if not isinstance(trg.get("forbidden_claims"), list):
                errors.append(f"{tag}: 금지 주장 목록 미검수")
            if not isinstance(trg.get("cited_evidence_ids"), list):
                errors.append(f"{tag}: 인용 근거 목록 미검수")
            if inp.get("evidence_status") == "not_built_retrieval_pending":
                errors.append(f"{tag}: 실제 근거 공급 조건 미확정")
            if not review.get("pdf_recheck_evidence"):
                errors.append(f"{tag}: S06 원문 PDF 재검수 증거가 없음")
            if not review.get("training_use_decision"):
                errors.append(f"{tag}: SFT 학습 사용 범위 확인 기록 없음")
        elif review.get("status") == "needs_review":
            warnings.append(f"{sid}: 원본 PDF/응답/학습 범위 검수 대기")
    if len(examples) != 15:
        errors.append(f"예시 수 {len(examples)}건: 현재 S06 목표 15건과 다름")
    if not examples:
        errors.append("JSONL이 비어 있음")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="S06 초안의 출처·분할·구조 검증")
    parser.add_argument("--examples", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--require-verified", action="store_true", help="직접 원문 검수 완료 Gate")
    args = parser.parse_args()
    try:
        if not args.examples.is_file():
            raise SourceError(f"예시 파일이 없습니다: {args.examples} (--write부터 실행)")
        examples = []
        with args.examples.open("r", encoding="utf-8-sig") as f:
            for n, raw in enumerate(f, 1):
                if raw.strip():
                    try:
                        examples.append(json.loads(raw))
                    except json.JSONDecodeError as exc:
                        raise SourceError(f"JSONL {n}행 JSON 형식 오류: {exc}") from exc
        rows, dups = read_s04(args.csv)
        scenarios = read_scenarios(args.scenarios)
        errors, warnings = validate(examples, rows, scenarios, args.require_verified)
        print("[S06] 검수 Gate:", "원문 직접 검수까지 요구" if args.require_verified else "검수용 초안 구조만 확인")
        print("JSONL:", args.examples)
        print("예시 수:", len(examples), "의미 그룹:", len(set(x.get("provenance", {}).get("semantic_group_id") for x in examples)))
        print("행동 분포:", dict(Counter(x.get("target", {}).get("action") for x in examples)))
        print("중복 헤더(동일 값 확인 후 허용):", dups)
        if warnings:
            print("검수 대기:", len(warnings), "건 (구조 검증 PASS와 학습 가능은 다름)")
        if errors:
            print("[S06] FAIL:", len(errors), "문제")
            for err in errors[:20]:
                print(" -", err)
            if len(errors) > 20:
                print(f" - 추가 {len(errors)-20}건 생략")
            return 1
        print("[S06] PASS: 구조/출처/분할 검증. 원문·학습 사용 권한은 별도 검수 필요.")
        return 0
    except (SourceError, OSError, ValueError) as exc:
        print("[S06] 중단:", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
