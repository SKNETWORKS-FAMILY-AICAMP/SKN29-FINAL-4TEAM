import { describe, expect, it, vi } from "vitest";

import type { ApiResponse } from "../../src/common/api/apiResponse";
import type { RequestContext } from "../../src/common/api/requestContext";
import type {
  HumanReviewDto,
  HumanReviewListDataDto,
} from "../../src/features/consultation/api/humanReviewRemoteTypes";
import {
  createRemoteHumanReviewRepository,
  type HumanReviewRequester,
} from "../../src/features/consultation/repositories/humanReviewRepository";

const context: RequestContext = {
  correlationId: "corr-review",
  idempotencyKey: "idem-review",
  headers: {
    "Idempotency-Key": "idem-review",
    "X-Correlation-ID": "corr-review",
  },
};

function emptySuccess<TData>(): ApiResponse<TData> {
  return {
    success: true,
    data: null,
    error: null,
    metadata: { correlation_id: "corr-review" },
  };
}

describe("HumanReview Repository 경계", () => {
  it("목록과 승인 요청을 확정된 API 주소와 요청 컨텍스트로 보낸다", async () => {
    const requester = vi.fn(async () => emptySuccess()) as HumanReviewRequester;
    const repository = createRemoteHumanReviewRepository(requester);

    await repository.list();
    await repository.decide(
      "review/1",
      {
        decision: "APPROVE",
        review_state_version: 3,
        reason_code: "APPROVED_AS_IS",
        consultation_disposition: "REQUIRE",
        consultation_reason_code: "PRODUCT_FUNCTION_UNCERTAIN",
      },
      context,
    );

    expect(requester).toHaveBeenNthCalledWith(1, "/inquiries/human-reviews");
    expect(requester).toHaveBeenNthCalledWith(
      2,
      "/inquiries/human-reviews/review%2F1/decision",
      {
        method: "POST",
        body: {
          decision: "APPROVE",
          review_state_version: 3,
          reason_code: "APPROVED_AS_IS",
          consultation_disposition: "REQUIRE",
          consultation_reason_code: "PRODUCT_FUNCTION_UNCERTAIN",
        },
        requestContext: context,
      },
    );
    expect(emptySuccess<HumanReviewListDataDto>()).toBeDefined();
    expect(emptySuccess<HumanReviewDto>()).toBeDefined();
  });
});
