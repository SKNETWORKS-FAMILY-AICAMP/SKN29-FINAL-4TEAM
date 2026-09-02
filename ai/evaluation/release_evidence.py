"""Evaluation-only provenance. Runtime code must not import this module."""

from datetime import datetime, timezone
from hashlib import sha1, sha256
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
    "ai/requirements.lock", "ai/requirements-linux.lock",
    "data/config/handoff/consumer_profiles.json",
    "data/config/rag/three_model_evaluation_cases.json",
    "data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl",
    "data/processed/structured/evidence/rag_evidence_groups_3model_v1.jsonl",
    "data/reference_cases/three_model_reference_scenarios_v1.json",
    "data/schemas/reference_cases/three_model_reference_scenarios_v1.schema.json",
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
    git_metadata_verified = False
    try:
        head = git("rev-parse", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            raise ValueError("COMMIT_SHA_INVALID")
        if Path(git("rev-parse", "--show-toplevel")).resolve() != root.resolve():
            raise ValueError("EXECUTION_REPOSITORY_ROOT_MISMATCH")
        commit = subprocess.run(
            ["git", "cat-file", "commit", head], cwd=root, check=True,
            capture_output=True, timeout=5,
        ).stdout
        header = f"commit {len(commit)}\0".encode("ascii")
        if sha1(header + commit, usedforsecurity=False).hexdigest() != head:
            raise ValueError("COMMIT_OBJECT_MISMATCH")
        branch = git("branch", "--show-current")
        dirty = bool(git("status", "--porcelain"))
        git_metadata_verified = True
    except (OSError, ValueError, subprocess.SubprocessError):
        head, branch, dirty = None, None, None
    inputs = {name: text_file_sha256(root / name) for name in IDENTITY_FILES if (root / name).is_file()}
    for task in ("symptom_structuring/v1", "followup_question/v1", "customer_guidance/v4"):
        for filename in ("system.txt", "user_template.txt"):
            path = root / "ai/prompts" / task / filename
            if path.is_file():
                inputs[path.relative_to(root).as_posix()] = text_file_sha256(path)
    code = {path.relative_to(root).as_posix(): text_file_sha256(path)
            for path in sorted((root / "ai/app").rglob("*.py"))}
    evaluation = {
        path.relative_to(root).as_posix(): text_file_sha256(path)
        for directory in ("ai/evaluation", "ai/scripts")
        for path in sorted((root / directory).rglob("*.py"))
    }
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": head, "branch": branch, "dirty": dirty,
        "python_version": platform.python_version(),
        "git_metadata_verified": git_metadata_verified,
        "file_hash_normalization": "UTF8_LF", "input_file_sha256": inputs,
        "runtime_source_sha256": json_sha256(code),
        "evaluation_source_sha256": json_sha256(evaluation),
        "missing_identity_files": [name for name in IDENTITY_FILES if name not in inputs],
    }


def execution_blockers(provenance: dict, expected_sha: str | None) -> list[str]:
    blockers = []
    if provenance.get("git_metadata_verified") is not True:
        blockers.append("VERIFIED_GIT_COMMIT_REQUIRED")
    if provenance.get("missing_identity_files"):
        blockers.append("RELEASE_IDENTITY_INPUTS_MISSING")
    if provenance["python_version"] != "3.13.13":
        blockers.append("PYTHON_VERSION_MISMATCH")
    if not expected_sha or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        blockers.append("FINAL_PR_SHA_REQUIRED")
    elif provenance["commit_sha"] != expected_sha:
        blockers.append("EXECUTION_SHA_MISMATCH")
    if provenance["dirty"] is not False:
        blockers.append("CLEAN_EXECUTION_TREE_REQUIRED")
    return blockers


def execution_source_changed(before: dict, after: dict) -> bool:
    """Include the evaluator, Oracle, Prompt and evidence inputs in the freeze."""
    return any(
        before.get(field) != after.get(field)
        for field in (
            "commit_sha", "dirty", "git_metadata_verified", "runtime_source_sha256",
            "evaluation_source_sha256", "input_file_sha256", "missing_identity_files",
        )
    )


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "artifact_payload_sha256": json_sha256(payload)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")
