import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { AppRoutes } from "../../src/app/router/AppRouter";
import { CONSULTANT_QUEUE_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";
import { COUNSELOR_QUEUE_PAGE_SIZE } from "../../src/features/consultation/model/consultantWorkspaceModel";

const CONSULTANT_USER = {
  id: "STAFF-CONS-TEST",
  displayName: "테스트 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
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

describe("ConsultantDashboardPage", () => {
  it("문의 목록에서 상담 진행 문의를 선택하면 상담 Form을 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "INQ-20260704-0013",
    );
    await user.click(screen.getByRole("button", { name: /INQ-20260704-0013/ }));

    expect(screen.getByRole("heading", { name: "제품 누수" })).toBeInTheDocument();
    expect(screen.getByLabelText("고객 및 제품 빠른 정보")).toHaveTextContent(
      "무상보증",
    );
    expect(screen.getByRole("combobox", { name: "문의 정렬" })).toBeVisible();
    expect(
      within(screen.getByRole("complementary", { name: "상담 문의 목록" }))
        .getByText(/연결부에서 한두 방울씩/),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /상담 기록/ })).toBeInTheDocument();
    expect(
      screen.getByText("방문 여부를 선택하면 다음 처리 버튼이 표시됩니다."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "상담 처리 완료" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "임시 저장" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "AI 상담 요약" })).toBeVisible();
    expect(screen.getByLabelText("완료 후 다음 문의 자동 열기")).toBeChecked();

    await user.click(screen.getByRole("radio", { name: "방문 불필요" }));
    expect(
      screen.getByRole("button", { name: "상담 처리 완료" }),
    ).toBeEnabled();
  });

  it("상담 완료 후 자동 진행을 켜면 다음 대기 문의를 연다", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "INQ-20260704-0013",
    );
    await user.click(screen.getByRole("button", { name: /INQ-20260704-0013/ }));
    await user.clear(screen.getByRole("searchbox", { name: "문의 검색" }));
    await user.type(
      screen.getByRole("textbox", { name: /상담 기록/ }),
      "안전 안내 후 누수가 멈춘 것을 확인했습니다.",
    );
    await user.click(screen.getByRole("radio", { name: "방문 불필요" }));
    await user.type(
      screen.getByRole("textbox", { name: "상담 결과 (필수)" }),
      "고객이 증상 해결을 확인했습니다.",
    );
    await user.click(screen.getByLabelText("AI 요약을 확인했습니다"));
    await user.click(screen.getByRole("button", { name: "상담 처리 완료" }));

    expect(
      await screen.findByRole("heading", { name: "무출수" }),
    ).toBeInTheDocument();
  });

  it("상담 대기 문의에서 상담 시작을 누르면 상담 기록 Form으로 전환한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "INQ-20260707-0024",
    );
    await user.click(screen.getByRole("button", { name: /INQ-20260707-0024/ }));
    await user.click(screen.getByRole("button", { name: "상담 시작" }));

    expect(
      await screen.findByRole("textbox", { name: /상담 기록/ }),
    ).toBeInTheDocument();
    const desk = screen.getByRole("region", { name: "선택 문의 처리" });
    expect(
      within(desk).getByLabelText("상태: 상담 진행 중"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("안내로 해결할지, 방문 검토가 필요한지 결정하세요."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "상담 시작" }),
    ).not.toBeInTheDocument();
    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    expect(
      within(queue).getByLabelText("상태: 상담 진행 중"),
    ).toBeInTheDocument();
  });

  it("상담 화면을 벗어나지 않고 기사 배정과 방문 일정을 확정한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "INQ-20260704-0013",
    );
    await user.click(screen.getByRole("button", { name: /INQ-20260704-0013/ }));
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
    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    expect(within(queue).getByLabelText("상태: 방문 예정")).toBeInTheDocument();
  });

  it("문의 전체 기록은 핵심 현황과 최근 이력을 대시보드로 보여준다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "전체 기록 보기" }));

    expect(
      await screen.findByRole("heading", { name: "문의 핵심 현황" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "고객 문의" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "즉시 사용 안내" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI 상담 요약" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "최근 처리 이력" })).toBeInTheDocument();
  });

  it("위험도 필터는 공식 fixture의 위험 문의만 큐에 남긴다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByRole("combobox", { name: "위험도" }), "DANGER");

    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    const dangerCount = CONSULTANT_QUEUE_INQUIRIES.filter(
      (item) => item.riskLevel === "DANGER",
    ).length;
    const firstPageCount = Math.min(dangerCount, COUNSELOR_QUEUE_PAGE_SIZE);

    expect(queue.querySelectorAll(".v6-queue-item")).toHaveLength(firstPageCount);
    expect(
      screen.getByText(
        `총 ${dangerCount}건 · 1/${Math.ceil(
          dangerCount / COUNSELOR_QUEUE_PAGE_SIZE,
        )}페이지`,
      ),
    ).toBeInTheDocument();
    expect(within(queue).getAllByLabelText("위험도: 긴급")).toHaveLength(
      firstPageCount,
    );
  });

  it("페이지와 담당자 조건을 URL Query에서 복원한다", () => {
    renderPage("/consultant/inquiries?assignee=UNASSIGNED&page=1");
    const unassignedCount = CONSULTANT_QUEUE_INQUIRIES.filter(
      (item) => item.assignedCounselor === "미배정",
    ).length;
    const totalPages = Math.ceil(unassignedCount / COUNSELOR_QUEUE_PAGE_SIZE);

    expect(screen.getByRole("combobox", { name: "담당자" })).toHaveValue(
      "UNASSIGNED",
    );
    expect(
      screen.getByRole("heading", { name: "IoT 기능 지원 문의" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(`총 ${unassignedCount}건 · 1/${totalPages}페이지`),
    ).toBeInTheDocument();
  });

  it("일반 문의는 AI가 방문기사에게 자동 인계하여 상담사 큐에 노출하지 않는다", () => {
    renderPage();

    const queue = screen.getByRole("complementary", { name: "상담 문의 목록" });
    expect(within(queue).queryByLabelText("위험도: 일반")).not.toBeInTheDocument();
    expect(
      CONSULTANT_QUEUE_INQUIRIES.every(
        (item) => item.riskLevel === "CAUTION" || item.riskLevel === "DANGER",
      ),
    ).toBe(true);
  });

  it.each([
    ["loading", "상담 문의 목록을 불러오고 있습니다."],
    ["error", "상담 문의 목록을 불러오지 못했습니다."],
    ["forbidden", "상담 문의 목록을 볼 권한이 없습니다."],
    ["empty", "아직 접수된 문의가 없습니다."],
  ])("목록 %s 상태를 다른 상태와 구분한다", async (state, message) => {
    renderPage(`/consultant/inquiries?mockState=${state}`);

    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  it("검색 결과가 없으면 초기 빈 목록과 다른 안내와 초기화 행동을 제공한다", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByRole("searchbox", { name: "문의 검색" }),
      "존재하지 않는 문의",
    );

    expect(screen.getByText("조건에 맞는 문의가 없습니다.")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "조건 초기화" }).length,
    ).toBeGreaterThan(0);
  });
});
