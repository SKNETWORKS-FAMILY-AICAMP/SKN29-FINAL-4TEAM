#!/usr/bin/env bash
set -euo pipefail

base_dir=/opt/waterbridge
previous_link="${base_dir}/previous"
current_link="${base_dir}/current"
worker_pointer="${base_dir}/shared/p1-auth-email-worker.release"
worker_service=waterbridge-p1-auth-email-worker.service

deactivate_worker() {
  systemctl stop "$worker_service" >/dev/null 2>&1 || true
  rm -f -- "$worker_pointer"
}

activate_worker_release() {
  local target="$1"
  local runner="${target}/scripts/deployment/production/run_p1_auth_email_worker.sh"
  local unit="${target}/infra/systemd/${worker_service}"
  [[ "$target" =~ ^/opt/waterbridge/releases/[0-9a-f]{40}/payload$ ]]
  [[ -f "$runner" && -f "$unit" ]]
  install -o root -g root -m 0750 \
    "$runner" "${base_dir}/shared/run-p1-auth-email-worker.sh"
  install -o root -g root -m 0644 \
    "$unit" "/etc/systemd/system/${worker_service}"
  ln -sfn "$target" "${worker_pointer}.next"
  mv -Tf "${worker_pointer}.next" "$worker_pointer"
  systemctl daemon-reload
  systemctl enable "$worker_service" >/dev/null
  systemctl restart "$worker_service"
  sleep 2
  systemctl is-active --quiet "$worker_service"
  sleep 5
  systemctl is-active --quiet "$worker_service"
  "${base_dir}/shared/run-p1-auth-email-worker.sh" --check
}

exec 9>"${base_dir}/shared/deploy.lock"
flock -n 9 || {
  echo "ROLLBACK_FAILED: another deployment holds the lock" >&2
  exit 1
}

if [[ -f "${base_dir}/shared/ai-handoff-canary.state" ]]; then
  echo "ROLLBACK_BLOCKED: active AI Handoff Canary window" >&2
  exit 1
fi

if [[ ! -L "$previous_link" ]]; then
  [[ -L "$current_link" ]] || {
    echo "ROLLBACK_FAILED: neither previous nor current release is available" >&2
    exit 1
  }
  current_target="$(readlink -f "$current_link")"
  current_compose="${current_target}/infra/docker/compose/production/compose.yml"
  current_env="${current_target}/release.env"
  [[ -f "$current_compose" && -f "$current_env" ]] || {
    echo "ROLLBACK_FAILED: current release files are incomplete" >&2
    exit 1
  }
  deactivate_worker
  docker compose --env-file "$current_env" -f "$current_compose" stop
  printf 'ROLLBACK_PASS\n'
  printf 'rollback_target=NO_PREVIOUS_RELEASE_NEW_SERVICES_STOPPED\n'
  printf 'p1_auth_email_worker=STOPPED_NO_PREVIOUS_RELEASE\n'
  exit 0
fi

previous_target="$(readlink -f "$previous_link")"
previous_compose="${previous_target}/infra/docker/compose/production/compose.yml"
previous_env="${previous_target}/release.env"
[[ -f "$previous_compose" && -f "$previous_env" ]] || {
  echo "ROLLBACK_FAILED: previous release files are incomplete" >&2
  exit 1
}

docker compose --env-file "$previous_env" -f "$previous_compose" up -d --wait --no-build --remove-orphans
if [[ -f "${previous_target}/scripts/deployment/production/run_p1_auth_email_worker.sh" \
    && -f "${previous_target}/infra/systemd/${worker_service}" ]]; then
  activate_worker_release "$previous_target"
  worker_status=SYSTEMD_ACTIVE_PROCESS_1
else
  deactivate_worker
  worker_status=STOPPED_UNSUPPORTED_RELEASE
fi
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:18080/health >/dev/null

current_target=""
if [[ -L "$current_link" ]]; then
  current_target="$(readlink -f "$current_link")"
fi
ln -sfn "$previous_target" "${base_dir}/current.next"
mv -Tf "${base_dir}/current.next" "$current_link"
if [[ -n "$current_target" && "$current_target" != "$previous_target" ]]; then
  ln -sfn "$current_target" "${base_dir}/previous.next"
  mv -Tf "${base_dir}/previous.next" "$previous_link"
fi

printf 'ROLLBACK_PASS\n'
printf 'p1_auth_email_worker=%s\n' "$worker_status"
