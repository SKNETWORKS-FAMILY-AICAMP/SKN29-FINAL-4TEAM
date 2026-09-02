# WaterBridge Production Deployment Runbook

## 1. Runtime boundary

Production uses exactly four containers:

```text
Host Nginx/TLS -> web -> backend -> ai -> trace-store
                           |               |
                           +-> AWS RDS     +-> Amazon S3
```

- `web`, `backend`, and `ai` images are stored in ECR and addressed by image digest.
- `trace-store` is the pinned linux/amd64 Tempo 3.0.3 image.
- PostgreSQL is the existing external RDS. Production Compose never starts PostgreSQL.
- Application deployment never runs Migration, Seed, Evidence Import, or volume deletion.
- Mobile is not a container in this topology.

## 2. One-time bootstrap

Run the `Production Bootstrap` workflow manually before enabling the first deployment.
It uses the existing GitHub OIDC role and performs the following fail-closed checks:

1. Resolve the EC2 instance profile role.
2. Reuse a specifically supplied or uniquely tagged compliant S3 bucket.
3. If no bucket exists and creation is enabled, create the retained CloudFormation storage stack.
4. Verify encryption, versioning, full public-access blocking, and EC2 prefix access.
5. Verify Docker Compose, Nginx, protected runtime env permissions, RDS CA, disk space, and the Host Nginx upstream.

The protected EC2 files default to `/etc/waterbridge/backend.env` and
`/etc/waterbridge/ai.env` and must not grant group or other access. They remain
separate so the AI container never receives the Django secret or Backend database
credentials. The workflow checks required key names without printing values. The
RDS CA defaults to `/etc/waterbridge/certs/rds-ca.pem`.

The existing Host Nginx must terminate TLS and route the WaterBridge virtual host
to `127.0.0.1:18080`. Bootstrap does not rewrite an unknown Nginx configuration.
Back up and validate the owner-approved host change with `nginx -t` before the
first automated deployment.

## 3. Stable SemVer tag deployment

`Production Deploy` starts only when a stable SemVer tag such as `v1.2.3` is
pushed. Pre-release or non-SemVer tags are rejected, and the tagged commit must
already be contained in `origin/main`. Ordinary `main` pushes never start a
production deployment.

The release workflow calls the reusable Backend three-shard gate and
`AI Backend Socket E2E Linux Gate`, then runs the Web, Contract, and Data gates
at the same tagged SHA. The separate Backend production-config gate keeps the
Gunicorn and `verify-full` TLS checks without repeating the full Backend pytest
suite. The AI Linux unit suite runs in a non-root Docker `qa` stage built from
the same locked dependency layer as the runtime image; only the fixed release
SHA is exposed to the test metadata helper.

The workflow stops before AWS mutation when any Dockerfile is still a placeholder.
After all gates pass it:

1. Builds the three application images for `linux/amd64`.
2. Pushes SHA-tagged images and records their ECR digests.
3. Creates a secret-free release bundle and uploads it to `releases/<SHA>/`.
4. Uses SSM to download the bundle and verify its SHA-256 on EC2.
5. Verifies PostgreSQL 16.14, the approved RDS pgvector 0.8.2 baseline,
   `evidence.0013` applied,
   `visits.0005` not applied, and no unexpected Migration plan without changing
   the database.
6. Verifies the AI role has read-only access to the approved 53-row View and no
   base-table or DML privilege.
7. Pulls and starts the four services without building or changing the database.
8. Verifies loopback root, `/health`, `X-Correlation-ID`, and the internal
   Backend-to-AI health socket.
9. Emits a synthetic AI Trace, waits for a new `tempo/` S3 block, queries the
   trace, restarts Tempo, and queries the same trace ID again.
10. Runs external HTTP-to-HTTPS, root, health, and correlation smoke checks.
11. Updates `current` and `previous` symlinks only after success.

Deployment is serialized with both GitHub concurrency and a host `flock`. A
failure returns to the previous release when available; first-release failure
stops only the new containers and preserves named volumes.

### Local image retention and disk headroom

`maintain_release_images.py` is included in the checksummed release bundle and
runs under the deployment shell's inherited `deploy.lock` (fd 9). It does not
source runtime env files or resolve Compose configuration containing secrets.

- Before `compose pull`, retain every image referenced by any existing container
  (including stopped containers), `current`, `previous`, and the incoming release.
  Resolve protected digests to local image IDs as well, so shared aliases cannot
  accidentally remove rollback images. Missing or invalid current/previous
  manifests or images stop the deployment before any removal or service change.
- Only remove local application images whose digest references are all recorded
  in valid historical release manifests for the incoming release's exact ECR
  `waterbridge/web`, `waterbridge/backend`, and `waterbridge/ai` repositories.
  The containerd image store can also return `repository@sha256:...` inside
  `RepoTags`. Such an alias is accepted only when it is present in the same
  image's `RepoDigests` and in a valid release manifest. An arbitrary digest-like
  alias does not establish ownership or bypass current/previous protection.
  Unknown aliases, mutable tags, dangling images, other accounts/repositories,
  Tempo and database/QA tools are not cleanup targets.
- Removal uses `docker image rm --no-prune` without force. Docker conflicts are
  reported, not overridden. No containers, volumes, model cache, Trace data,
  build cache, release directories or ECR objects are deleted.
- After cleanup, require at least **10 GiB available** on the host root,
  release directory, Docker data root, and default `/var/lib/containerd` store
  when present. This is a conservative minimum, not a prediction of arbitrary
  future image sizes: review it if images grow. A non-default containerd store
  requires a reviewed path check before using this policy. Insufficient space
  stops before `compose pull` and before installing the runtime rollback trap.
- After host Health/Trace/worker checks succeed and `current`/`previous` are
  updated, run cleanup again. Maintenance errors at this point are warnings,
  not a reason to roll back a healthy runtime. This occurs before the separate
  external HTTPS Smoke; its rollback target remains protected.
- On deployment failure, do not run post-success cleanup. Existing rollback
  behavior remains in place. The next attempt can remove recorded failed-release
  images only when no container or retained release still references them.

Evidence markers are `RELEASE_IMAGE_CLEANUP_PLAN`,
`RELEASE_IMAGE_CLEANUP_RESULT`, `DEPLOYMENT_DISK_SPACE`, and
`RELEASE_IMAGE_MAINTENANCE_FAILED`. Counts do not promise a reclaimed byte count:
layers may be shared. Verify available bytes after cleanup. Operators must not
substitute a broad prune command or remove named volumes to pass this gate.

The containerd store retains compressed and extracted image layers separately
from Docker's data root; see [Docker storage documentation](https://docs.docker.com/engine/storage/containerd/).
Image deletion behavior and conflict protection follow
[Docker image rm](https://docs.docker.com/reference/cli/docker/image/rm/).

### SSM shell boundary

GitHub Actions `shell: bash` does not select the interpreter used by
`AWS-RunShellScript` on EC2. The SSM agent's outer shell is `sh`, which is `dash`
on the observed Ubuntu host. Do not send unwrapped Bash `[[ ... ]]`, `%q`
quoting or `pipefail` setup to that outer shell.

The runner-side `build_ssm_bash_parameters.py` joins the trusted command strings
and POSIX-quotes the complete body for one explicit
`exec /bin/bash -euo pipefail -c ...` invocation. Release deployment, rollback and
Canary actions all use this builder. The Canary state guard runs before even
the shared-directory preparation or S3 download. The outer shell never evaluates
the inner Bash body, and the command exit status is preserved for SSM polling.
The Canary runner checks out the helper from its validated main caller SHA, not
the older expected runtime SHA, so it can still control a pre-fix deployment.

Regression tests execute the generated wire payload through Linux `/bin/sh`,
including active/inactive Canary state, S3-copy failure, rollback, pipeline
failure, unset variables, and Bash `%q` arguments with quotes/newlines. External
operations are replaced by test-only executables in an exclusive temporary PATH;
tests never call AWS or modify production paths. Container-based test runners
must provide an executable temporary directory for those stubs.

On a Windows workstation with an already running local Docker Desktop
containerd store, the opt-in probe below also verifies real image deletion:

```powershell
.\backend\.venv\Scripts\python.exe -B scripts/testing/verify_release_image_cleanup.py --run-local-probe
```

It creates two tiny OCI images locally (no registry pull or push), reproduces
digest references in both `RepoTags` and `RepoDigests`, selects/deletes the
obsolete image, and verifies that the protected image and existing volumes
remain. It then removes its remaining QA image, checking a unique ownership
label and excluding every pre-existing image ID. It rejects non-local Docker
endpoints and never creates a container or volume. This probe is not an EC2
cleanup command and is not run automatically by a release.

Tempo 3 uses `live_store` rather than the removed 2.x `ingester` section. In
monolithic `target=all` mode it flushes blocks to object storage without Kafka.
See the official [Tempo 3 upgrade notes](https://grafana.com/docs/tempo/latest/set-up-for-tracing/setup-tempo/upgrade/)
and [deployment modes](https://grafana.com/docs/tempo/latest/reference-tempo-architecture/deployment-modes/).

## 4. Current completion boundary

- Runtime success label: `DEPLOYMENT_RUNTIME_PASS`
- Current observability label: `OBSERVABILITY_PARTIAL`
- Final T-053 approval remains blocked until Backend OpenTelemetry,
  `traceparent` propagation, and `trace_id`/`correlation_id` linkage are verified.
- The AI and Tempo network needs an approved egress rule for external LLM/RDS/S3.
  Until that boundary is approved, the internal Docker network remains isolated.
- The Backend production image uses the approved Gunicorn 26.0.0 lock, runs as
  a non-root user, and collects static assets without connecting to the database.
- Web Mock fixtures and the internal Evidence registry are isolated under
  `web/tests`; production builds resolve a data-free module and use the `web/`
  Docker context with tests excluded. The source guard continues to block any
  future static Mock/Evidence import under `web/src`.
- The approved plan requests synthetic role login Smoke, but permanently
  enabling the public Demo Login boundary requires an explicit security
  approval. Until then external Smoke is limited to redirect, root, health, and
  correlation checks.
- Docker-based independent QA and socket E2E retain pgvector 0.8.6. The existing
  production RDS is pinned separately to pgvector 0.8.2 because that server does
  not provide 0.8.6, and 0.8.2 remains an explicitly verified Backend-compatible
  extension version. Production preflight requires exactly 0.8.2 so unexpected
  server drift still fails closed.

## 5. Evidence and rollback

Retain only non-sensitive evidence:

- full release SHA and image digests;
- release archive SHA-256;
- workflow and SSM command identifiers;
- container health and external smoke status;
- rollback status and the previous release SHA;
- Tempo readiness and trace query results after Backend tracing is completed.

Never record credentials, DSNs, passwords, tokens, prompts, vectors, customer
content, or the protected runtime env file contents.

## 6. AI Resume and Handoff Canary

The production Resume and Handoff flags are process-wide, not Inquiry-scoped.
Do not change `AI_HUMAN_REVIEW_RESUME_ENABLED` or
`AI_HANDOFF_BACKEND_ENABLED` by editing a container or by running an ad-hoc
Compose command. The only approved entry point is the `Production AI Handoff
Canary` workflow. Both Backend and AI Resume flags and the AI Handoff flag must
start and finish as `false`.

```text
Backend AI_HUMAN_REVIEW_RESUME_ENABLED=false
AI AI_HUMAN_REVIEW_RESUME_ENABLED=false
AI_HANDOFF_BACKEND_ENABLED=false
```

Every official release atomically normalizes the non-secret Handoff runtime
settings to the fail-closed production values: the flag is `false`, the Backend
address is the internal `backend:8000` service, and the timeout is bounded. The
release fails without changing the token when the pre-provisioned
`AI_HANDOFF_INTERNAL_TOKEN` is missing, empty, duplicated, or exposed through
unsafe file permissions. The release derives a distinct Resume credential by
domain-separated HMAC, writes the same protected credential to Backend and AI,
and keeps both Resume flags `false`. Secret values are never printed. Do not
append these keys manually on the host.

Before the first Canary, the official release prepares the one exact
`waterbridge.site` host Nginx server block that proxies to
`127.0.0.1:18080`. It backs up the source by SHA-256 and installs this include
inside that server block:

```nginx
include /etc/nginx/waterbridge-server.d/*.conf;
```

The release creates the directory as root with mode `0755`, runs `nginx -t`,
and reloads Nginx. Any failure restores the byte-identical source before the
release fails. If the public server name, source file, or upstream is ambiguous,
the release does not guess or rewrite the site file and the later Canary
preflight remains `ENVIRONMENT_BLOCKED`.

Use one new Inquiry created before the Canary by the approved JAC104 synthetic
fixture path. It must remain `DRAFT` at state version 1 with zero AI Run,
HumanReview, Resume Dispatch, Handoff, and Consultation rows. Do not run a
Migration, Schema change, Seed command, or unrelated direct RDS update inside
the Canary window. Record only the fixed release SHA, synthetic identifiers,
counts, hashes, health results, Workflow run ID, and SSM command ID.

The preferred action is `run`, which performs the following sequence in one
trusted SSM session and always invokes `close` on failure:

1. `preflight`: require the expected current SHA, protected AI environment,
   all three disabled flags, zero active AI Runs, no non-synthetic pending
   HumanReviews, an immutable count baseline for any pre-existing synthetic
   pending HumanReviews, and a fresh target baseline.
2. `open`: install a host Nginx gate that allows only the operator IP and target
   Inquiry's `submit` and `answers` paths. All equivalent paths for other
   Inquiries are denied. All public HumanReview decision paths are also denied
   for the maintenance window; the Canary applies its one target decision
   inside the Backend service boundary. Drain for 65 seconds while requiring
   the pre-existing synthetic pending count to remain unchanged, enable Backend
   Resume, AI Resume, and AI Handoff together, recreate Backend and AI from the
   current immutable Release, and arm the Watchdog.
3. `execute`: submit the exact synthetic Inquiry, require one official Evidence
   HumanReview, apply one official REJECT, and let Backend call the protected AI
   Resume endpoint. Require Context Agent 1, Context Provider 1, successful
   synthesis without fallback, Handoff 1, Consultation 1, decision Replay with
   no new Dispatch, and an HTTP Handoff Replay with no duplicate row.
4. `close`: stop Backend and AI, force all three flags to `false`, recreate and
   health-check both services, then remove the Nginx gate only after the
   original Nginx configuration checksum is restored.

The low-level `preflight`, `open`, `status`, and `close` actions remain available
for diagnosis and recovery. Do not use `open` as a substitute for `run` when
the approved goal is the automatic Resume-to-Handoff proof.

The Watchdog calls `close` after at most 15분 even if the operator is
disconnected. Any open failure attempts the same restoration. If restoration
cannot be proven, Backend and AI remain stopped and the Nginx gate remains active. An
ordinary production deployment is blocked while a Canary state file exists;
an early block does not invoke Release rollback because no deployment mutation
started.

Functional Canary failure alone does not roll back the Release. Use the recorded
previous SHA only for deployment or health regression, and verify the flag is
still `false` after rollback. A Canary PASS is evidence for one synthetic
Inquiry only; 상시 활성화 remains `HOLD` until independent QA and a separate PM
decision. Mobile and Web E2E starts only after the automatic `run` result and
the final three `false` flags have both been independently confirmed.

## 7. JAC104 Context Agent limited activation

Persistent activation is a separate production change from the 15-minute
Canary. Use the `Production AI Context Activation` workflow only after the
activation implementation is contained in an immutable deployed Release and PM
has explicitly approved this operational change. Do not edit either protected
environment file by hand.

The activation scope is fixed to `JAC104_LIMITED`. Backend rejects IAC425 and
IAC606 before dispatch, and AI independently authorizes only exact model code
`WPUJAC104DWH`. The activation does not contain a symptom, answer, Evidence
body, Provider output, or fixed consultation result.

Run the protected operations in this order:

1. `preflight`: bind to the exact deployed 40-character Release SHA, require all
   three flags to be `false`, require no active AI Run, validate protected file
   permissions and token agreement, and verify the Backend and AI JAC104-only
   code guards.
2. `activate`: acquire the deployment lock, record a non-secret activation
   state, atomically enable Backend Resume, AI Resume, and AI Handoff, recreate
   only Backend and AI, and require their internal health checks. Any failure
   restores all flags to `false`; if restoration cannot be proven, Backend and
   AI stay stopped.
3. `status`: read the exact Release, activation state, three flags, JAC104-only
   policy, internal health, and active AI Run count without changing state.
4. `deactivate`: atomically restore all three flags to `false`, verify that no
   unrelated protected environment content drifted, recreate Backend and AI,
   and remove the activation state only after health succeeds.

While the activation state exists, Release deployment, rollback, image
maintenance, and the isolated Handoff Canary are blocked. Deactivate before any
of those operations. Every normal Release still writes the three flags as
`false`; deploying a new Release never implicitly enables the Agent.

After the first activation, run only one approved synthetic JAC104 E2E. If it
fails, do not replay the decision, re-call the Provider, or repeat the test with
the same or a new Inquiry. Immediately run `deactivate`, retain only
non-sensitive identifiers, hashes, counts, and failure codes, and choose an
alternative path before another approval. Acceptable alternatives are a
component-only Context Agent invocation with Handoff disabled, deterministic
fallback consultation routing without Provider execution, or correction of the
specific contract/transport defect followed by a newly approved one-shot test.
Never hardcode a symptom, Evidence, Provider answer, or expected summary into
the production Agent to make the E2E pass.
