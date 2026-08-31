import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "../../src/pages/auth/LoginPage";

const auth = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
}));

vi.mock("../../src/app/providers/authContext", () => ({
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    user: null,
    signInWithPassword: auth.signInWithPassword,
  }),
}));

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/consultant/inquiries"
          element={<h1>상담사 문의 목록</h1>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("상담사 로그인 입력", () => {
  beforeEach(() => {
    auth.signInWithPassword.mockReset();
    auth.signInWithPassword.mockResolvedValue({
      id: "synthetic-consultant",
      displayName: "합성 상담사",
      roleCode: "CONSULTANT",
      isActive: true,
    });
  });

  it.each([
    ["MiXeD-Staff", "MiXeD-password!"],
    ["lower-staff", "lower-password!"],
    ["UPPER-STAFF", "UPPER-PASSWORD!"],
  ])("입력한 대소문자 %s를 변경하지 않고 인증 함수에 전달한다", async (username, password) => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("사번"), username);
    await user.type(screen.getByLabelText("비밀번호"), password);
    await user.click(screen.getByRole("button", { name: "사번/비밀번호로 로그인" }));

    expect(auth.signInWithPassword).toHaveBeenCalledTimes(1);
    expect(auth.signInWithPassword).toHaveBeenCalledWith(username, password);
    expect(await screen.findByRole("heading", { name: "상담사 문의 목록" })).toBeVisible();
  });

  it("사번과 비밀번호에 자동 대문자·자동 교정·맞춤법 검사를 적용하지 않는다", () => {
    renderLogin();

    for (const label of ["사번", "비밀번호"]) {
      const input = screen.getByLabelText(label);
      expect(input).toHaveAttribute("autocapitalize", "none");
      expect(input).toHaveAttribute("autocorrect", "off");
      expect(input).toHaveAttribute("spellcheck", "false");
    }
  });

  it("서버 인증이 실패하면 입력 대소문자를 바꿔 재시도하거나 로그인 성공 처리하지 않는다", async () => {
    const user = userEvent.setup();
    auth.signInWithPassword.mockRejectedValue(new Error("Authentication rejected"));
    renderLogin();

    await user.type(screen.getByLabelText("사번"), "MiXeD-Staff");
    await user.type(screen.getByLabelText("비밀번호"), "Wrong-Password!");
    await user.click(screen.getByRole("button", { name: "사번/비밀번호로 로그인" }));

    expect(await screen.findByRole("alert"))
      .toHaveTextContent("사번 또는 비밀번호를 확인해 주세요.");
    expect(auth.signInWithPassword).toHaveBeenCalledTimes(1);
    expect(auth.signInWithPassword)
      .toHaveBeenCalledWith("MiXeD-Staff", "Wrong-Password!");
    expect(screen.getByLabelText("사번")).toHaveValue("MiXeD-Staff");
    expect(screen.queryByRole("heading", { name: "상담사 문의 목록" }))
      .not.toBeInTheDocument();
  });
});
