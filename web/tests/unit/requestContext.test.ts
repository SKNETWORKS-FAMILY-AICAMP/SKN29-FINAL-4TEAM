import { describe, expect, it } from "vitest";

import { createRequestContext } from "../../src/common/api/requestContext";

describe("createRequestContext", () => {
  it("새 논리 쓰기 요청에 UUID 멱등 키와 추적 ID를 생성한다", () => {
    const first = createRequestContext();
    const second = createRequestContext();
    const uuidPattern =
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    expect(first.idempotencyKey).not.toBe(second.idempotencyKey);
    expect(first.correlationId).not.toBe(second.correlationId);
    expect(first.idempotencyKey).toMatch(uuidPattern);
    expect(first.correlationId).toMatch(uuidPattern);
    expect(first.headers["Idempotency-Key"]).toBe(first.idempotencyKey);
    expect(first.headers["X-Correlation-ID"]).toBe(first.correlationId);
  });

  it("재시도 멱등 키를 보존하면서 추적 ID는 새로 만든다", () => {
    const initial = createRequestContext();
    const retry = createRequestContext({
      idempotencyKey: initial.idempotencyKey,
    });

    expect(retry.idempotencyKey).toBe(initial.idempotencyKey);
    expect(retry.correlationId).not.toBe(initial.correlationId);
    expect(retry.headers["Idempotency-Key"]).toBe(initial.idempotencyKey);
  });
});

