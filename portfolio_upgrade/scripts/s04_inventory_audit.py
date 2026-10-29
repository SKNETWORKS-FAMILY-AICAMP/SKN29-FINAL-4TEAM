"""S04 first-pass audit of WaterBridge's EXISTING three-model data.

Read-only by default. Standard-library only.
Run from the project root:
    python s04_inventory_audit.py
    python s04_inventory_audit.py --case SYN-IAC425-101
    python s04_inventory_audit.py --prepare-review

The source is the team's PROCESSED data and synthetic CANDIDATES.
This script does not certify original PDFs, run a database/LLM, promote candidates,
or create train/dev/holdout labels.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


MODEL_PAGES = {
    "WPUJAC104DWH": "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl",
    "WPUIAC425SNW": "data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl",
    "WPUIAC606SNW": "data/processed/documents/manuals/expansion/manual_pages_iac606.jsonl",
}
SCENARIOS = "data/synthetic/candidates/manual_3model_candidate_scenarios.json"
CHUNKS = "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"
GROUPS = "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl"
INVENTORY = "data/processed/metadata/source_inventory.csv"
# Four different topics from each manual. All 12 have expected evidence.
REVIEW_IDS = (
    "SYN-JAC104-025", "SYN-JAC104-026", "SYN-JAC104-029", "SYN-JAC104-030",
    "SYN-IAC425-101", "SYN-IAC425-106", "SYN-IAC425-107", "SYN-IAC425-108",
    "SYN-IAC606-101", "SYN-IAC606-103", "SYN-IAC606-104", "SYN-IAC606-107",
)


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_data(root: Path) -> dict:
    def req(relative: str) -> Path:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"필요한 파일을 찾지 못했습니다: {path}")
        return path

    with req(INVENTORY).open(encoding="utf-8-sig", newline="") as f:
        inventory = list(csv.DictReader(f))
    return {
        "inventory": inventory,
        "scenarios": json.loads(req(SCENARIOS).read_text(encoding="utf-8")),
        "chunks": load_jsonl(req(CHUNKS)),
        "groups": load_jsonl(req(GROUPS)),
        "pages": {code: load_jsonl(req(path)) for code, path in MODEL_PAGES.items()},
    }


def audit(data: dict) -> tuple[list[str], list[list[dict]]]:
    errors: list[str] = []
    scenarios = data["scenarios"]
    chunks = data["chunks"]
    groups = data["groups"]
    official = {
        row["exact_sales_code"]: row for row in data["inventory"]
        if row.get("scope_role") in ("mvp", "expansion") and row.get("source_type") == "official_manual"
    }
    gbyid = {g["evidence_group_id"]: g for g in groups}
    cbyid = {c["child_id"]: c for c in chunks}
    pagebycode = {
        code: {int(page["page"]): page for page in pages}
        for code, pages in data["pages"].items()
    }

    if len(gbyid) != len(groups):
        errors.append("근거 그룹 ID가 중복됩니다.")
    if len(cbyid) != len(chunks):
        errors.append("청크 ID가 중복됩니다.")
    if len(set(s["scenario_id"] for s in scenarios)) != len(scenarios):
        errors.append("시나리오 ID가 중복됩니다.")

    for code, pages in pagebycode.items():
        inv = official.get(code)
        if not inv:
            errors.append(f"공식 목록에 모델 {code}가 없습니다.")
            continue
        if inv.get("page_count") and len(pages) != int(inv["page_count"]):
            errors.append(f"{code}: 페이지 개수 불일치 (목록 {inv['page_count']}, 가공본 {len(pages)})")
        for pg in pages.values():
            if pg.get("source_file_sha256", "").upper() != inv["sha256"].upper():
                errors.append(f"{code} p{pg['page']}: 팀 원본 목록 해시와 가공본 출처 해시 불일치")
                break

    for g in groups:
        gid, code = g["evidence_group_id"], g["exact_sales_code"]
        for cid in g.get("child_ids", []):
            c = cbyid.get(cid)
            if not c:
                errors.append(f"{gid}: 없는 청크 {cid} 참조")
            elif c.get("evidence_group_id") != gid or c.get("exact_sales_code") != code:
                errors.append(f"{gid}: 청크 {cid}의 모델/근거 그룹 불일치")
        for pg in g.get("page_refs", []):
            if int(pg) not in pagebycode.get(code, {}):
                errors.append(f"{gid}: 가공본에 p{pg} 없음")

    for s in scenarios:
        sid, code = s["scenario_id"], s["product"]["exact_sales_code"]
        exp = s["retrieval_expectation"]
        gids = exp.get("expected_evidence_group_ids", [])
        no_evidence = exp.get("expected_no_evidence") is True
        if no_evidence and gids:
            errors.append(f"{sid}: 정답 근거 없음 표시와 근거 ID가 충돌")
        if not no_evidence and not gids:
            errors.append(f"{sid}: 정답 근거가 필요한데 ID가 없음")
        for gid in gids:
            g = gbyid.get(gid)
            if not g:
                errors.append(f"{sid}: 근거 그룹 {gid} 없음")
            elif g["exact_sales_code"] != code:
                errors.append(f"{sid}: 다른 제품의 근거 그룹 {gid} 연결")
        # Unsupported-model negatives are intentional. Do not miscount as an extra manual.

    byhash: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        byhash[c["child_text_sha256"]].append(c)
    duplicate_groups = [v for v in byhash.values() if len({c["exact_sales_code"] for c in v}) > 1]
    return errors, duplicate_groups


def sources_for(s: dict, groupmap: dict[str, dict]) -> list[dict]:
    return [groupmap[gid] for gid in s["retrieval_expectation"]["expected_evidence_group_ids"]]


def show_case(s: dict, data: dict) -> None:
    groupmap = {g["evidence_group_id"]: g for g in data["groups"]}
    bycode = {code: {int(pg["page"]): pg for pg in pages} for code, pages in data["pages"].items()}
    code = s["product"]["exact_sales_code"]
    groups = sources_for(s, groupmap)
    print("\n=== 원문 대조 실습: "+s["scenario_id"]+" ===")
    print("모델:", code, "| 유형:", s["family"], "| 상태:", s["candidate_status"])
    print("고객 표현:", s["request"]["raw_symptom"])
    print("기대 근거 그룹:", ", ".join(g["evidence_group_id"] for g in groups) or "없음(정책/부정 사례)")
    if not groups:
        print("설명서 근거 대신 검색 전 정책·제품 지원 범위를 확인해야 하는 사례입니다.")
        return
    for g in groups:
        print("\n  근거:", g["evidence_group_id"], "| 페이지:", g["page_refs"])
        print("  팀이 정리한 안내 근거:", " / ".join(g.get("safe_actions", []))[:500])
        for page_no in g["page_refs"]:
            page = bycode.get(code, {}).get(int(page_no))
            if page:
                print(f"  [가공된 설명서 {page_no}쪽 텍스트 일부]")
                print("  "+page["text"][:1000].replace("\n", "\n  "))
    print("\n검토 포인트: 가공 텍스트가 아니라 원본 PDF 해당 쪽도 열어")
    print("  ① 증상/조건 ② 안내 조치 ③ 위험·상담 조건 ④ 모델 적용 여부를 확인해 주세요.")
    print("  지금은 자동 연결 확인일 뿐 원본 PDF 검수가 완료된 것이 아닙니다.")


def prepare_review(root: Path, data: dict) -> None:
    byid = {s["scenario_id"]: s for s in data["scenarios"]}
    groupmap = {g["evidence_group_id"]: g for g in data["groups"]}
    rows = []
    for sid in REVIEW_IDS:
        if sid not in byid:
            raise ValueError(f"시나리오 없음: {sid}")
        s = byid[sid]
        groups = sources_for(s, groupmap)
        if not groups:
            raise ValueError(f"원문 검토 대상 {sid}에 근거 그룹이 없습니다.")
        rows.append({
            "case_id": sid,
            "model_code": s["product"]["exact_sales_code"],
            "question": s["request"]["raw_symptom"],
            "scenario_family": s["family"],
            "question_variant": s["variant"],
            "expected_evidence_group_ids": [g["evidence_group_id"] for g in groups],
            "source_document_ids": sorted({g["document_id"] for g in groups}),
            "source_pages": sorted({int(pg) for g in groups for pg in g["page_refs"]}),
            "review_status": "UNREVIEWED",
            "original_pdf_checked": False,
            "source_text_checked": False,
            "review_note": "",
            "split": "UNASSIGNED",
        })
    dst = root/"portfolio_upgrade"/"data"/"review"/"s04_review_batch.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Prevent overwriting reviewed labels, even on repeated execution.
    with dst.open("x", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False)+"\n")
    print("\n검수 대기 데이터 생성:", dst.relative_to(root), f"({len(rows)}건)")
    print("모든 행은 UNREVIEWED/UNASSIGNED입니다. 실제 PDF 확인 후에만 검수 완료로 변경하세요.")


def main() -> None:
    ap = argparse.ArgumentParser(description="S04 기존 공식 설명서/후보 데이터 감사 (기본 읽기 전용)")
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="저장소 루트 (기본: 현재 폴더)")
    ap.add_argument("--case", default="SYN-IAC425-101", help="한 시나리오의 질문과 근거 페이지 미리보기")
    ap.add_argument("--prepare-review", action="store_true", help="12개 검수 대기 JSONL 생성 (기존 파일 덮어쓰기 금지)")
    args = ap.parse_args()
    root = args.root.resolve()
    data = load_data(root)
    scenarios = data["scenarios"]
    errors, duplicates = audit(data)
    negative = [s for s in scenarios if s["retrieval_expectation"].get("expected_no_evidence") is True]
    print("[S04] 팀 저장소의 오프라인 후보 데이터 (공개 서비스 적용 아님)")
    print("공식 설명서 가공본:", ", ".join(f"{code} {len(data['pages'][code])}쪽" for code in MODEL_PAGES))
    print(f"검색 후보 청크: {len(data['chunks'])}개 | 근거 그룹: {len(data['groups'])}개")
    print(f"합성 상담 시나리오 후보: {len(scenarios)}건 | 근거 있는 사례 {len(scenarios)-len(negative)}건 | 근거 없음/정책 사례 {len(negative)}건")
    print("모델 코드별 후보:", dict(sorted(Counter(s["product"]["exact_sales_code"] for s in scenarios).items())))
    print(f"다른 모델에도 동일한 내용이 반복되는 청크 그룹: {len(duplicates)}개")
    for group in duplicates[:3]:
        print("  예:", " / ".join(x["exact_sales_code"]+":"+x["child_id"].split("-")[-2] for x in group))
    print("검증한 연결 관계:", "이상 없음" if not errors else f"오류/불일치 {len(errors)}건")
    for e in errors[:15]:
        print("  !", e)
    print("원문 검수 추천 12건:", ", ".join(REVIEW_IDS))
    print("주의: 팀 목록의 파일 SHA나 가공 텍스트를 확인한 것이지 원본 PDF를 재검증한 것은 아닙니다.")
    matches = [s for s in scenarios if s["scenario_id"] == args.case]
    if len(matches) != 1:
        raise ValueError(f"알 수 없는 --case: {args.case}")
    show_case(matches[0], data)
    if args.prepare_review:
        if errors:
            raise ValueError("연결 관계 오류가 있어 검수 데이터 생성을 중단합니다.")
        prepare_review(root, data)


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, FileExistsError) as exc:
        raise SystemExit(f"ERROR: {exc}")
