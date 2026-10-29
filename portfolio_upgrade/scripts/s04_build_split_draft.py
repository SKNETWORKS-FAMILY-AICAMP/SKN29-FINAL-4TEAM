r"""S04: build a reproducible, leakage-aware DRAFT train/dev/holdout split.

Run from the SKN29-FINAL-4TEAM repository root (Windows CMD):
    python portfolio_upgrade\scripts\s04_build_split_draft.py
    python portfolio_upgrade\scripts\s04_build_split_draft.py --write

Standard library only. Read-only unless --write is used; --write NEVER overwrites.
This is not an approved final dataset, a runtime test, or proof against semantic leakage.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

SCENARIOS = Path("data/synthetic/candidates/manual_3model_candidate_scenarios.json")
CHUNKS = Path("data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl")
EVIDENCE = Path("data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl")
OUTPUT = Path("portfolio_upgrade/data/splits/s04_split_draft.csv")
TARGET = {"train": 18, "dev": 6, "holdout": 6}  # Initial proposal for 30 cases; not a quality claim
SEED = 29


def load_jsonl(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


class DisjointSet:
    def __init__(self, ids: list[str]):
        self.parent = {x: x for x in ids}

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while x != root:
            before = self.parent[x]
            self.parent[x] = root
            x = before
        return root

    def unite(self, a: str, b: str):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def build_groups(scenarios: list[dict], groups: list[dict], chunks: list[dict]):
    ids = [s["scenario_id"] for s in scenarios]
    if len(set(ids)) != len(ids):
        raise ValueError("중복 scenario_id가 있습니다.")
    dsu = DisjointSet(ids)
    by_group = {g["evidence_group_id"]: g for g in groups}
    by_chunk = {c["child_id"]: c for c in chunks}
    if len(by_group) != len(groups) or len(by_chunk) != len(chunks):
        raise ValueError("중복 evidence_group_id 또는 child_id가 있습니다.")

    owner_design: dict[str, str] = {}
    owner_evidence: dict[str, str] = {}
    owner_text: dict[str, str] = {}
    owner_negative_type: dict[str, str] = {}
    hashes_by_scenario: dict[str, set[str]] = {}
    reasons = defaultdict(set)

    def link(owner: dict[str, str], key: str, sid: str, reason: str):
        if key in owner:
            other = owner[key]
            dsu.unite(other, sid)
            reasons[sid].add(reason)
            reasons[other].add(reason)
        else:
            owner[key] = sid

    for s in sorted(scenarios, key=lambda x: x["scenario_id"]):
        sid = s["scenario_id"]
        if s.get("source_design_id"):
            link(owner_design, s["source_design_id"], sid, "SAME_SOURCE_DESIGN")
        refs = s["retrieval_expectation"]
        gids = refs.get("expected_evidence_group_ids", [])
        no_evidence = refs.get("expected_no_evidence") is True
        if no_evidence == bool(gids):
            raise ValueError(f"{sid}: 근거 유무와 기대 근거 ID가 충돌합니다.")
        all_hashes = set()
        for gid in gids:
            g = by_group.get(gid)
            if not g:
                raise ValueError(f"{sid}: 존재하지 않는 근거 그룹 {gid}")
            if g["exact_sales_code"] != s["product"]["exact_sales_code"]:
                raise ValueError(f"{sid}: 모델 코드와 근거 그룹 모델 코드가 다릅니다: {gid}")
            link(owner_evidence, gid, sid, "SAME_EVIDENCE_ID")
            for cid in g.get("child_ids", []):
                c = by_chunk.get(cid)
                if not c:
                    raise ValueError(f"{sid}: 없는 청크 참조 {cid}")
                h = c.get("child_text_sha256")
                if not h:
                    raise ValueError(f"{cid}: child_text_sha256이 없습니다.")
                all_hashes.add(h)
                link(owner_text, h, sid, "IDENTICAL_EVIDENCE_TEXT")
        hashes_by_scenario[sid] = all_hashes
        # No-evidence cases may not share official chunks. Keep policy variants of
        # the same failure family together to avoid obvious negative-case leakage.
        if no_evidence:
            link(owner_negative_type, s["family"], sid, "SAME_NEGATIVE_FAMILY")

    members = defaultdict(list)
    for sid in ids:
        members[dsu.find(sid)].append(sid)
    by_sid = {s["scenario_id"]: s for s in scenarios}
    component_records = []
    for member_ids in members.values():
        member_ids = sorted(member_ids)
        key = "g-" + hashlib.sha256("\n".join(member_ids).encode("utf-8")).hexdigest()[:10]
        negative = [sid for sid in member_ids if by_sid[sid]["retrieval_expectation"]["expected_no_evidence"] is True]
        positive = [sid for sid in member_ids if sid not in negative]
        if negative and positive:
            raise ValueError(f"같은 그룹에 정답근거 있음/없음이 함께 있음: {member_ids}")
        component_records.append({
            "group_id": key,
            "members": member_ids,
            "n": len(member_ids),
            "is_negative": bool(negative),
            "reasons": sorted(set().union(*(reasons[x] for x in member_ids))),
        })
    component_records.sort(key=lambda g: g["group_id"])
    return component_records, hashes_by_scenario


def allocate(components: list[dict], n: int, seed: int):
    if n != 30:
        raise ValueError(f"분할 비율은 아직 30건에만 검증했습니다. 현재 {n}건. 정책을 재검토하세요.")
    rng = random.Random(seed)
    positive = [g for g in components if not g["is_negative"]]
    negative = [g for g in components if g["is_negative"]]
    if len(negative) < 3:
        raise ValueError("부정/정책 그룹이 3개 미만이므로 평가 분할 비율을 수동 설계해야 합니다.")
    rng.shuffle(negative)
    rng.shuffle(positive)
    out = {}
    sizes = Counter()

    # Reserve at least one policy/no-evidence group in dev and holdout.
    for split, group in [("dev", negative[0]), ("holdout", negative[1])]:
        out[group["group_id"]] = split
        sizes[split] += group["n"]
    for g in negative[2:]:
        out[g["group_id"]] = "train"
        sizes["train"] += g["n"]

    # Larger groups first; choose smallest relative fill of currently feasible splits.
    positive.sort(key=lambda g: -g["n"])
    for group in positive:
        feasible = [x for x in TARGET if sizes[x] + group["n"] <= TARGET[x]]
        if not feasible:
            raise ValueError("그룹을 목표 개수에 맞춰 배치할 수 없습니다. 자동 분할하지 마세요.")
        choice = min(feasible, key=lambda x: (sizes[x] / TARGET[x], ["train", "dev", "holdout"].index(x)))
        out[group["group_id"]] = choice
        sizes[choice] += group["n"]
    if dict(sizes) != TARGET:
        raise ValueError(f"목표 분할 개수 불일치: {dict(sizes)} ≠ {TARGET}")
    return out


def validate(scenarios, components, assignments, hashes):
    where = {}
    for group in components:
        split = assignments[group["group_id"]]
        for sid in group["members"]:
            if sid in where:
                raise ValueError("동일 시나리오가 두 그룹에 있습니다: " + sid)
            where[sid] = split
    if len(where) != len(scenarios):
        raise ValueError("시나리오 누락 발생")
    by_hash = defaultdict(set)
    for sid, hlist in hashes.items():
        for h in hlist:
            by_hash[h].add(where[sid])
    leaking = [h for h, splits in by_hash.items() if len(splits) > 1]
    if leaking:
        raise ValueError(f"동일 근거 텍스트가 분할 경계를 넘음: {len(leaking)}개")
    return where


def main():
    parser = argparse.ArgumentParser(description="S04 train/dev/holdout 누출방지 분할 초안 (기본 읽기전용)")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Git 저장소 루트")
    parser.add_argument("--write", action="store_true", help="CSV 초안 생성 (덮어쓰기 금지)")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    root = args.root.resolve()
    scenarios = json.loads((root / SCENARIOS).read_text(encoding="utf-8"))
    chunks = load_jsonl(root / CHUNKS)
    evidence = load_jsonl(root / EVIDENCE)
    components, hashes = build_groups(scenarios, evidence, chunks)
    assignments = allocate(components, len(scenarios), args.seed)
    where = validate(scenarios, components, assignments, hashes)
    by_sid = {s["scenario_id"]: s for s in scenarios}

    print("[S04] 평가셋 분할 초안 (정답 원문/고객 시나리오 검수 전)")
    print(f"입력 {len(scenarios)}건 → 중복 연결 그룹 {len(components)}개")
    for split in TARGET:
        subset = [s for s in scenarios if where[s["scenario_id"]] == split]
        pos = sum(bool(s["retrieval_expectation"]["expected_evidence_group_ids"]) for s in subset)
        print(f"  {split}: {len(subset)}건 (근거 있음 {pos}, 없음/정책 {len(subset)-pos})")
    print("같은 근거 ID, 청크 본문 SHA256, 동일 설계/부정유형이 분할을 가로지르는지 검사: 통과")

    print("\n묶어서 이동하는 그룹 예시:")
    for group in sorted((g for g in components if len(g["members"]) > 1),key=lambda g:g["members"]):
        print(" ", "+".join(group["members"]), "=>", assignments[group["group_id"]])

    # Surface cross-split thematic repetition for manual review. It is not proof
    # of leakage; same family may represent meaningfully different conditions.
    family_splits = defaultdict(set)
    for s in scenarios:
        family_splits[s["family"]].add(where[s["scenario_id"]])
    shared = sorted(f for f, splits in family_splits.items() if len(splits) > 1)
    print(f"\n서로 다른 분할에 같은 증상 family가 존재하는 경우: {len(shared)}종")
    if shared:
        print(" ", ", ".join(shared))
    print("※ 동일 문장/근거 해시만 자동 방지했습니다. 의미가 유사한 질문은 사람이 추가 점검해야 합니다.")
    print("※ 현재 공식 설명서는 RAG 검색 DB에 들어갈 수 있습니다. 이 CSV는 질문/라벨의 학습·평가 구분용입니다.")
    print("※ 원본 PDF 검수와 독립 평가 타당성 점검 전이므로 최종 holdout 성능을 주장하면 안 됩니다.")

    if args.write:
        target = root / OUTPUT
        target.parent.mkdir(parents=True, exist_ok=True)
        gid_by_sid = {sid:g["group_id"] for g in components for sid in g["members"]}
        reason_by_sid = {sid:";".join(g["reasons"]) or "UNIQUE_BY_EXACT_HASH" for g in components for sid in g["members"]}
        with target.open("x",encoding="utf-8-sig",newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "scenario_id", "model_code", "family", "variant", "group_id", "split",
                "expected_evidence_group_ids", "grouping_reason", "review_status", "note",
            ])
            writer.writeheader()
            for sid in sorted(by_sid):
                s = by_sid[sid]
                writer.writerow({
                    "scenario_id": sid,
                    "model_code": s["product"]["exact_sales_code"],
                    "family": s["family"],
                    "variant": s["variant"],
                    "group_id": gid_by_sid[sid],
                    "split": where[sid],
                    "expected_evidence_group_ids": ";".join(s["retrieval_expectation"]["expected_evidence_group_ids"]),
                    "grouping_reason": reason_by_sid[sid],
                    "review_status": "UNREVIEWED_DRAFT",
                    "note": "",
                })
        print(f"\n저장: {target.relative_to(root)} (검수 전 초안, 기존 파일 덮어쓰기 안 함)")
    else:
        print("\n읽기 전용 미리보기입니다. CSV를 저장하려면 --write를 사용하세요.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as err:
        raise SystemExit(f"ERROR: {err}")
