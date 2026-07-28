import { describe, expect, it } from "vitest";

import { createRequestContext } from "../../src/common/api/requestContext";

describe("createRequestContext", () => {
  it("쓰기 요청마다 새로운 멱등 키와 추적 ID를 생성한다", () => {
    const first = createRequestContext();
    const second = createRequestContext();

    expect(first.idempotencyKey).not.toBe(second.idempotencyKey);
    expect(first.correlationId).not.toBe(second.correlationId);
    expect(first.headers["Idempotency-Key"]).toBe(first.idempotencyKey);
    expect(first.headers["X-Correlation-ID"]).toBe(first.correlationId);
  });
});

