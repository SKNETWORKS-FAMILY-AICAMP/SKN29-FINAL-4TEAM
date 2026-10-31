"""S06 원본 데이터가 없어도 동작하는 표준 라이브러리 기반 회귀 테스트."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from s06_build_examples import SourceError, plan, read_s04  # noqa: E402
from s06_validate_examples import validate  # noqa: E402


HEADERS = [
    "scenario_id", "model_code", "split", "semantic_group_id", "intended_oracle_action",
    "required_actions_from_pdf", "pdf_review_pages", "source_issue", "pdf_sha256_verified",
    "manual_answerable", "manual_answerable", "review_status", "source_use_limit",
    "expected_evidence_group_ids", "suggested_gold_evidence_group_ids",
]


def fixture_file(tmp: Path, *, conflict=False, cross=False):
    csv_path = tmp / "split.csv"
    json_path = tmp / "scenarios.json"
    rows, scenarios = [], []
    # Train 18 (표준 행동 16, 확장 행동 2), Dev 6, Holdout 6.
    actions = (["ANSWER"] * 7 + ["ESCALATE"] * 5 + ["ASK"] * 4
               + ["ANSWER_THEN_CONFIRM", "EXPLAIN_UNSUPPORTED"])
    for i in range(30):
        is_train = i < 18
        split = "train" if is_train else "dev" if i < 24 else "holdout"
        gid = f"train-{i % 9}" if is_train else f"dev-{i % 4}" if split == "dev" else f"hold-{i % 3}"
        if cross and i == 18:
            gid = "train-0"
        action = actions[i] if is_train else "ANSWER"
        sid = f"SYN-TST-{i+1:03d}"
        code = "CODE_A" if i % 2 else "CODE_B"
        row = [sid, code, split, gid, action, "설명서에서 요구하는 조치", "12;14", "NONE",
               "1" * 64, "YES", "NO" if conflict and i == 0 else "YES",
               "PDF_REVIEWED", "오프라인 평가용", "EVD-TST-001", "EVD-TST-001"]
        rows.append(row)
        scenarios.append({
            "scenario_id": sid, "product": {"exact_sales_code": code},
            "request": {"model_code": code, "raw_symptom": f"합성 문의 {i+1}", "selected_symptoms": [],
                        "previous_answers": []},
            "question_expectations": {"product_specific_target": {
                "missing_fields": ([{"field_name": "target_water_type"}] if action == "ASK" else []),
                "followup_questions": []
            }},
        })
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    json_path.write_text(json.dumps(scenarios, ensure_ascii=False), encoding="utf-8")
    return csv_path, json_path


class BuildS06Tests(unittest.TestCase):
    def test_same_value_duplicate_header_is_allowed_and_reported(self):
        with tempfile.TemporaryDirectory() as name:
            csv_path, _ = fixture_file(Path(name))
            rows, dups = read_s04(csv_path)
            self.assertEqual(len(rows), 30)
            self.assertEqual(dups, ["manual_answerable"])

    def test_conflicting_duplicate_header_is_blocked(self):
        with tempfile.TemporaryDirectory() as name:
            csv_path, _ = fixture_file(Path(name), conflict=True)
            with self.assertRaisesRegex(SourceError, "중복 헤더"):
                read_s04(csv_path)

    def test_semantic_group_cross_split_is_blocked(self):
        with tempfile.TemporaryDirectory() as name:
            csv_path, _ = fixture_file(Path(name), cross=True)
            with self.assertRaisesRegex(SourceError, "의미 그룹 분할 교차"):
                read_s04(csv_path)

    def test_train_only_fifteen_and_special_labels_reserved(self):
        with tempfile.TemporaryDirectory() as name:
            csv_path, json_path = fixture_file(Path(name))
            docs, inventory, report = plan(csv_path, json_path)
            self.assertEqual(len(docs), 15)
            self.assertEqual(len(inventory), 18)
            self.assertEqual(report["counts"]["train_semantic_groups"], 9)
            self.assertEqual(report["counts"]["selected_semantic_groups"], 9)
            self.assertEqual(report["counts"]["mapping_review_excluded"], 2)
            self.assertTrue(all(x["provenance"]["split"] == "train" for x in docs))
            self.assertTrue(all(x["review"]["status"] == "needs_review" for x in docs))
            self.assertTrue(all(x["target"]["assistant_message"] is None for x in docs))
            self.assertTrue(all(x["input"]["evidence"] == [] for x in docs))
            self.assertTrue(all(x["target"]["forbidden_claims"] is None for x in docs))

    def test_draft_validation_pass_but_verified_gate_fails(self):
        with tempfile.TemporaryDirectory() as name:
            csv_path, json_path = fixture_file(Path(name))
            docs, _, _ = plan(csv_path, json_path)
            rows, _ = read_s04(csv_path)
            scenarios = {v["scenario_id"]: v for v in json.loads(json_path.read_text("utf-8"))}
            errors, warnings = validate(docs, rows, scenarios)
            self.assertFalse(errors)
            self.assertEqual(len(warnings), 15)
            errors, _ = validate(docs, rows, scenarios, require_verified=True)
            self.assertTrue(errors)

    def test_dev_injection_is_blocked(self):
        with tempfile.TemporaryDirectory() as name:
            csv_path, json_path = fixture_file(Path(name))
            docs, _, _ = plan(csv_path, json_path)
            rows, _ = read_s04(csv_path)
            scenarios = {v["scenario_id"]: v for v in json.loads(json_path.read_text("utf-8"))}
            docs[0]["provenance"]["source_scenario_id"] = "SYN-TST-019"
            errors, _ = validate(docs, rows, scenarios)
            self.assertTrue(any("Train 원본이 아님" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
