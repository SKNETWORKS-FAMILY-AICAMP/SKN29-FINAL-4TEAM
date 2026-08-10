import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as consultationApi from "../../src/features/consultation/api/consultationMockApi";
import { useSaveConsultation } from "../../src/features/consultation/hooks/useSaveConsultation";
import { COUNSELOR_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";
import type { ConsultationFormValues } from "../../src/features/consultation/model/consultationTypes";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useSaveConsultation", () => {
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
