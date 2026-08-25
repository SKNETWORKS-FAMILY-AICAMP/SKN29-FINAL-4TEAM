"""Regression test for direct-mode MCP import isolation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_direct_router_does_not_eagerly_import_mcp_modules():
    repository_root = Path(__file__).resolve().parents[4]

    script = r"""
import os
import sys

os.environ["AI_RETRIEVAL_TRANSPORT"] = "direct"

from ai.app.orchestration.pipeline_router import PipelineRouter

loaded = sorted(
    name
    for name in sys.modules
    if name.startswith("ai.app.integrations.mcp")
)

if loaded:
    raise AssertionError(
        "MCP loaded on router import: "
        + ", ".join(loaded)
    )

PipelineRouter(
    search_service=None,
    mcp_context_service=None,
)

loaded = sorted(
    name
    for name in sys.modules
    if name.startswith("ai.app.integrations.mcp")
)

if loaded:
    raise AssertionError(
        "MCP loaded on direct construction: "
        + ", ".join(loaded)
    )
"""

    environment = os.environ.copy()
    environment["AI_RETRIEVAL_TRANSPORT"] = "direct"
    environment["PYTHONPATH"] = str(repository_root)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, (
        completed.stdout
        + completed.stderr
    )
