import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";
import { CONSULTANT_QUEUE_INQUIRIES } from "../fixtures/consultantWorkspaceMock";
import { getCounselorWorkBucket } from "../../src/features/consultation/model/consultantWorkspaceModel";
import {
  clearRecentConsultantInquiryIds,
  readRecentConsultantInquiryIds,
} from "../../src/features/consultation/model/recentConsultantInquiryIds";
import type { CounselorWorkBucket } from "../../src/features/consultation/model/consultantWorkspaceTypes";

const CONSULTANT_USER = {
  id: "STAFF-CONS-TEST",
  displayName: "테스트 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

const TAB_LABELS: Record<CounselorWorkBucket, RegExp> = {
  NEW: /전체 문의/,
  IN_PROGRESS: /처리 중인 문의/,
  COMPLETED: /처리 완료된 문의/,
};

const EXPECTED_BUCKET_COUNTS: Record<CounselorWorkBucket, number> = {
  NEW: 30,
  IN_PROGRESS: 30,
  COMPLETED: 30,
};

function renderPage(path = "/consultant/inquiries") {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

function getSidebarTabs() {
  return within(screen.getByRole("tablist", { name: "상담사 메뉴" }));
}

function getRiskTabs() {
  return within(screen.getByRole("tablist", { name: "문의 유형" }));
}

function getRiskPanel(risk: "all" | "danger" | "caution" | "general") {
  const panel = document.getElementById(`consultant-risk-panel-${risk}`);
  if (!panel) throw new Error(`문의 유형 패널을 찾을 수 없습니다: ${risk}`);
  return within(panel);
}

async function openInquiry(
  user: ReturnType<typeof userEvent.setup>,
  inquiryCode: string,
  bucket: CounselorWorkBucket,
) {
  await user.click(getSidebarTabs().getByRole("tab", { name: TAB_LABELS[bucket] }));
  const inquiry = CONSULTANT_QUEUE_INQUIRIES.find(
    (item) => item.inquiryCode === inquiryCode,
  );
  if (!inquiry) throw new Error(`문의 Mock을 찾을 수 없습니다: ${inquiryCode}`);
  const riskTabName = {
    DANGER: /긴급 문의/,
    CAUTION: /주의 문의/,
    GENERAL: /일반 문의/,
    UNKNOWN: /일반 문의/,
  }[inquiry.riskLevel];
  await user.click(screen.getByRole("tab", { name: riskTabName }));
  if (bucket === "NEW") {
    const search = screen.getByRole("searchbox", { name: "문의 검색" });
    await user.clear(search);
    await user.type(search, inquiryCode);
    await user.click(screen.getByRole("button", { name: "검색" }));
  }
  await user.click(
    screen.getByRole("button", {
      name: new RegExp(`${inquiryCode}.*상세 열기$`),
    }),
  );
}

describe("ConsultantInquiryListPage", () => {
  beforeEach(() => {
    clearRecentConsultantInquiryIds(CONSULTANT_USER.id);
  });

  it("첫 화면은 전체 문의를 포함한 업무 탭과 문의 목록만 보여준다", () => {
    renderPage();
    const sidebarTabs = getSidebarTabs();
    const riskTabs = getRiskTabs();

    const brandLink = screen.getByRole("link", {
      name: "Water Bridge 홈으로 이동",
    });
    expect(brandLink).toHaveTextContent("WaterBridge");
    expect(brandLink.querySelector("img")).toBeNull();
    expect(sidebarTabs.queryByRole("tab", { name: /새 문의/ })).not.toBeInTheDocument();
    expect(sidebarTabs.getByRole("tab", { name: /처리 중인 문의/ })).toBeVisible();
    expect(sidebarTabs.getByRole("tab", { name: /처리 완료된 문의/ })).toBeVisible();
    expect(sidebarTabs.getByRole("tab", { name: /전체 문의90/ })).toBeVisible();
    expect(sidebarTabs.getByRole("tab", { name: "전화 문의 등록" })).toBeVisible();
    expect(sidebarTabs.getByRole("tab", { name: /전체 문의90/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(riskTabs.getByRole("tab", { name: /전체 문의90/ })).toHaveClass(
      "consultant-risk-tab--all",
      "is-active",
    );
    expect(screen.getByRole("searchbox", { name: "문의 검색" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "문의 정렬" })).toHaveValue(
      "UPDATED_DESC",
    );
    expect(screen.getByText("테스트 상담원")).toBeVisible();
    expect(screen.queryByText("2026-001-256")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "로그아웃" })).toBeVisible();
    expect(screen.getByLabelText("상담 문의 목록")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /상담 기록/ })).not.toBeInTheDocument();
  });

  it("모든 문의 행을 제목·상태별 경과 시간·고객명 순서로 5건씩 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();

    const assertRows = (unit: "혼합" | "분" | "시간" | "일") => {
      const inquiryRows = screen.getAllByRole("button", { name: /상세 열기/ });
      expect(inquiryRows).toHaveLength(5);

      inquiryRows.forEach((row) => {
        const [subject, receivedAt, customer] = Array.from(row.children);

        expect(subject).toHaveClass("consultant-list-item__subject");
        expect(
          within(subject as HTMLElement).getByText(
            "WPU-JAC104D · 초소형 직수 냉온 정수기",
          ),
        ).toHaveClass("consultant-list-item__product");
        expect(receivedAt).toHaveClass("consultant-list-item__received-at");
        expect(receivedAt).toHaveAttribute("datetime");
        expect(receivedAt).toHaveAttribute("title");
        expect(receivedAt).toHaveTextContent(
          unit === "혼합"
            ? /^\d+(분|시간|일) 전$/
            : new RegExp(`^\\d+${unit} 전$`),
        );
        expect(customer).toHaveClass("consultant-list-item__customer");
        expect(customer).not.toBeEmptyDOMElement();
      });
    };

    assertRows("혼합");
    await user.click(getSidebarTabs().getByRole("tab", { name: /처리 중인 문의/ }));
    await waitFor(() => assertRows("시간"));
    await user.click(getSidebarTabs().getByRole("tab", { name: /처리 완료된 문의/ }));
    await waitFor(() => assertRows("일"));
  });

  it("문의 검색과 최신순·오래된순 정렬을 제공한다", async () => {
    const user = userEvent.setup();
    renderPage();

    const search = screen.getByRole("searchbox", { name: "문의 검색" });
    const sort = screen.getByRole("combobox", { name: "문의 정렬" });

    await user.type(search, "INQ-20260704-0013");
    expect(search).toHaveValue("INQ-20260704-0013");
    expect(
      screen.queryByRole("button", {
        name: /INQ-20260704-0013.*상세 열기/,
      }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "검색" }));
    expect(
      await screen.findByRole("button", {
        name: /INQ-20260704-0013.*상세 열기/,
      }),
    ).toBeVisible();

    await user.selectOptions(sort, "UPDATED_ASC");
    expect(sort).toHaveValue("UPDATED_ASC");
    expect(screen.getByRole("option", { name: "오래된순" })).toBeInTheDocument();
  });

  it("전체 문의의 위험도별 총합은 90건이며 페이지를 이동해도 유지된다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(getSidebarTabs().getByRole("tab", { name: /전체 문의90/ }));

    const expectStableRiskCounts = () => {
      const riskTabs = getRiskTabs();
      const allTab = riskTabs.getByRole("tab", { name: /전체 문의/ });
      const dangerTab = riskTabs.getByRole("tab", { name: /긴급 문의/ });
      const cautionTab = riskTabs.getByRole("tab", { name: /주의 문의/ });
      const generalTab = riskTabs.getByRole("tab", { name: /일반 문의/ });

      expect(within(allTab).getByText("90")).toBeVisible();
      expect(within(dangerTab).getByText("30")).toBeVisible();
      expect(within(cautionTab).getByText("30")).toBeVisible();
      expect(within(generalTab).getByText("30")).toBeVisible();
      expect(screen.getByText(/총 90건/)).toBeVisible();
    };

    expectStableRiskCounts();
    await user.click(screen.getByRole("button", { name: "다음" }));
    expectStableRiskCounts();
  });

  it("전체 문의 메뉴는 새 문의·처리 중·완료 문의를 모두 보여준다", () => {
    renderPage("/consultant/inquiries?bucket=ALL");

    expect(getSidebarTabs().getByRole("tab", { name: /전체 문의90/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tabpanel", { name: "전체 문의" })).toBeVisible();
    expect(screen.getByText(/총 90건/)).toBeVisible();
  });

  it("미배정 상담 대기 목록은 전체 문의에서만 보여준다", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByLabelText("미배정 상담 대기 목록")).toBeVisible();
    expect(document.getElementById("consultant-queue-panel")).toHaveClass(
      "consultant-queue-panel--with-unassigned",
    );

    await user.click(getSidebarTabs().getByRole("tab", { name: /처리 중인 문의/ }));
    expect(
      screen.queryByLabelText("미배정 상담 대기 목록"),
    ).not.toBeInTheDocument();
    expect(document.getElementById("consultant-queue-panel")).not.toHaveClass(
      "consultant-queue-panel--with-unassigned",
    );

    await user.click(getSidebarTabs().getByRole("tab", { name: /처리 완료된 문의/ }));
    expect(
      screen.queryByLabelText("미배정 상담 대기 목록"),
    ).not.toBeInTheDocument();
    expect(document.getElementById("consultant-queue-panel")).not.toHaveClass(
      "consultant-queue-panel--with-unassigned",
    );
  });

  it("전체·처리 중·처리 완료 탭의 건수는 상담사 문의 상태와 일치한다", () => {
    renderPage();

    (["IN_PROGRESS", "COMPLETED"] as const).forEach((bucket) => {
      const count = CONSULTANT_QUEUE_INQUIRIES.filter(
        (inquiry) => getCounselorWorkBucket(inquiry.status) === bucket,
      ).length;
      expect(count).toBe(EXPECTED_BUCKET_COUNTS[bucket]);
      expect(screen.getByRole("tab", { name: TAB_LABELS[bucket] })).toHaveTextContent(
        String(count),
      );
    });
    expect(getSidebarTabs().getByRole("tab", { name: /전체 문의90/ })).toBeVisible();
    expect(screen.queryByRole("tab", { name: /새 문의/ })).not.toBeInTheDocument();
  });

  it("문의 목록을 눌러야 상세 상담 화면이 열리고 닫을 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260707-0024", "NEW");

    const openedInquiry = CONSULTANT_QUEUE_INQUIRIES.find(
      (inquiry) => inquiry.inquiryCode === "INQ-20260707-0024",
    );
    expect(openedInquiry).toBeDefined();
    expect(readRecentConsultantInquiryIds(CONSULTANT_USER.id)).toEqual([
      openedInquiry!.inquiryId,
    ]);

    expect(screen.getByRole("dialog", { name: /IoT 기능 지원 문의/ })).toBeVisible();
    expect(screen.getByRole("button", { name: "상담 시작" })).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "문의 상세 닫기" })[1]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("처리 중인 문의에서 상담 기록과 기사 배정 판단 기능을 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260704-0013", "IN_PROGRESS");

    expect(screen.getByRole("heading", { name: "제품 누수" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /상담 기록/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "방문 필요" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "방문 불필요" })).toBeInTheDocument();
  });

  it("새 문의에서 상담 시작을 누르면 처리 중 탭으로 이동하고 상담 Form을 연다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260707-0024", "NEW");
    await user.click(screen.getByRole("button", { name: "상담 시작" }));

    expect(await screen.findByRole("textbox", { name: /상담 기록/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /처리 중인 문의/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.queryByRole("button", { name: "상담 시작" })).not.toBeInTheDocument();
  });

  it("기사 선택 API가 없으면 로컬 배정 대신 비활성 안내를 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260704-0013", "IN_PROGRESS");
    await user.type(
      screen.getByRole("textbox", { name: /상담 기록/ }),
      "누수 위치와 안전조치를 확인했고 현장 점검이 필요합니다.",
    );
    await user.click(screen.getByRole("radio", { name: "방문 필요" }));
    fireEvent.change(screen.getByLabelText("방문 희망 일시"), {
      target: { value: "2026-08-01" },
    });
    await user.type(
      screen.getByRole("textbox", { name: "기사 전달 메모" }),
      "누수 연결부를 우선 점검해 주세요.",
    );
    await user.click(screen.getByLabelText(/방문 주소 확인/));
    await user.click(screen.getByRole("button", { name: "상담 처리 완료" }));

    const scheduler = await screen.findByRole("region", {
      name: "기사 배정 및 일정 조율",
    });
    expect(
      within(scheduler).getByRole("heading", {
        name: "기사 선택·배정 API 미지원",
      }),
    ).toBeVisible();
    expect(
      within(scheduler).queryByRole("combobox", { name: "방문기사" }),
    ).not.toBeInTheDocument();
    expect(
      within(scheduler).getByRole("button", {
        name: "기사 선택·배정 비활성화",
      }),
    ).toBeDisabled();
    expect(within(scheduler).queryByRole("status")).not.toBeInTheDocument();
  });

  it("처리 완료 탭에서는 완료된 문의 이력을 확인한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260702-0005", "COMPLETED");

    expect(screen.getByRole("dialog")).toBeVisible();
    expect(
      within(screen.getByRole("dialog")).getByLabelText("상태: 처리 완료"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "상담 시작" })).not.toBeInTheDocument();
  });

  it("문의 상세 안에서 상담을 처리하고 별도 전체 기록 버튼은 표시하지 않는다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260704-0013", "IN_PROGRESS");

    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByRole("textbox", { name: /상담 기록/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "전체 기록 보기" }),
    ).not.toBeInTheDocument();
  });

  it("전체·긴급·주의·일반 탭을 전환하면 한 페이지에 문의 5건만 보여준다", async () => {
    const user = userEvent.setup();
    renderPage();

    (["NEW", "IN_PROGRESS", "COMPLETED"] as const).forEach((bucket) => {
      const bucketItems = CONSULTANT_QUEUE_INQUIRIES.filter(
        (item) => getCounselorWorkBucket(item.status) === bucket,
      );
      expect(
        bucketItems.filter((item) => item.riskLevel === "DANGER"),
      ).toHaveLength(10);
      expect(
        bucketItems.filter((item) => item.riskLevel === "CAUTION"),
      ).toHaveLength(10);
      expect(
        bucketItems.filter((item) => item.riskLevel === "GENERAL"),
      ).toHaveLength(10);
    });

    const riskTabs = getRiskTabs();
    const allTab = riskTabs.getByRole("tab", { name: /전체 문의/ });
    const dangerTab = riskTabs.getByRole("tab", { name: /긴급 문의/ });
    const cautionTab = riskTabs.getByRole("tab", { name: /주의 문의/ });
    const generalTab = riskTabs.getByRole("tab", { name: /일반 문의/ });

    expect(allTab).toHaveAttribute("aria-selected", "true");
    expect(allTab).toHaveClass("consultant-risk-tab--all");
    expect(dangerTab).toHaveClass("consultant-risk-tab--danger");
    expect(cautionTab).toHaveClass("consultant-risk-tab--caution");
    expect(generalTab).toHaveClass("consultant-risk-tab--general");
    expect(within(allTab).getByText("90")).toHaveClass(
      "consultant-risk-tab__count",
    );
    expect(within(dangerTab).getByText("30")).toHaveClass(
      "consultant-risk-tab__count",
    );
    expect(within(cautionTab).getByText("30")).toHaveClass(
      "consultant-risk-tab__count",
    );
    expect(within(generalTab).getByText("30")).toHaveClass(
      "consultant-risk-tab__count",
    );
    expect(
      getRiskPanel("all").getAllByRole(
        "button",
        { name: /상세 열기/ },
      ),
    ).toHaveLength(5);
    expect(
      screen.queryByRole("button", { name: "긴급 문의 상태 필터" }),
    ).not.toBeInTheDocument();
    expect(
      document
        .getElementById("consultant-risk-panel-all")
        ?.querySelector(".consultant-risk-section__count"),
    ).toBeNull();

    allTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(dangerTab).toHaveAttribute("aria-selected", "true");
    await waitFor(() =>
      expect(getRiskPanel("danger").getAllByRole("button", { name: /상세 열기/ })).toHaveLength(5),
    );

    await user.click(cautionTab);
    expect(cautionTab).toHaveAttribute("aria-selected", "true");
    expect(
      await getRiskPanel("caution").findAllByRole(
        "button",
        { name: /상세 열기/ },
      ),
    ).toHaveLength(5);

    await user.click(generalTab);
    expect(generalTab).toHaveAttribute("aria-selected", "true");
    expect(
      await getRiskPanel("general").findAllByRole(
        "button",
        { name: /상세 열기/ },
      ),
    ).toHaveLength(5);
  });

  it("API가 없는 대·중·소 분류는 숨기고 검색과 정렬은 유지한다", () => {
    renderPage();

    expect(
      screen.queryByRole("combobox", { name: "문의 대분류" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "문의 중분류" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: "문의 소분류" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "문의 검색" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "문의 정렬" })).toBeVisible();
  });

  it.each([
    ["loading", "상담 문의 목록을 불러오고 있습니다."],
    ["error", "네트워크 오류가 발생했습니다."],
    ["forbidden", "상담 문의 목록을 볼 권한이 없습니다."],
  ])("목록 %s 상태를 구분해 안내한다", async (state, message) => {
    renderPage(`/consultant/inquiries?mockState=${state}`);

    expect(await screen.findByText(message)).toBeInTheDocument();
    if (state === "error") {
      expect(
        screen.getByText("네트워크 연결을 확인한 뒤 다시 시도해 주세요."),
      ).toBeVisible();
      expect(screen.queryByText("문의가 없습니다.")).not.toBeInTheDocument();
    }
  });

  it("문의가 0건이어도 탭·검색·정렬·페이지 레이아웃을 유지한다", async () => {
    renderPage("/consultant/inquiries?mockState=empty");

    expect(await screen.findByText("문의가 없습니다.")).toBeVisible();
    expect(getRiskTabs().getByRole("tab", { name: /전체 문의0/ })).toBeVisible();
    expect(screen.getByRole("searchbox", { name: "문의 검색" })).toBeVisible();
    expect(screen.getByRole("combobox", { name: "문의 정렬" })).toBeVisible();
    expect(screen.getByRole("navigation", { name: "문의 목록 페이지" })).toHaveTextContent(
      "총 0건 · 1/1페이지",
    );
  });

  it("상담 완료 후 자동 진행을 사용하면 다음 처리 문의를 연다", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();

    await openInquiry(user, "INQ-20260704-0013", "IN_PROGRESS");
    await user.type(
      screen.getByRole("textbox", { name: /상담 기록/ }),
      "안전 안내 후 누수가 멈춘 것을 확인했습니다.",
    );
    await user.click(screen.getByRole("radio", { name: "방문 불필요" }));
    await user.type(
      screen.getByRole("textbox", { name: "상담 결과 (필수)" }),
      "고객의 증상 해결을 확인했습니다.",
    );
    await user.click(screen.getByLabelText("AI 요약을 확인했습니다"));
    await user.click(screen.getByRole("button", { name: "상담 처리 완료" }));

    expect(await screen.findByRole("dialog")).toBeVisible();
  });
});
