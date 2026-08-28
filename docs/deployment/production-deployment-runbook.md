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

## 6. AI Handoff Canary

The production Handoff flag is process-wide, not Inquiry-scoped. Do not change
`AI_HANDOFF_BACKEND_ENABLED` by editing the container or by running an ad-hoc
Compose command. The only approved entry point is the `Production AI Handoff
Canary` workflow, and the default and final state is always
`AI_HANDOFF_BACKEND_ENABLED=false`.

Every official release atomically normalizes the non-secret Handoff runtime
settings to the fail-closed production values: the flag is `false`, the Backend
address is the internal `backend:8000` service, and the timeout is bounded. The
release fails without changing the token when the pre-provisioned
`AI_HANDOFF_INTERNAL_TOKEN` is missing, empty, duplicated, or exposed through
unsafe file permissions. Do not append these keys manually on the host.

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

Use one new Inquiry created through the public API from an existing approved
synthetic customer and active subscription. Do not run Migration, Schema
changes, Seed commands, management-command fixture creation, or direct RDS
updates. Record only the fixed release SHA, Inquiry and correlation identifiers,
counts, hashes, health results, Workflow run ID, and SSM command ID.

Run the workflow actions in this order:

1. `preflight`: require the expected current SHA, protected AI environment,
   disabled flag, zero active AI Runs, and zero target AI/Handoff/Consultation
   rows.
2. `open`: install a host Nginx gate that allows only the operator IP and target
   Inquiry's `submit` and `answers` paths. All equivalent paths for other
   Inquiries are denied. Drain for 65 seconds, enable the flag atomically,
   recreate only AI from the current immutable Release, and arm the Watchdog.
3. `status`: record target and other-Inquiry AI Run counts without printing
   prompts, evidence, summaries, environment values, or customer content.
4. `close`: stop AI first, force the flag to `false`, recreate and health-check
   AI, then remove the Nginx gate only after the original Nginx configuration
   checksum is restored.

The Watchdog calls `close` after at most 15분 even if the operator is
disconnected. Any open failure attempts the same restoration. If restoration
cannot be proven, AI remains stopped and the Nginx gate remains active. An
ordinary production deployment is blocked while a Canary state file exists;
an early block does not invoke Release rollback because no deployment mutation
started.

Functional Canary failure alone does not roll back the Release. Use the recorded
previous SHA only for deployment or health regression, and verify the flag is
still `false` after rollback. A Canary PASS is evidence for one synthetic
Inquiry only; 상시 활성화 remains `HOLD` until independent QA and a separate PM
decision.
