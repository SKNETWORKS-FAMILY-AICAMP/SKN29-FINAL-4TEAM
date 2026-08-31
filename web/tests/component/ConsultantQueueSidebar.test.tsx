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
      "처리 중인 문의5",
      "처리 완료된 문의8",
      "전화 문의 등록",
      "공지사항",
      "직원 연락처",
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

    await user.click(screen.getByRole("tab", { name: "처리 중인 문의5" }));

    expect(onBucketChange).toHaveBeenCalledWith("IN_PROGRESS");
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
    expect(screen.getByRole("tab", { name: "직원 연락처" })).toHaveAttribute(
      "href",
      ROUTE_PATHS.consultantContacts,
    );
  });

  it("직원 연락처 화면에서는 연락처 메뉴만 선택된다", () => {
    render(
      <MemoryRouter>
        <ConsultantQueueSidebar
          activeBucket={null}
          bucketCounts={BUCKET_COUNTS}
          contactsActive
        />
      </MemoryRouter>,
    );
    const selectedTabs = screen.getAllByRole("tab").filter(
      (tab) => tab.getAttribute("aria-selected") === "true",
    );
    expect(selectedTabs).toHaveLength(1);
    expect(selectedTabs[0]).toHaveAccessibleName("직원 연락처");
  });

  it("전체 문의는 Bucket 합계 대신 전달받은 문의 목록 total을 표시한다", () => {
    render(
      <MemoryRouter>
        <ConsultantQueueSidebar
          activeBucket="ALL"
          bucketCounts={BUCKET_COUNTS}
          totalCount={21}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: "전체 문의21" })).toBeVisible();
    expect(screen.queryByRole("tab", { name: "새 문의3" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "처리 중인 문의5" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "처리 완료된 문의8" })).toBeVisible();
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
    expect(expandButton.querySelector("path")).toHaveAttribute(
      "d",
      "m9.5 6 6 6-6 6",
    );
    await user.click(expandButton);

    const collapseButton = screen.getByRole("button", {
      name: "사이드바 축소",
    });
    expect(sidebar).toHaveClass("is-user-expanded");
    expect(collapseButton).toHaveAttribute("aria-expanded", "true");
    expect(collapseButton.querySelector("path")).toHaveAttribute(
      "d",
      "m14.5 6-6 6 6 6",
    );

    await user.keyboard("{Escape}");
    expect(sidebar).not.toHaveClass("is-user-expanded");
    expect(screen.getByRole("button", { name: "사이드바 펼치기" })).toHaveFocus();
  });
});
