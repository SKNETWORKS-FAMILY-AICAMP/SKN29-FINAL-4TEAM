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
      phoneMasked: "010-****-0101",
    },
    productAndCare: null,
    symptomAndQuestionnaire: {
      symptomSummary: "출수량 감소",
      answers: [],
    },
    guidanceAndActions: {
      usageGuidanceStatus: "PENDING_CONSULTATION",
      usageGuidanceDisplayLabel: "상담 확인 필요",
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
    expect(screen.getByLabelText("상담 내용 수정본")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.type(
      screen.getByLabelText("상담 내용 수정본"),
      "필터 체결 안내 완료",
    );

    expect(screen.queryByLabelText("고객 안내 내용")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("추가 확인사항")).not.toBeInTheDocument();
    expect(screen.queryByText("추가 확인사항 입력")).not.toBeInTheDocument();
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
    expect(screen.getByLabelText("상담 내용 수정본")).toHaveValue(
      "필터 체결 안내 완료",
    );
    expect(screen.queryByText("상담 요약 확인")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "상담 내용 확정" }));

    expect(hookMocks.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        action: expect.objectContaining({ code: "CONFIRM_CONSULTATION_SUMMARY" }),
        values: expect.objectContaining({
          consultationNote: "고객 상태 확인",
          customerGuidance: "고객 상태 확인",
          additionalCheck: "고객 상태 확인",
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
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));

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

    expect(screen.getByLabelText("상담 기록")).toHaveValue(
      [
        "상담 기록",
        "저장된 상담 기록",
        "",
        "고객 안내 내용",
        "저장된 고객 안내",
        "",
        "추가 확인사항",
        "저장된 추가 확인",
      ].join("\n"),
    );
    expect(screen.getByLabelText("상담 내용 수정본")).toHaveValue(
      "확정 상담 요약",
    );
    expect(screen.getByLabelText("상담 내용 수정본")).toBeDisabled();
    expect(screen.getByLabelText("방문 필요 여부")).toHaveValue("NOT_REQUIRED");
    expect(screen.getByLabelText("제품 사용 상태")).toHaveValue("NORMAL");
    expect(screen.queryByLabelText("상담 결과")).not.toBeInTheDocument();
  });

  it("기존 세 필드의 서로 다른 내용만 단일 상담 기록에 중복 없이 합친다", () => {
    const inquiry = createDetail(6);
    inquiry.consultation = {
      consultationId: "30000000-0000-4000-8000-000000000301",
      resultCode: "PENDING",
      summary: {
        aiDraftSummary: null,
        editedSummary: null,
        confirmedSummary: null,
        confirmedAt: null,
      },
      consultationNote: "필터 상태 확인",
      customerGuidance: "필터 상태 확인",
      additionalCheck: "급수 밸브 재확인",
      usageGuidanceStatus: "PENDING_CONSULTATION",
    };

    render(
      <RemoteConsultationActionPanel
        inquiry={inquiry}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("상담 기록")).toHaveValue(
      [
        "상담 기록",
        "필터 상태 확인",
        "",
        "추가 확인사항",
        "급수 밸브 재확인",
      ].join("\n"),
    );
  });

  it("저장되지 않는 상담 결과 텍스트 없이 result_code 선택으로 완료한다", async () => {
    const user = userEvent.setup();
    const inquiry = createDetail(7);
    inquiry.consultation = {
      consultationId: "30000000-0000-4000-8000-000000000307",
      resultCode: "COMPLETED_NO_VISIT",
      summary: {
        aiDraftSummary: "AI 초안",
        editedSummary: "상담사 수정 요약",
        confirmedSummary: "확정 상담 요약",
        confirmedAt: "2026-08-13T11:20:00+09:00",
      },
      consultationNote: "",
      additionalCheck: "",
      customerGuidance: "",
      usageGuidanceStatus: "NORMAL",
    };
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
    await user.selectOptions(screen.getByLabelText("방문 필요 여부"), "NOT_REQUIRED");
    await user.click(screen.getByRole("button", { name: "상담 처리 완료" }));

    expect(hookMocks.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        action: expect.objectContaining({ code: "CONSULTATION_COMPLETED" }),
        values: expect.objectContaining({
          consultationNote: "고객 상태 확인",
          customerGuidance: "고객 상태 확인",
          additionalCheck: "고객 상태 확인",
          consultationResult: "",
          visitRequired: "NOT_REQUIRED",
        }),
      }),
    );
  });

  it("정상 성공은 업무 결과만, 오류는 확인 번호와 함께 표시한다", () => {
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
      "상담 요약을 저장했습니다.",
    );
    expect(screen.getByRole("status")).not.toHaveTextContent(
      "corr-action-success",
    );
    expect(screen.getByRole("status")).not.toHaveTextContent("상태 버전");

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

  it("확인 팝업 처리를 저장 Hook에 위임해 Component에서 중복 실행하지 않는다", async () => {
    const user = userEvent.setup();
    const inquiry = createDetail();
    inquiry.workflow.allowedActions = [
      {
        code: "UPDATE_CONSULTATION_SUMMARY",
        label: "상담 요약 수정",
        operationId: "updateConsultationSummary",
        style: "PRIMARY",
        requiresConfirmation: true,
        confirmationMessage: "상담 내용을 저장하시겠습니까?",
      },
    ];
    const confirmPrompt = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <RemoteConsultationActionPanel
        inquiry={inquiry}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText("상담 기록"), "필터 상태 확인");
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));

    expect(confirmPrompt).not.toHaveBeenCalled();
    expect(hookMocks.execute).toHaveBeenCalledTimes(1);
  });

  it("상담 처리용 내부 상태와 버전은 화면 문구로 노출하지 않는다", () => {
    render(
      <RemoteConsultationActionPanel
        inquiry={createDetail()}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.queryByText("현재 할 일")).not.toBeInTheDocument();
    expect(screen.queryByText(/현재 상태 ·/)).not.toBeInTheDocument();
    expect(screen.queryByText(/COUNSEL DESK/)).not.toBeInTheDocument();
    expect(screen.queryByText(/currentStatus/)).not.toBeInTheDocument();
    expect(screen.queryByText(/stateVersion/)).not.toBeInTheDocument();
    expect(screen.getByTestId("consultation-current-status")).toHaveAttribute(
      "data-workflow-status",
      "CONSULTATION_IN_PROGRESS",
    );
  });

  it("Backend가 허용한 문의 최종 완료 Action을 실행한다", async () => {
    const user = userEvent.setup();
    const inquiry = createDetail(8);
    inquiry.status = "COMPLETION_PENDING";
    inquiry.workflow = {
      status: "COMPLETION_PENDING",
      stateVersion: 8,
      allowedActions: [
        {
          code: "FINALIZE_INQUIRY",
          label: "문의 최종 완료",
          operationId: "finalizeInquiry",
          style: "PRIMARY",
          requiresConfirmation: true,
          confirmationMessage: "고객 해결 확인 후 문의를 완료하시겠습니까?",
        },
      ],
    };
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <RemoteConsultationActionPanel
        inquiry={inquiry}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "문의 최종 완료" }));

    expect(hookMocks.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        action: expect.objectContaining({ code: "FINALIZE_INQUIRY" }),
      }),
    );
  });

  it("Backend가 허용한 재개 문의를 상담 대기열 복귀 Action으로 실행한다", async () => {
    const user = userEvent.setup();
    const inquiry = createDetail(13);
    inquiry.status = "REOPENED";
    inquiry.workflow = {
      status: "REOPENED",
      stateVersion: 13,
      allowedActions: [
        {
          code: "RESUME_CONSULTATION",
          label: "상담 대기열로 복귀",
          operationId: "resumeConsultation",
          style: "PRIMARY",
          requiresConfirmation: false,
          confirmationMessage: null,
        },
      ],
    };

    render(
      <RemoteConsultationActionPanel
        inquiry={inquiry}
        onOpenVisit={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "상담 대기열로 복귀" }),
    );

    expect(hookMocks.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        action: expect.objectContaining({ code: "RESUME_CONSULTATION" }),
      }),
    );
  });
});
