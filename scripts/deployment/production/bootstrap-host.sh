#!/usr/bin/env bash
set -euo pipefail

backend_env_file="${1:-/etc/waterbridge/backend.env}"
ai_env_file="${2:-/etc/waterbridge/ai.env}"
rds_ca_file="${3:-/etc/waterbridge/certs/rds-ca.pem}"
public_domain="${4:-waterbridge.site}"
web_host_port="${5:-18080}"

fail() {
  printf 'HOST_BOOTSTRAP_FAILED: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command is missing: $1"
}

for command_name in aws docker nginx curl tar sha256sum flock python3 systemctl install; do
  require_command "$command_name"
done

docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is unavailable"
docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable"
nginx -t >/dev/null 2>&1 || fail "current host Nginx configuration is invalid"

[[ -f "$backend_env_file" ]] || fail "protected Backend env file is missing"
[[ -f "$ai_env_file" ]] || fail "protected AI env file is missing"
[[ -s "$rds_ca_file" ]] || fail "RDS CA file is missing or empty"

for protected_file in "$backend_env_file" "$ai_env_file"; do
  runtime_mode="$(stat -c '%a' "$protected_file")"
  if (( (8#$runtime_mode & 8#077) != 0 )); then
    fail "runtime env permissions must not grant group/other access"
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
  EMBEDDING_MODEL_NAME
  EMBEDDING_DIMENSION
  AI_VECTOR_DSN
  AI_EMBEDDING_REVISION
  AI_VECTOR_TABLE_NAME
  AI_HANDOFF_INTERNAL_TOKEN
  AI_HANDOFF_BACKEND_ENABLED
  AI_BACKEND_BASE_URL
  AI_HANDOFF_TIMEOUT_SECONDS
)

for key in "${required_backend_keys[@]}"; do
  grep -Eq "^[[:space:]]*${key}=.+$" "$backend_env_file" \
    || fail "required Backend runtime key is missing: ${key}"
done
grep -Eq '^[[:space:]]*AI_HANDOFF_BACKEND_ENABLED=false[[:space:]]*$' "$ai_env_file" \
  || fail "AI Handoff must start disabled"
grep -Eq '^[[:space:]]*AI_BACKEND_BASE_URL=http://backend:8000/?[[:space:]]*$' "$ai_env_file" \
  || fail "AI Backend URL must use the internal production service"
for key in "${required_ai_keys[@]}"; do
  grep -Eq "^[[:space:]]*${key}=.+$" "$ai_env_file" \
    || fail "required AI runtime key is missing: ${key}"
done

grep -Eq '^[[:space:]]*POSTGRES_SSLMODE=verify-full[[:space:]]*$' "$backend_env_file" \
  || fail "POSTGRES_SSLMODE must be verify-full"

available_kb="$(df -Pk /opt | awk 'NR==2 {print $4}')"
[[ "$available_kb" =~ ^[0-9]+$ ]] || fail "could not determine /opt free space"
(( available_kb >= 4194304 )) || fail "at least 4 GiB free space is required under /opt"

mkdir -p /opt/waterbridge/releases /opt/waterbridge/shared
chmod 0750 /opt/waterbridge /opt/waterbridge/releases /opt/waterbridge/shared

nginx_dump="$(mktemp)"
trap 'rm -f "$nginx_dump"' EXIT
nginx -T >"$nginx_dump" 2>&1
grep -Eq "server_name[[:space:]]+([^;[:space:]]+[[:space:]]+)*${public_domain}([[:space:];])" "$nginx_dump" \
  || fail "active Nginx configuration does not contain ${public_domain}"
grep -Fq "127.0.0.1:${web_host_port}" "$nginx_dump" \
  || fail "host Nginx is not yet configured for 127.0.0.1:${web_host_port}"

printf 'HOST_BOOTSTRAP_PASS\n'
printf 'docker_compose=available\n'
printf 'systemd=available\n'
printf 'nginx_config=valid\n'
printf 'backend_env=protected\n'
printf 'ai_env=protected_readonly_boundary\n'
printf 'rds_ca=present\n'
printf 'host_upstream=127.0.0.1:%s\n' "$web_host_port"
