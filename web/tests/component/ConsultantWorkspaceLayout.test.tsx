import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/app/providers/AuthProvider";
import ConsultantWorkspaceLayout from "../../src/features/consultation/components/ConsultantWorkspaceLayout";

const AUTHENTICATED_CONSULTANT = {
  id: "00000000-0000-4000-8000-000000000102",
  displayName: "인증 세션 상담원",
  roleCode: "CONSULTANT" as const,
  isActive: true,
};

describe("ConsultantWorkspaceLayout", () => {
  it("Header 상담사 정보를 인증 세션 사용자와 일치시킨다", () => {
    render(
      <AuthProvider initialUser={AUTHENTICATED_CONSULTANT}>
        <ConsultantWorkspaceLayout
          notificationOpen={false}
          queueCount={0}
          onCloseNotifications={vi.fn()}
          onNavigate={vi.fn()}
          onToggleNotifications={vi.fn()}
        >
          <p>테스트 본문</p>
        </ConsultantWorkspaceLayout>
      </AuthProvider>,
    );

    const header = screen.getByRole("banner");
    const userChip = header.querySelector(".v6-user-chip");

    expect(userChip).not.toBeNull();
    expect(within(userChip as HTMLElement).getByText("인증 세션 상담원")).toBeVisible();
    expect(within(userChip as HTMLElement).getByText("인")).toBeVisible();
    expect(within(userChip as HTMLElement).getByText("상담원")).toBeVisible();
    expect(within(header).queryByText("한유진")).not.toBeInTheDocument();
    expect(within(header).queryByText("STAFF-CONS-01")).not.toBeInTheDocument();
  });
});
