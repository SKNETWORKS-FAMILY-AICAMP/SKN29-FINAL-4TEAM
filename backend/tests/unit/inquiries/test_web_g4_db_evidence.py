"""Web G4 Backend/DB evidence collection and replay comparison checks."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.consultations.models import Consultation
from apps.inquiries.management.commands.collect_web_g4_db_evidence import (
    BACKEND_ROOT,
    _prepare_output_dir,
    _refresh_integrity_artifacts,
)
from apps.inquiries.models import Inquiry
from apps.workflow.models import IdempotencyRecord, TransitionHistory


pytestmark = pytest.mark.django_db(transaction=True)

SOURCE_REF = "test-main"


def seed_dependencies() -> None:
    call_command("seed_demo_accounts", verbosity=0)
    call_command("seed_demo_products", verbosity=0)
    call_command("seed_demo_subscriptions", verbosity=0)


def create_fixture(run_id: str) -> dict:
    from io import StringIO

    output = StringIO()
    call_command(
        "create_web_consultation_e2e_fixture",
        "--run-id",
        run_id,
        "--json",
        stdout=output,
    )
    return json.loads(output.getvalue())


def capture(
    *,
    output_dir: Path,
    inquiry_id: str,
    run_id: str,
    phase: str,
) -> None:
    call_command(
        "collect_web_g4_db_evidence",
        "--inquiry-id",
        inquiry_id,
        "--run-id",
        run_id,
        "--source-ref",
        SOURCE_REF,
        "--phase",
        phase,
        "--output-dir",
        str(output_dir),
        verbosity=0,
    )


def request(
    client: APIClient,
    *,
    method: str,
    path: str,
    body: dict,
    key: str,
):
    return getattr(client, method)(
        path,
        body,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        HTTP_X_CORRELATION_ID=str(uuid4()),
    )


def test_r3_final_is_sanitized_and_does_not_claim_replay(tmp_path: Path):
    seed_dependencies()
    fixture = create_fixture("evidence-r3-final")
    before_counts = evidence_row_counts()

    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r3-final",
    )
    assert evidence_row_counts() == before_counts

    context = json.loads(
        (tmp_path / "00-db-evidence-context.json").read_text(encoding="utf-8")
    )
    snapshot_text = (tmp_path / "04-r3-final-snapshot.json").read_text(
        encoding="utf-8"
    )
    snapshot = json.loads(snapshot_text)
    redaction = json.loads(
        (tmp_path / "13-backend-db-redaction-scan.json").read_text(
            encoding="utf-8"
        )
    )

    assert context["historical_replay_evidence"] == "NOT_CAPTURED"
    assert context["historical_schema_delta"] == "NOT_CAPTURED"
    assert snapshot["consultation"]["count"] == 1
    assert all(
        "actor_role_code" in row
        and "changed_by_type_code" in row
        and "changed_at" in row
        for row in snapshot["workflow"]["history"]
    )
    assert len(snapshot["snapshot_sha256"]) == 64
    assert snapshot["raw_business_text_included"] is False
    assert "합성 Web 상담 처리 E2E 문의" not in snapshot_text
    assert "DEMO-CUSTOMER-001" not in snapshot_text
    assert "010-" not in snapshot_text
    assert redaction == {
        "finding_count": 0,
        "findings": [],
        "scanned_file_count": redaction["scanned_file_count"],
        "status": "PASS",
    }
    assert (tmp_path / "SHA256SUMS.txt").is_file()


def test_r4_first_write_replay_and_stale_conflict_have_expected_db_deltas(
    tmp_path: Path,
):
    seed_dependencies()
    fixture = create_fixture("evidence-r4-replay")
    inquiry = Inquiry.objects.get(public_id=fixture["inquiry_id"])
    consultant = User.objects.get(username="DEMO-CONSULTANT-001")
    client = APIClient()
    client.force_authenticate(user=consultant)

    started = request(
        client,
        method="post",
        path=f"/api/v1/inquiries/{inquiry.public_id}/start-consultation",
        body={"state_version": inquiry.state_version},
        key="evidence-r4-start",
    )
    assert started.status_code == 200, started.json()
    inquiry.refresh_from_db()

    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r4-before-first-write",
    )

    save_path = f"/api/v1/inquiries/{inquiry.public_id}/consultation-summary"
    save_body = {
        "state_version": inquiry.state_version,
        "summary": "합성 r4 상담 요약",
        "consultation_note": "합성 r4 상담 기록",
        "customer_guidance": "합성 r4 고객 안내",
        "result_code": "COMPLETED_NO_VISIT",
        "usage_guidance_status": "NORMAL",
    }
    first = request(
        client,
        method="patch",
        path=save_path,
        body=save_body,
        key="evidence-r4-save",
    )
    assert first.status_code == 200, first.json()
    assert first.json()["data"]["idempotent_replay"] is False
    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r4-after-first-write",
    )

    replay = request(
        client,
        method="patch",
        path=save_path,
        body=save_body,
        key="evidence-r4-save",
    )
    assert replay.status_code == 200, replay.json()
    assert replay.json()["data"]["idempotent_replay"] is True
    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r4-after-replay",
    )
    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r4-before-conflict",
    )

    stale_state = request(
        client,
        method="patch",
        path=save_path,
        body={
            **save_body,
            "summary": "합성 stale",
            "state_version": save_body["state_version"],
        },
        key="evidence-r4-stale-state",
    )
    assert stale_state.status_code == 409, stale_state.json()
    assert stale_state.json()["error"]["code"] == "STATE-CONFLICT-01"
    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r4-after-conflict",
    )
    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r4-compare",
    )

    result = json.loads(
        (tmp_path / "09-r4-diff-and-duplicates.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == "PASS"
    assert result["first_write_delta"] == {
        "consultation": 0,
        "history": 1,
        "idempotency": 1,
        "state_version": 1,
    }
    assert result["replay_additional_rows"] == {
        "consultation": 0,
        "history": 0,
        "idempotency": 0,
        "state_version": 0,
    }
    assert result["stale_state_409_additional_rows"] == {
        "consultation": 0,
        "history": 0,
        "idempotency": 0,
        "state_version": 0,
    }
    assert result["first_write_snapshot_changed"] is True
    assert result["replay_snapshot_unchanged"] is True
    assert result["stale_state_409_snapshot_unchanged"] is True
    assert result["schema_unchanged"] is True
    assert result["migration_state_unchanged"] is True
    assert result["blockers"] == []


def test_evidence_capture_refuses_overwrite_and_mixed_identity(tmp_path: Path):
    seed_dependencies()
    fixture = create_fixture("evidence-overwrite")

    capture(
        output_dir=tmp_path,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r3-final",
    )
    with pytest.raises(CommandError, match="비어 있어야"):
        capture(
            output_dir=tmp_path,
            inquiry_id=fixture["inquiry_id"],
            run_id=fixture["run_id"],
            phase="r3-final",
        )

    other_dir = tmp_path / "mixed"
    capture(
        output_dir=other_dir,
        inquiry_id=fixture["inquiry_id"],
        run_id=fixture["run_id"],
        phase="r4-before-first-write",
    )
    with pytest.raises(CommandError, match="같은 r4 실행"):
        capture(
            output_dir=other_dir,
            inquiry_id=fixture["inquiry_id"],
            run_id="different-r4-run",
            phase="r4-after-first-write",
        )
    assert not (other_dir / "05-r4-after-first-write.json").exists()


def test_evidence_capture_rejects_operational_inquiry(tmp_path: Path):
    seed_dependencies()
    fixture = create_fixture("evidence-operational-reject")
    inquiry = Inquiry.objects.get(public_id=fixture["inquiry_id"])
    owner = inquiry.initiated_by
    owner.is_synthetic = False
    owner.save(update_fields=["is_synthetic", "updated_at"])

    with pytest.raises(CommandError, match="합성 Inquiry만"):
        capture(
            output_dir=tmp_path,
            inquiry_id=fixture["inquiry_id"],
            run_id=fixture["run_id"],
            phase="r3-final",
        )


def test_evidence_output_rejects_broad_backend_root():
    with pytest.raises(CommandError, match="넓은 상위 경로"):
        _prepare_output_dir(BACKEND_ROOT, phase="r3-final")


def test_integrity_scan_rejects_secret_and_absolute_path_candidates(
    tmp_path: Path,
):
    (tmp_path / "unsafe.txt").write_text(
        "dsn=postgresql://user:password@example.invalid/database\n"
        "path=C:\\Users\\example\\runtime.json\n",
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="민감정보 후보"):
        _refresh_integrity_artifacts(tmp_path)

    result = json.loads(
        (tmp_path / "13-backend-db-redaction-scan.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == "FAIL"
    assert {item["finding"] for item in result["findings"]} >= {
        "database_uri",
        "windows_absolute_path",
    }
    assert not (tmp_path / "SHA256SUMS.txt").exists()


def evidence_row_counts() -> dict[str, int]:
    return {
        "consultation": Consultation.objects.count(),
        "history": TransitionHistory.objects.count(),
        "idempotency": IdempotencyRecord.objects.count(),
    }
