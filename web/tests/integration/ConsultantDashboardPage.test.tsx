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
  NEW: /새로 들어온 문의/,
  IN_PROGRESS: /처리 중인 문의/,
  COMPLETED: /처리 완료된 문의/,
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

async function openInquiry(
  user: ReturnType<typeof userEvent.setup>,
  inquiryCode: string,
  bucket: CounselorWorkBucket,
) {
  if (bucket !== "NEW") {
    await user.click(screen.getByRole("tab", { name: TAB_LABELS[bucket] }));
  }
  await user.type(screen.getByRole("searchbox", { name: "문의 검색" }), inquiryCode);
  await user.click(screen.getByRole("button", { name: new RegExp(inquiryCode) }));
}

describe("ConsultantDashboardPage", () => {
  it("첫 화면은 세 가지 업무 탭과 문의 목록만 보여준다", () => {
    renderPage();

    expect(screen.getByRole("tab", { name: /새로 들어온 문의/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: /처리 중인 문의/ })).toBeVisible();
    expect(screen.getByRole("tab", { name: /처리 완료된 문의/ })).toBeVisible();
    expect(screen.getByLabelText("상담 문의 목록")).toBeVisible();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: /상담 기록/ })).not.toBeInTheDocument();
  });

  it("세 업무 탭의 건수는 상담사 문의 상태와 일치한다", () => {
    renderPage();

    (["NEW", "IN_PROGRESS", "COMPLETED"] as const).forEach((bucket) => {
      const count = CONSULTANT_QUEUE_INQUIRIES.filter(
        (inquiry) => getCounselorWorkBucket(inquiry.status) === bucket,
      ).length;
      expect(screen.getByRole("tab", { name: TAB_LABELS[bucket] })).toHaveTextContent(
        String(count),
      );
    });
  });

  it("문의 목록을 눌러야 상세 상담 화면이 열리고 닫을 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();

    await openInquiry(user, "INQ-20260707-0024", "NEW");

    expect(screen.getByRole("dialog", { name: /합성 고객.*IoT 기능 지원 문의/ })).toBeVisible();
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
      target: { value: "2026-08-01T10:00" },
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
      "STAFF-TECH-01",
    );
    fireEvent.change(within(scheduler).getByLabelText("고객 희망일"), {
      target: { value: "2026-08-01T10:00" },
    });
    fireEvent.change(within(scheduler).getByLabelText("확정 방문일"), {
      target: { value: "2026-08-01T11:00" },
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

  it("일반 문의는 방문기사에게 자동 인계되어 상담사 탭에 포함되지 않는다", () => {
    renderPage();

    expect(
      CONSULTANT_QUEUE_INQUIRIES.every(
        (item) => item.riskLevel === "CAUTION" || item.riskLevel === "DANGER",
      ),
    ).toBe(true);
    expect(screen.queryByLabelText("위험도: 일반")).not.toBeInTheDocument();
  });

  it.each([
    ["loading", "상담 문의 목록을 불러오고 있습니다."],
    ["error", "상담 문의 목록을 불러오지 못했습니다."],
    ["forbidden", "상담 문의 목록을 볼 권한이 없습니다."],
    ["empty", "새로 들어온 문의가 없습니다."],
  ])("목록 %s 상태를 구분해 안내한다", async (state, message) => {
    renderPage(`/consultant/inquiries?mockState=${state}`);

    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  it("검색 결과가 없으면 검색 초기화 행동을 제공한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "존재하지 않는 문의",
    );

    expect(screen.getByText("검색 조건에 맞는 문의가 없습니다.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "검색 초기화" })).toHaveLength(2);
  });

  it("한글 조합 중에는 검색 URL을 갱신하지 않고 조합 완료 후 검색한다", () => {
    renderPage();
    const searchInput = screen.getByRole("searchbox", { name: "문의 검색" });

    fireEvent.compositionStart(searchInput);
    fireEvent.change(searchInput, { target: { value: "존재하지 않는 문의" } });

    expect(searchInput).toHaveValue("존재하지 않는 문의");
    expect(
      screen.queryByText("검색 조건에 맞는 문의가 없습니다."),
    ).not.toBeInTheDocument();

    fireEvent.compositionEnd(searchInput, { data: "의" });

    expect(screen.getByText("검색 조건에 맞는 문의가 없습니다.")).toBeInTheDocument();
  });

  it("URL의 검색어를 복원하고 해당 상태 탭에서 결과를 찾을 수 있다", async () => {
    const user = userEvent.setup();
    renderPage("/consultant/inquiries?q=INQ-20260704-0013&page=1");

    expect(screen.getByRole("searchbox", { name: "문의 검색" })).toHaveValue(
      "INQ-20260704-0013",
    );
    await user.click(screen.getByRole("tab", { name: /처리 중인 문의/ }));
    expect(
      screen.getByRole("button", { name: /INQ-20260704-0013/ }),
    ).toBeInTheDocument();
  });

  it("상담 완료 후 자동 진행을 사용하면 다음 처리 문의를 연다", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();

    await openInquiry(user, "INQ-20260704-0013", "IN_PROGRESS");
    await user.clear(screen.getByRole("searchbox", { name: "문의 검색" }));
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
