import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

import {
  parseBackendFixture,
  readBackendFixture,
  toPublicFixtureJson,
  type WebConsultationE2EFixture,
} from "./backendFixture.js";

const SUPPORT_DIR = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = resolve(SUPPORT_DIR, "../..");
const REPOSITORY_ROOT = resolve(WEB_ROOT, "..");
const BACKEND_ROOT = resolve(REPOSITORY_ROOT, "backend");
const RUNTIME_FIXTURE_PATH = resolve(
  WEB_ROOT,
  ".runtime/playwright/backend-fixture.json",
);
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1", "[::1]"]);

function createRunId(): string {
  const build = (
    process.env.GITHUB_RUN_ID ||
    process.env.BUILD_NUMBER ||
    Date.now().toString(36)
  )
    .replace(/[^A-Za-z0-9._-]/g, "-")
    .slice(0, 24);
  const attempt = (
    process.env.GITHUB_RUN_ATTEMPT ||
    process.env.E2E_ATTEMPT ||
    "1"
  )
    .replace(/[^A-Za-z0-9._-]/g, "-")
    .slice(0, 8);
  const nonce = randomBytes(4).toString("hex");
  return `web-e2e-${build}-${attempt}-${nonce}`.slice(0, 64);
}

function backendPythonPath(): string {
  if (process.env.E2E_BACKEND_PYTHON?.trim()) {
    return resolve(process.env.E2E_BACKEND_PYTHON.trim());
  }
  return process.platform === "win32"
    ? resolve(BACKEND_ROOT, ".venv/Scripts/python.exe")
    : resolve(BACKEND_ROOT, ".venv/bin/python");
}

function backendEnvironmentValue(key: string): string {
  const inherited = process.env[key]?.trim();
  if (inherited) return inherited;

  let contents: string;
  try {
    contents = readFileSync(resolve(BACKEND_ROOT, ".env"), "utf8");
  } catch {
    throw new Error(
      "ENVIRONMENT_BLOCKED: Backend 로컬 환경 설정을 확인할 수 없습니다.",
    );
  }
  const prefix = `${key}=`;
  const line = contents
    .split(/\r?\n/)
    .map((candidate) => candidate.trim())
    .find((candidate) => candidate.startsWith(prefix));
  if (!line) {
    throw new Error(
      "ENVIRONMENT_BLOCKED: Backend PostgreSQL 대상이 설정되지 않았습니다.",
    );
  }
  const value = line.slice(prefix.length).trim();
  if (
    value.length >= 2 &&
    ((value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'")))
  ) {
    return value.slice(1, -1).trim();
  }
  return value;
}

function assertLoopbackUrl(rawUrl: string, label: string): void {
  let hostname: string;
  try {
    hostname = new URL(rawUrl).hostname.toLowerCase();
  } catch {
    throw new Error(`ENVIRONMENT_BLOCKED: ${label} 주소 형식이 올바르지 않습니다.`);
  }
  if (!LOOPBACK_HOSTS.has(hostname)) {
    throw new Error(
      `ENVIRONMENT_BLOCKED: 로컬 Fixture 생성 시 ${label}도 로컬 주소여야 합니다.`,
    );
  }
}

function assertLocalFixtureTarget(): void {
  const databaseHost = backendEnvironmentValue("POSTGRES_HOST").toLowerCase();
  if (!LOOPBACK_HOSTS.has(databaseHost)) {
    throw new Error(
      "ENVIRONMENT_BLOCKED: 공용 DB 또는 원격 DB에는 E2E Fixture를 생성하지 않습니다.",
    );
  }
  assertLoopbackUrl(
    process.env.E2E_BACKEND_BASE_URL?.trim() || "http://127.0.0.1:8000",
    "Backend",
  );
  const suppliedWebBaseUrl = process.env.E2E_WEB_BASE_URL?.trim();
  if (suppliedWebBaseUrl) assertLoopbackUrl(suppliedWebBaseUrl, "Web");
}

function runBackendCommand(args: readonly string[]): string {
  const result = spawnSync(
    backendPythonPath(),
    ["manage.py", ...args, "--settings=config.settings.local"],
    {
      cwd: BACKEND_ROOT,
      encoding: "utf8",
      env: process.env,
      maxBuffer: 1024 * 1024,
      timeout: 30_000,
      windowsHide: true,
    },
  );

  if (result.status !== 0 || !result.stdout.trim()) {
    throw new Error(
      "Backend 사전검증 또는 Fixture 생성에 실패했습니다. PostgreSQL 상태와 Demo Seed를 확인해 주세요.",
    );
  }
  return result.stdout;
}

function assertMigrationGate(): void {
  const output = runBackendCommand(["showmigrations"]);
  const states = new Map<string, "APPLIED" | "PENDING">();
  let currentApp = "";
  for (const line of output.split(/\r?\n/)) {
    const appMatch = line.match(/^([A-Za-z0-9_]+)\s*$/);
    if (appMatch) {
      currentApp = appMatch[1];
      continue;
    }
    const migrationMatch = line.match(/^\s*\[([ X])\]\s+([^\s]+)/);
    if (!migrationMatch || !currentApp) continue;
    states.set(
      `${currentApp}.${migrationMatch[2]}`,
      migrationMatch[1] === "X" ? "APPLIED" : "PENDING",
    );
  }

  const expectedHold = "visits.0005_replace_visit_result_assignment_fk";
  const unexpectedPending = [...states.entries()].filter(
    ([key, state]) => state === "PENDING" && key !== expectedHold,
  );
  if (
    states.get("operations.0002_consultant_dashboard_projection") !==
      "APPLIED" ||
    states.get(expectedHold) !== "PENDING" ||
    unexpectedPending.length > 0
  ) {
    throw new Error(
      "ENVIRONMENT_BLOCKED: operations.0002 적용, visits.0005 단독 HOLD, 예상 외 미적용 0건 상태가 필요합니다.",
    );
  }
}

async function assertBackendHealth(): Promise<void> {
  const backendBaseUrl =
    process.env.E2E_BACKEND_BASE_URL?.trim() || "http://127.0.0.1:8000";
  let response: globalThis.Response;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  try {
    response = await fetch(new URL("/health", backendBaseUrl), {
      signal: controller.signal,
    });
  } catch {
    throw new Error("ENVIRONMENT_BLOCKED: Backend Health에 연결할 수 없습니다.");
  } finally {
    clearTimeout(timeout);
  }
  if (response.status !== 200) {
    throw new Error("ENVIRONMENT_BLOCKED: Backend Health가 200이 아닙니다.");
  }
}

function generateFixture(runId: string): WebConsultationE2EFixture {
  const stdout = runBackendCommand([
    "create_web_consultation_e2e_fixture",
    "--run-id",
    runId,
    "--json",
  ]);

  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout.trim());
  } catch {
    throw new Error("Backend Fixture 명령이 공개 JSON만 반환하지 않았습니다.");
  }
  return parseBackendFixture(parsed, runId);
}

function assertSafeReplay(
  first: WebConsultationE2EFixture,
  replay: WebConsultationE2EFixture,
): void {
  if (
    replay.created ||
    replay.inquiryId !== first.inquiryId ||
    replay.inquiryCode !== first.inquiryCode ||
    replay.requestCorrelationId !== first.requestCorrelationId ||
    replay.stateVersion !== first.stateVersion
  ) {
    throw new Error("동일한 미소비 run_id가 같은 Fixture를 반환하지 않았습니다.");
  }
}

export default async function globalSetup(): Promise<void> {
  await assertBackendHealth();
  const suppliedFixturePath = process.env.E2E_FIXTURE_JSON_PATH?.trim();
  let fixture: WebConsultationE2EFixture;

  if (suppliedFixturePath) {
    fixture = readBackendFixture(resolve(suppliedFixturePath));
  } else {
    assertLocalFixtureTarget();
    assertMigrationGate();
    const runId = process.env.E2E_RUN_ID?.trim() || createRunId();
    fixture = generateFixture(runId);
    const replay = generateFixture(runId);
    assertSafeReplay(fixture, replay);
  }

  mkdirSync(dirname(RUNTIME_FIXTURE_PATH), { recursive: true });
  writeFileSync(
    RUNTIME_FIXTURE_PATH,
    `${JSON.stringify(toPublicFixtureJson(fixture), null, 2)}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
  process.env.E2E_FIXTURE_JSON_PATH = RUNTIME_FIXTURE_PATH;
}
