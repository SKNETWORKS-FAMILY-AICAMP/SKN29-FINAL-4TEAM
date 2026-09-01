import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import AppRouter, { AppRoutes } from "../../src/app/router/AppRouter";
import { ApiClientError } from "../../src/common/api/apiError";
import * as consultantNoticeApi from "../../src/features/notice/api/consultantNoticeApi";
import { MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA } from "../fixtures/consultantNoticeMock";

const CONSULTANT_USER = {
  id: "STAFF-CONTACT-TEST",
  displayName: "연락처 상담사",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};
const DATA = MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA;

function CurrentRoute() {
  const location = useLocation();
  return <span data-testid="contacts-test-route" hidden>{location.pathname}{location.search}</span>;
}

function renderPage(path = "/consultant/contacts") {
  return render(
    <AuthProvider initialUser={CONSULTANT_USER}>
      <MemoryRouter initialEntries={[path]}>
        <CurrentRoute />
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("ConsultantContactsPage", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("연락처 URL을 직접 열어도 기본·마지막 슬래시·query 경로가 404로 빠지지 않는다", async () => {
    for (const path of [
      "/consultant/contacts",
      "/consultant/contacts/",
      "/consultant/contacts?from=sidebar",
    ]) {
      const view = renderPage(path);
      try {
        expect(await screen.findByRole("heading", { level: 1, name: "직원 연락처" })).toBeVisible();
        expect(await screen.findByText(DATA.consultants[0].name)).toBeVisible();
        expect(screen.getByTestId("contacts-test-route")).toHaveTextContent(path);
        expect(screen.getByRole("tab", { name: "직원 연락처" })).toHaveAttribute("aria-selected", "true");
        expect(screen.queryByText("페이지를 찾을 수 없습니다.")).not.toBeInTheDocument();
      } finally {
        view.unmount();
      }
    }
  });

  it("BrowserRouter가 주소창의 연락처 경로에서 시작하고 새로 마운트되어도 연락처를 연다", async () => {
    const previousPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    window.history.replaceState({}, "", "/consultant/contacts");
    try {
      // A fresh router mount models receiving the SPA bundle at a deep link.
      for (let mount = 0; mount < 2; mount += 1) {
        const view = render(
          <AuthProvider initialUser={CONSULTANT_USER}>
            <AppRouter />
          </AuthProvider>,
        );
        try {
          expect(await screen.findByRole("heading", { level: 1, name: "직원 연락처" })).toBeVisible();
          expect(await screen.findByText(DATA.consultants[0].name)).toBeVisible();
          expect(window.location.pathname).toBe("/consultant/contacts");
          expect(screen.getByRole("tab", { name: "직원 연락처" })).toHaveAttribute("aria-selected", "true");
          expect(screen.queryByText("페이지를 찾을 수 없습니다.")).not.toBeInTheDocument();
        } finally {
          view.unmount();
        }
      }
    } finally {
      window.history.replaceState({}, "", previousPath);
    }
  });

  it("사이드바에서 전체 직원과 방문기사 연락처를 열고 문의 집계를 유지한다", async () => {
    const user = userEvent.setup();
    renderPage("/consultant/notices");
    await user.click(screen.getByRole("tab", { name: "직원 연락처" }));

    const table = await screen.findByRole("table", { name: "전체 직원 연락처" });
    expect(within(table).getAllByRole("row")).toHaveLength(DATA.consultants.length + DATA.technicians.length + 1);
    expect(within(table).getByText(DATA.consultants[0].name)).toBeVisible();
    expect(within(table).getByText(DATA.technicians[0].name)).toBeVisible();
    expect(within(table).getByText(DATA.consultants[0].extension)).toBeVisible();
    expect(within(table).getByText(DATA.technicians[0].phone)).toBeVisible();
    expect(screen.queryByRole("region", { name: "조직도" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "직원 연락처" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "전체 문의90" })).toBeVisible();
  });

  it("확장된 부서를 선택하면 해당 부서 연락처만 표시한다", async () => {
    const user = userEvent.setup();
    const department = "서비스기획팀";
    const departmentMembers = DATA.consultants.filter(
      (person) => person.department === department,
    );
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });

    await user.click(screen.getByRole("combobox", { name: "부서·지점 선택" }));
    await user.click(screen.getByRole("option", { name: department }));

    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(
      departmentMembers.length + 1,
    );
    departmentMembers.forEach((person) => {
      expect(screen.getByText(person.name)).toBeVisible();
    });
  });

  it("방문기사와 부서·지점 필터는 연락처만 필터링한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });

    await user.click(screen.getByRole("button", { name: /^방문기사/ }));
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(DATA.technicians.length + 1);
    await user.click(screen.getByRole("combobox", { name: "부서·지점 선택" }));
    await user.click(screen.getByRole("option", { name: DATA.technicians[0].branch }));

    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(
      DATA.technicians.filter(
        (technician) => technician.branch === DATA.technicians[0].branch,
      ).length + 1,
    );
    expect(within(table).getByText(DATA.technicians[0].name)).toBeVisible();
    expect(screen.getByRole("tab", { name: "전체 문의90" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "처리 중인 문의30" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "처리 완료된 문의30" })).toBeVisible();
  });

  it("연락처에서 공지사항·대시보드 링크를 누르면 실제 경로와 선택 메뉴가 바뀐다", async () => {
    const user = userEvent.setup();
    renderPage();

    for (const destination of [
      { label: "공지사항", path: "/consultant/notices" },
      { label: "업무 대시보드", path: "/consultant/dashboard" },
    ]) {
      await screen.findByRole("table", { name: "전체 직원 연락처" });
      const menu = within(screen.getByRole("tablist", { name: "상담사 메뉴" }));
      await user.click(menu.getByRole("tab", { name: destination.label }));

      expect(screen.getByTestId("contacts-test-route")).toHaveTextContent(destination.path);
      expect(screen.queryByRole("table", { name: "전체 직원 연락처" })).not.toBeInTheDocument();
      const destinationMenu = within(screen.getByRole("tablist", { name: "상담사 메뉴" }));
      expect(destinationMenu.getByRole("tab", { name: destination.label })).toHaveAttribute("aria-selected", "true");
      expect(destinationMenu.getByRole("tab", { name: "직원 연락처" })).toHaveAttribute("aria-selected", "false");

      await user.click(destinationMenu.getByRole("tab", { name: "직원 연락처" }));
      expect(screen.getByTestId("contacts-test-route")).toHaveTextContent("/consultant/contacts");
    }
  });

  it("연락처에서 펼친 사이드바의 문의 메뉴를 누르면 해당 Bucket으로 이동한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });
    const expand = screen.queryByRole("button", { name: "사이드바 펼치기" });
    if (expand) await user.click(expand);

    for (const destination of [
      { label: "전체 문의", bucket: "ALL" },
      { label: "처리 중인 문의", bucket: "IN_PROGRESS" },
      { label: "처리 완료된 문의", bucket: "COMPLETED" },
    ]) {
      await screen.findByRole("table", { name: "전체 직원 연락처" });
      const menu = within(screen.getByRole("tablist", { name: "상담사 메뉴" }));
      await user.click(menu.getByRole("tab", { name: new RegExp(`^${destination.label}`) }));

      expect(screen.getByTestId("contacts-test-route")).toHaveTextContent(`/consultant/inquiries?bucket=${destination.bucket}`);
      expect(await screen.findByRole("tabpanel", { name: destination.label })).toBeVisible();
      expect(screen.queryByRole("table", { name: "전체 직원 연락처" })).not.toBeInTheDocument();
      const destinationMenu = within(screen.getByRole("tablist", { name: "상담사 메뉴" }));
      expect(destinationMenu.getByRole("tab", { name: new RegExp(`^${destination.label}`) })).toHaveAttribute("aria-selected", "true");
      expect(destinationMenu.getByRole("tab", { name: "직원 연락처" })).toHaveAttribute("aria-selected", "false");

      await user.click(destinationMenu.getByRole("tab", { name: "직원 연락처" }));
    }
    await screen.findByRole("table", { name: "전체 직원 연락처" });
    await user.click(screen.getByRole("button", { name: "사이드바 축소" }));
  });

  it("검색 버튼이나 Enter로 검색을 적용하고 검색 중 화면을 다시 불러오지 않는다", async () => {
    const user = userEvent.setup();
    const getData = vi.spyOn(consultantNoticeApi, "getSyntheticConsultantDashboardData").mockResolvedValue(DATA);
    renderPage();
    await screen.findByRole("table");
    const search = screen.getByRole("searchbox", { name: "직원 이름, 부서, 연락처 검색" });

    await user.type(search, DATA.consultants[0].name);
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(DATA.consultants.length + DATA.technicians.length + 1);
    await user.click(screen.getByRole("button", { name: "검색" }));
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(2);
    expect(screen.getByText(DATA.consultants[0].email)).toBeVisible();

    await user.clear(search);
    await user.type(search, "없는직원이름{Enter}");
    expect(screen.getByText("조건에 맞는 연락처가 없습니다.")).toBeVisible();
    expect(getData).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("tab", { name: "전체 문의90" })).toBeVisible();
  });

  it("하이픈 없이 전화번호를 검색해도 일치하며 표시 원문은 유지한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });
    const person = DATA.consultants[0];
    const digits = person.extension.replace(/\D/g, "");

    await user.type(screen.getByRole("searchbox", { name: "직원 이름, 부서, 연락처 검색" }), `${digits}{Enter}`);

    const table = screen.getByRole("table", { name: "전체 직원 연락처" });
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(within(table).getByText(person.name)).toBeVisible();
    expect(within(table).getByText(person.extension)).toBeVisible();
    expect(within(table).getByText(person.email)).toBeVisible();
  });

  it("필터 초기화로 직원 구분·부서·검색을 해제하고 전체 연락처를 복원한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });
    expect(screen.getByRole("button", { name: "필터 초기화" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: /^방문기사/ }));
    await user.click(screen.getByRole("combobox", { name: "부서·지점 선택" }));
    await user.click(screen.getByRole("option", { name: DATA.technicians[0].branch }));
    await user.type(screen.getByRole("searchbox"), `${DATA.technicians[0].name}{Enter}`);
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "필터 초기화" }));

    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(DATA.consultants.length + DATA.technicians.length + 1);
    expect(screen.getByRole("searchbox")).toHaveValue("");
    expect(screen.getByRole("combobox", { name: "부서·지점 선택" })).toHaveTextContent("전체 부서·지점");
    expect(screen.getByRole("button", { name: /^전체 연락처/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "필터 초기화" })).toBeDisabled();
    expect(screen.getByRole("tab", { name: "전체 문의90" })).toBeVisible();
  });

  it("연락처와 이메일 복사는 API 원문을 전달하고 각각 완료 상태를 안내한다", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    const person = DATA.consultants[0];
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });

    await user.click(screen.getByRole("button", { name: `${person.name} 연락처 복사` }));
    expect(writeText).toHaveBeenLastCalledWith(person.extension);
    expect(await screen.findByRole("status")).toHaveTextContent(`${person.name} 연락처 복사 완료`);

    await user.click(screen.getByRole("button", { name: `${person.name} 이메일 복사` }));
    expect(writeText).toHaveBeenLastCalledWith(person.email);
    expect(screen.getByRole("status")).toHaveTextContent(`${person.name} 이메일 복사 완료`);
    expect(writeText).toHaveBeenCalledTimes(2);
    expect(screen.getByText(person.extension)).toBeVisible();
    expect(screen.getByText(person.email)).toBeVisible();
  });

  it("클립보드 권한 거절을 안내하고 연락처 원문은 계속 보여준다", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new DOMException("Permission denied", "NotAllowedError"));
    const person = DATA.technicians[0];
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });

    await user.click(screen.getByRole("button", { name: `${person.name} 연락처 복사` }));

    expect(writeText).toHaveBeenCalledWith(person.phone);
    expect(await screen.findByRole("status")).toHaveTextContent("복사하지 못했습니다. 내용을 직접 선택해 복사해 주세요.");
    expect(screen.getByText(person.phone)).toBeVisible();
    expect(screen.getByText(person.email)).toBeVisible();
    expect(screen.queryByText("페이지를 찾을 수 없습니다.")).not.toBeInTheDocument();
  });

  it("연락처 새로고침은 읽기 API를 다시 호출하고 데이터 원문을 변경하지 않는다", async () => {
    const user = userEvent.setup();
    const fixture = structuredClone(DATA);
    const getData = vi.spyOn(consultantNoticeApi, "getSyntheticConsultantDashboardData").mockResolvedValue(fixture);
    renderPage();
    await screen.findByRole("table", { name: "전체 직원 연락처" });
    expect(getData).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "직원 연락처 새로고침" }));

    await waitFor(() => expect(getData).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(DATA.consultants[0].extension)).toBeVisible();
    expect(screen.getByText(DATA.consultants[0].email)).toBeVisible();
    expect(fixture).toEqual(DATA);
    expect(screen.getByRole("tab", { name: "전체 문의90" })).toBeVisible();
  });

  it("대시보드 연락처의 전체 보기로 전체 연락처 화면에 진입한다", async () => {
    const user = userEvent.setup();
    renderPage("/consultant/dashboard");
    await user.click(await screen.findByLabelText("직원 연락처 전체 보기"));

    expect(await screen.findByRole("table", { name: "전체 직원 연락처" })).toBeVisible();
    expect(screen.getByTestId("contacts-test-route")).toHaveTextContent("/consultant/contacts");
    expect(screen.getByRole("tab", { name: "직원 연락처" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText("페이지를 찾을 수 없습니다.")).not.toBeInTheDocument();
  });

  it("데이터를 불러오는 동안 빈 연락처 상태를 표시하지 않는다", () => {
    vi.spyOn(consultantNoticeApi, "getSyntheticConsultantDashboardData").mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("직원 연락처를 불러오고 있습니다.")).toBeVisible();
    expect(screen.queryByText("등록된 직원 연락처가 없습니다.")).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toBeDisabled();
  });

  it("실제 빈 연락처를 오류와 구분한다", async () => {
    vi.spyOn(consultantNoticeApi, "getSyntheticConsultantDashboardData").mockResolvedValue({ ...DATA, consultants: [], technicians: [] });
    renderPage();
    expect(await screen.findByText("등록된 직원 연락처가 없습니다.")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "전체 문의90" })).toBeVisible();
  });

  it("연락처 API 오류에도 문의 숫자를 유지하며 네트워크 안내와 재시도를 표시한다", async () => {
    const user = userEvent.setup();
    const getData = vi.spyOn(consultantNoticeApi, "getSyntheticConsultantDashboardData")
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockResolvedValue(DATA);
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("네트워크 연결을 확인한 뒤 다시 시도해 주세요.");
    expect(screen.queryByText("등록된 직원 연락처가 없습니다.")).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "전체 문의90" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(await screen.findByRole("table")).toBeVisible();
    expect(getData).toHaveBeenCalledTimes(2);
  });

  it.each([
    [401, "UNAUTHORIZED" as const, "로그인이 만료되어 직원 연락처를 볼 수 없습니다."],
    [403, "FORBIDDEN" as const, "직원 연락처를 볼 권한이 없습니다."],
  ])("연락처 API %i 응답을 권한 상태로 표시한다", async (status, kind, message) => {
    vi.spyOn(consultantNoticeApi, "getSyntheticConsultantDashboardData").mockRejectedValue(new ApiClientError({ kind, status, code: kind, message: kind }));
    renderPage();
    expect(await screen.findByText(message)).toBeVisible();
    expect(screen.queryByText("등록된 직원 연락처가 없습니다.")).not.toBeInTheDocument();
  });
});
