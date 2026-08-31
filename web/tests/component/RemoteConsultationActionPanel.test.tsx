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
      phoneDisplay: "010-****-0101",
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

function createStoredDetail(stateVersion = 4): ConsultantInquiryDetailViewModel {
  return {
    ...createDetail(stateVersion),
    consultation: {
      consultationId: "30000000-0000-4000-8000-000000000301",
      resultCode: "PENDING",
      summary: {
        aiDraftSummary: null,
        editedSummary: "이전 서버 요약",
        confirmedSummary: null,
        confirmedAt: null,
      },
      consultationNote: "화면의 상담 기록",
      customerGuidance: "화면의 상담 기록",
      additionalCheck: "화면의 상담 기록",
      usageGuidanceStatus: "PENDING_CONSULTATION",
    },
  };
}

describe("Remote 상담 처리 Panel", () => {
  beforeEach(() => {
    hookMocks.error = null;
    hookMocks.execute.mockReset();
    hookMocks.execute.mockResolvedValue({ ok: true });
    hookMocks.success = null;
  });

  it("상담 기록은 수정 버튼으로 열고 저장하면 다시 잠기며 확정 시 실제 상태를 전달한다", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    const onSummaryConfirmed = vi.fn();
    hookMocks.execute.mockResolvedValue({ ok: true, result: { status: "CONSULTATION_IN_PROGRESS", stateVersion: 6 } });
    const { rerender } = render(
      <RemoteConsultationActionPanel
        inquiry={createDetail()}
        onOpenVisit={vi.fn()}
        onRefresh={onRefresh}
        onSummaryConfirmed={onSummaryConfirmed}
      />,
    );

    expect(screen.getByLabelText("상담 기록")).toBeDisabled();
    await user.type(screen.getByLabelText("상담 기록"), "비활성 입력");
    expect(screen.getByLabelText("상담 기록")).toHaveValue("");
    expect(screen.queryByLabelText("상담 내용 수정본")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    expect(screen.getByLabelText("상담 기록")).toBeEnabled();
    await user.type(screen.getByLabelText("상담 기록"), "고객 상태 확인");
    expect(screen.getByRole("button", { name: "상담 내용 확정" })).toBeDisabled();

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
        onSummaryConfirmed={onSummaryConfirmed}
      />,
    );

    expect(screen.getByLabelText("상담 기록")).toHaveValue("고객 상태 확인");
    expect(screen.getByLabelText("상담 기록")).toBeEnabled();
    expect(screen.queryByText("상담 요약 확인")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));
    expect(screen.getByLabelText("상담 기록")).toBeDisabled();
    expect(onSummaryConfirmed).not.toHaveBeenCalled();
    expect(hookMocks.execute).toHaveBeenLastCalledWith(expect.objectContaining({
      action: expect.objectContaining({ code: "UPDATE_CONSULTATION_SUMMARY" }),
      values: expect.objectContaining({
        consultationNote: "고객 상태 확인", summaryRevision: "고객 상태 확인",
        customerGuidance: "고객 상태 확인", additionalCheck: "고객 상태 확인",
      }),
    }));
    await user.click(screen.getByRole("button", { name: "상담 내용 확정" }));

    expect(hookMocks.execute).toHaveBeenCalledWith(
      expect.objectContaining({
        action: expect.objectContaining({ code: "CONFIRM_CONSULTATION_SUMMARY" }),
        values: expect.objectContaining({
          consultationNote: "고객 상태 확인",
          customerGuidance: "고객 상태 확인",
          additionalCheck: "고객 상태 확인",
          summaryRevision: "고객 상태 확인",
          summaryConfirmed: true,
        }),
      }),
    );
    expect(onRefresh).toHaveBeenCalledTimes(2);
    expect(onSummaryConfirmed).toHaveBeenCalledWith("CONSULTATION_IN_PROGRESS");
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

    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.type(screen.getByLabelText("상담 기록"), "충돌 전 작성 기록");
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
    expect(screen.getByLabelText("상담 기록")).toBeEnabled();
  });

  it("서버 요약과 다른 세 원문을 보존하고 무타이핑 저장 후 재마운트 없이 확정한다", async () => {
    const user = userEvent.setup();
    const inquiry = createStoredDetail();
    inquiry.consultation!.customerGuidance = "기존 고객 안내 원문";
    inquiry.consultation!.additionalCheck = "기존 추가 확인 원문";
    const expectedRecord = [
      "상담 기록", "화면의 상담 기록", "", "고객 안내 내용", "기존 고객 안내 원문",
      "", "추가 확인사항", "기존 추가 확인 원문",
    ].join("\n");
    const onSummaryConfirmed = vi.fn();
    hookMocks.execute
      .mockResolvedValueOnce({ ok: true, result: { status: "CONSULTATION_IN_PROGRESS", stateVersion: 5 } })
      .mockResolvedValueOnce({ ok: true, result: { status: "CONSULTATION_IN_PROGRESS", stateVersion: 6 } });
    render(<RemoteConsultationActionPanel inquiry={inquiry} onOpenVisit={vi.fn()} onRefresh={vi.fn()} onSummaryConfirmed={onSummaryConfirmed} />);
    const confirm = screen.getByRole("button", { name: "상담 내용 확정" });
    const record = screen.getByLabelText("상담 기록");

    expect(record).toHaveValue(expectedRecord);
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAccessibleDescription(/현재 상담 기록을 저장/);
    await user.click(confirm);
    expect(hookMocks.execute).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));

    expect(hookMocks.execute).toHaveBeenNthCalledWith(1, expect.objectContaining({
      action: expect.objectContaining({ code: "UPDATE_CONSULTATION_SUMMARY" }),
      values: expect.objectContaining({
        consultationNote: expectedRecord, customerGuidance: expectedRecord,
        additionalCheck: expectedRecord, summaryRevision: expectedRecord,
      }),
    }));
    expect(record).toBeDisabled();
    expect(confirm).toBeEnabled();
    expect(screen.queryByText(/현재 상담 기록을 저장해 주세요/)).not.toBeInTheDocument();
    expect(onSummaryConfirmed).not.toHaveBeenCalled();
    await user.click(confirm);
    expect(onSummaryConfirmed).toHaveBeenCalledExactlyOnceWith("CONSULTATION_IN_PROGRESS");
  });

  it.each([
    ["저장 실패", { ok: false, error: { kind: "NETWORK_ERROR", message: "네트워크 오류" } }],
    ["저장 취소", { ok: false, cancelled: true }],
  ])("%s 시 수정 원문과 저장 필요 상태를 유지하고 이동하지 않는다", async (_name, outcome) => {
    const user = userEvent.setup();
    const onSummaryConfirmed = vi.fn();
    const onRefresh = vi.fn();
    hookMocks.execute.mockResolvedValue(outcome);
    render(<RemoteConsultationActionPanel inquiry={createStoredDetail()} onOpenVisit={vi.fn()} onRefresh={onRefresh} onSummaryConfirmed={onSummaryConfirmed} />);

    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));
    expect(screen.getByLabelText("상담 기록")).toHaveValue("화면의 상담 기록");
    expect(screen.getByLabelText("상담 기록")).toBeEnabled();
    expect(screen.getByText(/현재 상담 기록을 저장해 주세요/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "상담 내용 확정" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "상담 내용 확정" }));
    expect(hookMocks.execute).toHaveBeenCalledTimes(1);
    expect(onSummaryConfirmed).not.toHaveBeenCalled();
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("AI 초안만 있으면 서버 저장 전에는 확정할 수 없다", async () => {
    const user = userEvent.setup();
    const inquiry = createStoredDetail();
    inquiry.consultation!.consultationNote = "";
    inquiry.consultation!.customerGuidance = "";
    inquiry.consultation!.additionalCheck = "";
    inquiry.consultation!.summary.editedSummary = null;
    inquiry.consultation!.summary.aiDraftSummary = "AI가 생성한 초안";
    hookMocks.execute.mockResolvedValue({ ok: true, result: { status: "CONSULTATION_IN_PROGRESS", stateVersion: 5 } });
    render(<RemoteConsultationActionPanel inquiry={inquiry} onOpenVisit={vi.fn()} onRefresh={vi.fn()} />);

    expect(screen.getByLabelText("상담 기록")).toHaveValue("AI가 생성한 초안");
    expect(screen.getByRole("button", { name: "상담 내용 확정" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));
    expect(hookMocks.execute).toHaveBeenCalledWith(expect.objectContaining({ values: expect.objectContaining({ summaryRevision: "AI가 생성한 초안" }) }));
    expect(screen.getByRole("button", { name: "상담 내용 확정" })).toBeEnabled();
  });

  it("서버의 현재 수정 요약이 기록과 같으면 과거 확정본보다 우선해 바로 확정할 수 있다", () => {
    const inquiry = createStoredDetail();
    inquiry.consultation!.summary.editedSummary = "화면의 상담 기록";
    inquiry.consultation!.summary.confirmedSummary = "과거 확정본";
    render(<RemoteConsultationActionPanel inquiry={inquiry} onOpenVisit={vi.fn()} onRefresh={vi.fn()} />);
    expect(screen.getByRole("button", { name: "상담 내용 확정" })).toBeEnabled();
    expect(screen.queryByText(/현재 상담 기록을 저장해 주세요/)).not.toBeInTheDocument();
  });

  it("저장 후 더 최신 서버 요약이 달라지면 이전 저장 성공만으로 확정하지 않는다", async () => {
    const user = userEvent.setup();
    hookMocks.execute.mockResolvedValue({ ok: true, result: { status: "CONSULTATION_IN_PROGRESS", stateVersion: 5 } });
    const { rerender } = render(<RemoteConsultationActionPanel inquiry={createStoredDetail()} onOpenVisit={vi.fn()} onRefresh={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));
    expect(screen.getByRole("button", { name: "상담 내용 확정" })).toBeEnabled();

    const refreshed = createStoredDetail(6);
    refreshed.consultation!.summary.editedSummary = "다른 상담사가 이후 저장한 요약";
    rerender(<RemoteConsultationActionPanel inquiry={refreshed} onOpenVisit={vi.fn()} onRefresh={vi.fn()} />);
    expect(screen.getByLabelText("상담 기록")).toHaveValue("화면의 상담 기록");
    expect(screen.getByRole("button", { name: "상담 내용 확정" })).toBeDisabled();
    expect(screen.getByText(/현재 상담 기록을 저장해 주세요/)).toBeInTheDocument();
  });

  it.each(["VISIT_REVIEW_REQUIRED", "VISIT_NEEDED"])("숨긴 %s만 남아도 빈 화면 대신 안내한다", (code) => {
    const inquiry = createDetail();
    inquiry.workflow.allowedActions = [{
      code, label: "방문 검토", operationId: "visitReview", style: "PRIMARY",
      requiresConfirmation: false, confirmationMessage: null,
    }];
    render(<RemoteConsultationActionPanel inquiry={inquiry} onOpenVisit={vi.fn()} onRefresh={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /방문/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("상담 기록")).not.toBeInTheDocument();
    expect(screen.getByText("현재 진행할 상담 작업이 없습니다.")).toBeInTheDocument();
  });

  it("저장 폼 없는 상담 시작은 요약 저장 가드에 영향받지 않는다", async () => {
    const user = userEvent.setup();
    const inquiry = createDetail();
    inquiry.workflow.allowedActions = [{
      code: "START_CONSULTATION", label: "상담 시작", operationId: "startConsultation", style: "PRIMARY",
      requiresConfirmation: false, confirmationMessage: null,
    }];
    render(<RemoteConsultationActionPanel inquiry={inquiry} onOpenVisit={vi.fn()} onRefresh={vi.fn()} />);
    expect(screen.getByRole("button", { name: "상담 시작" })).toBeEnabled();
    expect(screen.queryByText(/현재 상담 기록을 저장해 주세요/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "상담 시작" }));
    expect(hookMocks.execute).toHaveBeenCalledWith(expect.objectContaining({ action: expect.objectContaining({ code: "START_CONSULTATION" }) }));
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
    expect(screen.queryByLabelText("상담 내용 수정본")).not.toBeInTheDocument();
    expect(screen.getByLabelText("상담 기록")).toBeDisabled();
    expect(screen.getByLabelText("방문 필요 여부")).toHaveTextContent("방문 불필요");
    expect(screen.getByLabelText("제품 사용 상태")).toHaveTextContent("정상 사용 가능");
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
    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.clear(screen.getByLabelText("상담 기록"));
    await user.type(screen.getByLabelText("상담 기록"), "고객 상태 확인");
    await user.click(screen.getByLabelText("방문 필요 여부"));
    await user.click(screen.getByRole("option", { name: "방문 불필요" }));
    await user.click(screen.getByRole("button", { name: "수정 내용 저장" }));
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

    await user.click(screen.getByRole("button", { name: "상담 내용 수정" }));
    await user.type(screen.getByLabelText("상담 기록"), "필터 상태 확인");
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
