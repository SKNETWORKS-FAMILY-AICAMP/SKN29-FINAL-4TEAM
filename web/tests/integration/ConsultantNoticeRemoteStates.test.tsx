import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import { ApiClientError, type ApiErrorKind } from "../../src/common/api/apiError";
import ConsultantNoticePage from "../../src/pages/consultant/ConsultantNoticePage";

const noticeRemoteMocks = vi.hoisted(() => ({
  getDetail: vi.fn(),
  getPage: vi.fn(),
}));

vi.mock("../../src/features/notice/api/consultantNoticeApi", () => ({
  getConsultantNoticeDetail: noticeRemoteMocks.getDetail,
  getConsultantNoticePageData: noticeRemoteMocks.getPage,
}));

const CONSULTANT_USER = {
  id: "STAFF-CONS-NOTICE-REMOTE",
  displayName: "원격 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

const REMOTE_NOTICE = {
  noticeId: "notice-remote-001",
  noticeCode: "NOTICE-REMOTE-001",
  categoryCode: "SYSTEM" as const,
  category: "시스템",
  title: "Backend 운영 공지",
  content: "Backend에서 받은 운영 공지 내용입니다.",
  department: "시스템운영팀",
  publishedOn: "2026-08-27",
};

const REMOTE_NOTICE_PAGE = {
  summary: { total: 7, new: 2, inProgress: 3, completed: 2 },
  notices: [REMOTE_NOTICE],
};

function createApiError(status: number, kind: ApiErrorKind) {
  return new ApiClientError({
    kind,
    status,
    code: kind,
    message: kind,
  });
}

function renderPage(path = "/consultant/notices") {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <ConsultantNoticePage />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("ConsultantNoticePage Remote 응답 상태", () => {
  beforeEach(() => {
    noticeRemoteMocks.getPage.mockReset();
    noticeRemoteMocks.getPage.mockResolvedValue(REMOTE_NOTICE_PAGE);
    noticeRemoteMocks.getDetail.mockReset();
    noticeRemoteMocks.getDetail.mockResolvedValue(REMOTE_NOTICE);
  });

  it("공지 목록과 상세의 200 응답을 실제 화면에 표시한다", async () => {
    renderPage("/consultant/notices?noticeId=notice-remote-001");

    expect(
      await screen.findByRole("heading", { name: "Backend 운영 공지" }),
    ).toBeVisible();
    expect(screen.getByText("Backend에서 받은 운영 공지 내용입니다.")).toBeVisible();
    expect(noticeRemoteMocks.getPage).toHaveBeenCalledTimes(1);
    expect(noticeRemoteMocks.getDetail).toHaveBeenCalledWith(
      "notice-remote-001",
    );
  });

  it.each([
    [
      401,
      "UNAUTHORIZED" as const,
      "로그인이 만료되어 공지사항을 불러올 수 없습니다.",
    ],
    [403, "FORBIDDEN" as const, "공지사항을 볼 권한이 없습니다."],
    [
      500,
      "SERVER_ERROR" as const,
      "공지사항 서버에 일시적인 오류가 발생했습니다.",
    ],
  ])("공지 목록 %i 응답을 구분한다", async (status, kind, expectedMessage) => {
    noticeRemoteMocks.getPage.mockRejectedValue(createApiError(status, kind));

    renderPage();

    expect(await screen.findByText(expectedMessage)).toBeVisible();
  });

  it.each([
    [401, "UNAUTHORIZED" as const, "로그인이 만료되어 공지사항을 볼 수 없습니다."],
    [403, "FORBIDDEN" as const, "이 공지사항을 볼 권한이 없습니다."],
    [404, "NOT_FOUND" as const, "해당 공지사항을 찾을 수 없습니다."],
    [
      500,
      "SERVER_ERROR" as const,
      "공지사항 서버에 일시적인 오류가 발생했습니다.",
    ],
  ])("공지 상세 %i 응답을 구분한다", async (status, kind, expectedMessage) => {
    noticeRemoteMocks.getDetail.mockRejectedValue(createApiError(status, kind));

    renderPage("/consultant/notices?noticeId=notice-remote-001");

    expect(await screen.findByText(expectedMessage)).toBeVisible();
  });
});
