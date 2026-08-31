"""Evaluation-only provenance. Runtime code must not import this module."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess

from ai.app.retrieval.runtime_profile import REPOSITORY_ROOT


IDENTITY_FILES = (
    "ai/configs/model_profiles.yaml", "ai/configs/runtime_identity.json",
    "ai/configs/retrieval_policy.yaml", "ai/configs/safety_rules.yaml",
    "ai/configs/retry_policy.yaml", "ai/configs/index_manifest.json",
    "ai/configs/index_manifest_3model.json",
    "ai/configs/canonical_evidence_identity_3model.json",
    "ai/configs/canonical_evidence_topics_3model.json",
    "ai/prompts/prompt_registry.yaml",
)


def json_sha256(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def text_file_sha256(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256(raw).hexdigest()


def execution_provenance(root: Path = REPOSITORY_ROOT) -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=root, check=True,
                              capture_output=True, text=True, encoding="utf-8", timeout=5).stdout.strip()
    try:
        head, branch, dirty = git("rev-parse", "HEAD"), git("branch", "--show-current"), bool(git("status", "--porcelain"))
    except (OSError, subprocess.SubprocessError):
        head, branch, dirty = None, None, None
    inputs = {name: text_file_sha256(root / name) for name in IDENTITY_FILES if (root / name).is_file()}
    for task in ("symptom_structuring/v1", "followup_question/v1", "customer_guidance/v3"):
        for filename in ("system.txt", "user_template.txt"):
            path = root / "ai/prompts" / task / filename
            if path.is_file():
                inputs[path.relative_to(root).as_posix()] = text_file_sha256(path)
    code = {path.relative_to(root).as_posix(): text_file_sha256(path)
            for path in sorted((root / "ai/app").rglob("*.py"))}
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": head, "branch": branch, "dirty": dirty,
        "python_version": platform.python_version(),
        "file_hash_normalization": "UTF8_LF", "input_file_sha256": inputs,
        "runtime_source_sha256": json_sha256(code),
    }


def execution_blockers(provenance: dict, expected_sha: str | None) -> list[str]:
    blockers = []
    if provenance["python_version"] != "3.13.13":
        blockers.append("PYTHON_VERSION_MISMATCH")
    if not expected_sha or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        blockers.append("FINAL_PR_SHA_REQUIRED")
    elif provenance["commit_sha"] != expected_sha:
        blockers.append("EXECUTION_SHA_MISMATCH")
    if provenance["dirty"] is not False:
        blockers.append("CLEAN_EXECUTION_TREE_REQUIRED")
    return blockers


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "artifact_payload_sha256": json_sha256(payload)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
