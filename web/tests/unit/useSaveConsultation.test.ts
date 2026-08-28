import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as consultationApi from "../../src/features/consultation/api/consultationMockApi";
import { ApiClientError } from "../../src/common/api/apiError";
import { useSaveConsultation } from "../../src/features/consultation/hooks/useSaveConsultation";
import { COUNSELOR_INQUIRIES } from "../fixtures/consultantWorkspaceMock";
import type { ConsultationFormValues } from "../../src/features/consultation/model/consultationTypes";
import type { ConsultationWriteRepository } from "../../src/features/consultation/repositories/consultationWriteRepository";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useSaveConsultation", () => {
  it("omits a blank summary for a valid note-only remote save", async () => {
    const inquiry = COUNSELOR_INQUIRIES.find((item) =>
      item.allowedActions.some((action) => action.code === "UPDATE_CONSULTATION_SUMMARY"),
    );
    if (!inquiry) throw new Error("Updateable consultation fixture is missing.");
    const action = inquiry.allowedActions.find(
      (item) => item.code === "UPDATE_CONSULTATION_SUMMARY",
    );
    if (!action) throw new Error("Update consultation action is missing.");

    const saveSummary = vi.fn().mockResolvedValue({
      success: true,
      data: {
        message: "Saved",
        inquiry_id: inquiry.inquiryId,
        status: "CONSULTATION_IN_PROGRESS",
        state_version: inquiry.stateVersion + 1,
        allowed_actions: [],
        idempotent_replay: false,
        resource: null,
      },
      error: null,
      metadata: { correlation_id: "corr-note-only" },
    });
    const repository = {
      start: vi.fn(), saveSummary, confirmSummary: vi.fn(), complete: vi.fn(),
    } as ConsultationWriteRepository;
    const values: ConsultationFormValues = {
      consultationNote: "Customer condition checked",
      additionalCheck: "",
      customerGuidance: "",
      consultationResult: "",
      summaryRevision: "   ",
      summaryConfirmed: false,
      visitRequired: "UNDECIDED",
      usageStatus: inquiry.usageStatus,
    };
    const { result } = renderHook(() => useSaveConsultation(inquiry, {
      dataSource: "REMOTE", remoteRepository: repository,
    }));

    await act(async () => {
      await result.current.execute({ action, values, scenario: "SUCCESS" });
    });

    expect(saveSummary).toHaveBeenCalledWith(
      inquiry.inquiryId,
      expect.objectContaining({
        state_version: inquiry.stateVersion,
        consultation_note: "Customer condition checked",
      }),
      expect.any(Object),
    );
    expect(saveSummary.mock.calls[0]?.[1]).not.toHaveProperty("summary");
  });

  it("Remote 상담 요약 저장은 공개 DTO 필드와 현재 state_version만 전송한다", async () => {
    const inquiry = COUNSELOR_INQUIRIES.find((item) =>
      item.allowedActions.some((action) => action.code === "UPDATE_CONSULTATION_SUMMARY"),
    );
    if (!inquiry) throw new Error("상담 저장 fixture가 없습니다.");
    const action = inquiry.allowedActions.find((item) => item.code === "UPDATE_CONSULTATION_SUMMARY");
    if (!action) throw new Error("상담 저장 action이 없습니다.");
    const saveSummary = vi.fn().mockResolvedValue({
      success: true,
      data: {
        message: "저장 완료",
        inquiry_id: inquiry.inquiryId,
        status: "CONSULTATION_IN_PROGRESS",
        state_version: inquiry.stateVersion + 1,
        allowed_actions: [],
        idempotent_replay: false,
      },
      error: null,
      metadata: { correlation_id: "corr-remote" },
    });
    const repository = {
      start: vi.fn(), saveSummary, confirmSummary: vi.fn(), complete: vi.fn(),
    } as ConsultationWriteRepository;
    const values: ConsultationFormValues = {
      consultationNote: " 상담 기록 ", additionalCheck: " 추가 확인 ",
      customerGuidance: " 고객 안내 ", consultationResult: "처리 중",
      summaryRevision: " 확정 요약 ", summaryConfirmed: false,
      visitRequired: "NOT_REQUIRED", usageStatus: "NORMAL",
    };
    const { result } = renderHook(() => useSaveConsultation(inquiry, {
      dataSource: "REMOTE", remoteRepository: repository,
    }));

    await act(async () => { await result.current.execute({ action, values, scenario: "SUCCESS" }); });

    expect(saveSummary).toHaveBeenCalledWith(
      inquiry.inquiryId,
      {
        state_version: inquiry.stateVersion,
        summary: "확정 요약",
        consultation_note: "상담 기록",
        additional_check: "추가 확인",
        customer_guidance: "고객 안내",
        result_code: "COMPLETED_NO_VISIT",
        usage_guidance_status: "NORMAL",
      },
      expect.objectContaining({ idempotencyKey: expect.any(String) }),
    );
    expect(result.current.stateVersion).toBe(inquiry.stateVersion + 1);
  });

  it("Remote 409 충돌 시 최신 버전을 반영하고 성공으로 오인하지 않는다", async () => {
    const inquiry = COUNSELOR_INQUIRIES.find((item) =>
      item.allowedActions.some((action) => action.code === "START_CONSULTATION"),
    );
    if (!inquiry) throw new Error("상담 시작 fixture가 없습니다.");
    const action = inquiry.allowedActions.find((item) => item.code === "START_CONSULTATION");
    if (!action) throw new Error("상담 시작 action이 없습니다.");
    const start = vi.fn().mockRejectedValue(new ApiClientError({
      kind: "CONFLICT", status: 409, code: "STATE-CONFLICT-01",
      message: "상태가 변경되었습니다.", correlationId: "corr-conflict",
      details: {
        current_status: "CONSULTATION_IN_PROGRESS",
        current_state_version: inquiry.stateVersion + 2,
        allowed_actions: [],
      },
    }));
    const repository = {
      start, saveSummary: vi.fn(), confirmSummary: vi.fn(), complete: vi.fn(),
    } as ConsultationWriteRepository;
    const values: ConsultationFormValues = {
      consultationNote: "", additionalCheck: "", customerGuidance: "",
      consultationResult: "", summaryRevision: "", summaryConfirmed: false,
      visitRequired: "UNDECIDED", usageStatus: inquiry.usageStatus,
    };
    const { result } = renderHook(() => useSaveConsultation(inquiry, {
      dataSource: "REMOTE", remoteRepository: repository,
    }));

    await act(async () => { await result.current.execute({ action, values, scenario: "SUCCESS" }); });

    expect(result.current.success).toBeNull();
    expect(result.current.error).toMatchObject({ kind: "CONFLICT", conflictCode: "STATE-CONFLICT-01" });
    expect(result.current.stateVersion).toBe(inquiry.stateVersion + 2);
  });

  it("Remote 상담 시작부터 저장·확정·완료까지 서버 최신 state_version을 이어 쓴다", async () => {
    const inquiry = COUNSELOR_INQUIRIES.find((item) =>
      item.allowedActions.some((action) => action.code === "START_CONSULTATION"),
    );
    if (!inquiry) throw new Error("상담 시작 fixture가 없습니다.");
    const startAction = inquiry.allowedActions.find(
      (action) => action.code === "START_CONSULTATION",
    );
    if (!startAction) throw new Error("상담 시작 action이 없습니다.");

    const updateActionDto = {
      code: "UPDATE_CONSULTATION_SUMMARY",
      label: "상담 요약 수정",
      operation_id: "updateConsultationSummary",
      style: "SECONDARY" as const,
      requires_confirmation: false,
      confirmation_message: null,
    };
    const confirmActionDto = {
      code: "CONFIRM_CONSULTATION_SUMMARY",
      label: "상담 요약 확정",
      operation_id: "confirmConsultationSummary",
      style: "PRIMARY" as const,
      requires_confirmation: true,
      confirmation_message: "상담 요약을 확정하시겠습니까?",
    };
    const completeActionDto = {
      code: "CONSULTATION_COMPLETED",
      label: "상담 처리 완료",
      operation_id: "completeConsultation",
      style: "PRIMARY" as const,
      requires_confirmation: true,
      confirmation_message: "상담 처리를 완료하시겠습니까?",
    };
    const response = (
      stateVersion: number,
      allowedActions: Array<
        typeof updateActionDto | typeof confirmActionDto | typeof completeActionDto
      >,
      status: "CONSULTATION_IN_PROGRESS" | "COMPLETION_PENDING" =
        "CONSULTATION_IN_PROGRESS",
    ) => ({
      success: true as const,
      data: {
        message: "처리 완료",
        inquiry_id: inquiry.inquiryId,
        status,
        state_version: stateVersion,
        allowed_actions: allowedActions,
        idempotent_replay: false,
      },
      error: null,
      metadata: { correlation_id: `corr-${stateVersion}` },
    });
    const start = vi.fn().mockResolvedValue(
      response(inquiry.stateVersion + 1, [updateActionDto]),
    );
    const saveSummary = vi.fn().mockResolvedValue(
      response(inquiry.stateVersion + 2, [updateActionDto, confirmActionDto]),
    );
    const confirmSummary = vi.fn().mockResolvedValue(
      response(inquiry.stateVersion + 3, [updateActionDto, completeActionDto]),
    );
    const complete = vi.fn().mockResolvedValue(
      response(inquiry.stateVersion + 4, [], "COMPLETION_PENDING"),
    );
    const repository = {
      start,
      saveSummary,
      confirmSummary,
      complete,
    } as ConsultationWriteRepository;
    const values: ConsultationFormValues = {
      consultationNote: "고객 상태 확인",
      additionalCheck: "필터 체결 확인",
      customerGuidance: "정상 사용 안내",
      consultationResult: "방문 없이 해결",
      summaryRevision: "상담 확정 요약",
      summaryConfirmed: true,
      visitRequired: "NOT_REQUIRED",
      usageStatus: "NORMAL",
    };
    const confirmPrompt = vi.spyOn(window, "confirm").mockReturnValue(true);
    const { result } = renderHook(() =>
      useSaveConsultation(inquiry, {
        dataSource: "REMOTE",
        remoteRepository: repository,
      }),
    );

    await act(async () => {
      await result.current.execute({ action: startAction, values, scenario: "SUCCESS" });
    });
    const updateAction = result.current.allowedActions.find(
      (action) => action.code === "UPDATE_CONSULTATION_SUMMARY",
    );
    if (!updateAction) throw new Error("상담 저장 action이 없습니다.");
    await act(async () => {
      await result.current.execute({ action: updateAction, values, scenario: "SUCCESS" });
    });
    const confirmAction = result.current.allowedActions.find(
      (action) => action.code === "CONFIRM_CONSULTATION_SUMMARY",
    );
    if (!confirmAction) throw new Error("상담 확정 action이 없습니다.");
    await act(async () => {
      await result.current.execute({ action: confirmAction, values, scenario: "SUCCESS" });
    });
    expect(confirmPrompt).toHaveBeenCalledTimes(1);
    const completeAction = result.current.allowedActions.find(
      (action) => action.code === "CONSULTATION_COMPLETED",
    );
    if (!completeAction) throw new Error("상담 완료 action이 없습니다.");
    await act(async () => {
      await result.current.execute({ action: completeAction, values, scenario: "SUCCESS" });
    });
    expect(confirmPrompt).toHaveBeenCalledTimes(2);

    expect(start).toHaveBeenCalledWith(
      inquiry.inquiryId,
      { state_version: inquiry.stateVersion },
      expect.any(Object),
    );
    expect(saveSummary).toHaveBeenCalledWith(
      inquiry.inquiryId,
      expect.objectContaining({ state_version: inquiry.stateVersion + 1 }),
      expect.any(Object),
    );
    expect(confirmSummary).toHaveBeenCalledWith(
      inquiry.inquiryId,
      { state_version: inquiry.stateVersion + 2 },
      expect.any(Object),
    );
    expect(complete).toHaveBeenCalledWith(
      inquiry.inquiryId,
      { state_version: inquiry.stateVersion + 3 },
      expect.any(Object),
    );
    expect(result.current.currentStatus).toBe("COMPLETION_PENDING");
    expect(result.current.stateVersion).toBe(inquiry.stateVersion + 4);
    expect(result.current.allowedActions).toEqual([]);
  });

  it("Remote 문의 최종 완료는 Backend finalize API 결과로 상태를 동기화한다", async () => {
    const baseInquiry = COUNSELOR_INQUIRIES[0];
    if (!baseInquiry) throw new Error("상담 문의 fixture가 없습니다.");
    const finalizeAction = {
      code: "FINALIZE_INQUIRY" as const,
      label: "문의 최종 완료",
      operationId: "finalizeInquiry",
      style: "PRIMARY" as const,
      requiresConfirmation: true,
      confirmationMessage: "고객 해결 확인 후 문의를 완료하시겠습니까?",
    };
    const inquiry = {
      ...baseInquiry,
      status: "COMPLETION_PENDING" as const,
      stateVersion: 8,
      allowedActions: [finalizeAction],
    };
    const finalize = vi.fn().mockResolvedValue({
      success: true,
      data: {
        message: "문의가 최종 완료되었습니다.",
        inquiry_id: inquiry.inquiryId,
        status: "RESOLVED",
        state_version: 9,
        allowed_actions: [],
        idempotent_replay: false,
        resource: null,
      },
      error: null,
      metadata: { correlation_id: "corr-finalize" },
    });
    const repository = {
      start: vi.fn(),
      saveSummary: vi.fn(),
      confirmSummary: vi.fn(),
      complete: vi.fn(),
      finalize,
    } as ConsultationWriteRepository;
    const values: ConsultationFormValues = {
      consultationNote: "",
      additionalCheck: "",
      customerGuidance: "",
      consultationResult: "",
      summaryRevision: "",
      summaryConfirmed: false,
      visitRequired: "UNDECIDED",
      usageStatus: "NORMAL",
    };
    const finalizeConfirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const { result } = renderHook(() =>
      useSaveConsultation(inquiry, {
        dataSource: "REMOTE",
        remoteRepository: repository,
      }),
    );

    await act(async () => {
      await result.current.execute({
        action: finalizeAction,
        values,
        scenario: "SUCCESS",
      });
    });

    expect(finalize).toHaveBeenCalledWith(
      inquiry.inquiryId,
      { state_version: 8 },
      expect.any(Object),
    );
    expect(result.current.currentStatus).toBe("RESOLVED");
    expect(result.current.stateVersion).toBe(9);
    expect(result.current.allowedActions).toEqual([]);
    expect(finalizeConfirm).toHaveBeenCalledTimes(1);
  });

  it("Remote 재개 문의는 현재 버전으로 Backend 상담 재개 API를 호출한다", async () => {
    const baseInquiry = COUNSELOR_INQUIRIES[0];
    if (!baseInquiry) throw new Error("상담 문의 fixture가 없습니다.");
    const resumeAction = {
      code: "RESUME_CONSULTATION" as const,
      label: "상담 대기열로 복귀",
      operationId: "resumeConsultation",
      style: "PRIMARY" as const,
      requiresConfirmation: false,
      confirmationMessage: null,
    };
    const inquiry = {
      ...baseInquiry,
      status: "REOPENED" as const,
      stateVersion: 13,
      allowedActions: [resumeAction],
    };
    const resume = vi.fn().mockResolvedValue({
      success: true,
      data: {
        message: "재개 문의가 상담 대기열로 복귀했습니다.",
        inquiry_id: inquiry.inquiryId,
        status: "CONSULTATION_REQUIRED",
        state_version: 14,
        allowed_actions: [],
        idempotent_replay: false,
        resource: null,
      },
      error: null,
      metadata: { correlation_id: "corr-resume" },
    });
    const repository = {
      start: vi.fn(),
      saveSummary: vi.fn(),
      confirmSummary: vi.fn(),
      complete: vi.fn(),
      resume,
      finalize: vi.fn(),
    } as ConsultationWriteRepository;
    const values: ConsultationFormValues = {
      consultationNote: "",
      additionalCheck: "",
      customerGuidance: "",
      consultationResult: "",
      summaryRevision: "",
      summaryConfirmed: false,
      visitRequired: "UNDECIDED",
      usageStatus: "NORMAL",
    };
    const { result } = renderHook(() =>
      useSaveConsultation(inquiry, {
        dataSource: "REMOTE",
        remoteRepository: repository,
      }),
    );

    await act(async () => {
      await result.current.execute({
        action: resumeAction,
        values,
        scenario: "SUCCESS",
      });
    });

    expect(resume).toHaveBeenCalledWith(
      inquiry.inquiryId,
      { state_version: 13 },
      expect.any(Object),
    );
    expect(result.current.currentStatus).toBe("CONSULTATION_REQUIRED");
    expect(result.current.stateVersion).toBe(14);
    expect(result.current.allowedActions).toEqual([]);
  });

  it("재조회한 동일 문의의 workflow snapshot으로 로컬 상태를 동기화한다", async () => {
    const inquiry = COUNSELOR_INQUIRIES.find((item) =>
      item.allowedActions.some((action) => action.code === "START_CONSULTATION"),
    );
    if (!inquiry) throw new Error("상담 시작 fixture가 없습니다.");
    const nextAction = {
      code: "UPDATE_CONSULTATION_SUMMARY" as const,
      label: "상담 요약 수정",
      operationId: "updateConsultationSummary",
      style: "SECONDARY" as const,
      requiresConfirmation: false,
      confirmationMessage: null,
    };
    const { result, rerender } = renderHook(
      ({ runtimeInquiry }) =>
        useSaveConsultation(runtimeInquiry, { dataSource: "REMOTE" }),
      { initialProps: { runtimeInquiry: inquiry } },
    );

    rerender({
      runtimeInquiry: {
        ...inquiry,
        status: "CONSULTATION_IN_PROGRESS" as const,
        stateVersion: inquiry.stateVersion + 1,
        allowedActions: [nextAction],
      },
    });

    await act(async () => undefined);
    expect(result.current.currentStatus).toBe("CONSULTATION_IN_PROGRESS");
    expect(result.current.stateVersion).toBe(inquiry.stateVersion + 1);
    expect(result.current.allowedActions).toEqual([nextAction]);
  });

  it("네트워크 재시도에는 같은 멱등 키와 새로운 추적 ID를 사용한다", async () => {
    const inquiry = COUNSELOR_INQUIRIES.find(
      (item) => item.inquiryCode === "INQ-20260704-0013",
    );
    if (!inquiry) throw new Error("상담 저장 테스트 문의가 없습니다.");

    const action = inquiry.allowedActions.find(
      (item) => item.code === "UPDATE_CONSULTATION_SUMMARY",
    );
    if (!action) throw new Error("상담 저장 테스트 행동이 없습니다.");

    const values: ConsultationFormValues = {
      consultationNote: "고객 상태 확인",
      additionalCheck: "",
      customerGuidance: "안전 안내",
      consultationResult: "상담 진행",
      summaryRevision: "수정 요약",
      summaryConfirmed: false,
      visitRequired: "UNDECIDED",
      usageStatus: inquiry.usageStatus,
    };
    const submit = vi
      .spyOn(consultationApi, "submitConsultationMock")
      .mockRejectedValueOnce(
        new consultationApi.ConsultationMockError({
          kind: "NETWORK_ERROR",
          message: "일시적인 네트워크 오류",
        }),
      )
      .mockResolvedValue({
        message: "저장 완료",
        status: inquiry.status,
        stateVersion: inquiry.stateVersion,
        allowedActions: inquiry.allowedActions,
        correlationId: "server-correlation-id",
      });
    const { result } = renderHook(() => useSaveConsultation(inquiry));

    await act(async () => {
      await result.current.execute({ action, values, scenario: "NETWORK_ERROR" });
    });
    await act(async () => {
      await result.current.execute({ action, values, scenario: "SUCCESS" });
    });
    await act(async () => {
      await result.current.execute({ action, values, scenario: "SUCCESS" });
    });

    const firstRequest = submit.mock.calls[0][0];
    const retryRequest = submit.mock.calls[1][0];
    const newOperationRequest = submit.mock.calls[2][0];

    expect(retryRequest.idempotency_key).toBe(firstRequest.idempotency_key);
    expect(retryRequest.correlation_id).not.toBe(firstRequest.correlation_id);
    expect(newOperationRequest.idempotency_key).not.toBe(
      retryRequest.idempotency_key,
    );
  });

  it("처리 중 중복 클릭은 두 번째 전송을 만들지 않는다", async () => {
    const inquiry = COUNSELOR_INQUIRIES.find(
      (item) => item.inquiryCode === "INQ-20260704-0013",
    );
    if (!inquiry) throw new Error("상담 저장 테스트 문의가 없습니다.");
    const action = inquiry.allowedActions[0];
    if (!action) throw new Error("상담 저장 테스트 행동이 없습니다.");
    const values: ConsultationFormValues = {
      consultationNote: "고객 상태 확인",
      additionalCheck: "",
      customerGuidance: "안전 안내",
      consultationResult: "상담 진행",
      summaryRevision: "수정 요약",
      summaryConfirmed: false,
      visitRequired: "UNDECIDED",
      usageStatus: inquiry.usageStatus,
    };
    let resolveRequest!: (value: Awaited<ReturnType<typeof consultationApi.submitConsultationMock>>) => void;
    const submit = vi
      .spyOn(consultationApi, "submitConsultationMock")
      .mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    const { result } = renderHook(() => useSaveConsultation(inquiry));

    let firstRequest!: ReturnType<typeof result.current.execute>;
    await act(async () => {
      firstRequest = result.current.execute({ action, values, scenario: "SUCCESS" });
      const duplicate = await result.current.execute({ action, values, scenario: "SUCCESS" });
      expect(duplicate).toMatchObject({ ok: false, duplicateClick: true });
    });
    resolveRequest({
      message: "저장 완료",
      status: inquiry.status,
      stateVersion: inquiry.stateVersion + 1,
      allowedActions: inquiry.allowedActions,
      correlationId: "server-correlation-id",
    });
    await act(async () => { await firstRequest; });

    expect(submit).toHaveBeenCalledTimes(1);
    expect(result.current.lastRefreshedAt).not.toBeNull();
  });
});
