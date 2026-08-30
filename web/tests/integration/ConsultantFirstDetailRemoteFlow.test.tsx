import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { ApiClientError } from "../../src/common/api/apiError";
import type {
  ConsultantInquiryListQuery,
} from "../../src/features/consultation/api/consultantWorkspaceRemoteTypes";
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
  listUnassignedConsultations: vi.fn(),
  requestApi: vi.fn(),
}));

vi.mock("../../src/common/api/httpClient", async (importOriginal) => {
  const actual = await importOriginal<
    typeof import("../../src/common/api/httpClient")
  >();
  return {
    ...actual,
    requestApi: remoteMocks.requestApi,
  };
});

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
        listUnassignedConsultations: remoteMocks.listUnassignedConsultations,
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
const CLAIM_INQUIRY_ID = "10000000-0000-4000-8000-000000000102";

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
    phoneMasked: "010-****-0101",
    phoneDisplay: "010-****-0101",
  },
  productAndCare: null,
  symptomAndQuestionnaire: {
    symptomSummary: "누수 긴급 점검 요청",
    answers: [],
  },
  guidanceAndActions: {
    usageGuidanceStatus: "TOTAL_STOP",
    usageGuidanceDisplayLabel: "제품 사용 중단",
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

const DASHBOARD_OVERVIEW_LIST: ConsultantInquiryListViewModel = {
  items: [],
  pageInfo: { page: 1, size: 100, total: 11 },
  statusCounts: {
    CONSULTATION_REQUIRED: 2,
    REOPENED: 1,
    DRAFT: 1,
    CONSULTATION_IN_PROGRESS: 2,
    VISIT_SCHEDULING: 1,
    COMPLETION_PENDING: 1,
    RESOLVED: 2,
    CANCELLED: 1,
  },
};

const isDashboardOverviewQuery = (
  query?: ConsultantInquiryListQuery,
): boolean => query?.page === 1 && query.size === 100;

const REMOTE_DASHBOARD_DATA = {
  ...MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA,
  generatedAt: "2026-08-24T10:00:00+09:00",
  summary: {
    total: 7,
    new: 2,
    inProgress: 3,
    completed: 2,
  },
  notices: [
    {
      ...MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA.notices[0],
      title: "Backend에서 받은 상담사 공지",
    },
  ],
  consultants: [
    {
      ...MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA.consultants[0],
      name: "원격 상담사",
      department: "원격 고객지원팀",
    },
  ],
  technicians: [
    {
      ...MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA.technicians[0],
      name: "원격 방문기사",
      branch: "원격 서울지사",
    },
  ],
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
    : "/consultant/inquiries?bucket=ALL";
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
  afterEach(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    clearRecentConsultantInquiryIds(CONSULTANT_USER.id);
    remoteMocks.getDashboard.mockReset();
    remoteMocks.getDashboard.mockResolvedValue(REMOTE_DASHBOARD_DATA);
    remoteMocks.getInquiryDetail.mockReset();
    remoteMocks.getInquiryDetail.mockResolvedValue({
      correlationId: "corr-detail",
      data: DETAIL,
    });
    remoteMocks.listInquiries.mockReset();
    remoteMocks.listInquiries.mockImplementation((query) => {
      const isOverview = isDashboardOverviewQuery(query);
      return Promise.resolve({
        correlationId: isOverview ? "corr-overview" : "corr-list",
        data: isOverview ? DASHBOARD_OVERVIEW_LIST : LIST,
      });
    });
    remoteMocks.listUnassignedConsultations.mockReset();
    remoteMocks.listUnassignedConsultations.mockResolvedValue({
      correlationId: "corr-unassigned",
      data: {
        items: [],
        pageInfo: { page: 1, size: 3, total: 0 },
      },
    });
    remoteMocks.requestApi.mockReset();
    remoteMocks.requestApi.mockResolvedValue({
      success: true,
      data: {
        message: "상담을 가져왔습니다.",
        inquiry_id: CLAIM_INQUIRY_ID,
        status: "CONSULTATION_REQUIRED",
        state_version: 4,
        allowed_actions: [],
        idempotent_replay: false,
        resource: null,
      },
      error: null,
      metadata: { correlation_id: "corr-claim" },
    });
  });

  it("문의 목록 overview 집계로 업무 요약·사이드바 숫자를 통일하고 Dashboard 부가 기능은 유지한다", async () => {
    const user = userEvent.setup();
    remoteMocks.getDashboard.mockResolvedValue({
      ...REMOTE_DASHBOARD_DATA,
      summary: { total: 0, new: 0, inProgress: 0, completed: 0 },
    });
    renderPage("dashboard");

    expect(
      await screen.findByRole("heading", {
        name: "Remote 상담원님 반갑습니다!",
      }),
    ).toBeVisible();
    expect(
      await screen.findByRole("button", { name: "전체 문의 수11" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "새 문의3" })).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "처리 중인 문의5" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "처리 완료된 문의3" }),
    ).toBeEnabled();
    expect(screen.getByRole("tab", { name: "전체 문의11" })).toBeVisible();
    expect(
      screen.queryByRole("tab", { name: "새 문의3" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "처리 중인 문의5" })).toBeVisible();
    expect(
      screen.getByRole("tab", { name: "처리 완료된 문의3" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", {
        name: /누수 긴급 점검 요청.*다시 열기/,
      }),
    ).toBeVisible();
    expect(screen.getByText("Backend에서 받은 상담사 공지")).toBeVisible();

    const contactSearch = screen.getByRole("searchbox", {
      name: "직원 연락처 검색",
    });
    await user.type(contactSearch, "원격 상담사");
    expect(screen.getByRole("cell", { name: "원격 상담사" })).toBeVisible();

    await user.clear(contactSearch);
    await user.click(
      screen.getByRole("button", { name: /방문기사 연락처/ }),
    );
    expect(screen.getByRole("cell", { name: "원격 방문기사" })).toBeVisible();
    expect(remoteMocks.getDashboard).toHaveBeenCalledTimes(1);
    expect(
      remoteMocks.listInquiries.mock.calls.filter(([query]) =>
        isDashboardOverviewQuery(query),
      ),
    ).toHaveLength(1);
  });

  it("Dashboard 응답 대기 중에도 문의 목록 overview가 성공하면 집계 숫자를 활성 표시한다", async () => {
    remoteMocks.getDashboard.mockReturnValue(new Promise(() => undefined));

    renderPage("dashboard");

    expect(
      await screen.findByRole("button", { name: "전체 문의 수11" }),
    ).toBeEnabled();
    expect(screen.getByRole("tab", { name: "전체 문의11" })).toBeVisible();
    expect(
      screen.getByText("대시보드 공지를 불러오고 있습니다."),
    ).toBeVisible();
    expect(
      screen.getByText("직원 연락처를 불러오고 있습니다."),
    ).toBeVisible();
    expect(
      screen.queryByText("Backend에서 받은 상담사 공지"),
    ).not.toBeInTheDocument();
  });

  it("Dashboard Runtime 오류에서는 Mock을 섞지 않고 재시도로 원격 데이터를 복구한다", async () => {
    const user = userEvent.setup();
    remoteMocks.getDashboard
      .mockRejectedValueOnce(new Error("backend unavailable"))
      .mockResolvedValueOnce(REMOTE_DASHBOARD_DATA);

    renderPage("dashboard");

    expect(
      await screen.findByText("대시보드 공지를 불러오지 못했습니다."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "전체 문의 수11" }),
    ).toBeEnabled();
    expect(screen.getByRole("tab", { name: "전체 문의11" })).toBeVisible();
    expect(
      screen.queryByText("긴급 문의 응대 절차 안내"),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getAllByRole("button", { name: "다시 시도" })[0],
    );

    expect(
      await screen.findByText("Backend에서 받은 상담사 공지"),
    ).toBeVisible();
    expect(remoteMocks.getDashboard).toHaveBeenCalledTimes(2);
  });

  it("업무 빠른 필터를 변경해도 전체 overview 집계와 고정 query를 유지한다", async () => {
    renderPage("dashboard");

    expect(
      await screen.findByRole("button", { name: "전체 문의 수11" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "새 문의3" })).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "처리 중인 문의5" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "처리 완료된 문의3" }),
    ).toBeEnabled();

    fireEvent.click(
      screen.getByRole("button", {
        name: "처리 중인 문의",
        hidden: true,
      }),
    );

    await waitFor(() =>
      expect(remoteMocks.listInquiries).toHaveBeenCalledWith(
        expect.objectContaining({
          status: expect.arrayContaining([
            "CONSULTATION_IN_PROGRESS",
            "VISIT_SCHEDULING",
            "COMPLETION_PENDING",
          ]),
          page: 1,
          size: 30,
        }),
      ),
    );
    expect(screen.getByRole("button", { name: "전체 문의 수11" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "새 문의3" })).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "처리 중인 문의5" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "처리 완료된 문의3" }),
    ).toBeEnabled();

    const overviewCalls = remoteMocks.listInquiries.mock.calls.filter(
      ([query]) => isDashboardOverviewQuery(query),
    );
    expect(overviewCalls).toHaveLength(1);
    expect(overviewCalls[0]?.[0]).toEqual({
      status: [
        "CONSULTATION_REQUIRED",
        "REOPENED",
        "DRAFT",
        "QUESTIONNAIRE_IN_PROGRESS",
        "AI_GUIDANCE",
        "CONSULTATION_IN_PROGRESS",
        "VISIT_REVIEW_PENDING",
        "VISIT_SCHEDULING",
        "VISIT_SCHEDULED",
        "COMPLETION_PENDING",
        "REVISIT_REQUIRED",
        "RESOLVED",
        "CANCELLED",
      ],
      page: 1,
      size: 100,
    });
  });

  it("Dashboard API 403은 일반 오류가 아닌 상담사 권한 안내로 구분한다", async () => {
    remoteMocks.getDashboard.mockRejectedValue(
      new ApiClientError({
        kind: "FORBIDDEN",
        status: 403,
        code: "FORBIDDEN",
        message: "forbidden",
      }),
    );

    renderPage("dashboard");

    expect(
      await screen.findByText("대시보드 공지를 볼 권한이 없습니다."),
    ).toBeVisible();
    expect(
      screen.getByText("직원 연락처를 볼 권한이 없습니다."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "다시 시도" }),
    ).not.toBeInTheDocument();
  });

  it("Dashboard API 401은 로그인 만료 안내로 구분한다", async () => {
    remoteMocks.getDashboard.mockRejectedValue(
      new ApiClientError({
        kind: "UNAUTHORIZED",
        status: 401,
        code: "UNAUTHORIZED",
        message: "unauthorized",
      }),
    );

    renderPage("dashboard");

    expect(
      await screen.findByText(
        "로그인이 만료되어 공지를 불러올 수 없습니다.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        "로그인이 만료되어 직원 연락처를 불러올 수 없습니다.",
      ),
    ).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: "로그인 화면으로" }),
    ).toHaveLength(2);
  });

  it("Dashboard API 500은 Backend 서버 오류 안내로 구분한다", async () => {
    remoteMocks.getDashboard.mockRejectedValue(
      new ApiClientError({
        kind: "SERVER_ERROR",
        status: 500,
        code: "INTERNAL_SERVER_ERROR",
        message: "server error",
      }),
    );

    renderPage("dashboard");

    expect(
      await screen.findByText(
        "대시보드 공지 서버에 일시적인 오류가 발생했습니다.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText("직원 연락처 서버에 일시적인 오류가 발생했습니다."),
    ).toBeVisible();
    expect(
      screen.getAllByRole("button", { name: "다시 시도" }),
    ).toHaveLength(2);
  });

  it("미배정 상담을 가져오면 내 목록을 갱신하고 그 문의 상세를 연다", async () => {
    const user = userEvent.setup();
    remoteMocks.listUnassignedConsultations.mockResolvedValue({
      correlationId: "corr-unassigned",
      data: {
        items: [
          {
            inquiryId: CLAIM_INQUIRY_ID,
            inquiryCode: "SYN-INQ-0102",
            status: "CONSULTATION_REQUIRED",
            stateVersion: 3,
            riskLevel: "caution",
            priority: "HIGH",
            symptomSummary: "미배정 누수 상담",
            customerDisplayNameMasked: "합성 고객 02",
            productModel: "WPUJAC104DWH",
            currentAssigneeType: "NONE",
            receivedAt: "2026-08-24T09:00:00+09:00",
            updatedAt: "2026-08-24T09:01:00+09:00",
            waitingSeconds: 600,
            allowedActions: [
              {
                code: "CLAIM_CONSULTATION",
                label: "상담 가져오기",
                operationId: "claimConsultation",
                style: "PRIMARY",
                requiresConfirmation: false,
                confirmationMessage: null,
              },
            ],
          },
        ],
        pageInfo: { page: 1, size: 3, total: 1 },
      },
    });
    remoteMocks.getInquiryDetail.mockResolvedValue({
      correlationId: "corr-claimed-detail",
      data: {
        ...DETAIL,
        inquiryId: CLAIM_INQUIRY_ID,
        inquiryCode: "SYN-INQ-0102",
      },
    });

    renderPage("list");
    await user.click(
      await screen.findByRole("button", {
        name: "합성 고객 02 미배정 누수 상담 상담 시작",
      }),
    );

    await waitFor(() =>
      expect(remoteMocks.requestApi).toHaveBeenCalledWith(
        `/inquiries/${CLAIM_INQUIRY_ID}/claim-consultation`,
        expect.objectContaining({
          method: "POST",
          body: { state_version: 3 },
          requestContext: expect.objectContaining({
            idempotencyKey: expect.any(String),
            correlationId: expect.any(String),
          }),
        }),
      ),
    );
    await waitFor(() =>
      expect(remoteMocks.listInquiries.mock.calls.length).toBeGreaterThanOrEqual(
        4,
      ),
    );
    expect(remoteMocks.getInquiryDetail).toHaveBeenCalledWith(CLAIM_INQUIRY_ID);
    expect(await screen.findByRole("dialog")).toBeVisible();
  });

  it("WPUJAC104DWH 새 합성 문의를 가져와 상담 시작·저장·요약 확정·완료까지 이어간다", async () => {
    const user = userEvent.setup();
    type WorkflowAction = ConsultantInquiryDetailViewModel["workflow"]["allowedActions"][number];
    type RuntimeStatus =
      | "CONSULTATION_REQUIRED"
      | "CONSULTATION_IN_PROGRESS"
      | "COMPLETION_PENDING";
    const makeAction = (
      code: string,
      label: string,
      operationId: string,
      requiresConfirmation = false,
    ): WorkflowAction => ({
      code,
      label,
      operationId,
      style: "PRIMARY",
      requiresConfirmation,
      confirmationMessage: requiresConfirmation
        ? `${label}하시겠습니까?`
        : null,
    });
    const startAction = makeAction(
      "START_CONSULTATION",
      "상담 시작",
      "startConsultation",
    );
    const saveAction = makeAction(
      "UPDATE_CONSULTATION_SUMMARY",
      "상담 내용 저장",
      "updateConsultationSummary",
    );
    const confirmAction = makeAction(
      "CONFIRM_CONSULTATION_SUMMARY",
      "요약 확정",
      "confirmConsultationSummary",
      true,
    );
    const completeAction = makeAction(
      "CONSULTATION_COMPLETED",
      "상담 완료",
      "completeConsultation",
      true,
    );
    const toDto = (action: WorkflowAction) => ({
      code: action.code,
      label: action.label,
      operation_id: action.operationId,
      style: action.style,
      requires_confirmation: action.requiresConfirmation,
      confirmation_message: action.confirmationMessage,
    });
    let claimed = false;
    let currentStatus: RuntimeStatus = "CONSULTATION_REQUIRED";
    let currentStateVersion = 3;
    let currentActions: readonly WorkflowAction[] = [startAction];
    let savedNote: string | null = null;
    let savedGuidance: string | null = null;
    let savedSummary: string | null = null;
    let confirmedSummary: string | null = null;

    const unassignedItem = {
      inquiryId: CLAIM_INQUIRY_ID,
      inquiryCode: "SYN-INQ-WPUJAC104DWH-NEW",
      status: "CONSULTATION_REQUIRED" as const,
      stateVersion: 3,
      riskLevel: "caution" as const,
      priority: "HIGH" as const,
      symptomSummary: "출수량이 줄어든 새 합성 문의",
      customerDisplayNameMasked: "합성 고객 104",
      productModel: "WPUJAC104DWH",
      currentAssigneeType: "NONE" as const,
      receivedAt: "2026-08-24T10:00:00+09:00",
      updatedAt: "2026-08-24T10:01:00+09:00",
      waitingSeconds: 60,
      allowedActions: [
        makeAction(
          "CLAIM_CONSULTATION",
          "상담 가져오기",
          "claimConsultation",
        ),
      ],
    };
    const currentDetail = (): ConsultantInquiryDetailViewModel => ({
      ...DETAIL,
      inquiryId: CLAIM_INQUIRY_ID,
      inquiryCode: unassignedItem.inquiryCode,
      status: currentStatus,
      stateVersion: currentStateVersion,
      productAndCare: {
        productModel: "WPUJAC104DWH",
        productModelName: "아이콘 얼음정수기",
        subscriptionStatus: "ACTIVE",
        managementType: "VISIT_CARE",
        recentCareDate: null,
      },
      symptomAndQuestionnaire: {
        symptomSummary: unassignedItem.symptomSummary,
        answers: [],
      },
      consultation: currentStatus === "CONSULTATION_REQUIRED"
        ? null
        : {
            consultationId: "consultation-wpujac104dwh",
            resultCode: currentStatus === "COMPLETION_PENDING"
              ? "COMPLETED_NO_VISIT"
              : "PENDING",
            summary: {
              aiDraftSummary: null,
              editedSummary: savedSummary,
              confirmedSummary,
              confirmedAt: confirmedSummary
                ? "2026-08-24T10:10:00+09:00"
                : null,
            },
            consultationNote: savedNote,
            additionalCheck: null,
            customerGuidance: savedGuidance,
            usageGuidanceStatus: "NORMAL",
          },
      workflow: {
        status: currentStatus,
        stateVersion: currentStateVersion,
        allowedActions: currentActions,
      },
    });
    const transitionResponse = () => ({
      success: true as const,
      data: {
        message: "Backend 상담 단계 처리 완료",
        inquiry_id: CLAIM_INQUIRY_ID,
        status: currentStatus,
        state_version: currentStateVersion,
        allowed_actions: currentActions.map(toDto),
        idempotent_replay: false,
        resource: null,
      },
      error: null,
      metadata: { correlation_id: `corr-${currentStateVersion}` },
    });

    remoteMocks.listUnassignedConsultations.mockImplementation(async () => ({
      correlationId: "corr-unassigned-wpujac104dwh",
      data: {
        items: claimed ? [] : [unassignedItem],
        pageInfo: { page: 1, size: 3, total: claimed ? 0 : 1 },
      },
    }));
    remoteMocks.listInquiries.mockImplementation(async () => ({
      correlationId: "corr-list-wpujac104dwh",
      data: claimed
        ? {
            items: [
              {
                ...LIST.items[0],
                inquiryId: CLAIM_INQUIRY_ID,
                inquiryCode: unassignedItem.inquiryCode,
                status: currentStatus,
                stateVersion: currentStateVersion,
                symptomSummary: unassignedItem.symptomSummary,
                productModel: "WPUJAC104DWH",
                allowedActions: currentActions,
              },
            ],
            pageInfo: { page: 1, size: 10, total: 1 },
            statusCounts: { [currentStatus]: 1 },
          }
        : LIST,
    }));
    remoteMocks.getInquiryDetail.mockImplementation(async (inquiryId) => ({
      correlationId: `corr-detail-${currentStateVersion}`,
      data: inquiryId === CLAIM_INQUIRY_ID ? currentDetail() : DETAIL,
    }));
    remoteMocks.requestApi.mockImplementation(async (path) => {
      if (path.endsWith("/claim-consultation")) {
        claimed = true;
        currentStateVersion = 4;
        currentStatus = "CONSULTATION_REQUIRED";
        currentActions = [startAction];
        return transitionResponse();
      }
      if (path.endsWith("/start-consultation")) {
        currentStateVersion = 5;
        currentStatus = "CONSULTATION_IN_PROGRESS";
        currentActions = [saveAction];
        return transitionResponse();
      }
      if (path.endsWith("/consultation-summary")) {
        currentStateVersion = 6;
        currentStatus = "CONSULTATION_IN_PROGRESS";
        currentActions = [saveAction, confirmAction];
        savedNote = "고객과 출수 상태를 확인했습니다.";
        savedGuidance = "필터 상태를 확인하고 정상 사용을 안내했습니다.";
        savedSummary = "출수량 저하 상담 요약";
        return transitionResponse();
      }
      if (path.endsWith("/consultation-summary/confirm")) {
        currentStateVersion = 7;
        currentStatus = "CONSULTATION_IN_PROGRESS";
        currentActions = [saveAction, completeAction];
        confirmedSummary = savedSummary;
        return transitionResponse();
      }
      if (path.endsWith("/complete-consultation")) {
        currentStateVersion = 8;
        currentStatus = "COMPLETION_PENDING";
        currentActions = [];
        return transitionResponse();
      }
      throw new Error(`예상하지 않은 API 경로: ${path}`);
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage("list");
    await user.click(
      await screen.findByRole("button", {
        name: `${unassignedItem.customerDisplayNameMasked} ${unassignedItem.symptomSummary} 상담 시작`,
      }),
    );

    expect(
      await screen.findByText("현재 기다리는 미배정 상담이 없습니다."),
    ).toBeVisible();
    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(
      screen.getAllByText(
        "WPUJAC104DWH · 초소형 직수 냉온 정수기",
      ),
    ).not.toHaveLength(0);

    await user.click(
      screen.getByRole("button", {
        name: "상담 3단계: 상담 진행",
      }),
    );
    await user.click(
      await screen.findByRole("button", { name: "상담 시작" }),
    );
    await user.type(
      await screen.findByLabelText("상담 기록"),
      "고객과 출수 상태를 확인하고 필터 상태 및 정상 사용 방법을 안내했습니다.",
    );
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.type(
      screen.getByLabelText("상담 내용 수정본"),
      "출수량 저하 상담 요약",
    );
    await user.selectOptions(screen.getByLabelText("방문 필요 여부"), "NOT_REQUIRED");

    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));
    await user.click(await screen.findByRole("button", { name: "상담 내용 확정" }));
    await user.click(await screen.findByRole("button", { name: "상담 완료" }));

    await waitFor(() =>
      expect(remoteMocks.requestApi).toHaveBeenCalledWith(
        expect.stringContaining("complete-consultation"),
        expect.objectContaining({
          body: expect.objectContaining({ state_version: 7 }),
        }),
      ),
    );
    expect(
      await screen.findByText("현재 진행할 상담 작업이 없습니다."),
    ).toBeVisible();
    expect(screen.getByText("최종 완료 대기")).toBeVisible();

    const expectedCalls = [
      ["claim-consultation", 3],
      ["start-consultation", 4],
      ["consultation-summary", 5],
      ["consultation-summary/confirm", 6],
      ["complete-consultation", 7],
    ] as const;
    expectedCalls.forEach(([pathSuffix, stateVersion]) => {
      expect(remoteMocks.requestApi).toHaveBeenCalledWith(
        expect.stringContaining(pathSuffix),
        expect.objectContaining({
          body: expect.objectContaining({ state_version: stateVersion }),
          requestContext: expect.objectContaining({
            idempotencyKey: expect.any(String),
            correlationId: expect.any(String),
          }),
        }),
      );
    });
    expect(remoteMocks.getInquiryDetail.mock.calls.length).toBeGreaterThanOrEqual(5);
  });

  it.each([
    ["dashboard", "/consultant/dashboard"],
    ["list", "/consultant/inquiries?bucket=ALL"],
  ] as const)(
    "%s 문의 클릭은 현재 화면을 유지하고 Remote 첫 패널을 연다",
    async (page, expectedPath) => {
      const user = userEvent.setup();
      renderPage(page);

      await user.click(
        await screen.findByRole("button", {
          name: page === "dashboard"
            ? /누수 긴급 점검 요청.*다시 열기/
            : /SYN-INQ-0101.*상세 열기/,
        }),
      );

      expect(screen.getByLabelText("현재 경로")).toHaveTextContent(expectedPath);
      expect(await screen.findByRole("dialog")).toBeVisible();
      expect(screen.getByLabelText("상담 문의 상세")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "전체 기록 보기" }),
      ).not.toBeInTheDocument();
      ["합성 고객 01", "고객 증상과 답변", "제품·관리 정보"].forEach(
        (heading) =>
        expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument(),
      );
      expect(
        screen.queryByRole("heading", { name: "고객에게 안내할 내용" }),
      ).not.toBeInTheDocument();

      await user.click(
        screen.getByRole("button", {
          name: "상담 2단계: AI 상담 · 이전 상담 기록 확인",
        }),
      );
      expect(
        screen.getByRole("heading", { name: "고객에게 안내할 내용" }),
      ).toBeVisible();

      await user.click(
        screen.getByRole("button", {
          name: "상담 3단계: 상담 진행",
        }),
      );
      expect(screen.getByLabelText("상담 처리 작업")).toBeVisible();
      expect(screen.queryByText("현재 할 일")).not.toBeInTheDocument();
      expect(screen.queryByText(/현재 상태 ·/)).not.toBeInTheDocument();
      expect(screen.getByText("제품 사용 중단")).toBeInTheDocument();
      expect(screen.queryByText("TOTAL_STOP")).not.toBeInTheDocument();
      expect(remoteMocks.getInquiryDetail).toHaveBeenCalledWith(INQUIRY_ID);
    },
  );

  it("Remote 첫 패널은 별도 전체 기록 화면으로 이동하지 않고 현재 목록 경로를 유지한다", async () => {
    const user = userEvent.setup();
    renderPage("list");

    await user.click(
      await screen.findByRole("button", {
        name: /SYN-INQ-0101.*상세 열기/,
      }),
    );

    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(screen.getByLabelText("현재 경로")).toHaveTextContent(
      "/consultant/inquiries?bucket=ALL",
    );
    expect(
      screen.queryByRole("button", { name: "전체 기록 보기" }),
    ).not.toBeInTheDocument();
  });
});
