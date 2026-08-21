import { describe, expect, it } from "vitest";

import { ApiClientError } from "../../src/common/api/apiError";
import { classifyTechnicianSourceFailure } from "../../src/features/visit-transition/model/technicianSource";

describe("합성 방문기사 Source 오류 분류", () => {
  it("403 응답은 권한 없음으로 분류한다", () => {
    expect(
      classifyTechnicianSourceFailure(
        new ApiClientError({
          kind: "FORBIDDEN",
          message: "접근 권한이 없습니다.",
          status: 403,
        }),
      ),
    ).toBe("forbidden");
  });

  it("인증 외 오류는 재시도 가능한 일반 오류로 분류한다", () => {
    expect(
      classifyTechnicianSourceFailure(
        new ApiClientError({
          kind: "SERVER_ERROR",
          message: "잠시 후 다시 시도해 주세요.",
          status: 500,
        }),
      ),
    ).toBe("error");
    expect(classifyTechnicianSourceFailure(new Error("network"))).toBe(
      "error",
    );
  });
});
