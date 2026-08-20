import { readFileSync } from "node:fs";

const MAX_FIXTURE_BYTES = 64 * 1024;
const EXPECTED_KEYS = [
  "allowed_actions",
  "assigned_consultant",
  "consultation_status",
  "created",
  "fixture_readiness",
  "fixture_scope",
  "g3_audit_result",
  "inquiry_code",
  "inquiry_id",
  "known_blocker",
  "request_correlation_id",
  "run_id",
  "state_version",
  "status",
] as const;

export interface WebConsultationE2EFixture {
  allowedActions: readonly ["START_CONSULTATION"];
  assignedConsultant: "DEMO-CONSULTANT-001";
  consultationStatus: "WAITING";
  created: boolean;
  fixtureReadiness: "READY";
  fixtureScope: "WEB_G4_CONSULTATION";
  g3AuditResult: "NOT_APPLICABLE";
  inquiryCode: string;
  inquiryId: string;
  knownBlocker: "NONE";
  requestCorrelationId: string;
  runId: string;
  stateVersion: number;
  status: "CONSULTATION_REQUIRED";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function assertPublicFixtureOnly(value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach(assertPublicFixtureOnly);
    return;
  }
  if (!isRecord(value)) return;

  for (const [key, child] of Object.entries(value)) {
    if (
      /(?:access|refresh)?_?token|authorization|password|cookie|phone|email|customer_name|raw_text/i.test(
        key,
      )
    ) {
      throw new Error(
        "Backend Fixture JSON에 허용되지 않은 비밀정보 또는 개인정보 필드가 있습니다.",
      );
    }
    assertPublicFixtureOnly(child);
  }
}

function requireString(
  source: Record<string, unknown>,
  key: string,
): string {
  const value = source[key];
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`Backend Fixture JSON의 ${key} 값이 올바르지 않습니다.`);
  }
  return value;
}

function requireLiteral<T extends string>(
  source: Record<string, unknown>,
  key: string,
  expected: T,
): T {
  if (source[key] !== expected) {
    throw new Error(`Backend Fixture가 ${key}=${expected} 상태가 아닙니다.`);
  }
  return expected;
}

export function parseBackendFixture(
  raw: unknown,
  expectedRunId?: string,
): WebConsultationE2EFixture {
  assertPublicFixtureOnly(raw);
  if (!isRecord(raw)) {
    throw new Error("Backend Fixture JSON은 객체여야 합니다.");
  }

  const actualKeys = Object.keys(raw).sort();
  const expectedKeys = [...EXPECTED_KEYS].sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index])
  ) {
    throw new Error("Backend Fixture JSON 공개 필드 계약이 변경되었습니다.");
  }

  const runId = requireString(raw, "run_id");
  if (expectedRunId && runId !== expectedRunId) {
    throw new Error("Backend Fixture의 run_id가 요청한 실행과 다릅니다.");
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(runId)) {
    throw new Error("Backend Fixture의 run_id 형식이 올바르지 않습니다.");
  }

  const stateVersion = raw.state_version;
  if (
    typeof stateVersion !== "number" ||
    !Number.isInteger(stateVersion) ||
    stateVersion < 1
  ) {
    throw new Error("Backend Fixture의 state_version이 올바르지 않습니다.");
  }
  if (typeof raw.created !== "boolean") {
    throw new Error("Backend Fixture의 created 값이 올바르지 않습니다.");
  }
  if (
    !Array.isArray(raw.allowed_actions) ||
    raw.allowed_actions.length !== 1 ||
    raw.allowed_actions[0] !== "START_CONSULTATION"
  ) {
    throw new Error(
      "Backend Fixture의 allowed_actions가 상담 시작 경계와 다릅니다.",
    );
  }

  return {
    allowedActions: ["START_CONSULTATION"],
    assignedConsultant: requireLiteral(
      raw,
      "assigned_consultant",
      "DEMO-CONSULTANT-001",
    ),
    consultationStatus: requireLiteral(raw, "consultation_status", "WAITING"),
    created: raw.created,
    fixtureReadiness: requireLiteral(raw, "fixture_readiness", "READY"),
    fixtureScope: requireLiteral(
      raw,
      "fixture_scope",
      "WEB_G4_CONSULTATION",
    ),
    g3AuditResult: requireLiteral(
      raw,
      "g3_audit_result",
      "NOT_APPLICABLE",
    ),
    inquiryCode: requireString(raw, "inquiry_code"),
    inquiryId: requireString(raw, "inquiry_id"),
    knownBlocker: requireLiteral(raw, "known_blocker", "NONE"),
    requestCorrelationId: requireString(raw, "request_correlation_id"),
    runId,
    stateVersion,
    status: requireLiteral(raw, "status", "CONSULTATION_REQUIRED"),
  };
}

export function readBackendFixture(
  fixturePath: string,
): WebConsultationE2EFixture {
  const contents = readFileSync(fixturePath);
  if (contents.byteLength > MAX_FIXTURE_BYTES) {
    throw new Error("Backend Fixture JSON 파일이 허용 크기를 초과했습니다.");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(contents.toString("utf8"));
  } catch {
    throw new Error("Backend Fixture JSON 파일을 해석할 수 없습니다.");
  }
  return parseBackendFixture(parsed);
}

export function toPublicFixtureJson(
  fixture: WebConsultationE2EFixture,
): Record<string, unknown> {
  return {
    allowed_actions: [...fixture.allowedActions],
    assigned_consultant: fixture.assignedConsultant,
    consultation_status: fixture.consultationStatus,
    created: fixture.created,
    fixture_readiness: fixture.fixtureReadiness,
    fixture_scope: fixture.fixtureScope,
    g3_audit_result: fixture.g3AuditResult,
    inquiry_code: fixture.inquiryCode,
    inquiry_id: fixture.inquiryId,
    known_blocker: fixture.knownBlocker,
    request_correlation_id: fixture.requestCorrelationId,
    run_id: fixture.runId,
    state_version: fixture.stateVersion,
    status: fixture.status,
  };
}
