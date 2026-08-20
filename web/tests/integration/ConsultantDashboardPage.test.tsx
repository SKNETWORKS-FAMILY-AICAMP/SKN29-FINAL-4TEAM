import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";
import { CONSULTANT_QUEUE_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";
import { getCounselorWorkBucket } from "../../src/features/consultation/model/consultantWorkspaceModel";
import type { CounselorWorkBucket } from "../../src/features/consultation/model/consultantWorkspaceTypes";

const CONSULTANT_USER = {
  id: "STAFF-CONS-TEST",
  displayName: "테스트 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

const TAB_LABELS: Record<CounselorWorkBucket, RegExp> = {
  NEW: /새 문의/,
  IN_PROGRESS: /처리 중인 문의/,
  COMPLETED: /처리 완료된 문의/,
};

const EXPECTED_BUCKET_COUNTS: Record<CounselorWorkBucket, number> = {
  NEW: 30,
  IN_PROGRESS: 30,
  COMPLETED: 30,
};

function renderPage(path = "/consultant/dashboard") {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

async function openInquiry(
  user: ReturnType<typeof userEvent.setup>,
  inquiryCode: string,
  bucket: CounselorWorkBucket,
) {
  await user.click(screen.getByRole("tab", { name: TAB_LABELS[bucket] }));
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
  await user.click(
    within(screen.getByLabelText("상담 문의 목록")).getByRole("button", {
      name: new RegExp(`${inquiryCode}.*상세 열기`),
    }),
  );
}

describe("ConsultantDashboardPage", () => {
  it("첫 화면은 개인 업무 요약과 세 가지 업무 탭을 함께 보여준다", () => {
    renderPage();

    expect(
      screen.getByRole("heading", {
        name: "테스트 상담원님 반갑습니다!",
      }),
    ).toBeVisible();
    expect(screen.getByText("오늘도 좋은 하루 되세요 😊")).toBeVisible();
    expect(
      screen
        .getByText(/^\d{4}\. \d{2}\. \d{2}\. \([일월화수목금토]\)$/)
        .getAttribute("datetime"),
    ).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    const workSummary = within(screen.getByLabelText("업무 요약"));
    expect(workSummary.getByRole("button", { name: /전체 문의 수90/ })).toBeVisible();
    expect(workSummary.getByRole("button", { name: /새 문의30/ })).toBeVisible();
    expect(workSummary.getByRole("button", { name: /처리 중인 문의30/ })).toBeVisible();
    expect(workSummary.getAllByText("전날 대비")).toHaveLength(4);
    ["↑ +8", "↑ +5", "↓ -2", "↑ +3"].forEach((change) =>
      expect(workSummary.getByText(change)).toBeVisible(),
    );
    expect(screen.getByRole("heading", { name: "공지사항" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "직원 연락처" })).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByLabelText("조직도")).toBeVisible();
    const noticePanel = within(
      screen.getByRole("heading", { name: "공지사항" }).closest("article")!,
    );
    ["긴급", "이벤트", "시스템", "근무", "복지", "교육"].forEach(
      (category) => expect(noticePanel.getByText(category)).toBeVisible(),
    );
    expect(
      screen.queryByLabelText("디자인 Mock 데이터 사용 중"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("MY WORKSPACE")).not.toBeInTheDocument();
    expect(
      screen.queryByText("안전 확인과 상담 연결이 필요한 문의부터 순서대로 보여드립니다."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("안전·재문의·상담 대기")).not.toBeInTheDocument();
    expect(screen.queryByText("신규·진행 중 전체")).not.toBeInTheDocument();
    expect(screen.queryByText("접수 후 90분 이상")).not.toBeInTheDocument();
    expect(screen.queryByText("현재 목록 기준")).not.toBeInTheDocument();
    expect(screen.queryByText("PRIORITY QUEUE")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/위험도와 접수 경과 기준 정렬/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("긴급 문의 목록")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "업무 대시보드" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: /새 문의/ })).toHaveAttribute(
      "aria-selected",
      "false",
    );
    expect(screen.getByRole("tab", { name: /전체 문의/ })).toBeVisible();
    expect(screen.getByRole("tab", { name: /처리 중인 문의/ })).toBeVisible();
    expect(screen.getByRole("tab", { name: /처리 완료된 문의/ })).toBeVisible();
    expect(screen.getByRole("tab", { name: "전화 문의 등록" })).toBeVisible();
    expect(screen.getByLabelText("상담 문의 목록")).not.toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /상담 기록/ })).not.toBeInTheDocument();
  });

  it("조직도에서 부서를 선택하면 직원 연락처 목록을 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /고객케어팀/ }));

    ["직원명", "부서명", "직책", "내선번호", "이메일"].forEach(
      (column) =>
        expect(screen.getByRole("columnheader", { name: column })).toBeVisible(),
    );
    expect(
      screen.queryByRole("columnheader", { name: "휴대폰번호" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "한예나" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "02-3274-9502" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "조직도" }));
    expect(screen.getByLabelText("조직도")).toBeVisible();
  });

  it("조직도 아래에서 방문기사 연락처 목록을 확인한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole("button", { name: /방문기사 연락처/ }),
    );

    expect(screen.getByText("방문기사 연락처")).toBeVisible();
    ["직원명", "지사", "연락처", "이메일"].forEach((column) =>
      expect(screen.getByRole("columnheader", { name: column })).toBeVisible(),
    );
    expect(screen.getByRole("cell", { name: "오민석" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "서울동부지사" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "010-2501-5001" })).toBeVisible();
  });

  it("직원 연락처 검색으로 전체 조직의 직원을 찾는다", async () => {
    const user = userEvent.setup();
    renderPage();

    const contactSearch = screen.getByRole("searchbox", {
      name: "직원 연락처 검색",
    });
    expect(contactSearch).toHaveAttribute("placeholder", "검색");

    await user.type(contactSearch, "한예나");

    expect(screen.getByRole("cell", { name: "한예나" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "고객케어팀" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "02-3274-9502" })).toBeVisible();
  });

  it("대시보드 상단에는 문의 검색과 사용자 화살표를 표시하지 않는다", () => {
    const { container } = renderPage();

    expect(
      screen.queryByRole("searchbox", { name: "문의 검색" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "검색" })).not.toBeInTheDocument();
    expect(container.querySelector(".simple-user__chevron")).toBeNull();
    expect(screen.getByText("테스트 상담원")).toBeVisible();
    expect(screen.getByText("2026-001-256")).toBeVisible();
    expect(screen.getByRole("button", { name: "로그아웃" })).toBeVisible();
  });

  it.each([
    [/전체 문의 수90/, /전체 문의/],
    [/새 문의30/, /새 문의/],
    [/처리 중인 문의30/, /처리 중인 문의/],
    [/AI 검토30/, /처리 중인 문의/],
  ])("업무 요약 카드 %s가 해당 문의 메뉴로 이동한다", async (card, menu) => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      within(screen.getByLabelText("업무 요약")).getByRole("button", {
        name: card,
      }),
    );

    expect(
      within(screen.getByRole("tablist", { name: "상담사 메뉴" })).getByRole(
        "tab",
        { name: menu },
      ),
    ).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it.skip("디자인 Mock에서는 모든 업무 요약 카드가 문의 목록을 제공한다", async () => {
    const user = userEvent.setup();
    renderPage();

    const workSummary = within(screen.getByLabelText("업무 요약"));
    const inquiryList = within(screen.getByLabelText("상담 문의 목록"));

    for (const cardName of [
      /전체 문의 수90/,
      /새 문의30/,
      /처리 중인 문의30/,
      /AI 검토30/,
    ]) {
      await user.click(workSummary.getByRole("button", { name: cardName }));
      expect(
        inquiryList.getAllByRole("button", { name: /상세 열기/ }).length,
      ).toBeGreaterThan(0);
    }
  });

  it("세 업무 탭의 건수는 상담사 문의 상태와 일치한다", () => {
    renderPage();

    (["NEW", "IN_PROGRESS", "COMPLETED"] as const).forEach((bucket) => {
      const count = CONSULTANT_QUEUE_INQUIRIES.filter(
        (inquiry) => getCounselorWorkBucket(inquiry.status) === bucket,
      ).length;
      expect(count).toBe(EXPECTED_BUCKET_COUNTS[bucket]);
      expect(screen.getByRole("tab", { name: TAB_LABELS[bucket] })).toHaveTextContent(
        String(count),
      );
    });
  });

  it.skip("문의 목록을 눌러야 상세 상담 화면이 열리고 닫을 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260707-0024", "NEW");

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

  it.skip("새 문의에서 상담 시작을 누르면 처리 중 탭으로 이동하고 상담 Form을 연다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260707-0024", "NEW");
    await user.click(screen.getByRole("button", { name: "상담 시작" }));

    expect(await screen.findByRole("textbox", { name: /상담 기록/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "업무 대시보드" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.queryByRole("button", { name: "상담 시작" })).not.toBeInTheDocument();
  });

  it("상담 상세에서 기사 배정과 방문 일정을 한 흐름으로 확정한다", async () => {
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
    await user.selectOptions(
      within(scheduler).getByRole("combobox", { name: "방문기사" }),
      "00000000-0000-4000-8000-000000000101",
    );
    fireEvent.change(within(scheduler).getByLabelText("고객 희망일"), {
      target: { value: "2026-08-01" },
    });
    fireEvent.change(within(scheduler).getByLabelText("확정 방문일"), {
      target: { value: "2026-08-02" },
    });
    await user.click(
      within(scheduler).getByRole("button", { name: "기사 배정·방문 확정" }),
    );

    expect(
      await within(scheduler).findByText(
        "오세훈 기사 배정과 방문 일정이 확정되었습니다.",
      ),
    ).toBeInTheDocument();
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

  it("문의 전체 기록으로 이동하면 상세 대시보드를 보여준다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260704-0013", "IN_PROGRESS");
    await user.click(screen.getByRole("button", { name: "전체 기록 보기" }));

    expect(await screen.findByRole("heading", { name: "문의 핵심 현황" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "고객 문의" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "최근 처리 이력" })).toBeInTheDocument();
  });

  it.skip("긴급·주의·일반 탭을 전환하면 해당 문의 10건만 보여준다", async () => {
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

    const dangerTab = screen.getByRole("tab", { name: /긴급 문의/ });
    const cautionTab = screen.getByRole("tab", { name: /주의 문의/ });
    const generalTab = screen.getByRole("tab", { name: /일반 문의/ });

    expect(dangerTab).toHaveAttribute("aria-selected", "true");
    expect(dangerTab).toHaveClass("consultant-risk-tab--danger");
    expect(cautionTab).toHaveClass("consultant-risk-tab--caution");
    expect(generalTab).toHaveClass("consultant-risk-tab--general");
    expect(within(dangerTab).getByText("10")).toHaveClass(
      "consultant-risk-tab__count",
    );
    expect(within(cautionTab).getByText("10")).toHaveClass(
      "consultant-risk-tab__count",
    );
    expect(within(generalTab).getByText("10")).toHaveClass(
      "consultant-risk-tab__count",
    );
    expect(
      within(screen.getByRole("tabpanel", { name: /긴급 문의/ })).getAllByRole(
        "button",
        { name: /상세 열기/ },
      ),
    ).toHaveLength(10);
    expect(
      screen.queryByRole("button", { name: "긴급 문의 상태 필터" }),
    ).not.toBeInTheDocument();
    expect(
      screen
        .getByRole("tabpanel", { name: /긴급 문의/ })
        .querySelector(".consultant-risk-section__count"),
    ).toBeNull();

    dangerTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(cautionTab).toHaveAttribute("aria-selected", "true");
    expect(
      within(screen.getByRole("tabpanel", { name: /주의 문의/ })).getAllByRole(
        "button",
        { name: /상세 열기/ },
      ),
    ).toHaveLength(10);

    await user.click(generalTab);
    expect(generalTab).toHaveAttribute("aria-selected", "true");
    expect(
      within(screen.getByRole("tabpanel", { name: /일반 문의/ })).getAllByRole(
        "button",
        { name: /상세 열기/ },
      ),
    ).toHaveLength(10);
  });

  it.each([
    ["loading", "상담 문의 목록을 불러오고 있습니다."],
    ["error", "상담 문의 목록을 불러오지 못했습니다."],
    ["forbidden", "상담 문의 목록을 볼 권한이 없습니다."],
    ["empty", "새 문의가 없습니다."],
  ])("목록 %s 상태를 구분해 안내한다", async (state, message) => {
    renderPage(`/consultant/dashboard?mockState=${state}`);

    expect(await screen.findByText(message)).toBeInTheDocument();
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

  it.skip("고객 원문과 AI 요약을 비교하고 승인할 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();

    const summary = screen.getByRole("textbox", { name: "AI 요약 수정본" });
    expect((summary as HTMLTextAreaElement).value).toContain("문의입니다");

    await user.click(screen.getByRole("button", { name: "승인" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      /요약을 승인했습니다/,
    );
  });
});
