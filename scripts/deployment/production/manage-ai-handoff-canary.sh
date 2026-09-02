#!/usr/bin/env bash
set -euo pipefail

action="${1:-}"
expected_release_sha="${2:-}"
inquiry_id="${3:-}"
operator_ip="${4:-}"

base_dir="${WATERBRIDGE_BASE_DIR:-/opt/waterbridge}"
backend_env_file="${WATERBRIDGE_BACKEND_ENV_FILE:-/etc/waterbridge/backend.env}"
ai_env_file="${WATERBRIDGE_AI_ENV_FILE:-/etc/waterbridge/ai.env}"
public_domain="${WATERBRIDGE_PUBLIC_DOMAIN:-waterbridge.site}"
nginx_dropin_dir="${WATERBRIDGE_NGINX_SERVER_DROPIN_DIR:-/etc/nginx/waterbridge-server.d}"
nginx_gate_file="${nginx_dropin_dir}/50-ai-handoff-canary.conf"
nginx_include="include ${nginx_dropin_dir}/*.conf;"
shared_dir="${base_dir}/shared"
state_file="${shared_dir}/ai-handoff-canary.state"
lock_file="${shared_dir}/deploy.lock"
watchdog_prefix="waterbridge-ai-handoff-canary"
max_window_minutes=15
drain_seconds=65
open_in_progress=0
close_in_progress=0
release_drift=0

fail() {
  if [[ "$action" == "preflight" ]]; then
    printf 'ENVIRONMENT_BLOCKED reason=%s\n' "$1" >&2
  else
    printf 'AI_HANDOFF_CANARY_FAILED reason=%s\n' "$1" >&2
  fi
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 \
    || fail "required_command_missing_${1}"
}

for command_name in \
  awk cat chmod date docker flock grep mktemp mv nginx python3 readlink sed \
  sha256sum systemctl systemd-run; do
  require_command "$command_name"
done

[[ "$action" =~ ^(preflight|open|execute|close|status)$ ]] \
  || fail "action_invalid"
[[ "$expected_release_sha" =~ ^[0-9a-f]{40}$ ]] \
  || fail "expected_release_sha_invalid"
[[ "$inquiry_id" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] \
  || fail "inquiry_id_invalid"
python3 - "$operator_ip" <<'PY' || fail "operator_ip_invalid"
import ipaddress
import sys

address = ipaddress.ip_address(sys.argv[1])
if address.version != 4 or not address.is_global:
    raise SystemExit(1)
PY

mkdir -p "$shared_dir"
chmod 0750 "$base_dir" "$shared_dir"
exec 9>"$lock_file"
flock -n 9 || fail "deployment_or_canary_lock_busy"

current_target=""
compose_file=""
release_env=""

resolve_release() {
  [[ -L "${base_dir}/current" ]] || fail "current_release_link_missing"
  current_target="$(readlink -f "${base_dir}/current")"
  if [[ "$current_target" != "${base_dir}/releases/${expected_release_sha}/payload" ]]; then
    if [[ "$action" == "close" \
        && "$current_target" =~ ^${base_dir}/releases/[0-9a-f]{40}/payload$ ]]; then
      release_drift=1
    else
      fail "current_release_sha_mismatch"
    fi
  fi
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

write_state() {
  local phase="$1"
  local opened_at="$2"
  local nginx_sha="$3"
  local window_id="$4"
  local temporary="${state_file}.tmp"
  {
    printf 'phase=%s\n' "$phase"
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'inquiry_id=%s\n' "$inquiry_id"
    printf 'operator_ip=%s\n' "$operator_ip"
    printf 'opened_at=%s\n' "$opened_at"
    printf 'nginx_sha_before=%s\n' "$nginx_sha"
    printf 'window_id=%s\n' "$window_id"
  } >"$temporary"
  chmod 0600 "$temporary"
  mv -f -- "$temporary" "$state_file"
}

validate_state_identity() {
  [[ -f "$state_file" ]] || fail "canary_state_missing"
  [[ "$(read_state_value release_sha)" == "$expected_release_sha" ]] \
    || fail "canary_state_release_mismatch"
  [[ "$(read_state_value inquiry_id)" == "$inquiry_id" ]] \
    || fail "canary_state_inquiry_mismatch"
  [[ "$(read_state_value operator_ip)" == "$operator_ip" ]] \
    || fail "canary_state_operator_mismatch"
}

runtime_status() {
  python3 - "$backend_env_file" "$ai_env_file" <<'PY'
import hmac
import os
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit

def read_values(raw_path, label):
    path = Path(raw_path)
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"{label} environment must be one regular file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"{label} environment grants group or other access")
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

nginx_dump_sha() {
  local dump
  dump="$(mktemp)"
  if ! nginx -T >"$dump" 2>&1; then
    rm -f -- "$dump"
    fail "nginx_configuration_invalid"
  fi
  if ! python3 - "$dump" "$public_domain" "$nginx_include" <<'PY'; then
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="strict")
domain = sys.argv[2]
required_include = sys.argv[3]
server_blocks = []
current = []
depth = 0

for raw_line in text.splitlines():
    line = raw_line.split("#", 1)[0]
    if not current:
        if re.match(r"^\s*server\s*\{", line):
            current = [line]
            depth = line.count("{") - line.count("}")
        continue
    current.append(line)
    depth += line.count("{") - line.count("}")
    if depth == 0:
        server_blocks.append("\n".join(current))
        current = []

domain_pattern = re.compile(
    rf"server_name\s+[^;]*\b{re.escape(domain)}\b[^;]*;"
)
candidates = [
    block
    for block in server_blocks
    if domain_pattern.search(block)
    and required_include in block
    and "127.0.0.1:18080" in block
]
if len(candidates) != 1:
    raise SystemExit(1)
PY
    rm -f -- "$dump"
    fail "nginx_canary_server_scope_invalid"
  fi
  if [[ ! -d "$nginx_dropin_dir" ]]; then
    rm -f -- "$dump"
    fail "nginx_canary_dropin_directory_missing"
  fi
  sha256sum "$dump" | awk '{print $1}'
  rm -f -- "$dump"
}

install_gate() {
  [[ -d "$nginx_dropin_dir" ]] || fail "nginx_canary_dropin_directory_missing"
  [[ ! -e "$nginx_gate_file" ]] || fail "nginx_canary_gate_already_exists"
  local temporary="${nginx_gate_file}.tmp"
  cat >"$temporary" <<EOF
# Managed only by manage-ai-handoff-canary.sh. No secrets belong here.
location ~ ^/api/v1/inquiries/${inquiry_id}/(submit|answers)/?$ {
    allow ${operator_ip};
    deny all;
    proxy_pass http://127.0.0.1:18080;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Correlation-ID \$http_x_correlation_id;
    proxy_connect_timeout 5s;
    proxy_read_timeout 65s;
}

location ~ "^/api/v1/inquiries/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}/(submit|answers)/?$" {
    deny all;
}
EOF
  chmod 0644 "$temporary"
  mv -f -- "$temporary" "$nginx_gate_file"
  if ! nginx -t >/dev/null 2>&1; then
    rm -f -- "$nginx_gate_file"
    fail "nginx_canary_gate_validation_failed"
  fi
  systemctl reload nginx
}

restore_nginx() {
  local expected_sha="$1"
  rm -f -- "$nginx_gate_file"
  local restored_sha
  restored_sha="$(nginx_dump_sha)"
  [[ "$restored_sha" == "$expected_sha" ]] \
    || return 1
  nginx -t >/dev/null 2>&1
  systemctl reload nginx
}

active_ai_runs() {
  compose exec -T backend python -c \
    "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production'); import django; django.setup(); from apps.audit.models import AIRun; print(AIRun.objects.filter(status_code__in=('QUEUED','RUNNING','RETRYING')).count())"
}

pending_human_reviews() {
  compose exec -T backend python -c \
    "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production'); import django; django.setup(); from apps.inquiries.models import HumanReview; print(HumanReview.objects.filter(status_code='PENDING').count())"
}

target_snapshot() {
  local opened_at="${1:-}"
  compose exec -T backend python -c \
    "import os,sys; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production'); import django; django.setup(); from django.utils.dateparse import parse_datetime; from apps.audit.models import AIRun; from apps.consultations.models import Consultation,ConsultationHandoff; from apps.inquiries.models import HumanReview,HumanReviewResumeDispatch,Inquiry; inquiry=Inquiry.objects.select_related('initiated_by','subscription__product_model').get(public_id=sys.argv[1]); assert inquiry.initiated_by.is_synthetic; assert inquiry.subscription.status_code == 'ACTIVE'; assert inquiry.subscription.product_model.model_code == 'WPUJAC104DWH'; runs=AIRun.objects.filter(inquiry=inquiry); handoffs=ConsultationHandoff.objects.filter(inquiry=inquiry); consultations=Consultation.objects.filter(inquiry=inquiry); reviews=HumanReview.objects.filter(inquiry=inquiry); dispatches=HumanReviewResumeDispatch.objects.filter(human_review__in=reviews); print('target_status='+inquiry.status_code); print('target_state_version='+str(inquiry.state_version)); print('target_ai_runs='+str(runs.count())); print('target_reviews='+str(reviews.count())); print('target_resume_dispatches='+str(dispatches.count())); print('target_handoffs='+str(handoffs.count())); print('target_consultations='+str(consultations.count())); print('target_payload_hashes='+','.join(handoffs.order_by('created_at').values_list('payload_sha256',flat=True))); opened=parse_datetime(sys.argv[2]) if sys.argv[2] else None; window=AIRun.objects.filter(created_at__gte=opened) if opened else AIRun.objects.none(); print('window_ai_runs='+str(window.count())); print('other_window_ai_runs='+str(window.exclude(inquiry=inquiry).count()))" \
    "$inquiry_id" "$opened_at"
}

assert_target_baseline() {
  local snapshot="$1"
  grep -q '^target_ai_runs=0$' <<<"$snapshot" \
    || fail "target_ai_run_baseline_not_zero"
  grep -q '^target_reviews=0$' <<<"$snapshot" \
    || fail "target_review_baseline_not_zero"
  grep -q '^target_resume_dispatches=0$' <<<"$snapshot" \
    || fail "target_resume_dispatch_baseline_not_zero"
  grep -q '^target_handoffs=0$' <<<"$snapshot" \
    || fail "target_handoff_baseline_not_zero"
  grep -q '^target_consultations=0$' <<<"$snapshot" \
    || fail "target_consultation_baseline_not_zero"
  grep -q '^target_status=DRAFT$' <<<"$snapshot" \
    || fail "target_status_baseline_invalid"
  grep -q '^target_state_version=1$' <<<"$snapshot" \
    || fail "target_state_version_baseline_invalid"
}

recreate_runtime() {
  compose up -d --no-deps --force-recreate --wait ai
  compose up -d --no-deps --force-recreate --wait backend
  verify_runtime
}

verify_runtime() {
  compose exec -T backend python -c \
    "import os; value=os.getenv('AI_HUMAN_REVIEW_RESUME_ENABLED','').strip().lower(); assert value in {'true','false'}; token=os.getenv('AI_HUMAN_REVIEW_RESUME_TOKEN',''); assert len(token.encode()) >= 32; print('backend_resume_enabled='+value); print('backend_resume_token=PROTECTED')"
  compose exec -T ai python -c \
    "import os; resume=os.getenv('AI_HUMAN_REVIEW_RESUME_ENABLED','').strip().lower(); handoff=os.getenv('AI_HANDOFF_BACKEND_ENABLED','').strip().lower(); assert resume in {'true','false'} and handoff in {'true','false'}; token=os.getenv('AI_HUMAN_REVIEW_RESUME_TOKEN',''); assert len(token.encode()) >= 32; print('ai_resume_enabled='+resume); print('ai_handoff_enabled='+handoff); print('ai_resume_token=PROTECTED')"
  compose exec -T backend python -c \
    "import urllib.request; response=urllib.request.urlopen('http://ai:8001/api/v1/ai/health',timeout=5); assert response.status == 200; print('backend_to_ai_health=PASS')"
}

cancel_watchdog() {
  local window_id="$1"
  [[ -n "$window_id" ]] || return 0
  systemctl stop "${watchdog_prefix}-${window_id}.timer" >/dev/null 2>&1 || true
  systemctl reset-failed "${watchdog_prefix}-${window_id}.service" >/dev/null 2>&1 || true
}

schedule_watchdog() {
  local window_id="$1"
  local script_path="${current_target}/scripts/deployment/production/manage-ai-handoff-canary.sh"
  [[ -x "$script_path" ]] || fail "canary_script_not_executable_in_current_release"
  systemd-run \
    --quiet \
    --collect \
    --unit "${watchdog_prefix}-${window_id}" \
    --on-active "${max_window_minutes}m" \
    --timer-property AccuracySec=1s \
    --setenv WATERBRIDGE_CANARY_WATCHDOG=1 \
    "$script_path" close "$expected_release_sha" "$inquiry_id" "$operator_ip"
}

cleanup_open_failure() {
  local original_exit="$1"
  local nginx_sha=""
  local window_id=""
  local restored=1
  set +e
  if [[ -f "$state_file" ]]; then
    nginx_sha="$(read_state_value nginx_sha_before)"
    window_id="$(read_state_value window_id)"
  fi
  compose stop backend ai >/dev/null 2>&1
  set_runtime_enabled false >/dev/null 2>&1 || restored=0
  if [[ "$(runtime_status 2>/dev/null)" == "false:false:false" ]]; then
    recreate_runtime >/dev/null 2>&1 || restored=0
  else
    restored=0
  fi
  if [[ "$nginx_sha" =~ ^[0-9a-f]{64}$ ]]; then
    restore_nginx "$nginx_sha" >/dev/null 2>&1 || restored=0
  else
    restored=0
  fi
  cancel_watchdog "$window_id"
  if (( restored == 1 )); then
    rm -f -- "$state_file"
    printf 'CANARY_OPEN_FAILURE_RESTORED\n' >&2
  else
    [[ -f "$nginx_gate_file" ]] || install_gate >/dev/null 2>&1 || true
    compose stop backend ai >/dev/null 2>&1 || true
    printf 'CANARY_OPEN_FAILURE_FAIL_CLOSED backend=stopped ai=stopped nginx_gate=retained\n' >&2
  fi
  exit "$original_exit"
}

cleanup_close_failure() {
  local original_exit="$1"
  local nginx_sha=""
  local window_id=""
  local restored=1
  set +e
  if [[ -f "$state_file" ]]; then
    nginx_sha="$(read_state_value nginx_sha_before)"
    window_id="$(read_state_value window_id)"
  fi
  compose stop backend ai >/dev/null 2>&1
  set_runtime_enabled false >/dev/null 2>&1 || restored=0
  if [[ "$(runtime_status 2>/dev/null)" == "false:false:false" ]]; then
    recreate_runtime >/dev/null 2>&1 || restored=0
  else
    restored=0
  fi
  if [[ "$nginx_sha" =~ ^[0-9a-f]{64}$ ]]; then
    restore_nginx "$nginx_sha" >/dev/null 2>&1 || restored=0
  elif [[ -e "$nginx_gate_file" ]]; then
    restored=0
  fi
  if (( restored == 1 )); then
    cancel_watchdog "$window_id"
    rm -f -- "$state_file"
    printf 'CANARY_CLOSE_FAILURE_RESTORED backend_resume=false ai_resume=false ai_handoff=false nginx_gate=removed\n' >&2
  else
    [[ -f "$nginx_gate_file" ]] || install_gate >/dev/null 2>&1 || true
    compose stop backend ai >/dev/null 2>&1 || true
    printf 'CANARY_CLOSE_FAILURE_FAIL_CLOSED backend=stopped ai=stopped nginx_gate=retained\n' >&2
  fi
  exit "$original_exit"
}

on_exit() {
  local exit_code=$?
  if (( exit_code != 0 && open_in_progress == 1 )); then
    trap - EXIT
    cleanup_open_failure "$exit_code"
  fi
  if (( exit_code != 0 && close_in_progress == 1 )); then
    trap - EXIT
    cleanup_close_failure "$exit_code"
  fi
}

trap on_exit EXIT

close_window() {
  if [[ ! -f "$state_file" ]]; then
    [[ "$(runtime_status)" == "false:false:false" ]] \
      || fail "canary_state_missing_while_enabled"
    [[ ! -e "$nginx_gate_file" ]] \
      || fail "canary_state_missing_with_gate"
    verify_runtime
    printf 'CANARY_CLOSE_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'release_drift=%s\n' "$release_drift"
    printf 'close_idempotent=true\n'
    printf 'backend_resume_enabled=false\n'
    printf 'ai_resume_enabled=false\n'
    printf 'ai_handoff_enabled=false\n'
    printf 'nginx_gate=removed\n'
    return 0
  fi
  validate_state_identity
  close_in_progress=1
  local nginx_sha window_id opened_at
  nginx_sha="$(read_state_value nginx_sha_before)"
  window_id="$(read_state_value window_id)"
  opened_at="$(read_state_value opened_at)"
  [[ "$nginx_sha" =~ ^[0-9a-f]{64}$ ]] || fail "canary_state_nginx_sha_invalid"

  compose stop backend ai >/dev/null
  set_runtime_enabled false
  [[ "$(runtime_status)" == "false:false:false" ]] \
    || fail "canary_false_restore_failed"
  recreate_runtime
  if ! restore_nginx "$nginx_sha"; then
    install_gate || true
    fail "nginx_original_checksum_not_restored"
  fi
  [[ "${WATERBRIDGE_CANARY_WATCHDOG:-0}" == "1" ]] \
    || cancel_watchdog "$window_id"
  rm -f -- "$state_file"
  close_in_progress=0
  printf 'CANARY_CLOSE_PASS\n'
  printf 'release_sha=%s\n' "$expected_release_sha"
  printf 'release_drift=%s\n' "$release_drift"
  printf 'backend_resume_enabled=false\n'
  printf 'ai_resume_enabled=false\n'
  printf 'ai_handoff_enabled=false\n'
  printf 'nginx_gate=removed\n'
  printf 'active_ai_runs=%s\n' "$(active_ai_runs)"
  target_snapshot "$opened_at"
}

resolve_release

case "$action" in
  preflight)
    [[ ! -e "$state_file" && ! -e "$nginx_gate_file" ]] \
      || fail "existing_canary_window_or_gate"
    [[ "$(runtime_status)" == "false:false:false" ]] \
      || fail "resume_and_handoff_must_start_disabled"
    nginx_sha="$(nginx_dump_sha)"
    [[ "$(active_ai_runs)" == "0" ]] || fail "active_ai_runs_present"
    [[ "$(pending_human_reviews)" == "0" ]] \
      || fail "pending_human_reviews_present"
    snapshot="$(target_snapshot)"
    assert_target_baseline "$snapshot"
    printf 'CANARY_PREFLIGHT_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'backend_resume_enabled=false\n'
    printf 'ai_resume_enabled=false\n'
    printf 'ai_handoff_enabled=false\n'
    printf 'nginx_sha=%s\n' "$nginx_sha"
    printf 'active_ai_runs=0\n'
    printf 'pending_human_reviews=0\n'
    printf '%s\n' "$snapshot"
    ;;
  open)
    open_in_progress=1
    [[ ! -e "$state_file" && ! -e "$nginx_gate_file" ]] \
      || fail "existing_canary_window_or_gate"
    [[ "$(runtime_status)" == "false:false:false" ]] \
      || fail "resume_and_handoff_must_start_disabled"
    nginx_sha="$(nginx_dump_sha)"
    [[ "$(active_ai_runs)" == "0" ]] || fail "active_ai_runs_present"
    [[ "$(pending_human_reviews)" == "0" ]] \
      || fail "pending_human_reviews_present"
    snapshot="$(target_snapshot)"
    assert_target_baseline "$snapshot"
    opened_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    window_id="$(date -u +%Y%m%dT%H%M%SZ)-${expected_release_sha:0:8}"
    write_state opening "$opened_at" "$nginx_sha" "$window_id"
    install_gate
    deadline=$((SECONDS + drain_seconds))
    while (( SECONDS < deadline )); do
      [[ "$(active_ai_runs)" == "0" ]] || fail "ai_run_started_during_drain"
      [[ "$(pending_human_reviews)" == "0" ]] \
        || fail "human_review_started_during_drain"
      sleep 5
    done
    compose stop backend ai >/dev/null
    set_runtime_enabled true
    [[ "$(runtime_status)" == "true:true:true" ]] \
      || fail "canary_true_activation_failed"
    if ! recreate_runtime; then
      compose stop backend ai >/dev/null 2>&1 || true
      set_runtime_enabled false || true
      recreate_runtime >/dev/null 2>&1 || true
      restore_nginx "$nginx_sha" >/dev/null 2>&1 || true
      fail "runtime_recreate_after_activation_failed"
    fi
    schedule_watchdog "$window_id"
    write_state open "$opened_at" "$nginx_sha" "$window_id"
    open_in_progress=0
    printf 'CANARY_OPEN_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'window_id=%s\n' "$window_id"
    printf 'window_expires_after_minutes=%s\n' "$max_window_minutes"
    printf 'backend_resume_enabled=true\n'
    printf 'ai_resume_enabled=true\n'
    printf 'ai_handoff_enabled=true\n'
    printf 'nginx_gate=active\n'
    ;;
  execute)
    validate_state_identity
    [[ "$(read_state_value phase)" == "open" ]] \
      || fail "canary_window_not_open"
    [[ -f "$nginx_gate_file" ]] || fail "canary_gate_missing"
    [[ "$(runtime_status)" == "true:true:true" ]] \
      || fail "resume_and_handoff_not_enabled"
    [[ "$(active_ai_runs)" == "0" ]] || fail "active_ai_runs_present"
    [[ "$(pending_human_reviews)" == "0" ]] \
      || fail "pending_human_reviews_present"
    snapshot="$(target_snapshot "$(read_state_value opened_at)")"
    assert_target_baseline "$snapshot"
    execution="$(compose exec -T backend python manage.py \
      run_ai_context_resume_handoff_canary \
      --inquiry-id "$inquiry_id" \
      --expected-release-sha "$expected_release_sha" \
      --apply \
      --json)"
    python3 - "$execution" "$expected_release_sha" "$inquiry_id" <<'PY' \
      || fail "automatic_context_canary_report_invalid"
import json
import sys

report = json.loads(sys.argv[1])
expected_release = sys.argv[2]
expected_inquiry = sys.argv[3]
expected = {
    "overall_status": "AWS_AUTO_CONTEXT_HANDOFF_PASS",
    "release_sha": expected_release,
    "inquiry_id": expected_inquiry,
    "initial_context_agent_calls": 0,
    "initial_context_provider_calls": 0,
    "context_agent_calls": 1,
    "provider_calls": 1,
    "resume_attempt_count": 1,
    "resume_dispatch_count": 1,
    "handoff_count": 1,
    "consultation_count": 1,
    "context_synthesis_status": "SUCCEEDED",
    "fallback_reason": None,
    "decision_replay_idempotent": True,
    "handoff_http_replay_idempotent": True,
    "sensitive_data_exposure": "NONE_DETECTED",
}
if not isinstance(report, dict) or any(
    report.get(key) != value for key, value in expected.items()
):
    raise SystemExit(1)
PY
    final_snapshot="$(target_snapshot "$(read_state_value opened_at)")"
    grep -q '^target_status=CONSULTATION_REQUIRED$' <<<"$final_snapshot" \
      || fail "target_final_status_invalid"
    grep -q '^target_ai_runs=1$' <<<"$final_snapshot" \
      || fail "target_final_ai_run_count_invalid"
    grep -q '^target_reviews=1$' <<<"$final_snapshot" \
      || fail "target_final_review_count_invalid"
    grep -q '^target_resume_dispatches=1$' <<<"$final_snapshot" \
      || fail "target_final_resume_dispatch_count_invalid"
    grep -q '^target_handoffs=1$' <<<"$final_snapshot" \
      || fail "target_final_handoff_count_invalid"
    grep -q '^target_consultations=1$' <<<"$final_snapshot" \
      || fail "target_final_consultation_count_invalid"
    grep -q '^other_window_ai_runs=0$' <<<"$final_snapshot" \
      || fail "other_inquiry_ai_run_detected"
    printf 'CANARY_EXECUTE_PASS\n'
    printf '%s\n' "$execution"
    printf '%s\n' "$final_snapshot"
    ;;
  close)
    close_window
    ;;
  status)
    enabled="$(runtime_status)"
    IFS=: read -r backend_resume ai_resume ai_handoff <<<"$enabled"
    printf 'CANARY_STATUS_PASS\n'
    printf 'release_sha=%s\n' "$expected_release_sha"
    printf 'backend_resume_enabled=%s\n' "$backend_resume"
    printf 'ai_resume_enabled=%s\n' "$ai_resume"
    printf 'ai_handoff_enabled=%s\n' "$ai_handoff"
    if [[ -f "$state_file" ]]; then
      validate_state_identity
      printf 'window_phase=%s\n' "$(read_state_value phase)"
      printf 'window_id=%s\n' "$(read_state_value window_id)"
      printf 'nginx_gate=%s\n' "$([[ -f "$nginx_gate_file" ]] && echo active || echo missing)"
      printf 'active_ai_runs=%s\n' "$(active_ai_runs)"
      target_snapshot "$(read_state_value opened_at)"
    else
      printf 'window_phase=closed\n'
      printf 'nginx_gate=%s\n' "$([[ -f "$nginx_gate_file" ]] && echo unexpected || echo removed)"
      printf 'active_ai_runs=%s\n' "$(active_ai_runs)"
      target_snapshot
    fi
    ;;
esac
