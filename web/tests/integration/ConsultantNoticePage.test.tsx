import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";
import * as consultantNoticeApi from "../../src/features/notice/api/consultantNoticeApi";
import { MOCK_CONSULTANT_NOTICE_PAGE_DATA } from "../../src/features/notice/model/consultantNoticeMock";

const CONSULTANT_USER = {
  id: "STAFF-CONS-NOTICE-TEST",
  displayName: "테스트 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

function renderPage(path = "/consultant/notices") {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("ConsultantNoticePage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("상담사 메뉴에서 공지사항 페이지를 열고 전체 공지를 보여준다", async () => {
    const user = userEvent.setup();
    renderPage("/consultant/dashboard");

    await user.click(screen.getByRole("tab", { name: "공지사항" }));

    const panel = await screen.findByRole("tabpanel", { name: "공지사항" });
    expect(
      within(panel).queryByText("상담 업무에 필요한 안내와 일정을 확인해 주세요."),
    ).not.toBeInTheDocument();
    expect(within(panel).queryByText("6건")).not.toBeInTheDocument();
    expect(
      within(panel).queryByText(
        "누수·감전·이상 냄새 등 안전 위험 문의는 고객에게 제품 사용 중지를 먼저 안내하고 긴급 상담 절차로 연결해 주세요.",
      ),
    ).not.toBeInTheDocument();
    expect(within(panel).getAllByRole("listitem")).toHaveLength(6);
    const pagination = within(panel).getByRole("navigation", {
      name: "공지사항 목록 페이지",
    });
    expect(pagination).toHaveTextContent("이전1/1다음");
    expect(pagination).not.toHaveTextContent("총 6건");
    expect(pagination).not.toHaveTextContent("페이지");
    expect(within(panel).getByLabelText("공지 번호 6")).toBeVisible();
    expect(within(panel).getByLabelText("공지 번호 2")).toBeVisible();
    expect(within(panel).getByLabelText("공지 번호 1")).toBeVisible();
    expect(within(panel).getByRole("button", { name: "다음" })).toBeDisabled();

    const firstNoticeRow = within(panel).getByRole("button", {
      name: /긴급 문의 응대 절차 안내/,
    });
    const [number, category, title, byline] = Array.from(
      firstNoticeRow.children,
    );
    expect(number).toHaveClass("consultant-notice-list__number");
    expect(number).toHaveTextContent(/^6$/);
    expect(number.children).toHaveLength(0);
    expect(category).toHaveClass("consultant-notice-list__category");
    expect(category).toHaveTextContent("긴급");
    expect(title).toHaveClass("consultant-notice-list__title");
    expect(title).toHaveTextContent("긴급 문의 응대 절차 안내");
    expect(byline).toHaveClass("consultant-notice-list__byline");
    const [department, divider, date] = Array.from(byline.children);
    expect(department).toHaveClass("consultant-notice-list__department");
    expect(department).toHaveTextContent("고객케어팀");
    expect(divider).toHaveClass("consultant-notice-list__divider");
    expect(divider).toHaveAttribute("aria-hidden", "true");
    expect(divider).toHaveTextContent("|");
    expect(date).toHaveClass("consultant-notice-list__date");
    expect(date).toHaveTextContent("2026.08.18");
    expect(date).toHaveAttribute("datetime", "2026-08-18");
    expect(screen.getByRole("tab", { name: "공지사항" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "직원 연락처" })).toBeVisible();
    expect(panel).toHaveClass("consultant-directory-panel");
    expect(panel.closest(".consultant-directory-app")).not.toBeNull();
    expect(
      within(panel).queryByText(/안전 위험 문의는 일반 문의보다 먼저 처리합니다/),
    ).not.toBeInTheDocument();
    expect(
      within(panel).queryByText(/임의 분해나 수리를 요구하지 마세요/),
    ).not.toBeInTheDocument();
  });

  it("분류와 검색어로 필요한 공지만 찾을 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();

    const panel = await screen.findByRole("tabpanel", { name: "공지사항" });
    await user.click(within(panel).getByRole("button", { name: "시스템" }));
    expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
    expect(within(panel).getByText("상담 시스템 정기 점검 안내")).toBeVisible();
    expect(within(panel).getByLabelText("공지 번호 4")).toBeVisible();

    await user.click(within(panel).getByRole("button", { name: "전체" }));
    await user.type(within(panel).getByRole("searchbox"), "건강검진");
    expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
    expect(within(panel).getByText("임직원 건강검진 신청 안내")).toBeVisible();
  });

  it("공지 Dashboard 집계가 0이어도 문의 목록 집계로 사이드바 숫자를 표시한다", async () => {
    vi.spyOn(consultantNoticeApi, "getConsultantNoticePageData").mockResolvedValue({
      ...MOCK_CONSULTANT_NOTICE_PAGE_DATA,
      summary: { total: 0, new: 0, inProgress: 0, completed: 0 },
    });

    renderPage();

    expect(
      await screen.findByRole("tab", { name: "전체 문의90" }),
    ).toBeVisible();
    expect(screen.queryByRole("tab", { name: "새 문의30" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "처리 중인 문의30" }),
    ).toBeVisible();
    expect(
      screen.getByRole("tab", { name: "처리 완료된 문의30" }),
    ).toBeVisible();
  });

  it("noticeId가 있으면 해당 공지 상세를 보여주고 목록으로 돌아간다", async () => {
    const user = userEvent.setup();
    renderPage("/consultant/notices?noticeId=notice-emergency-001");

    const panel = await screen.findByRole("tabpanel", { name: "공지사항 상세" });
    expect(
      within(panel).queryByText("선택한 공지의 내용을 자세히 확인해 주세요."),
    ).not.toBeInTheDocument();
    expect(
      within(panel).getByRole("heading", {
        level: 2,
        name: "긴급 문의 응대 절차 안내",
      }),
    ).toBeVisible();
    expect(within(panel).getByText("SYN-WEB-DASH-NOTICE-001")).toBeVisible();
    expect(
      within(panel).getByText(/제품 사용을 즉시 중지/),
    ).toBeVisible();
    expect(
      within(panel).getByText(/임의 분해나 수리를 요구하지 마세요/),
    ).toBeVisible();

    await user.click(
      within(panel).getByRole("button", { name: /공지사항 목록으로/ }),
    );

    const listPanel = await screen.findByRole("tabpanel", { name: "공지사항" });
    expect(within(listPanel).getAllByRole("listitem")).toHaveLength(6);
  });

  it("공지 목록을 누르면 상세 화면으로 이동하고 한 페이지에 10건씩 표시한다", async () => {
    const user = userEvent.setup();
    const baseNotice = MOCK_CONSULTANT_NOTICE_PAGE_DATA.notices[0]!;
    const notices = Array.from({ length: 11 }, (_, index) => ({
      ...baseNotice,
      noticeId: `notice-page-${index + 1}`,
      noticeCode: `NOTICE-PAGE-${index + 1}`,
      title: `페이지 공지 ${index + 1}`,
      publishedOn: `2026-08-${String(index + 1).padStart(2, "0")}`,
    }));
    vi.spyOn(consultantNoticeApi, "getConsultantNoticePageData").mockResolvedValue({
      ...MOCK_CONSULTANT_NOTICE_PAGE_DATA,
      notices,
    });
    vi.spyOn(consultantNoticeApi, "getConsultantNoticeDetail").mockResolvedValue(
      notices[10]!,
    );
    renderPage();

    const panel = await screen.findByRole("tabpanel", { name: "공지사항" });
    await user.click(
      within(panel).getByRole("button", { name: /페이지 공지 11/ }),
    );
    expect(
      await screen.findByRole("tabpanel", { name: "공지사항 상세" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: /공지사항 목록으로/ }));
    const listPanel = await screen.findByRole("tabpanel", { name: "공지사항" });
    expect(within(listPanel).getAllByRole("listitem")).toHaveLength(10);
    await user.click(within(listPanel).getByRole("button", { name: "다음" }));
    expect(within(listPanel).getAllByRole("listitem")).toHaveLength(1);
    expect(within(listPanel).getByLabelText("공지 번호 1")).toBeVisible();
    expect(
      within(listPanel).getByRole("navigation", { name: "공지사항 목록 페이지" }),
    ).toHaveTextContent("이전2/2다음");
  });

  it("게시되지 않았거나 존재하지 않는 공지는 빈 상태로 안내한다", async () => {
    renderPage("/consultant/notices?noticeId=missing-notice");

    const panel = await screen.findByRole("tabpanel", { name: "공지사항 상세" });
    expect(
      await within(panel).findByText("해당 공지사항을 찾을 수 없습니다."),
    ).toBeVisible();
    expect(
      within(panel).getByRole("button", { name: "공지사항 목록으로" }),
    ).toBeEnabled();
  });
});
