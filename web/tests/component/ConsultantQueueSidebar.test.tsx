import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ROUTE_PATHS } from "../../src/app/router/routePaths";
import ConsultantQueueSidebar from "../../src/features/consultation/components/ConsultantQueueSidebar";

const BUCKET_COUNTS = {
  NEW: 3,
  IN_PROGRESS: 5,
  COMPLETED: 8,
} as const;

describe("ConsultantQueueSidebar", () => {
  it("상담사 메뉴를 아이콘이 있는 세로 탭으로 표시한다", () => {
    const { container } = render(
      <MemoryRouter>
        <ConsultantQueueSidebar
          activeBucket="ALL"
          bucketCounts={BUCKET_COUNTS}
        />
      </MemoryRouter>,
    );

    const menu = screen.getByRole("tablist", { name: "상담사 메뉴" });
    const tabs = within(menu).getAllByRole("tab");

    expect(tabs).toHaveLength(7);
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      "업무 대시보드",
      "전체 문의16",
      "새 문의3",
      "처리 중인 문의5",
      "처리 완료된 문의8",
      "전화 문의 등록",
      "공지사항",
    ]);
    expect(menu.querySelectorAll("svg")).toHaveLength(7);
    expect(container.querySelectorAll(".consultant-work-tab__icon")).toHaveLength(
      7,
    );
    expect(
      tabs.filter((tab) => tab.getAttribute("aria-selected") === "true"),
    ).toHaveLength(1);
    expect(screen.getByRole("tab", { name: "전체 문의16" })).toHaveClass(
      "is-active",
    );
  });

  it("문의 탭 선택과 화면 링크를 기존 경로에 연결한다", async () => {
    const user = userEvent.setup();
    const onBucketChange = vi.fn();

    render(
      <MemoryRouter>
        <ConsultantQueueSidebar
          activeBucket="ALL"
          bucketCounts={BUCKET_COUNTS}
          onBucketChange={onBucketChange}
        />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("tab", { name: "새 문의3" }));

    expect(onBucketChange).toHaveBeenCalledWith("NEW");
    expect(
      screen.getByRole("tab", { name: "업무 대시보드" }),
    ).toHaveAttribute("href", ROUTE_PATHS.consultantDashboard);
    expect(
      screen.getByRole("tab", { name: "전화 문의 등록" }),
    ).toHaveAttribute("href", ROUTE_PATHS.consultantPhoneInquiryCreate);
    expect(screen.getByRole("tab", { name: "공지사항" })).toHaveAttribute(
      "href",
      ROUTE_PATHS.consultantNotices,
    );
  });

  it("hover가 아닌 명시적 버튼으로 사이드바를 열고 닫는다", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <ConsultantQueueSidebar
          activeBucket="ALL"
          bucketCounts={BUCKET_COUNTS}
        />
      </MemoryRouter>,
    );

    const sidebar = screen.getByLabelText("상담사 사이드바");
    await user.hover(sidebar);
    expect(sidebar).not.toHaveClass("is-user-expanded");

    const expandButton = screen.getByRole("button", {
      name: "사이드바 펼치기",
    });
    expect(expandButton).toHaveAttribute("aria-expanded", "false");
    await user.click(expandButton);

    const collapseButton = screen.getByRole("button", {
      name: "사이드바 축소",
    });
    expect(sidebar).toHaveClass("is-user-expanded");
    expect(collapseButton).toHaveAttribute("aria-expanded", "true");

    await user.keyboard("{Escape}");
    expect(sidebar).not.toHaveClass("is-user-expanded");
    expect(screen.getByRole("button", { name: "사이드바 펼치기" })).toHaveFocus();
  });
});
