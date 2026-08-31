import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../src/common/api/apiError";
import type { ApiResponse } from "../../src/common/api/apiResponse";
import UnassignedConsultationQueue from "../../src/features/consultation/components/UnassignedConsultationQueue";
import type { UnassignedConsultationQueueQuery } from "../../src/features/consultation/api/consultantWorkspaceRemoteTypes";
import type { UnassignedConsultationQueueViewModel } from "../../src/features/consultation/model/consultantWorkspaceRemoteMapper";
import type { ConsultantWorkspaceDataRepository } from "../../src/features/consultation/repositories/consultantWorkspaceDataRepository";
import type {
  ConsultationWriteRepository,
  StateTransitionResultDto,
} from "../../src/features/consultation/repositories/consultationWriteRepository";

const INQUIRY_ID = "10000000-0000-4000-8000-000000000101";

function createQueue(
  allowedActionCode = "CLAIM_CONSULTATION",
): UnassignedConsultationQueueViewModel {
  return {
    items: [
      {
        inquiryId: INQUIRY_ID,
        inquiryCode: "SYN-INQ-0101",
        status: "CONSULTATION_REQUIRED",
        stateVersion: 3,
        riskLevel: "danger",
        priority: "URGENT",
        symptomSummary: "정수기에서 물이 새요",
        customerDisplayNameMasked: "합성고객 01",
        productModel: "WPUJAC104DWH",
        currentAssigneeType: "NONE",
        receivedAt: "2026-08-24T09:00:00+09:00",
        updatedAt: "2026-08-24T09:01:00+09:00",
        waitingSeconds: 900,
        allowedActions: allowedActionCode
          ? [
              {
                code: allowedActionCode,
                label: "상담 가져오기",
                operationId: "claimConsultation",
                style: "PRIMARY",
                requiresConfirmation: false,
                confirmationMessage: null,
              },
            ]
          : [],
      },
    ],
    pageInfo: { page: 1, size: 20, total: 1 },
  };
}

function successResponse(
  overrides: Partial<StateTransitionResultDto> = {},
): ApiResponse<StateTransitionResultDto> {
  return {
    success: true,
    data: {
      message: "상담 대기 문의를 배정받았습니다.",
      inquiry_id: INQUIRY_ID,
      status: "CONSULTATION_REQUIRED",
      state_version: 4,
      allowed_actions: [],
      idempotent_replay: false,
      resource: null,
      ...overrides,
    },
    error: null,
    metadata: { correlation_id: "corr-claim-success" },
  };
}

function createDataRepository(
  queue = createQueue(),
  dataSource: "MOCK" | "REMOTE" = "REMOTE",
): ConsultantWorkspaceDataRepository {
  return {
    dataSource,
    listInquiries: vi.fn(),
    listUnassignedConsultations: vi.fn(async () => ({
      data: queue,
      correlationId: "corr-unassigned-list",
    })),
    getInquiryDetail: vi.fn(),
  };
}

function createWriteRepository(
  claimConsultation = vi.fn(async () => successResponse()),
): ConsultationWriteRepository {
  return {
    claimConsultation,
    start: vi.fn(async () => successResponse()),
    saveSummary: vi.fn(async () => successResponse()),
    confirmSummary: vi.fn(async () => successResponse()),
    complete: vi.fn(async () => successResponse()),
  };
}

describe("미배정 상담 대기 목록", () => {
  it("미배정 목록은 한글 긴급도·문의 내용·대기 시간과 허용된 상담 시작만 표시한다", async () => {
    const dataRepository = createDataRepository();

    render(
      <UnassignedConsultationQueue
        dataRepository={dataRepository}
        writeRepository={createWriteRepository()}
        onClaimed={vi.fn()}
      />,
    );

    expect(await screen.findByText("정수기에서 물이 새요")).toBeVisible();
    expect(screen.queryByText(/WPUJAC104DWH/)).not.toBeInTheDocument();
    expect(screen.queryByText(/초소형 직수 냉온 정수기/)).not.toBeInTheDocument();
    expect(screen.queryByText("합성고객 01")).not.toBeInTheDocument();
    expect(screen.queryByText("URGENT")).not.toBeInTheDocument();
    expect(screen.getByText("긴급")).toBeVisible();
    expect(screen.queryByText("SYN-INQ-0101")).not.toBeInTheDocument();
    expect(screen.getByText("15분 대기")).toBeVisible();
    expect(screen.queryByText("UNASSIGNED")).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "원하는 문의를 가져오면 내 상담 목록에서 이어서 처리할 수 있습니다.",
      ),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "정수기에서 물이 새요 상담 시작",
      }),
    ).toBeVisible();
    expect(dataRepository.getInquiryDetail).not.toHaveBeenCalled();
    expect(dataRepository.listUnassignedConsultations).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      sort: "WAITING_DESC",
    });
    expect(screen.getByRole("navigation", { name: "미배정 상담 페이지" }))
      .toHaveTextContent("총 1건 · 1/1페이지");
    expect(screen.getByRole("button", { name: "미배정 이전 페이지" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "미배정 다음 페이지" })).toBeDisabled();
  });

  it("네 건을 한 페이지에 보여주며 페이지 조작부는 스크롤 본문 밖에 둔다", async () => {
    const queue = createQueue();
    const inquiries = Array.from({ length: 4 }, (_, index) => ({
      ...queue.items[0],
      inquiryId: `waiting-inquiry-${index}`,
      symptomSummary: `접수된 문의 ${index + 1}`,
    }));
    render(
      <UnassignedConsultationQueue
        dataRepository={createDataRepository({
          ...queue,
          items: inquiries,
          pageInfo: { page: 1, size: 20, total: 4 },
        })}
        writeRepository={createWriteRepository()}
        onClaimed={vi.fn()}
      />,
    );

    expect(await screen.findAllByRole("button", { name: /문의 미리보기$/ }))
      .toHaveLength(4);
    const pagination = screen.getByRole("navigation", { name: "미배정 상담 페이지" });
    const section = screen.getByRole("region", { name: "미배정 상담 대기 목록" });
    expect(pagination.parentElement).toBe(section);
    expect(pagination.previousElementSibling)
      .toHaveClass("unassigned-consultation-queue__content");
    expect(pagination).toHaveTextContent("총 4건 · 1/1페이지");
    expect(screen.getByRole("button", { name: "미배정 다음 페이지" })).toBeDisabled();
  });

  it("목록을 누르면 기존 문의 미리보기를 열고 영문 긴급도는 노출하지 않는다", async () => {
    const user = userEvent.setup();
    const dataRepository = createDataRepository();
    render(
      <UnassignedConsultationQueue
        dataRepository={dataRepository}
        writeRepository={createWriteRepository()}
        onClaimed={vi.fn()}
      />,
    );

    await user.click(await screen.findByRole("button", {
      name: "정수기에서 물이 새요 문의 미리보기",
    }));

    const preview = within(screen.getByRole("dialog"));
    expect(preview.getByRole("heading", { name: "정수기에서 물이 새요" })).toBeVisible();
    expect(preview.getByText("긴급")).toBeVisible();
    expect(preview.queryByText("URGENT")).not.toBeInTheDocument();
    expect(preview.getByRole("button", { name: "상담 시작" })).toBeEnabled();
    expect(dataRepository.getInquiryDetail).not.toHaveBeenCalled();
  });

  it("상태 버전과 요청 식별 Header로 한 번만 가져온 뒤 목록과 상세 갱신을 요청한다", async () => {
    const user = userEvent.setup();
    const claimConsultation = vi.fn(async () => successResponse());
    const dataRepository = createDataRepository();
    const onClaimed = vi.fn();

    render(
      <UnassignedConsultationQueue
        dataRepository={dataRepository}
        writeRepository={createWriteRepository(claimConsultation)}
        onClaimed={onClaimed}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "정수기에서 물이 새요 상담 시작",
      }),
    );

    await waitFor(() => expect(onClaimed).toHaveBeenCalledWith(INQUIRY_ID));
    expect(
      screen.getByText("상담 대기 문의를 배정받았습니다."),
    ).toBeVisible();
    expect(claimConsultation).toHaveBeenCalledTimes(1);
    expect(claimConsultation).toHaveBeenCalledWith(
      INQUIRY_ID,
      { state_version: 3 },
      expect.objectContaining({
        headers: {
          "Idempotency-Key": expect.any(String),
          "X-Correlation-ID": expect.any(String),
        },
      }),
    );
    await waitFor(() =>
      expect(dataRepository.listUnassignedConsultations).toHaveBeenCalledTimes(
        2,
      ),
    );
  });

  it("처리 중 빠르게 두 번 눌러도 Claim 요청은 한 번만 전송한다", async () => {
    let resolveClaim:
      | ((response: ApiResponse<StateTransitionResultDto>) => void)
      | undefined;
    const claimConsultation = vi.fn(
      () =>
        new Promise<ApiResponse<StateTransitionResultDto>>((resolve) => {
          resolveClaim = resolve;
        }),
    );

    render(
      <UnassignedConsultationQueue
        dataRepository={createDataRepository()}
        writeRepository={createWriteRepository(claimConsultation)}
        onClaimed={vi.fn()}
      />,
    );

    const button = await screen.findByRole("button", {
      name: "정수기에서 물이 새요 상담 시작",
    });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(claimConsultation).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("시작하는 중");

    resolveClaim?.(successResponse());
  });

  it("동일 요청 Replay 성공도 Backend 결과로 처리하고 최신 화면을 다시 조회한다", async () => {
    const user = userEvent.setup();
    const dataRepository = createDataRepository();
    const onClaimed = vi.fn();
    const claimConsultation = vi.fn(async () =>
      successResponse({
        idempotent_replay: true,
        message: "기존 상담 배정 결과를 반환했습니다.",
      }),
    );

    render(
      <UnassignedConsultationQueue
        dataRepository={dataRepository}
        writeRepository={createWriteRepository(claimConsultation)}
        onClaimed={onClaimed}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "정수기에서 물이 새요 상담 시작",
      }),
    );

    expect(
      await screen.findByText("기존 상담 배정 결과를 반환했습니다."),
    ).toBeVisible();
    expect(onClaimed).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(dataRepository.listUnassignedConsultations).toHaveBeenCalledTimes(
        2,
      ),
    );
  });

  it.each([
    ["응답 data 없음", null],
    [
      "다른 inquiry_id",
      successResponse({
        inquiry_id: "10000000-0000-4000-8000-000000000999",
      }).data,
    ],
  ])("2xx %s은 화면에서 성공으로 만들지 않는다", async (_case, data) => {
    const user = userEvent.setup();
    const onClaimed = vi.fn();
    const invalidResponse: ApiResponse<StateTransitionResultDto> = {
      ...successResponse(),
      data,
    };

    render(
      <UnassignedConsultationQueue
        dataRepository={createDataRepository()}
        writeRepository={createWriteRepository(
          vi.fn(async () => invalidResponse),
        )}
        onClaimed={onClaimed}
      />,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "정수기에서 물이 새요 상담 시작",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "상담을 가져오지 못했습니다.",
    );
    expect(onClaimed).not.toHaveBeenCalled();
  });

  it.each([
    [
      404,
      "RESOURCE_NOT_FOUND",
      "다른 상담사가 먼저 가져간 문의입니다.",
    ],
    [
      409,
      "STATE-CONFLICT-01",
      "화면이 오래되어 문의 상태가 달라졌습니다.",
    ],
    [
      409,
      "DUPLICATE-EVENT-01",
      "같은 요청이 다른 내용으로 이미 처리되었습니다.",
    ],
  ])(
    "%i %s 오류를 설명하고 최신 미배정 목록을 다시 조회한다",
    async (status, code, message) => {
      const user = userEvent.setup();
      const dataRepository = createDataRepository();
      const claimConsultation = vi.fn(async () => {
        throw new ApiClientError({
          kind: status === 404 ? "NOT_FOUND" : "CONFLICT",
          status,
          code,
          correlationId: "corr-claim-error",
          message: "request failed",
        });
      });

      render(
        <UnassignedConsultationQueue
          dataRepository={dataRepository}
          writeRepository={createWriteRepository(claimConsultation)}
          onClaimed={vi.fn()}
        />,
      );

      await user.click(
        await screen.findByRole("button", {
          name: "정수기에서 물이 새요 상담 시작",
        }),
      );

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(screen.getByRole("alert")).toHaveTextContent(
        "확인 번호: corr-claim-error",
      );
      await waitFor(() =>
        expect(
          dataRepository.listUnassignedConsultations,
        ).toHaveBeenCalledTimes(2),
      );
    },
  );

  it.each([
    [
      401,
      "UNAUTHORIZED",
      "AUTH_REQUIRED",
      "로그인이 필요하거나 로그인 정보가 만료되었습니다.",
    ],
    [403, "FORBIDDEN", "FORBIDDEN", "이 상담을 가져올 권한이 없습니다."],
    [
      422,
      "VALIDATION_ERROR",
      "VALIDATION_ERROR",
      "요청 정보를 확인할 수 없습니다.",
    ],
  ] as const)(
    "Claim %i %s 오류를 Backend 실패로 안내하고 성공 처리하지 않는다",
    async (status, kind, code, message) => {
      const user = userEvent.setup();
      const dataRepository = createDataRepository();
      const onClaimed = vi.fn();
      const claimConsultation = vi.fn(async () => {
        throw new ApiClientError({
          kind,
          status,
          code,
          correlationId: "corr-claim-denied",
          message: "request failed",
        });
      });

      render(
        <UnassignedConsultationQueue
          dataRepository={dataRepository}
          writeRepository={createWriteRepository(claimConsultation)}
          onClaimed={onClaimed}
        />,
      );

      await user.click(
        await screen.findByRole("button", {
          name: "정수기에서 물이 새요 상담 시작",
        }),
      );

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(onClaimed).not.toHaveBeenCalled();
      expect(dataRepository.listUnassignedConsultations).toHaveBeenCalledTimes(
        2,
      );
    },
  );

  it.each([
    [
      0,
      "NETWORK_ERROR",
      "네트워크 오류가 발생했습니다. 네트워크 연결을 확인해 주세요.",
    ],
    [401, "UNAUTHORIZED", "로그인이 필요하거나 로그인 정보가 만료되었습니다."],
    [403, "FORBIDDEN", "미배정 상담 목록을 볼 권한이 없습니다."],
    [422, "VALIDATION_ERROR", "미배정 상담 목록의 조회 조건을 확인할 수 없습니다."],
  ] as const)(
    "미배정 목록 %i 오류를 구분해서 안내한다",
    async (status, kind, message) => {
      const dataRepository = createDataRepository();
      dataRepository.listUnassignedConsultations = vi.fn(async () => {
        throw new ApiClientError({
          kind,
          status,
          code: kind,
          correlationId: "corr-queue-error",
          message: "request failed",
        });
      });

      render(
        <UnassignedConsultationQueue
          dataRepository={dataRepository}
          writeRepository={createWriteRepository()}
          onClaimed={vi.fn()}
        />,
      );

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(screen.getByRole("alert")).toHaveTextContent(
        "확인 번호: corr-queue-error",
      );
    },
  );

  it("허용 동작이 없으면 상담 가져오기 버튼을 숨긴다", async () => {
    render(
      <UnassignedConsultationQueue
        dataRepository={createDataRepository(createQueue(""))}
        writeRepository={createWriteRepository()}
        onClaimed={vi.fn()}
      />,
    );

    expect(await screen.findByText("현재 배정할 수 없음")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /상담 시작/ }),
    ).not.toBeInTheDocument();
  });

  it.each(["WPUIAC425SNW", "WPUIAC606SNW", "WPUJCC104D"])(
    "%s 문의에 Backend Claim 허용 동작이 없으면 Web도 배정 버튼을 만들지 않는다",
    async (productModel) => {
      const queue = createQueue("");
      const productQueue: UnassignedConsultationQueueViewModel = {
        ...queue,
        items: [{ ...queue.items[0], productModel }],
      };

      render(
        <UnassignedConsultationQueue
          dataRepository={createDataRepository(productQueue)}
          writeRepository={createWriteRepository()}
          onClaimed={vi.fn()}
        />,
      );

      expect(
        await screen.findByTestId(`unassigned-consultation-${INQUIRY_ID}`),
      ).not.toHaveTextContent(productModel);
      expect(screen.getByText("현재 배정할 수 없음")).toBeVisible();
      expect(
        screen.queryByRole("button", { name: /상담 시작/ }),
      ).not.toBeInTheDocument();
    },
  );

  it("디자인 Mock에서는 API를 호출하지 않고 상담 화면 미리보기를 연다", async () => {
    const user = userEvent.setup();
    const claimConsultation = vi.fn(async () => successResponse());
    const onClaimed = vi.fn();

    render(
      <UnassignedConsultationQueue
        dataRepository={createDataRepository(createQueue(), "MOCK")}
        writeRepository={createWriteRepository(claimConsultation)}
        onClaimed={onClaimed}
      />,
    );

    const button = await screen.findByRole("button", {
      name: "정수기에서 물이 새요 상담 시작",
    });
    expect(button).toBeEnabled();
    await user.click(button);

    expect(claimConsultation).not.toHaveBeenCalled();
    expect(onClaimed).toHaveBeenCalledWith(INQUIRY_ID);
  });

  it("마지막 페이지의 마지막 문의가 사라지면 남은 마지막 페이지로 돌아간다", async () => {
    const user = userEvent.setup();
    const pageTwoItem = createQueue().items[0];
    const pageOneItem = {
      ...pageTwoItem,
      inquiryId: "10000000-0000-4000-8000-000000000201",
      inquiryCode: "SYN-INQ-0201",
      symptomSummary: "1페이지에 남은 상담",
    };
    let claimed = false;
    const listUnassignedConsultations = vi.fn(
      async (query: UnassignedConsultationQueueQuery = {}) => {
        const isSecondPage = query.page === 2;
        return {
          correlationId: "corr-page-clamp",
          data: {
            items: isSecondPage && claimed
              ? []
              : [isSecondPage ? pageTwoItem : pageOneItem],
            pageInfo: {
              page: query.page ?? 1,
              size: 3,
              total: claimed ? 3 : 4,
            },
          },
        };
      },
    );
    const dataRepository: ConsultantWorkspaceDataRepository = {
      ...createDataRepository(),
      listUnassignedConsultations,
    };
    const claimConsultation = vi.fn(async () => {
      claimed = true;
      return successResponse();
    });

    render(
      <UnassignedConsultationQueue
        dataRepository={dataRepository}
        writeRepository={createWriteRepository(claimConsultation)}
        onClaimed={vi.fn()}
      />,
    );

    await user.click(
      await screen.findByRole("button", { name: "미배정 다음 페이지" }),
    );
    await user.click(
      await screen.findByRole("button", {
        name: "정수기에서 물이 새요 상담 시작",
      }),
    );

    expect(await screen.findByText("1페이지에 남은 상담")).toBeVisible();
    await waitFor(() =>
      expect(
        listUnassignedConsultations.mock.calls.map(([query]) => query?.page),
      ).toEqual([1, 2, 1]),
    );
  });
});
