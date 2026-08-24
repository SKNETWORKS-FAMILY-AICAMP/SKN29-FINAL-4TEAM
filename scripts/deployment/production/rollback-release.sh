#!/usr/bin/env bash
set -euo pipefail

base_dir=/opt/waterbridge
previous_link="${base_dir}/previous"
current_link="${base_dir}/current"

exec 9>"${base_dir}/shared/deploy.lock"
flock -n 9 || {
  echo "ROLLBACK_FAILED: another deployment holds the lock" >&2
  exit 1
}

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
  docker compose --env-file "$current_env" -f "$current_compose" stop
  printf 'ROLLBACK_PASS\n'
  printf 'rollback_target=NO_PREVIOUS_RELEASE_NEW_SERVICES_STOPPED\n'
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
