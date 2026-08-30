import { readFileSync } from "node:fs";

const MAX_FIXTURE_BYTES = 64 * 1024;
const EXPECTED_KEYS = [
  "allowed_actions_for_assignee",
  "assigned_consultant",
  "concealed_from",
  "consultation_status",
  "created",
  "expected_error_code",
  "expected_http_status",
  "fixture_readiness",
  "fixture_scope",
  "inquiry_code",
  "inquiry_id",
  "run_id",
  "state_version",
  "status",
] as const;

export interface WebConcealedE2EFixture {
  created: boolean;
  inquiryId: string;
  runId: string;
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
        "Backend Concealed Fixture JSON에 허용되지 않은 비밀정보 또는 개인정보 필드가 있습니다.",
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
    throw new Error(
      `Backend Concealed Fixture JSON의 ${key} 값이 올바르지 않습니다.`,
    );
  }
  return value;
}

function requireLiteral(
  source: Record<string, unknown>,
  key: string,
  expected: string | number,
): void {
  if (source[key] !== expected) {
    throw new Error(
      `Backend Concealed Fixture가 ${key}=${expected} 상태가 아닙니다.`,
    );
  }
}

export function parseBackendConcealedFixture(
  raw: unknown,
  expectedRunId?: string,
): WebConcealedE2EFixture {
  assertPublicFixtureOnly(raw);
  if (!isRecord(raw)) {
    throw new Error("Backend Concealed Fixture JSON은 객체여야 합니다.");
  }

  const actualKeys = Object.keys(raw).sort();
  const expectedKeys = [...EXPECTED_KEYS].sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index])
  ) {
    throw new Error(
      "Backend Concealed Fixture JSON 공개 필드 계약이 변경되었습니다.",
    );
  }

  const runId = requireString(raw, "run_id");
  if (expectedRunId && runId !== expectedRunId) {
    throw new Error(
      "Backend Concealed Fixture의 run_id가 요청한 실행과 다릅니다.",
    );
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(runId)) {
    throw new Error("Backend Concealed Fixture의 run_id 형식이 올바르지 않습니다.");
  }
  if (typeof raw.created !== "boolean") {
    throw new Error("Backend Concealed Fixture의 created 값이 올바르지 않습니다.");
  }
  if (
    !Array.isArray(raw.allowed_actions_for_assignee) ||
    !raw.allowed_actions_for_assignee.includes("START_CONSULTATION") ||
    raw.allowed_actions_for_assignee.some(
      (action) => typeof action !== "string",
    )
  ) {
    throw new Error(
      "Backend Concealed Fixture의 담당자 행동 경계가 올바르지 않습니다.",
    );
  }

  requireLiteral(raw, "assigned_consultant", "SYN-WEB-G4-CONSULTANT-404");
  requireLiteral(raw, "concealed_from", "DEMO-CONSULTANT-001");
  requireLiteral(raw, "consultation_status", "ASSIGNED");
  requireLiteral(raw, "expected_error_code", "RESOURCE_NOT_FOUND");
  requireLiteral(raw, "expected_http_status", 404);
  requireLiteral(raw, "fixture_readiness", "READY");
  requireLiteral(raw, "fixture_scope", "WEB_G4_CONCEALED_404");
  requireLiteral(raw, "status", "CONSULTATION_REQUIRED");

  const stateVersion = raw.state_version;
  if (
    typeof stateVersion !== "number" ||
    !Number.isInteger(stateVersion) ||
    stateVersion < 1
  ) {
    throw new Error(
      "Backend Concealed Fixture의 state_version이 올바르지 않습니다.",
    );
  }

  requireString(raw, "inquiry_code");
  return {
    created: raw.created,
    inquiryId: requireString(raw, "inquiry_id"),
    runId,
  };
}

export function readBackendConcealedFixture(
  fixturePath: string,
): WebConcealedE2EFixture {
  const contents = readFileSync(fixturePath);
  if (contents.byteLength > MAX_FIXTURE_BYTES) {
    throw new Error(
      "Backend Concealed Fixture JSON 파일이 허용 크기를 초과했습니다.",
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(contents.toString("utf8"));
  } catch {
    throw new Error("Backend Concealed Fixture JSON 파일을 해석할 수 없습니다.");
  }
  return parseBackendConcealedFixture(parsed);
}
