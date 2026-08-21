import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../src/common/api/apiError";
import { parseInquiryId } from "../../src/entities/inquiry/inquiryIdentifiers";
import RemoteConsultantFirstDetailPanel from "../../src/features/consultation/components/RemoteConsultantFirstDetailPanel";
import type {
  ConsultantInquiryDetailViewModel,
  ConsultantInquiryListViewModel,
} from "../../src/features/consultation/model/consultantWorkspaceRemoteMapper";
import type { ConsultantWorkspaceDataRepository } from "../../src/features/consultation/repositories/consultantWorkspaceDataRepository";

const INQUIRY_ID = parseInquiryId(
  "10000000-0000-4000-8000-000000000101",
);

const EMPTY_LIST: ConsultantInquiryListViewModel = {
  items: [],
  pageInfo: { page: 1, size: 10, total: 0 },
  statusCounts: {},
};

const DETAIL: ConsultantInquiryDetailViewModel = {
  inquiryId: INQUIRY_ID,
  inquiryCode: "SYN-INQ-0101",
  status: "CONSULTATION_REQUIRED",
  stateVersion: 4,
  riskLevel: "caution",
  priority: "HIGH",
  receivedAt: "2026-08-20T09:00:00+09:00",
  updatedAt: "2026-08-20T09:05:00+09:00",
  customer: {
    isSynthetic: true,
    displayName: "합성 고객 01",
    phone: "010-0000-0101",
  },
  productAndCare: null,
  symptomAndQuestionnaire: {
    symptomSummary: "출수량이 감소함",
    answers: [],
  },
  guidanceAndActions: {
    usageGuidanceStatus: "PENDING_CONSULTATION",
    usageGuidanceMessage: "상담 연결을 기다려 주세요.",
    restrictedFunctions: [],
  },
  consultation: null,
  visit: null,
  stateHistory: [],
  workflow: {
    status: "CONSULTATION_REQUIRED",
    stateVersion: 4,
    allowedActions: [
      {
        code: "START_CONSULTATION",
        label: "상담 시작",
        operationId: "startConsultation",
        style: "PRIMARY",
        requiresConfirmation: false,
        confirmationMessage: null,
      },
    ],
  },
  sectionErrors: [],
};

function createRepository(
  getInquiryDetail: ConsultantWorkspaceDataRepository["getInquiryDetail"],
): ConsultantWorkspaceDataRepository {
  return {
    dataSource: "REMOTE",
    getInquiryDetail,
    listInquiries: vi.fn(async () => ({
      correlationId: "corr-list",
      data: EMPTY_LIST,
    })),
  };
}

function renderPanel(
  repository: ConsultantWorkspaceDataRepository,
  onRefreshWorkspace = vi.fn(),
) {
  render(
    <MemoryRouter initialEntries={["/consultant/inquiries?bucket=NEW"]}>
      <Routes>
        <Route
          path="/consultant/inquiries"
          element={
            <RemoteConsultantFirstDetailPanel
              inquiryId={INQUIRY_ID}
              repository={repository}
              returnTo="/consultant/inquiries?bucket=NEW"
              onClose={vi.fn()}
              onRefreshWorkspace={onRefreshWorkspace}
            />
          }
        />
        <Route
          path="/consultant/inquiries/:inquiryId"
          element={<h1>기존 전체 기록 화면</h1>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Remote 첫 문의 상세 패널", () => {
  it("로딩 후 실제 상세와 상담 처리 및 기존 전체 기록 버튼을 표시한다", async () => {
    let resolveDetail:
      | ((value: {
          correlationId: string;
          data: ConsultantInquiryDetailViewModel;
        }) => void)
      | undefined;
    const repository = createRepository(
      vi.fn(
        () =>
          new Promise((resolve) => {
            resolveDetail = resolve;
          }),
      ),
    );

    renderPanel(repository);

    expect(
      screen.getByText("문의 정보를 불러오고 있습니다."),
    ).toBeInTheDocument();

    act(() => {
      resolveDetail?.({ correlationId: "corr-detail", data: DETAIL });
    });

    expect(
      await screen.findByLabelText("실제 API 문의 상세"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("상담 처리 작업")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "상담 시작" })).toBeInTheDocument();
    expect(screen.getByText("조회 확인 번호: corr-detail")).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "전체 기록 보기" }),
    );
    expect(
      await screen.findByRole("heading", { name: "기존 전체 기록 화면" }),
    ).toBeInTheDocument();
  });

  it("403 오류와 확인 번호를 패널 안에서 안내한다", async () => {
    const repository = createRepository(
      vi.fn(async () => {
        throw new ApiClientError({
          correlationId: "corr-forbidden",
          kind: "FORBIDDEN",
          message: "forbidden",
          status: 403,
        });
      }),
    );

    renderPanel(repository);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("이 문의에 접근할 권한이 없습니다.");
    expect(alert).toHaveTextContent("확인 번호: corr-forbidden");
    expect(screen.queryByLabelText("실제 API 문의 상세")).not.toBeInTheDocument();
  });

  it("404는 문의 존재 여부와 배정 여부를 구분하지 않는 동일 문구로 표시한다", async () => {
    const repository = createRepository(
      vi.fn(async () => {
        throw new ApiClientError({
          correlationId: "corr-not-found",
          kind: "NOT_FOUND",
          message: "내부 배정 정보 노출 금지",
          status: 404,
        });
      }),
    );

    renderPanel(repository);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("문의 정보를 찾을 수 없습니다.");
    expect(alert).toHaveTextContent(
      "문의가 없거나 현재 상담사에게 배정되지 않은 경우 동일하게 안내됩니다.",
    );
    expect(alert).toHaveTextContent("확인 번호: corr-not-found");
    expect(alert).not.toHaveTextContent("내부 배정 정보 노출 금지");
  });

  it("409 조회 충돌에서 최신 상태 재시도를 제공한다", async () => {
    const getInquiryDetail = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiClientError({
          correlationId: "corr-conflict",
          kind: "CONFLICT",
          message: "conflict",
          status: 409,
        }),
      )
      .mockResolvedValueOnce({ correlationId: "corr-retry", data: DETAIL });
    const repository = createRepository(getInquiryDetail);

    renderPanel(repository);

    expect(
      await screen.findByText("문의 상태가 변경되었습니다."),
    ).toBeInTheDocument();
    expect(screen.getByText(/corr-conflict/)).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "최신 상태 다시 불러오기" }),
    );

    expect(
      await screen.findByLabelText("실제 API 문의 상세"),
    ).toBeInTheDocument();
    expect(getInquiryDetail).toHaveBeenCalledTimes(2);
  });
});
