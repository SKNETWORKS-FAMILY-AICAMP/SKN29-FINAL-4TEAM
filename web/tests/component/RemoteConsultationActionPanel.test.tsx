import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RemoteConsultationActionPanel from "../../src/features/consultation/components/RemoteConsultationActionPanel";
import type { ConsultantInquiryDetailViewModel } from "../../src/features/consultation/model/consultantWorkspaceRemoteMapper";

const hookMocks = vi.hoisted(() => ({
  error: null as null | {
    correlationId?: string;
    kind: string;
    message: string;
  },
  execute: vi.fn(),
  success: null as null | {
    allowedActions: readonly unknown[];
    correlationId: string;
    message: string;
    stateVersion: number;
    status: string;
  },
}));

vi.mock(
  "../../src/features/consultation/hooks/useSaveConsultation",
  () => ({
    useSaveConsultation: (inquiry: {
      status: string;
      stateVersion: number;
      allowedActions: readonly unknown[];
    }) => ({
      isSaving: false,
      isWriteEnabled: true,
      success: hookMocks.success,
      error: hookMocks.error,
      currentStatus: inquiry.status,
      stateVersion: inquiry.stateVersion,
      allowedActions: inquiry.allowedActions,
      lastRefreshedAt: null,
      execute: hookMocks.execute,
    }),
  }),
);

function createDetail(
  stateVersion = 4,
): ConsultantInquiryDetailViewModel {
  const allowedActions = [
    {
      code: "UPDATE_CONSULTATION_SUMMARY",
      label: "상담 요약 수정",
      operationId: "updateConsultationSummary",
      style: "SECONDARY" as const,
      requiresConfirmation: false,
      confirmationMessage: null,
    },
    {
      code: "CONFIRM_CONSULTATION_SUMMARY",
      label: "상담 요약 확정",
      operationId: "confirmConsultationSummary",
      style: "PRIMARY" as const,
      requiresConfirmation: false,
      confirmationMessage: null,
    },
  ];

  return {
    inquiryId: "10000000-0000-4000-8000-000000000101",
    inquiryCode: "SYN-INQ-0101",
    status: "CONSULTATION_IN_PROGRESS",
    stateVersion,
    riskLevel: "caution",
    priority: "HIGH",
    receivedAt: "2026-08-13T01:00:00Z",
    updatedAt: "2026-08-13T01:10:00Z",
    customer: {
      isSynthetic: true,
      displayName: "합성고객 01",
      phone: "010-0000-0101",
    },
    productAndCare: null,
    symptomAndQuestionnaire: {
      symptomSummary: "출수량 감소",
      answers: [],
    },
    guidanceAndActions: {
      usageGuidanceStatus: "PENDING_CONSULTATION",
      usageGuidanceMessage: "상담 연결을 기다려 주세요.",
      restrictedFunctions: [],
    },
    consultation: null,
    visit: null,
    stateHistory: [],
    workflow: {
      status: "CONSULTATION_IN_PROGRESS",
      stateVersion,
      allowedActions,
    },
    sectionErrors: [],
  };
}

describe("Remote 상담 처리 Panel", () => {
  beforeEach(() => {
    hookMocks.error = null;
    hookMocks.execute.mockReset();
    hookMocks.execute.mockResolvedValue({ ok: true });
    hookMocks.success = null;
  });

  it("요약 확정 입력을 제공하고 동일 문의 재조회에도 작성 내용을 유지한다", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    const { rerender } = render(
      <RemoteConsultationActionPanel
        inquiry={createDetail()}
        onOpenVisit={vi.fn()}
        onRefresh={onRefresh}
      />,
    );

    await user.type(screen.getByLabelText("상담 기록"), "고객 상태 확인");
    await user.type(screen.getByLabelText("확정 요약"), "필터 체결 안내 완료");
    await user.click(screen.getByRole("checkbox", { name: "상담 요약 검토·확정" }));

    expect(
      screen.getByTestId("consultation-field-consultationNote"),
    ).toHaveValue("고객 상태 확인");

    rerender(
      <RemoteConsultationActionPanel
        inquiry={createDetail(5)}
        onOpenVisit={vi.fn()}
        onRefresh={onRefresh}
      />,
    );

    expect(screen.getByLabelText("상담 기록")).toHaveValue("고객 상태 확인");
    expect(screen.getByLabelText("확정 요약")).toHaveValue("필터 체결 안내 완료");
    expect(
      screen.getByRole("checkbox", { name: "상담 요약 검토·확정" }),
    ).toBeChecked();

    await user.click(screen.getByRole("button", { name: "상담 요약 확정" }));

    expect(hookMocks.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        action: expect.objectContaining({ code: "CONFIRM_CONSULTATION_SUMMARY" }),
        values: expect.objectContaining({
          consultationNote: "고객 상태 확인",
          summaryRevision: "필터 체결 안내 완료",
          summaryConfirmed: true,
        }),
      }),
    );
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("409 충돌 재조회에도 작성 중인 상담 기록을 유지한다", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    hookMocks.execute.mockResolvedValue({
      ok: false,
      error: {
        kind: "CONFLICT",
        conflictCode: "STATE-CONFLICT-01",
        message: "상태가 변경되었습니다.",
      },
    });
    const { rerender } = render(
      <RemoteConsultationActionPanel
        inquiry={createDetail()}
        onOpenVisit={vi.fn()}
        onRefresh={onRefresh}
      />,
    );

    await user.type(screen.getByLabelText("상담 기록"), "충돌 전 작성 기록");
    await user.click(screen.getByRole("button", { name: "상담 요약 수정" }));

    expect(onRefresh).toHaveBeenCalledTimes(1);

    rerender(
      <RemoteConsultationActionPanel
        inquiry={createDetail(5)}
        onOpenVisit={vi.fn()}
        onRefresh={onRefresh}
      />,
    );
    expect(screen.getByLabelText("상담 기록")).toHaveValue("충돌 전 작성 기록");
  });

  it("브라우저 재진입 시 서버 상담 기록으로 완료 Form을 복구한다", () => {
    const inquiry = createDetail(6);
    inquiry.consultation = {
      consultationId: "30000000-0000-4000-8000-000000000301",
      resultCode: "COMPLETED_NO_VISIT",
      summary: {
        aiDraftSummary: "AI 초안",
        editedSummary: "상담사 수정 요약",
        confirmedSummary: "확정 상담 요약",
        confirmedAt: "2026-08-13T11:20:00+09:00",
      },
      consultationNote: "저장된 상담 기록",
      additionalCheck: "저장된 추가 확인",
      customerGuidance: "저장된 고객 안내",
      usageGuidanceStatus: "NORMAL",
    };

    render(
      <RemoteConsultationActionPanel
        inquiry={inquiry}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("상담 기록")).toHaveValue("저장된 상담 기록");
    expect(screen.getByLabelText("확정 요약")).toHaveValue("확정 상담 요약");
    expect(
      screen.getByRole("checkbox", { name: "상담 요약 검토·확정" }),
    ).toBeChecked();
    expect(screen.getByLabelText("방문 필요 여부")).toHaveValue("NOT_REQUIRED");
    expect(screen.getByLabelText("사용 안내 상태")).toHaveValue("NORMAL");
    expect(screen.queryByLabelText("상담 결과")).not.toBeInTheDocument();
  });

  it("저장되지 않는 상담 결과 텍스트 없이 result_code 선택으로 완료한다", async () => {
    const user = userEvent.setup();
    const inquiry = createDetail(7);
    inquiry.workflow.allowedActions = [
      {
        code: "UPDATE_CONSULTATION_SUMMARY",
        label: "상담 요약 수정",
        operationId: "updateConsultationSummary",
        style: "SECONDARY",
        requiresConfirmation: false,
        confirmationMessage: null,
      },
      {
        code: "CONSULTATION_COMPLETED",
        label: "상담 처리 완료",
        operationId: "completeConsultation",
        style: "PRIMARY",
        requiresConfirmation: false,
        confirmationMessage: null,
      },
    ];

    render(
      <RemoteConsultationActionPanel
        inquiry={inquiry}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText("상담 결과")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("상담 기록"), "고객 상태 확인");
    await user.type(screen.getByLabelText("고객 안내"), "전체 사용 중지를 안내함");
    await user.selectOptions(screen.getByLabelText("방문 필요 여부"), "NOT_REQUIRED");
    await user.click(
      screen.getByRole("checkbox", { name: "상담 요약 검토·확정" }),
    );
    await user.click(screen.getByRole("button", { name: "상담 처리 완료" }));

    expect(hookMocks.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        action: expect.objectContaining({ code: "CONSULTATION_COMPLETED" }),
        values: expect.objectContaining({
          consultationResult: "",
          visitRequired: "NOT_REQUIRED",
        }),
      }),
    );
  });

  it("처리 성공과 오류의 확인 번호를 상담사에게 표시한다", () => {
    hookMocks.success = {
      allowedActions: [],
      correlationId: "corr-action-success",
      message: "상담 요약을 저장했습니다.",
      stateVersion: 8,
      status: "CONSULTATION_IN_PROGRESS",
    };

    const { rerender } = render(
      <RemoteConsultationActionPanel
        inquiry={createDetail()}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "확인 번호: corr-action-success",
    );
    expect(screen.getByRole("status")).toHaveTextContent("상태 버전 8");

    hookMocks.success = null;
    hookMocks.error = {
      correlationId: "corr-action-conflict",
      kind: "CONFLICT",
      message: "문의 상태가 변경되었습니다.",
    };
    rerender(
      <RemoteConsultationActionPanel
        inquiry={createDetail()}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "확인 번호: corr-action-conflict",
    );
  });
});
