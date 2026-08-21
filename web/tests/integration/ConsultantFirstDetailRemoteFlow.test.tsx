import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import type {
  ConsultantInquiryDetailViewModel,
  ConsultantInquiryListViewModel,
} from "../../src/features/consultation/model/consultantWorkspaceRemoteMapper";
import {
  clearRecentConsultantInquiryIds,
  rememberRecentConsultantInquiryId,
} from "../../src/features/consultation/model/recentConsultantInquiryIds";
import { MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA } from "../../src/features/notice/model/consultantNotice";
import ConsultantDashboardPage from "../../src/pages/consultant/ConsultantDashboardPage";
import ConsultantInquiryListPage from "../../src/pages/consultant/ConsultantInquiryListPage";

const remoteMocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getInquiryDetail: vi.fn(),
  listInquiries: vi.fn(),
}));

vi.mock("../../src/app/config/env", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/app/config/env")>();
  return {
    ...actual,
    appEnv: {
      ...actual.appEnv,
      enableDesignMockFallback: false,
      useMockApi: false,
    },
  };
});

vi.mock(
  "../../src/features/consultation/repositories/consultantWorkspaceDataRepository",
  async (importOriginal) => {
    const actual = await importOriginal<
      typeof import("../../src/features/consultation/repositories/consultantWorkspaceDataRepository")
    >();
    return {
      ...actual,
      consultantWorkspaceDataRepository: {
        dataSource: "REMOTE",
        getInquiryDetail: remoteMocks.getInquiryDetail,
        listInquiries: remoteMocks.listInquiries,
      },
    };
  },
);

vi.mock(
  "../../src/features/notice/api/consultantNoticeApi",
  async (importOriginal) => {
    const actual = await importOriginal<
      typeof import("../../src/features/notice/api/consultantNoticeApi")
    >();
    return {
      ...actual,
      getSyntheticConsultantDashboardData: remoteMocks.getDashboard,
    };
  },
);

const CONSULTANT_USER = {
  id: "STAFF-CONS-REMOTE",
  displayName: "Remote 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

const INQUIRY_ID = "10000000-0000-4000-8000-000000000101";

const DETAIL: ConsultantInquiryDetailViewModel = {
  inquiryId: INQUIRY_ID,
  inquiryCode: "SYN-INQ-0101",
  status: "CONSULTATION_REQUIRED",
  stateVersion: 4,
  riskLevel: "danger",
  priority: "URGENT",
  receivedAt: "2026-08-20T09:00:00+09:00",
  updatedAt: "2026-08-20T09:05:00+09:00",
  customer: {
    isSynthetic: true,
    displayName: "합성 고객 01",
    phone: "010-0000-0101",
  },
  productAndCare: null,
  symptomAndQuestionnaire: {
    symptomSummary: "누수 긴급 점검 요청",
    answers: [],
  },
  guidanceAndActions: {
    usageGuidanceStatus: "TOTAL_STOP",
    usageGuidanceMessage: "급수 밸브를 잠가 주세요.",
    restrictedFunctions: ["출수"],
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

const LIST: ConsultantInquiryListViewModel = {
  items: [
    {
      inquiryId: INQUIRY_ID,
      inquiryCode: DETAIL.inquiryCode,
      status: DETAIL.status,
      stateVersion: DETAIL.stateVersion,
      riskLevel: DETAIL.riskLevel,
      priority: DETAIL.priority,
      symptomSummary: DETAIL.symptomAndQuestionnaire.symptomSummary,
      customerDisplayNameMasked: DETAIL.customer.displayName,
      productModel: "SYN-WP-01",
      receivedAt: DETAIL.receivedAt,
      updatedAt: DETAIL.updatedAt,
      waitingSeconds: 300,
      allowedActions: DETAIL.workflow.allowedActions,
    },
  ],
  pageInfo: { page: 1, size: 10, total: 1 },
  statusCounts: { CONSULTATION_REQUIRED: 1 },
};

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="현재 경로">{location.pathname}{location.search}</output>;
}

function renderPage(
  page: "dashboard" | "list",
) {
  if (page === "dashboard") {
    rememberRecentConsultantInquiryId(CONSULTANT_USER.id, INQUIRY_ID);
  }

  const path = page === "dashboard"
    ? "/consultant/dashboard"
    : "/consultant/inquiries?bucket=NEW";
  const Page = page === "dashboard"
    ? ConsultantDashboardPage
    : ConsultantInquiryListPage;

  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path={page === "dashboard" ? "/consultant/dashboard" : "/consultant/inquiries"}
            element={
              <>
                <Page />
                <LocationProbe />
              </>
            }
          />
          <Route
            path="/consultant/inquiries/:inquiryId"
            element={<h1>기존 전체 기록 화면</h1>}
          />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("상담사 Remote 첫 상세 패널 경로", () => {
  beforeEach(() => {
    clearRecentConsultantInquiryIds(CONSULTANT_USER.id);
    remoteMocks.getDashboard.mockReset();
    remoteMocks.getDashboard.mockResolvedValue(
      MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA,
    );
    remoteMocks.getInquiryDetail.mockReset();
    remoteMocks.getInquiryDetail.mockResolvedValue({
      correlationId: "corr-detail",
      data: DETAIL,
    });
    remoteMocks.listInquiries.mockReset();
    remoteMocks.listInquiries.mockResolvedValue({
      correlationId: "corr-list",
      data: LIST,
    });
  });

  it.each([
    ["dashboard", "/consultant/dashboard"],
    ["list", "/consultant/inquiries?bucket=NEW"],
  ] as const)(
    "%s 문의 클릭은 현재 화면을 유지하고 Remote 첫 패널을 연다",
    async (page, expectedPath) => {
      const user = userEvent.setup();
      renderPage(page);

      await user.click(
        await screen.findByRole("button", {
          name: page === "dashboard"
            ? /SYN-INQ-0101.*다시 열기/
            : /SYN-INQ-0101.*상세 열기/,
        }),
      );

      expect(screen.getByLabelText("현재 경로")).toHaveTextContent(expectedPath);
      expect(await screen.findByRole("dialog")).toBeVisible();
      expect(screen.getByLabelText("실제 API 문의 상세")).toBeInTheDocument();
      expect(screen.getByLabelText("상담 처리 작업")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "전체 기록 보기" }),
      ).toBeInTheDocument();
      expect(remoteMocks.getInquiryDetail).toHaveBeenCalledWith(INQUIRY_ID);
    },
  );

  it("Remote 첫 패널에서도 기존 전체 기록 화면으로 이동할 수 있다", async () => {
    const user = userEvent.setup();
    renderPage("list");

    await user.click(
      await screen.findByRole("button", {
        name: /SYN-INQ-0101.*상세 열기/,
      }),
    );
    await user.click(
      await screen.findByRole("button", { name: "전체 기록 보기" }),
    );

    expect(
      await screen.findByRole("heading", { name: "기존 전체 기록 화면" }),
    ).toBeInTheDocument();
  });
});
