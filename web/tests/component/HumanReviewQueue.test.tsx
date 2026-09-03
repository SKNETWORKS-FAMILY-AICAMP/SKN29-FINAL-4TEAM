import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../src/common/api/apiError";
import type { ApiResponse } from "../../src/common/api/apiResponse";
import HumanReviewQueue from "../../src/features/consultation/components/HumanReviewQueue";
import type {
  HumanReviewDto,
  HumanReviewListDataDto,
} from "../../src/features/consultation/api/humanReviewRemoteTypes";
import type { HumanReviewRepository } from "../../src/features/consultation/repositories/humanReviewRepository";
import type {
  ConsultationWriteRepository,
  StateTransitionResultDto,
} from "../../src/features/consultation/repositories/consultationWriteRepository";

const REVIEW_ID = "20000000-0000-4000-8000-000000000201";
const INQUIRY_ID = "10000000-0000-4000-8000-000000000101";

function review(overrides: Partial<HumanReviewDto> = {}): HumanReviewDto {
  return {
    review_id: REVIEW_ID,
    inquiry_id: INQUIRY_ID,
    inquiry_status: "QUESTIONNAIRE_IN_PROGRESS",
    inquiry_state_version: 3,
    model_code: "WPUJAC104DWH",
    status: "PENDING",
    decision: null,
    review_state_version: 1,
    source_inquiry_state_version: 3,
    reason_code: "LOW_CONFIDENCE",
    original_requires_consultation: false,
    proposed_guidance: {
      guidance_id: "30000000-0000-4000-8000-000000000301",
      guidance_version: 1,
      title: "누수 여부를 확인해 주세요",
      summary_text: "급수 밸브와 제품 주변을 확인해 주세요.",
      safety_notice: "젖은 바닥에서 미끄러지지 않도록 주의해 주세요.",
      requires_consultation: false,
      items: [
        {
          step_no: 1,
          instruction_text: "급수 밸브를 잠가 주세요.",
          caution_text: null,
          requires_confirmation: true,
        },
      ],
    },
    allowed_actions: ["DECIDE_HUMAN_REVIEW"],
    ...overrides,
  };
}

function response<TData>(data: TData, correlationId: string): ApiResponse<TData> {
  return {
    success: true,
    data,
    error: null,
    metadata: { correlation_id: correlationId },
  };
}

function createReviewRepository(
  decide = vi.fn(async () =>
    response(
      review({
        inquiry_status: "CONSULTATION_REQUIRED",
        inquiry_state_version: 4,
        status: "APPROVED",
        decision: "APPROVE",
        review_state_version: 2,
      }),
      "corr-decision",
    ),
  ),
): HumanReviewRepository {
  return {
    list: vi.fn(async () =>
      response<HumanReviewListDataDto>({ items: [review()] }, "corr-list"),
    ),
    decide,
  };
}

function claimResponse(): ApiResponse<StateTransitionResultDto> {
  return response(
    {
      message: "상담 대기 문의를 배정받았습니다.",
      inquiry_id: INQUIRY_ID,
      status: "CONSULTATION_REQUIRED",
      state_version: 5,
      allowed_actions: [],
      idempotent_replay: false,
      resource: null,
    },
    "corr-claim",
  );
}

function createWriteRepository(
  claimConsultation = vi.fn(async () => claimResponse()),
): ConsultationWriteRepository {
  return {
    cancel: vi.fn(),
    claimConsultation,
    start: vi.fn(),
    saveSummary: vi.fn(),
    confirmSummary: vi.fn(),
    complete: vi.fn(),
    resume: vi.fn(),
    finalize: vi.fn(),
  };
}

describe("상담사 AI 검수 대기", () => {
  it("승인 결과의 문의 상태 버전으로 상담을 배정한다", async () => {
    const user = userEvent.setup();
    const reviewRepository = createReviewRepository();
    const writeRepository = createWriteRepository();
    const onClaimed = vi.fn();

    render(
      <HumanReviewQueue
        reviewRepository={reviewRepository}
        writeRepository={writeRepository}
        onClaimed={onClaimed}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "검수 승인 후 상담 시작" }),
    );

    await waitFor(() => expect(onClaimed).toHaveBeenCalledWith(INQUIRY_ID));
    expect(reviewRepository.decide).toHaveBeenCalledTimes(1);
    expect(reviewRepository.decide).toHaveBeenCalledWith(
      REVIEW_ID,
      {
        decision: "APPROVE",
        review_state_version: 1,
        reason_code: "APPROVED_AS_IS",
        consultation_disposition: "REQUIRE",
        consultation_reason_code: "PRODUCT_FUNCTION_UNCERTAIN",
      },
      expect.objectContaining({ idempotencyKey: expect.any(String) }),
    );
    expect(writeRepository.claimConsultation).toHaveBeenCalledWith(
      INQUIRY_ID,
      { state_version: 4 },
      expect.objectContaining({ idempotencyKey: expect.any(String) }),
    );
  });

  it("승인 뒤 네트워크가 끊기면 승인 재호출 없이 같은 키로 배정만 재시도한다", async () => {
    const user = userEvent.setup();
    const reviewRepository = createReviewRepository();
    const claimConsultation = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiClientError({ kind: "NETWORK_ERROR", message: "offline" }),
      )
      .mockResolvedValueOnce(claimResponse());
    const writeRepository = createWriteRepository(claimConsultation);
    const onClaimed = vi.fn();

    render(
      <HumanReviewQueue
        reviewRepository={reviewRepository}
        writeRepository={writeRepository}
        onClaimed={onClaimed}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "검수 승인 후 상담 시작" }),
    );
    expect(
      await screen.findByRole("button", { name: "상담 배정 다시 시도" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "상담 배정 다시 시도" }));

    await waitFor(() => expect(onClaimed).toHaveBeenCalledWith(INQUIRY_ID));
    expect(reviewRepository.decide).toHaveBeenCalledTimes(1);
    expect(claimConsultation).toHaveBeenCalledTimes(2);
    expect(claimConsultation.mock.calls[0][2].idempotencyKey).toBe(
      claimConsultation.mock.calls[1][2].idempotencyKey,
    );
  });
});
