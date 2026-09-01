#!/bin/sh
# Operator-run evaluation only: no service rollout, DB writes, Provider or new branch.
set -eu
set +x
umask 077

[ "$#" -eq 2 ] || { printf '%s\n' 'Usage: sh run_readonly_qa_candidate.sh COMMIT_SHA EXISTING_AI_IMAGE_DIGEST'; exit 64; }
qa_expected_sha=$1
qa_base_image=$2
printf '%s' "$qa_expected_sha" | grep -Eq '^[0-9a-f]{40}$' || exit 64
printf '%s' "$qa_base_image" | grep -Eq '^[a-zA-Z0-9./_-]+@sha256:[0-9a-f]{64}$' || exit 64
qa_memory_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
[ "$qa_memory_kb" -ge 5242880 ] || { printf '%s\n' 'HOLD_HOST_MEMORY_BELOW_5_GIB'; exit 2; }
[ "$(df -Pk /var/tmp | awk 'NR==2 {print $4}')" -ge 8388608 ] || { printf '%s\n' 'HOLD_HOST_DISK_BELOW_8_GIB'; exit 2; }

qa_ai_ids=$(docker ps --quiet --filter label=com.docker.compose.service=ai)
set -- $qa_ai_ids
[ "$#" -eq 1 ] || { printf '%s\n' 'HOLD_SINGLE_AI_CONTAINER_REQUIRED'; exit 2; }
qa_ai_id=$1
[ "$(docker inspect --format '{{.Config.Image}}' "$qa_ai_id")" = "$qa_base_image" ] || { printf '%s\n' 'HOLD_BASE_IMAGE_MISMATCH'; exit 2; }
qa_dir=$(mktemp -d /var/tmp/waterbridge-readonly-qa.XXXXXXXX)
qa_token=${qa_dir##*.}
qa_container=waterbridge-readonly-qa-$qa_token
qa_image=waterbridge-readonly-qa:$qa_token
qa_env=$(mktemp --suffix=.env /dev/shm/waterbridge-readonly-qa.XXXXXXXX)
printf '%s\n' "$qa_token" > "$qa_dir/owned-by-this-run"

cleanup() {
    qa_result=$?
    trap - EXIT HUP INT TERM
    if [ "$(docker inspect --format '{{index .Config.Labels "waterbridge.qa.run"}}' "$qa_container" 2>/dev/null || true)" = "$qa_token" ]; then
        docker rm --force "$qa_container" >/dev/null 2>&1 || true
    fi
    if [ "$(docker image inspect --format '{{index .Config.Labels "waterbridge.qa.run"}}' "$qa_image" 2>/dev/null || true)" = "$qa_token" ]; then
        docker image rm "$qa_image" >/dev/null 2>&1 || true
    fi
    case "$qa_env" in /dev/shm/waterbridge-readonly-qa.*.env) rm -f -- "$qa_env" ;; esac
    case "$qa_dir" in
        /var/tmp/waterbridge-readonly-qa.*)
            if [ "$(realpath "$qa_dir")" = "$qa_dir" ] && [ "$(cat "$qa_dir/owned-by-this-run")" = "$qa_token" ]; then
                rm -rf -- "$qa_dir"
            fi
            ;;
    esac
    if [ -n "${qa_before:-}" ]; then
        qa_cleanup_ai=$(docker inspect --format '{{.Id}}|{{.Image}}|{{.RestartCount}}|{{.State.StartedAt}}|{{.State.Status}}|{{.State.Health.Status}}' "$qa_ai_id")
        if [ "$qa_cleanup_ai" = "$qa_before" ]; then
            printf '%s\n' 'RUNNING_AI_METADATA_UNCHANGED=true'
        else
            printf '%s\n' 'HOLD_RUNNING_AI_CHANGED'
            qa_result=2
        fi
    fi
    if [ ! -e "$qa_dir" ] && [ ! -e "$qa_env" ] \
        && ! docker inspect "$qa_container" >/dev/null 2>&1 \
        && ! docker image inspect "$qa_image" >/dev/null 2>&1; then
        printf '%s\n' 'QA_OWN_TEMP_RESOURCES_CLEANED'
    else
        printf '%s\n' 'HOLD_QA_TEMP_CLEANUP_INCOMPLETE'
        qa_result=2
    fi
    exit "$qa_result"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM

qa_before=$(docker inspect --format '{{.Id}}|{{.Image}}|{{.RestartCount}}|{{.State.StartedAt}}|{{.State.Status}}|{{.State.Health.Status}}' "$qa_ai_id")
printf '%s\n' "QA_SOURCE_SHA=$qa_expected_sha" "AI_STATE_BEFORE=$qa_before"
# Forward only the already configured read-only DSN to a mode-600 RAM file.
# No OpenAI key, customer token, Backend DSN, or full environment is copied.
docker exec -i "$qa_ai_id" python -B - > "$qa_env" <<'QA_DSN'
import os
import platform
import sys
from psycopg.conninfo import conninfo_to_dict
try:
    assert platform.python_version() == '3.13.13', 'PYTHON_VERSION_MISMATCH'
    dsn = os.environ['AI_VECTOR_DSN']
    assert '\n' not in dsn and '\r' not in dsn, 'INVALID_DSN_FORMAT'
    info = conninfo_to_dict(dsn)
    assert info.get('sslmode') == 'verify-full', 'VERIFIED_TLS_REQUIRED'
    assert info.get('sslrootcert', '') in {'', '/run/secrets/rds-ca.pem'}, 'UNSUPPORTED_CA_MOUNT'
    print('AI_VECTOR_DSN=' + dsn)
except Exception:
    print('HOLD_READONLY_ENVIRONMENT_FORWARDING_FAILED', file=sys.stderr)
    raise SystemExit(2)
QA_DSN
qa_ca=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/run/secrets/rds-ca.pem"}}{{.Source}}{{end}}{{end}}' "$qa_ai_id")
[ -n "$qa_ca" ] && [ -f "$qa_ca" ] || { printf '%s\n' 'HOLD_APPROVED_RDS_CA_MOUNT_REQUIRED'; exit 2; }

mkdir "$qa_dir/source" "$qa_dir/build" "$qa_dir/cache" "$qa_dir/output"
GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null git -C "$qa_dir/source" init --quiet
timeout 180 env GIT_TERMINAL_PROMPT=0 GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    git -c credential.helper= -C "$qa_dir/source" fetch --quiet --depth=1 --no-tags \
    https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM.git "$qa_expected_sha"
git -C "$qa_dir/source" checkout --quiet --detach FETCH_HEAD
[ "$(git -C "$qa_dir/source" rev-parse HEAD)" = "$qa_expected_sha" ]
[ "$(git -C "$qa_dir/source" status --porcelain)" = '' ]
git -C "$qa_dir/source" cat-file commit HEAD >/dev/null
printf '%s\n' 'QA_REAL_GIT_SOURCE_VERIFIED'

# The repository's ai/evaluation/** text rule also covers this binary NPZ.
# Keep its exact committed bytes; override text conversion only in this temporary
# checkout's Git metadata. Never ignore changes or alter the tracked attributes.
qa_binary=ai/evaluation/indexes/playground_bge_m3_page_v1.npz
qa_binary_blob=$(git -C "$qa_dir/source" rev-parse "HEAD:$qa_binary")
[ "$(git -C "$qa_dir/source" hash-object --no-filters "$qa_binary")" = "$qa_binary_blob" ]
printf '%s\n' "$qa_binary -text" > "$qa_dir/source/.git/info/attributes"
printf '%s\n' "QA_BINARY_ATTRIBUTE_OVERRIDE=$qa_binary -text" "QA_BINARY_COMMITTED_BLOB=$qa_binary_blob"

cat > "$qa_dir/build/Dockerfile" <<'QA_DOCKERFILE'
ARG QA_BASE_IMAGE
FROM ${QA_BASE_IMAGE}
USER root
RUN apt-get update && apt-get install --yes --no-install-recommends git && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 GIT_OPTIONAL_LOCKS=0
HEALTHCHECK NONE
USER 10001:10001
WORKDIR /workspace
ENTRYPOINT ["python", "-B"]
QA_DOCKERFILE
timeout 240 docker build --quiet --build-arg "QA_BASE_IMAGE=$qa_base_image" \
    --label "waterbridge.qa.run=$qa_token" --label "waterbridge.qa.source=$qa_expected_sha" \
    --tag "$qa_image" "$qa_dir/build" > "$qa_dir/build.log" 2>&1 || {
        printf '%s\n' 'HOLD_QA_IMAGE_BUILD_FAILED'; exit 2;
    }
printf '%s\n' "QA_IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$qa_image")"

chown -R 10001:10001 "$qa_dir/source" "$qa_dir/cache" "$qa_dir/output"
qa_exit=0
timeout --signal=TERM 1200 docker run --rm --name "$qa_container" \
    --label "waterbridge.qa.run=$qa_token" \
    --read-only --network host --cap-drop ALL --security-opt no-new-privileges \
    --memory 4g --memory-swap 4g --cpus 1 --pids-limit 256 \
    --tmpfs /tmp:rw,noexec,nosuid,size=128m \
    --mount "type=bind,src=$qa_dir/source,dst=/workspace,readonly" \
    --mount "type=bind,src=$qa_dir/cache,dst=/qa-cache" \
    --mount "type=bind,src=$qa_dir/output,dst=/qa-output" \
    --mount "type=bind,src=$qa_ca,dst=/run/secrets/rds-ca.pem,readonly" \
    --env-file "$qa_env" --env "QA_EXPECTED_SHA=$qa_expected_sha" \
    --env PGSSLROOTCERT=/run/secrets/rds-ca.pem \
    --env AI_RAG_RUNTIME_PROFILE=three_model_integration \
    --env AI_VECTOR_TABLE_NAME=backend_ai_rag_chunks_v1 \
    --env AI_EMBEDDING_REVISION=5617a9f61b028005a4858fdac845db406aefb181 \
    --env AI_RETRIEVAL_TRANSPORT=direct --env OPENAI_API_KEY= \
    --env HF_HOME=/qa-cache --env HF_HUB_DISABLE_TELEMETRY=1 \
    --env OMP_NUM_THREADS=1 --env MKL_NUM_THREADS=1 --env OPENBLAS_NUM_THREADS=1 \
    --env TOKENIZERS_PARALLELISM=false \
    -i "$qa_image" - > "$qa_dir/evaluation.log" 2>&1 <<'QA_EVALUATION' || qa_exit=$?
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from hashlib import sha1
import psycopg
stage = 'PYTHON_RUNTIME'
source_check = {}
try:
    source_check['python_version'] = platform.python_version()
    source_check['git_executable'] = shutil.which('git')
    assert platform.python_version() == '3.13.13', 'PYTHON_VERSION_MISMATCH'
    stage = 'EXACT_GIT_SHA'
    sha = os.environ['QA_EXPECTED_SHA']
    source_check['actual_commit_sha'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert source_check['actual_commit_sha'] == sha
    stage = 'RAW_TRACKED_BLOB_IDENTITY'
    entries = subprocess.check_output(['git', 'ls-files', '--stage', '-z']).split(b'\0')
    mismatches = []
    file_count = 0
    for entry in entries:
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, blob_oid, index_stage = metadata.split()
        assert index_stage == b'0' and mode in (b'100644', b'100755', b'120000')
        path = Path(os.fsdecode(raw_path))
        if mode == b'120000':
            content = os.fsencode(os.readlink(path))
            digest = sha1(f'blob {len(content)}\0'.encode() + content, usedforsecurity=False)
        else:
            digest = sha1(f'blob {path.stat().st_size}\0'.encode(), usedforsecurity=False)
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1048576), b''):
                    digest.update(chunk)
        if digest.hexdigest().encode() != blob_oid:
            mismatches.append(path.as_posix())
        file_count += 1
    source_check['raw_tracked_file_count'] = file_count
    source_check['raw_blob_mismatches'] = mismatches[:20]
    source_check['raw_tracked_bytes_match_git_index'] = not mismatches
    source_check['temporary_binary_text_override'] = 'ai/evaluation/indexes/playground_bge_m3_page_v1.npz -text'
    assert not mismatches
    stage = 'CLEAN_GIT_TREE'
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    source_check['dirty_entry_count'] = len(dirty.splitlines()) if dirty else 0
    source_check['dirty_entries'] = dirty.splitlines()[:20]
    assert not dirty
    stage = 'GIT_COMMIT_OBJECT'
    subprocess.run(['git', 'cat-file', 'commit', sha], check=True, stdout=subprocess.DEVNULL)
    stage = 'RDS_READONLY_PRIVILEGES'
    with psycopg.connect(os.environ['AI_VECTOR_DSN'], connect_timeout=5) as connection:
        assert connection.pgconn.ssl_in_use, 'TLS_REQUIRED'
        connection.read_only = True
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SELECT current_setting('default_transaction_read_only'), current_setting('transaction_read_only'), has_table_privilege(current_user,'backend_ai_rag_chunks_v1','SELECT'), has_table_privilege(current_user,'backend_ai_rag_chunks_v1','INSERT,UPDATE,DELETE,TRUNCATE'), has_schema_privilege(current_user,'public','CREATE')")
            assert cursor.fetchone() == ('on', 'on', True, False, False), 'READONLY_PRIVILEGES_REQUIRED'
    stage = 'READONLY_EVALUATION'
    from ai.scripts.verify_three_model_readonly_runtime import main
    exit_code = main(Path('/qa-output/readonly-50.json'), expected_sha=sha)
    Path('/qa-output/source-check.json').write_text(json.dumps(source_check, sort_keys=True) + '\n', encoding='utf-8')
except Exception as exc:
    Path('/qa-output/readonly-50.json').write_text(json.dumps({
        'status':'HOLD', 'failure_stage':stage, 'error_type':type(exc).__name__,
        'source_check':source_check,
        'executed_case_count': 0 if stage != 'READONLY_EVALUATION' else None,
        'public_runtime_activation':'HOLD', 'final_sha_eligible':False,
    }, sort_keys=True) + '\n', encoding='utf-8')
    exit_code = 2
raise SystemExit(exit_code)
QA_EVALUATION

qa_after=$(docker inspect --format '{{.Id}}|{{.Image}}|{{.RestartCount}}|{{.State.StartedAt}}|{{.State.Status}}|{{.State.Health.Status}}' "$qa_ai_id")
printf '%s\n' "AI_STATE_AFTER=$qa_after" "QA_EXIT_CODE=$qa_exit"
[ "$qa_before" = "$qa_after" ] || { printf '%s\n' 'HOLD_RUNNING_AI_CHANGED'; exit 2; }
[ -f "$qa_dir/output/readonly-50.json" ] || { printf '%s\n' 'HOLD_QA_REPORT_NOT_CREATED'; exit 2; }

# The complete report is compressed for the SSM console limit, not redacted or sampled.
# It contains case IDs and evidence hashes, never a DSN or a Provider request body.
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
    --memory 256m --cpus 1 \
    --mount "type=bind,src=$qa_dir/output,dst=/qa-output,readonly" -i "$qa_image" - <<'QA_REPORT'
import base64
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
raw = Path('/qa-output/readonly-50.json').read_bytes()
assert not re.search(rb'postgres(?:ql)?://|sk-[A-Za-z0-9_-]{20,}|SecretString', raw), 'REPORT_SECRET_RISK'
data = json.loads(raw)
source_report = Path('/qa-output/source-check.json')
if source_report.is_file():
    print('QA_SOURCE_CHECK=' + source_report.read_text(encoding='utf-8').strip())
summary_keys = ('status','case_count','passed_count','positive_group_hit_count','negative_no_evidence_count','cross_model_hit_count','direct_parent_hit_count','unverified_evidence_hit_count','final_sha_eligible','reason_code','final_sha_blockers')
print('QA_REPORT_SUMMARY=' + json.dumps({k:data.get(k) for k in summary_keys}, sort_keys=True))
print('QA_REPORT_SHA256=' + sha256(raw).hexdigest())
encoded = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode('ascii')
assert len(encoded) <= 20000, 'REPORT_EXCEEDS_CONSOLE_CAPACITY'
print('QA_REPORT_GZIP_BASE64=' + encoded)
print('QA_SCOPE=CURRENT_COMMITTED_CANDIDATE_NOT_FINAL_LEDGER_PR')
print('PUBLIC_RUNTIME_ACTIVATION=HOLD')
QA_REPORT
exit "$qa_exit"
