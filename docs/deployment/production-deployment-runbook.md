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

## 3. Automatic deployment

`Production Deploy` starts only after the exact main SHA passes the existing
`AI Backend Socket E2E Linux Gate`. It then re-runs the Backend, Web, Contract,
and Data gates at the same SHA. The AI Linux unit suite runs in a non-root
Docker `qa` stage built from the same locked dependency layer as the runtime
image; only the fixed release SHA is exposed to the test metadata helper.

The workflow stops before AWS mutation when any Dockerfile is still a placeholder.
After all gates pass it:

1. Builds the three application images for `linux/amd64`.
2. Pushes SHA-tagged images and records their ECR digests.
3. Creates a secret-free release bundle and uploads it to `releases/<SHA>/`.
4. Uses SSM to download the bundle and verify its SHA-256 on EC2.
5. Verifies PostgreSQL 16.14, pgvector 0.8.6, `evidence.0013` applied,
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
