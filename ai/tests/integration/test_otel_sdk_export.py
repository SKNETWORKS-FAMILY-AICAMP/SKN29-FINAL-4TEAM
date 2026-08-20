"""Fresh-process real OpenTelemetry SDK export verification."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = (
    REPO_ROOT
    / "ai"
    / "scripts"
    / "verify_reliability_otel_export.py"
)


def test_reliability_spans_export_through_real_otel_sdk():
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

    combined = completed.stdout + "\n" + completed.stderr
    assert completed.returncode == 0, combined
    assert "OTEL_EXPORT_VERIFIED" in completed.stdout
    assert "pii_safe=true" in completed.stdout
    assert "service_name=waterbridge-ai" in completed.stdout

    for span_name in (
        "waterbridge.harness.runtime",
        "waterbridge.harness.verify",
        "waterbridge.harness.resume_review",
        "waterbridge.hitl.start",
        "waterbridge.hitl.resume",
        "waterbridge.handoff.create",
    ):
        assert span_name in completed.stdout

    assert "OTEL_PRIVATE_SENTINEL" not in completed.stdout
    assert "010-1234-5678" not in completed.stdout
    assert "private@example.com" not in completed.stdout
    assert "OTEL_PRIVATE_EVIDENCE_BODY" not in completed.stdout
