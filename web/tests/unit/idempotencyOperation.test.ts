import { describe, expect, it } from "vitest";

import { IdempotencyOperationTracker } from "../../src/common/api/idempotencyOperation";

function createTracker() {
  let sequence = 0;
  return new IdempotencyOperationTracker(() => `key-${++sequence}`);
}

describe("IdempotencyOperationTracker", () => {
  it("같은 요청의 네트워크 재시도에는 같은 키를 사용한다", () => {
    const tracker = createTracker();
    const firstKey = tracker.begin("same-request");

    tracker.fail(true);

    expect(tracker.begin("same-request")).toBe(firstKey);
  });

  it("성공한 요청을 다시 시작하면 새 키를 사용한다", () => {
    const tracker = createTracker();
    const firstKey = tracker.begin("same-request");

    tracker.finish();

    expect(tracker.begin("same-request")).not.toBe(firstKey);
  });

  it("재시도할 수 없는 실패나 변경된 요청에는 새 키를 사용한다", () => {
    const tracker = createTracker();
    const firstKey = tracker.begin("first-request");

    tracker.fail(false);
    const secondKey = tracker.begin("first-request");
    const changedRequestKey = tracker.begin("changed-request");

    expect(secondKey).not.toBe(firstKey);
    expect(changedRequestKey).not.toBe(secondKey);
  });
});
