#!/usr/bin/env bash
set -euo pipefail

release_sha="${1:?release SHA is required}"
storage_bucket="${2:?storage bucket is required}"
aws_region="${3:?AWS region is required}"
backend_env_file="${4:-/etc/waterbridge/backend.env}"
ai_env_file="${5:-/etc/waterbridge/ai.env}"
rds_ca_file="${6:-/etc/waterbridge/certs/rds-ca.pem}"

[[ "$release_sha" =~ ^[0-9a-f]{40}$ ]] || {
  echo "DEPLOYMENT_FAILED: release SHA must be 40 lowercase hexadecimal characters" >&2
  exit 1
}

base_dir=/opt/waterbridge
release_dir="${base_dir}/releases/${release_sha}"
payload_dir="${release_dir}/payload"
archive_path="${release_dir}/release.tar.gz"
checksum_path="${archive_path}.sha256"
compose_file="${payload_dir}/infra/docker/compose/production/compose.yml"
release_env="${payload_dir}/release.env"
lock_file="${base_dir}/shared/deploy.lock"

mkdir -p "$release_dir" "${base_dir}/shared"
chmod 0750 "$base_dir" "${base_dir}/releases" "${base_dir}/shared" "$release_dir"

exec 9>"$lock_file"
flock -n 9 || {
  echo "DEPLOYMENT_FAILED: another deployment holds the lock" >&2
  exit 1
}

aws s3 cp \
  "s3://${storage_bucket}/releases/${release_sha}/release.tar.gz" \
  "$archive_path" \
  --region "$aws_region" \
  --only-show-errors
aws s3 cp \
  "s3://${storage_bucket}/releases/${release_sha}/release.tar.gz.sha256" \
  "$checksum_path" \
  --region "$aws_region" \
  --only-show-errors

expected_sha256="$(awk 'NR==1 {print $1}' "$checksum_path")"
actual_sha256="$(sha256sum "$archive_path" | awk '{print $1}')"
[[ "$expected_sha256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "DEPLOYMENT_FAILED: release checksum file is invalid" >&2
  exit 1
}
[[ "$actual_sha256" == "$expected_sha256" ]] || {
  echo "DEPLOYMENT_FAILED: release checksum mismatch" >&2
  exit 1
}

expected_payload_dir="${base_dir}/releases/${release_sha}/payload"
[[ "$payload_dir" == "$expected_payload_dir" ]] || {
  echo "DEPLOYMENT_FAILED: unsafe payload directory" >&2
  exit 1
}
rm -rf -- "$payload_dir"
mkdir -p "$payload_dir"
tar -xzf "$archive_path" -C "$payload_dir"

[[ -f "$compose_file" ]] || {
  echo "DEPLOYMENT_FAILED: production compose file is missing" >&2
  exit 1
}
[[ -f "$release_env" ]] || {
  echo "DEPLOYMENT_FAILED: non-secret release.env is missing" >&2
  exit 1
}
[[ -f "$backend_env_file" && -f "$ai_env_file" && -s "$rds_ca_file" ]] || {
  echo "DEPLOYMENT_FAILED: protected service env or RDS CA is unavailable" >&2
  exit 1
}
for protected_file in "$backend_env_file" "$ai_env_file"; do
  runtime_mode="$(stat -c '%a' "$protected_file")"
  if (( (8#$runtime_mode & 8#077) != 0 )); then
    echo "DEPLOYMENT_FAILED: runtime env permissions grant group/other access" >&2
    exit 1
  fi
done

required_backend_keys=(
  DJANGO_SECRET_KEY
  DJANGO_TIME_ZONE
  DJANGO_ALLOWED_HOSTS
  DJANGO_CORS_ALLOWED_ORIGINS
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_HOST
  POSTGRES_PORT
  POSTGRES_SSLMODE
)
required_ai_keys=(
  OPENAI_API_KEY
  AI_LLM_MODEL
  AI_VECTOR_DSN
  AI_VECTOR_TABLE_NAME
  AI_EMBEDDING_REVISION
  EMBEDDING_MODEL_NAME
  EMBEDDING_DIMENSION
  AI_HANDOFF_INTERNAL_TOKEN
)
for key in "${required_backend_keys[@]}"; do
  grep -Eq "^[[:space:]]*${key}=.+$" "$backend_env_file" || {
    echo "DEPLOYMENT_FAILED: required Backend runtime key is missing: ${key}" >&2
    exit 1
  }
done
for key in "${required_ai_keys[@]}"; do
  grep -Eq "^[[:space:]]*${key}=.+$" "$ai_env_file" || {
    echo "DEPLOYMENT_FAILED: required AI runtime key is missing: ${key}" >&2
    exit 1
  }
done
grep -Eq '^[[:space:]]*POSTGRES_SSLMODE=verify-full[[:space:]]*$' "$backend_env_file" || {
  echo "DEPLOYMENT_FAILED: POSTGRES_SSLMODE must be verify-full" >&2
  exit 1
}

{
  printf '\nAWS_REGION=%s\n' "$aws_region"
  printf 'TEMPO_S3_BUCKET=%s\n' "$storage_bucket"
  printf 'BACKEND_RUNTIME_ENV_FILE=%s\n' "$backend_env_file"
  printf 'AI_RUNTIME_ENV_FILE=%s\n' "$ai_env_file"
  printf 'RDS_CA_HOST_PATH=%s\n' "$rds_ca_file"
  printf 'WEB_HOST_PORT=18080\n'
} >>"$release_env"
chmod 0640 "$release_env"

compose() {
  docker compose --env-file "$release_env" -f "$compose_file" "$@"
}

mapfile -t services < <(compose config --services | sort)
expected_services=(ai backend trace-store web)
[[ "${services[*]}" == "${expected_services[*]}" ]] || {
  echo "DEPLOYMENT_FAILED: compose service boundary is not web/backend/ai/trace-store" >&2
  exit 1
}
if compose config | grep -Eiq '(^|[[:space:]])postgres(ql)?([:[:space:]]|$)'; then
  echo "DEPLOYMENT_FAILED: production compose must not contain PostgreSQL" >&2
  exit 1
fi

previous_target=""
if [[ -L "${base_dir}/current" ]]; then
  previous_target="$(readlink -f "${base_dir}/current")"
fi

rollback() {
  local exit_code=$?
  trap - ERR
  echo "DEPLOYMENT_FAILED: rolling back without deleting volumes" >&2
  if [[ -n "$previous_target" && -f "${previous_target}/infra/docker/compose/production/compose.yml" ]]; then
    local previous_env="${previous_target}/release.env"
    local previous_compose="${previous_target}/infra/docker/compose/production/compose.yml"
    docker compose --env-file "$previous_env" -f "$previous_compose" up -d --wait --no-build --remove-orphans || true
  else
    compose stop || true
  fi
  exit "$exit_code"
}
trap rollback ERR

compose pull
compose run --rm --no-deps trace-store \
  -config.file=/etc/tempo/tempo.yml \
  -config.expand-env=true \
  -config.verify=true
compose run --rm --no-deps \
  --volume "${payload_dir}/scripts/deployment/production/validate_backend_runtime.py:/tmp/validate_backend_runtime.py:ro" \
  backend python /tmp/validate_backend_runtime.py
compose run --rm --no-deps \
  --volume "${payload_dir}/scripts/deployment/production/validate_ai_readonly_runtime.py:/tmp/validate_ai_readonly_runtime.py:ro" \
  ai python /tmp/validate_ai_readonly_runtime.py
compose up -d --wait --no-build --remove-orphans

compose exec -T backend python -c \
  "import urllib.request; response=urllib.request.urlopen('http://ai:8001/api/v1/ai/health', timeout=5); assert response.status == 200; print('BACKEND_TO_AI_SOCKET_PASS')"

trace_canary_script="${payload_dir}/scripts/deployment/production/trace_canary.py"
[[ -f "$trace_canary_script" ]] || {
  echo "DEPLOYMENT_FAILED: Trace canary script is missing" >&2
  false
}
canary_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
canary_output="$(compose run --rm --no-deps \
  --volume "${trace_canary_script}:/tmp/trace_canary.py:ro" \
  ai python /tmp/trace_canary.py emit)"
trace_id="$(sed -n 's/^TRACE_CANARY_EXPORTED trace_id=\([0-9a-f]\{32\}\)$/\1/p' <<<"$canary_output")"
[[ "$trace_id" =~ ^[0-9a-f]{32}$ ]] || {
  echo "DEPLOYMENT_FAILED: AI Trace canary did not return a canonical trace ID" >&2
  false
}

s3_block_found=false
for _ in {1..24}; do
  object_times="$(aws s3api list-objects-v2 \
    --bucket "$storage_bucket" \
    --prefix tempo/ \
    --query 'Contents[].LastModified' \
    --output text \
    --region "$aws_region")"
  for object_time in $object_times; do
    if [[ "$object_time" > "$canary_started" || "$object_time" == "$canary_started" ]]; then
      s3_block_found=true
      break 2
    fi
  done
  sleep 10
done
[[ "$s3_block_found" == true ]] || {
  echo "DEPLOYMENT_FAILED: no Tempo S3 block appeared after the AI canary" >&2
  false
}

compose run --rm --no-deps \
  --volume "${trace_canary_script}:/tmp/trace_canary.py:ro" \
  ai python /tmp/trace_canary.py query "$trace_id"
compose restart trace-store
compose up -d --wait --no-build trace-store
compose run --rm --no-deps \
  --volume "${trace_canary_script}:/tmp/trace_canary.py:ro" \
  ai python /tmp/trace_canary.py query "$trace_id"
printf 'TRACE_S3_RESTART_QUERY_PASS\n'

curl --fail --silent --show-error --max-time 10 \
  --header 'Host: waterbridge.site' \
  http://127.0.0.1:18080/ >/dev/null
health_headers="$(mktemp)"
trap 'rm -f "$health_headers"' EXIT
curl --fail --silent --show-error --max-time 10 \
  --header 'Host: waterbridge.site' \
  --dump-header "$health_headers" \
  http://127.0.0.1:18080/health >/dev/null
grep -Eiq '^X-Correlation-ID:[[:space:]]*[0-9a-f-]+[[:space:]]*$' "$health_headers" \
  || {
    echo "DEPLOYMENT_FAILED: /health is missing X-Correlation-ID" >&2
    false
  }

if [[ -n "$previous_target" && "$previous_target" != "$payload_dir" ]]; then
  ln -sfn "$previous_target" "${base_dir}/previous.next"
  mv -Tf "${base_dir}/previous.next" "${base_dir}/previous"
fi
ln -sfn "$payload_dir" "${base_dir}/current.next"
mv -Tf "${base_dir}/current.next" "${base_dir}/current"

trap - ERR
printf 'DEPLOYMENT_RUNTIME_PASS\n'
printf 'release_sha=%s\n' "$release_sha"
printf 'observability=OBSERVABILITY_PARTIAL\n'
