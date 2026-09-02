#!/usr/bin/env bash
set -euo pipefail

expected_release_sha="${1:-}"
inquiry_id="${2:-}"
operator_ip="${3:-}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
manager="${script_dir}/manage-ai-handoff-canary.sh"
opened=0

[[ -x "$manager" ]] || {
  printf 'CANARY_RUN_FAILED reason=manager_not_executable\n' >&2
  exit 1
}

close_after_run() {
  local original_exit=$?
  if (( opened == 1 )); then
    set +e
    close_output="$($manager close \
      "$expected_release_sha" "$inquiry_id" "$operator_ip" 2>&1)"
    close_exit=$?
    printf '%s\n' "$close_output"
    if (( close_exit == 0 )) \
      && grep -q '^CANARY_CLOSE_PASS$' <<<"$close_output"; then
      printf 'CANARY_RUN_FAILURE_RESTORED\n' >&2
    else
      printf 'CANARY_RUN_FAILURE_FAIL_CLOSED\n' >&2
    fi
  fi
  exit "$original_exit"
}

trap close_after_run EXIT

"$manager" preflight \
  "$expected_release_sha" "$inquiry_id" "$operator_ip"
"$manager" open \
  "$expected_release_sha" "$inquiry_id" "$operator_ip"
opened=1
"$manager" execute \
  "$expected_release_sha" "$inquiry_id" "$operator_ip"
"$manager" close \
  "$expected_release_sha" "$inquiry_id" "$operator_ip"
opened=0

trap - EXIT
printf 'CANARY_RUN_PASS\n'
printf 'release_sha=%s\n' "$expected_release_sha"
printf 'inquiry_id=%s\n' "$inquiry_id"
printf 'backend_resume_enabled=false\n'
printf 'ai_resume_enabled=false\n'
printf 'ai_handoff_enabled=false\n'
printf 'nginx_gate=removed\n'
