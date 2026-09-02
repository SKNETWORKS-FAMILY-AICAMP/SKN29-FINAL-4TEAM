#!/usr/bin/env bash
set -euo pipefail

action="${1:-}"
expected_release_sha="${2:-}"

base_dir="${WATERBRIDGE_BASE_DIR:-/opt/waterbridge}"
backend_env_file="${WATERBRIDGE_BACKEND_ENV_FILE:-/etc/waterbridge/backend.env}"
ai_env_file="${WATERBRIDGE_AI_ENV_FILE:-/etc/waterbridge/ai.env}"
shared_dir="${base_dir}/shared"
state_file="${shared_dir}/ai-context-activation.state"
canary_state_file="${shared_dir}/ai-handoff-canary.state"
lock_file="${shared_dir}/deploy.lock"
activation_in_progress=0
deactivation_in_progress=0

fail() {
  printf 'AI_CONTEXT_ACTIVATION_FAILED reason=%s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 \
    || fail "required_command_missing_${1}"
}

for command_name in chmod date docker flock mkdir mv python3 readlink sed; do
  require_command "$command_name"
done

[[ "$action" =~ ^(preflight|activate|deactivate|status)$ ]] \
  || fail "action_invalid"
[[ "$expected_release_sha" =~ ^[0-9a-f]{40}$ ]] \
  || fail "expected_release_sha_invalid"

mkdir -p "$shared_dir"
chmod 0750 "$base_dir" "$shared_dir"
exec 9>"$lock_file"
flock -n 9 || fail "deployment_or_activation_lock_busy"

current_target=""
compose_file=""
release_env=""

resolve_release() {
  [[ -L "${base_dir}/current" ]] || fail "current_release_link_missing"
  current_target="$(readlink -f "${base_dir}/current")"
  [[ "$current_target" == "${base_dir}/releases/${expected_release_sha}/payload" ]] \
    || fail "current_release_sha_mismatch"
  compose_file="${current_target}/infra/docker/compose/production/compose.yml"
  release_env="${current_target}/release.env"
  [[ -f "$compose_file" && -f "$release_env" ]] \
    || fail "current_release_assets_missing"
}

compose() {
  docker compose --env-file "$release_env" -f "$compose_file" "$@"
}

read_state_value() {
  local key="$1"
  [[ -f "$state_file" ]] || return 1
  sed -n "s/^${key}=//p" "$state_file"
}

normalized_env_sha() {
  local path="$1"
  local label="$2"
  shift 2
  python3 - "$path" "$label" "$@" <<'PY'
from hashlib import sha256
import stat
import sys
from pathlib import Path

path = Path(sys.argv[1])
label = sys.argv[2]
keys = tuple(sys.argv[3:])
if not path.is_file() or path.is_symlink():
    raise SystemExit(f"{label} environment must be one regular file")
if stat.S_IMODE(path.stat().st_mode) & 0o077:
    raise SystemExit(f"{label} environment permissions are unsafe")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
for key in keys:
    indexes = [
        index
        for index, line in enumerate(lines)
        if line.lstrip().startswith(f"{key}=")
    ]
    if len(indexes) != 1:
        raise SystemExit(f"{label} key must occur exactly once: {key}")
    index = indexes[0]
    ending = "\n" if lines[index].endswith("\n") else ""
    lines[index] = f"{key}=false{ending}"
print(sha256("".join(lines).encode("utf-8")).hexdigest())
PY
}

write_state() {
  local phase="$1"
  local activated_at="$2"
  local backend_sha="$3"
  local ai_sha="$4"
  local activation_id="$5"
  local temporary="${state_file}.tmp"
  [[ "$backend_sha" =~ ^[0-9a-f]{64}$ && "$ai_sha" =~ ^[0-9a-f]{64}$ ]] \
    || fail "normalized_environment_sha_invalid"
  {
    printf 'phase=%s\n' "$phase"
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'mode=JAC104_LIMITED\n'
    printf 'activated_at=%s\n' "$activated_at"
    printf 'activation_id=%s\n' "$activation_id"
    printf 'backend_env_normalized_sha256=%s\n' "$backend_sha"
    printf 'ai_env_normalized_sha256=%s\n' "$ai_sha"
  } >"$temporary"
  chmod 0600 "$temporary"
  mv -f -- "$temporary" "$state_file"
}

validate_state() {
  [[ -f "$state_file" ]] || fail "activation_state_missing"
  [[ "$(read_state_value release_sha)" == "$expected_release_sha" ]] \
    || fail "activation_state_release_mismatch"
  [[ "$(read_state_value mode)" == "JAC104_LIMITED" ]] \
    || fail "activation_mode_invalid"
  [[ "$(read_state_value activation_id)" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$ ]] \
    || fail "activation_id_invalid"
  [[ "$(read_state_value backend_env_normalized_sha256)" =~ ^[0-9a-f]{64}$ ]] \
    || fail "backend_environment_state_sha_invalid"
  [[ "$(read_state_value ai_env_normalized_sha256)" =~ ^[0-9a-f]{64}$ ]] \
    || fail "ai_environment_state_sha_invalid"
}

runtime_status() {
  python3 - "$backend_env_file" "$ai_env_file" <<'PY'
import hmac
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit

def read_values(raw_path, label):
    path = Path(raw_path)
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"{label} environment must be one regular file")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise SystemExit(f"{label} environment permissions are unsafe")
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in values:
            raise SystemExit(f"duplicate {label} environment key: {key}")
        values[key] = value.strip()
    return values

backend = read_values(sys.argv[1], "Backend")
ai = read_values(sys.argv[2], "AI")
backend_required = (
    "AI_HANDOFF_INTERNAL_TOKEN",
    "AI_HUMAN_REVIEW_RESUME_ENABLED",
    "AI_HUMAN_REVIEW_RESUME_TOKEN",
)
ai_required = (
    "AI_HANDOFF_BACKEND_ENABLED",
    "AI_BACKEND_BASE_URL",
    "AI_HANDOFF_INTERNAL_TOKEN",
    "AI_HANDOFF_TIMEOUT_SECONDS",
    "AI_HUMAN_REVIEW_RESUME_ENABLED",
    "AI_HUMAN_REVIEW_RESUME_TOKEN",
)
if any(not backend.get(key) for key in backend_required):
    raise SystemExit("required Backend Resume environment key is missing")
if any(not ai.get(key) for key in ai_required):
    raise SystemExit("required AI Resume or Handoff environment key is missing")
if not hmac.compare_digest(
    backend["AI_HANDOFF_INTERNAL_TOKEN"],
    ai["AI_HANDOFF_INTERNAL_TOKEN"],
):
    raise SystemExit("Backend and AI Handoff source tokens differ")
if not hmac.compare_digest(
    backend["AI_HUMAN_REVIEW_RESUME_TOKEN"],
    ai["AI_HUMAN_REVIEW_RESUME_TOKEN"],
):
    raise SystemExit("Backend and AI Resume tokens differ")
if len(backend["AI_HUMAN_REVIEW_RESUME_TOKEN"].encode("utf-8")) < 32:
    raise SystemExit("Resume token is too short")
flags = (
    backend["AI_HUMAN_REVIEW_RESUME_ENABLED"].casefold(),
    ai["AI_HUMAN_REVIEW_RESUME_ENABLED"].casefold(),
    ai["AI_HANDOFF_BACKEND_ENABLED"].casefold(),
)
if any(value not in {"true", "false"} for value in flags):
    raise SystemExit("Resume or Handoff enabled value is invalid")
parsed = urlsplit(ai["AI_BACKEND_BASE_URL"])
if (
    parsed.scheme != "http"
    or parsed.hostname != "backend"
    or parsed.port != 8000
    or parsed.username is not None
    or parsed.password is not None
    or parsed.path not in {"", "/"}
    or parsed.query
    or parsed.fragment
):
    raise SystemExit("AI Backend URL must be the internal production service")
try:
    timeout = float(ai["AI_HANDOFF_TIMEOUT_SECONDS"])
except ValueError as exc:
    raise SystemExit("AI Handoff timeout is invalid") from exc
if not 0.1 <= timeout <= 10.0:
    raise SystemExit("AI Handoff timeout is outside the allowed range")
print(":".join(flags))
PY
}

set_runtime_enabled() {
  local value="$1"
  [[ "$value" == "true" || "$value" == "false" ]] \
    || fail "internal_enabled_value_invalid"
  python3 - "$backend_env_file" "$ai_env_file" "$value" <<'PY'
import os
import stat
import sys
import tempfile
from pathlib import Path

backend_path = Path(sys.argv[1])
ai_path = Path(sys.argv[2])
new_value = sys.argv[3]

def load(path, label, keys):
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"{label} environment must be one regular file")
    metadata = path.stat()
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise SystemExit(f"{label} environment permissions are unsafe")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    matches = {}
    for key in keys:
        indexes = [
            index
            for index, line in enumerate(lines)
            if line.lstrip().startswith(f"{key}=")
        ]
        if len(indexes) != 1:
            raise SystemExit(f"{label} key must occur exactly once: {key}")
        matches[key] = indexes[0]
    return metadata, lines, matches

def render(lines, matches):
    rendered = list(lines)
    for key, index in matches.items():
        ending = "\n" if rendered[index].endswith("\n") else ""
        rendered[index] = f"{key}={new_value}{ending}"
    return "".join(rendered)

def atomic_write(path, metadata, content):
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            os.fchmod(temporary.fileno(), stat.S_IMODE(metadata.st_mode))
            os.fchown(temporary.fileno(), metadata.st_uid, metadata.st_gid)
        os.replace(temporary_name, path)
        temporary_name = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)

backend_metadata, backend_lines, backend_matches = load(
    backend_path,
    "Backend",
    ("AI_HUMAN_REVIEW_RESUME_ENABLED",),
)
ai_metadata, ai_lines, ai_matches = load(
    ai_path,
    "AI",
    (
        "AI_HUMAN_REVIEW_RESUME_ENABLED",
        "AI_HANDOFF_BACKEND_ENABLED",
    ),
)
backend_original = "".join(backend_lines)
atomic_write(
    backend_path,
    backend_metadata,
    render(backend_lines, backend_matches),
)
try:
    atomic_write(ai_path, ai_metadata, render(ai_lines, ai_matches))
except Exception:
    restored = backend_path.stat()
    atomic_write(backend_path, restored, backend_original)
    raise
PY
}

active_ai_runs() {
  compose exec -T backend python -c \
    "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production'); import django; django.setup(); from apps.audit.models import AIRun; print(AIRun.objects.filter(status_code__in=('QUEUED','RUNNING','RETRYING')).count())"
}

verify_runtime() {
  compose exec -T backend python -c \
    "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production'); import django; django.setup(); value=os.getenv('AI_HUMAN_REVIEW_RESUME_ENABLED','').strip().lower(); assert value in {'true','false'}; token=os.getenv('AI_HUMAN_REVIEW_RESUME_TOKEN',''); assert len(token.encode()) >= 32; from integrations.ai.human_review_resume import CONTEXT_RESUME_APPROVED_MODEL_CODES; assert CONTEXT_RESUME_APPROVED_MODEL_CODES == frozenset({'WPUJAC104DWH'}); print('backend_context_resume_scope=JAC104_ONLY'); print('backend_resume_enabled='+value)"
  compose exec -T --workdir /workspace/ai ai python -c \
    "import os; resume=os.getenv('AI_HUMAN_REVIEW_RESUME_ENABLED','').strip().lower(); handoff=os.getenv('AI_HANDOFF_BACKEND_ENABLED','').strip().lower(); assert resume in {'true','false'} and handoff in {'true','false'}; token=os.getenv('AI_HUMAN_REVIEW_RESUME_TOKEN',''); assert len(token.encode()) >= 32; from app.orchestration.harness.product_registry import RUNTIME_APPROVED_EXACT_MODEL_CODES; assert RUNTIME_APPROVED_EXACT_MODEL_CODES == frozenset({'WPUJAC104DWH'}); print('ai_context_resume_scope=JAC104_ONLY'); print('ai_resume_enabled='+resume); print('ai_handoff_enabled='+handoff)"
  compose exec -T backend python -c \
    "import urllib.request; response=urllib.request.urlopen('http://ai:8001/api/v1/ai/health',timeout=5); assert response.status == 200; print('backend_to_ai_health=PASS')"
}

recreate_runtime() {
  compose up -d --no-deps --force-recreate --wait ai
  compose up -d --no-deps --force-recreate --wait backend
  verify_runtime
}

environment_matches_state() {
  [[ "$(normalized_env_sha "$backend_env_file" Backend AI_HUMAN_REVIEW_RESUME_ENABLED)" \
      == "$(read_state_value backend_env_normalized_sha256)" ]] \
    && [[ "$(normalized_env_sha "$ai_env_file" AI AI_HUMAN_REVIEW_RESUME_ENABLED AI_HANDOFF_BACKEND_ENABLED)" \
      == "$(read_state_value ai_env_normalized_sha256)" ]]
}

cleanup_activation_failure() {
  local original_exit="$1"
  local restored=1
  set +e
  compose stop backend ai >/dev/null 2>&1
  set_runtime_enabled false >/dev/null 2>&1 || restored=0
  [[ "$(runtime_status 2>/dev/null)" == "false:false:false" ]] || restored=0
  if (( restored == 1 )); then
    recreate_runtime >/dev/null 2>&1 || restored=0
  fi
  if (( restored == 1 )); then
    rm -f -- "$state_file"
    printf 'AI_CONTEXT_ACTIVATION_FAILURE_RESTORED backend_resume=false ai_resume=false ai_handoff=false\n' >&2
  else
    compose stop backend ai >/dev/null 2>&1 || true
    printf 'AI_CONTEXT_ACTIVATION_FAILURE_FAIL_CLOSED backend=stopped ai=stopped\n' >&2
  fi
  exit "$original_exit"
}

cleanup_deactivation_failure() {
  local original_exit="$1"
  local restored=1
  set +e
  compose stop backend ai >/dev/null 2>&1
  set_runtime_enabled false >/dev/null 2>&1 || restored=0
  [[ "$(runtime_status 2>/dev/null)" == "false:false:false" ]] || restored=0
  if (( restored == 1 )); then
    recreate_runtime >/dev/null 2>&1 || restored=0
  fi
  if (( restored == 1 )) && environment_matches_state >/dev/null 2>&1; then
    rm -f -- "$state_file"
    printf 'AI_CONTEXT_DEACTIVATION_FAILURE_RESTORED backend_resume=false ai_resume=false ai_handoff=false\n' >&2
  else
    compose stop backend ai >/dev/null 2>&1 || true
    printf 'AI_CONTEXT_DEACTIVATION_FAILURE_FAIL_CLOSED backend=stopped ai=stopped\n' >&2
  fi
  exit "$original_exit"
}

on_exit() {
  local exit_code=$?
  if (( exit_code != 0 && activation_in_progress == 1 )); then
    trap - EXIT
    cleanup_activation_failure "$exit_code"
  fi
  if (( exit_code != 0 && deactivation_in_progress == 1 )); then
    trap - EXIT
    cleanup_deactivation_failure "$exit_code"
  fi
}

trap on_exit EXIT
resolve_release

case "$action" in
  preflight)
    [[ ! -e "$canary_state_file" ]] || fail "canary_window_is_active"
    [[ ! -e "$state_file" ]] || fail "activation_state_already_exists"
    [[ "$(runtime_status)" == "false:false:false" ]] \
      || fail "resume_and_handoff_must_start_disabled"
    [[ "$(active_ai_runs)" == "0" ]] || fail "active_ai_runs_present"
    verify_runtime
    printf 'AI_CONTEXT_ACTIVATION_PREFLIGHT_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'activation_mode=JAC104_LIMITED\n'
    printf 'backend_resume_enabled=false\n'
    printf 'ai_resume_enabled=false\n'
    printf 'ai_handoff_enabled=false\n'
    printf 'active_ai_runs=0\n'
    ;;
  activate)
    [[ ! -e "$canary_state_file" ]] || fail "canary_window_is_active"
    [[ ! -e "$state_file" ]] || fail "activation_state_already_exists"
    [[ "$(runtime_status)" == "false:false:false" ]] \
      || fail "resume_and_handoff_must_start_disabled"
    [[ "$(active_ai_runs)" == "0" ]] || fail "active_ai_runs_present"
    verify_runtime
    activation_in_progress=1
    backend_sha="$(normalized_env_sha \
      "$backend_env_file" Backend AI_HUMAN_REVIEW_RESUME_ENABLED)"
    ai_sha="$(normalized_env_sha \
      "$ai_env_file" AI AI_HUMAN_REVIEW_RESUME_ENABLED AI_HANDOFF_BACKEND_ENABLED)"
    activated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    activation_id="$(date -u +%Y%m%dT%H%M%SZ)-${expected_release_sha:0:8}"
    write_state activating "$activated_at" "$backend_sha" "$ai_sha" \
      "$activation_id"
    compose stop backend ai >/dev/null
    set_runtime_enabled true
    [[ "$(runtime_status)" == "true:true:true" ]] \
      || fail "runtime_activation_failed"
    recreate_runtime
    write_state active "$activated_at" "$backend_sha" "$ai_sha" \
      "$activation_id"
    activation_in_progress=0
    printf 'AI_CONTEXT_ACTIVATION_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'activation_id=%s\n' "$activation_id"
    printf 'activation_mode=JAC104_LIMITED\n'
    printf 'backend_resume_enabled=true\n'
    printf 'ai_resume_enabled=true\n'
    printf 'ai_handoff_enabled=true\n'
    ;;
  deactivate)
    [[ ! -e "$canary_state_file" ]] || fail "canary_window_is_active"
    if [[ ! -e "$state_file" ]]; then
      [[ "$(runtime_status)" == "false:false:false" ]] \
        || fail "activation_state_missing_while_enabled"
      verify_runtime
      printf 'AI_CONTEXT_DEACTIVATION_PASS\n'
      printf 'release_sha=%s\n' "$expected_release_sha"
      printf 'deactivation_idempotent=true\n'
      printf 'backend_resume_enabled=false\n'
      printf 'ai_resume_enabled=false\n'
      printf 'ai_handoff_enabled=false\n'
      exit 0
    fi
    validate_state
    deactivation_in_progress=1
    compose stop backend ai >/dev/null
    set_runtime_enabled false
    [[ "$(runtime_status)" == "false:false:false" ]] \
      || fail "runtime_deactivation_failed"
    environment_matches_state || fail "protected_environment_drift_detected"
    recreate_runtime
    rm -f -- "$state_file"
    deactivation_in_progress=0
    printf 'AI_CONTEXT_DEACTIVATION_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'backend_resume_enabled=false\n'
    printf 'ai_resume_enabled=false\n'
    printf 'ai_handoff_enabled=false\n'
    ;;
  status)
    [[ ! -e "$canary_state_file" ]] || fail "canary_window_is_active"
    enabled="$(runtime_status)"
    IFS=: read -r backend_resume ai_resume ai_handoff <<<"$enabled"
    verify_runtime
    if [[ -f "$state_file" ]]; then
      validate_state
      [[ "$(read_state_value phase)" == "active" ]] \
        || fail "activation_phase_not_active"
      [[ "$enabled" == "true:true:true" ]] \
        || fail "activation_state_and_runtime_disagree"
      environment_matches_state || fail "protected_environment_drift_detected"
      activation_phase=active
      activation_id="$(read_state_value activation_id)"
    else
      [[ "$enabled" == "false:false:false" ]] \
        || fail "activation_state_missing_while_enabled"
      activation_phase=inactive
      activation_id=NONE
    fi
    printf 'AI_CONTEXT_ACTIVATION_STATUS_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'activation_mode=JAC104_LIMITED\n'
    printf 'activation_phase=%s\n' "$activation_phase"
    printf 'activation_id=%s\n' "$activation_id"
    printf 'backend_resume_enabled=%s\n' "$backend_resume"
    printf 'ai_resume_enabled=%s\n' "$ai_resume"
    printf 'ai_handoff_enabled=%s\n' "$ai_handoff"
    printf 'active_ai_runs=%s\n' "$(active_ai_runs)"
    ;;
esac
