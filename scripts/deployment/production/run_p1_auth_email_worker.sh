#!/usr/bin/env bash
set -euo pipefail

base_dir=/opt/waterbridge
release_pointer="${base_dir}/shared/p1-auth-email-worker.release"
supervisor_lock=/run/lock/waterbridge-p1-auth-email-worker.lock

fail() {
  printf 'P1_AUTH_EMAIL_WORKER_FAILED: %s\n' "$1" >&2
  exit 1
}

[[ -L "$release_pointer" ]] || fail "active worker release pointer is missing"
release_dir="$(readlink -f "$release_pointer")"
[[ "$release_dir" =~ ^/opt/waterbridge/releases/[0-9a-f]{40}/payload$ ]] \
  || fail "active worker release pointer is unsafe"

compose_file="${release_dir}/infra/docker/compose/production/compose.yml"
release_env="${release_dir}/release.env"
[[ -f "$compose_file" && -f "$release_env" ]] \
  || fail "active worker release assets are incomplete"

compose() {
  docker compose --env-file "$release_env" -f "$compose_file" "$@"
}

backend_container="$(compose ps -q backend)"
[[ -n "$backend_container" ]] || fail "Backend container is unavailable"
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$backend_container")" == "healthy" ]] \
  || fail "Backend container is not healthy"

worker_process_code='import os,sys
matches=[]
for name in os.listdir("/proc"):
    if not name.isdigit() or int(name) in (1, os.getpid()):
        continue
    try:
        raw=open(f"/proc/{name}/cmdline","rb").read()
    except OSError:
        continue
    args=[part.decode("utf-8","replace") for part in raw.split(b"\0") if part]
    if "process_p1_auth_email_outbox" in args:
        matches.append(int(name))
print(" ".join(str(pid) for pid in sorted(matches)))'

worker_pids() {
  docker exec "$backend_container" python -c "$worker_process_code"
}

stop_worker() {
  local pids
  pids="$(worker_pids 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0
  docker exec "$backend_container" python -c \
    'import os,signal,sys
for value in sys.argv[1:]:
    try:
        os.kill(int(value), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, ValueError):
        pass' $pids >/dev/null 2>&1 || true
}

wait_for_worker_exit() {
  local attempt
  for attempt in {1..20}; do
    [[ -z "$(worker_pids 2>/dev/null || true)" ]] && return 0
    sleep 0.25
  done
  return 1
}

if [[ "${1:-}" == "--check" ]]; then
  read -r -a running_pids <<<"$(worker_pids)"
  [[ "${#running_pids[@]}" -eq 1 ]] \
    || fail "worker process count=${#running_pids[@]}; expected=1"
  printf 'P1_AUTH_EMAIL_WORKER_PROCESS_PASS\n'
  printf 'worker_process_count=1\n'
  exit 0
fi

cleanup() {
  local exit_code=$?
  trap - EXIT TERM INT
  stop_worker
  if [[ -n "${compose_exec_pid:-}" ]]; then
    kill "$compose_exec_pid" >/dev/null 2>&1 || true
    wait "$compose_exec_pid" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}

exec 9>"$supervisor_lock"
flock -n 9 || fail "another worker supervisor is active"

if [[ -n "$(worker_pids)" ]]; then
  stop_worker
  wait_for_worker_exit || fail "stale worker process could not be stopped"
  printf 'P1_AUTH_EMAIL_WORKER_STALE_PROCESS_CLEANED\n'
fi
trap cleanup EXIT TERM INT

printf 'P1_AUTH_EMAIL_WORKER_START\n'
compose exec -T backend \
  python manage.py process_p1_auth_email_outbox --poll-seconds 2 &
compose_exec_pid=$!
wait "$compose_exec_pid"
