import { describe, expect, it } from "vitest";

import { parseBackendFixture } from "../../e2e/support/backendFixture";

const readyFixture = {
  allowed_actions: ["START_CONSULTATION"],
  assigned_consultant: "DEMO-CONSULTANT-001",
  consultation_status: "WAITING",
  created: true,
  fixture_readiness: "READY",
  fixture_scope: "WEB_G4_CONSULTATION",
  g3_audit_result: "NOT_APPLICABLE",
  inquiry_code: "WEB-G4-INQ-EXAMPLE",
  inquiry_id: "opaque-inquiry-id",
  known_blocker: "NONE",
  request_correlation_id: "opaque-correlation-id",
  run_id: "web-e2e-example-1",
  state_version: 2,
  status: "CONSULTATION_REQUIRED",
};

describe("Backend Playwright Fixture loader", () => {
  it("READY 공개 Crosswalk만 읽는다", () => {
    const fixture = parseBackendFixture(readyFixture, "web-e2e-example-1");

    expect(fixture.inquiryId).toBe("opaque-inquiry-id");
    expect(fixture.allowedActions).toEqual(["START_CONSULTATION"]);
    expect(fixture.fixtureReadiness).toBe("READY");
  });

  it("준비되지 않은 Fixture를 거부한다", () => {
    expect(() =>
      parseBackendFixture({
        ...readyFixture,
        fixture_readiness: "BLOCKED",
      }),
    ).toThrow("fixture_readiness=READY");
  });

  it("Token이나 개인정보 필드가 섞인 Fixture를 거부한다", () => {
    expect(() =>
      parseBackendFixture({
        ...readyFixture,
        access_token: "secret",
      }),
    ).toThrow("비밀정보 또는 개인정보");
  });

  it("상담 시작 외의 허용 행동이 포함된 Fixture를 거부한다", () => {
    expect(() =>
      parseBackendFixture({
        ...readyFixture,
        allowed_actions: ["START_CONSULTATION", "FINALIZE_INQUIRY"],
      }),
    ).toThrow("상담 시작 경계");
  });
});
