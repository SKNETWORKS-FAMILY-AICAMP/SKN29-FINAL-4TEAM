import { describe, expect, it, vi } from "vitest";

import type { ApiResponse } from "../../src/common/api/apiResponse";
import type { RequestContext } from "../../src/common/api/requestContext";
import {
  createRemoteConsultationWriteRepository,
  type ConsultationWriteRequester,
} from "../../src/features/consultation/repositories/consultationWriteRepository";
import {
  buildVisitScheduleRequest,
  createRemoteVisitWriteRepository,
  toNullableDateOnly,
  type CreateVisitRequestDto,
  type VisitWriteRequester,
} from "../../src/features/visit-transition/repositories/visitWriteRepository";

const context: RequestContext = {
  correlationId: "corr-1",
  idempotencyKey: "idem-1",
  headers: {
    "Idempotency-Key": "idem-1",
    "X-Correlation-ID": "corr-1",
  },
};

function emptySuccess<T>(): ApiResponse<T> {
  return {
    success: true,
    data: null,
    error: null,
    metadata: { correlation_id: "corr-1" },
  };
}

describe("상담 Write Repository 경계", () => {
  it("확정된 주소와 메서드로만 상담 쓰기 요청을 보낸다", async () => {
    const requester = vi.fn(async () => emptySuccess()) as ConsultationWriteRequester;
    const repository = createRemoteConsultationWriteRepository(requester);

    await repository.cancel(
      "inquiry/1",
      {
        state_version: 1,
        reason_code: "OTHER",
        reason_detail: "상담사 화면에서 문의 삭제 요청",
      },
      context,
    );
    await repository.claimConsultation(
      "inquiry/1",
      { state_version: 2 },
      context,
    );
    await repository.start("inquiry/1", { state_version: 3 }, context);
    await repository.saveSummary(
      "inquiry/1",
      { state_version: 4, summary: "요약" },
      context,
    );
    await repository.confirmSummary("inquiry/1", { state_version: 5 }, context);
    await repository.complete(
      "inquiry/1",
      { state_version: 6 },
      context,
    );
    await repository.resume(
      "inquiry/1",
      { state_version: 7 },
      context,
    );
    await repository.finalize(
      "inquiry/1",
      { state_version: 8 },
      context,
    );

    expect(requester.mock.calls.map(([path, options]) => [path, options.method])).toEqual([
      ["/inquiries/inquiry%2F1/cancel", "POST"],
      ["/inquiries/inquiry%2F1/claim-consultation", "POST"],
      ["/inquiries/inquiry%2F1/start-consultation", "POST"],
      ["/inquiries/inquiry%2F1/consultation-summary", "PATCH"],
      ["/inquiries/inquiry%2F1/consultation-summary/confirm", "POST"],
      ["/inquiries/inquiry%2F1/complete-consultation", "POST"],
      ["/inquiries/inquiry%2F1/resume-consultation", "POST"],
      ["/inquiries/inquiry%2F1/finalize", "POST"],
    ]);
    expect(requester.mock.calls[0][1]).toMatchObject({
      body: {
        state_version: 1,
        reason_code: "OTHER",
        reason_detail: "상담사 화면에서 문의 삭제 요청",
      },
      requestContext: context,
    });
    expect(requester.mock.calls[1][1]).toMatchObject({
      body: { state_version: 2 },
      requestContext: context,
    });
  });
});

describe("방문 Write Repository 경계", () => {
  it("방문 생성에는 기사를 넣지 않고 생성→일정→확정 순서의 주소를 사용한다", async () => {
    const requester = vi.fn(async () => emptySuccess()) as VisitWriteRequester;
    const repository = createRemoteVisitWriteRepository(requester);
    const createBody: CreateVisitRequestDto = {
      state_version: 4,
      visit_reason: "현장 확인 필요",
      preferred_date: "2026-08-13",
      usage_guidance_status: "PARTIAL_STOP",
      handoff: {
        product_summary: "합성 제품",
        symptom_summary: "누수 의심",
        action_summary: "사용 중지 안내",
        risk_summary: "바닥 미끄럼 주의",
        priority_check_items: ["급수 밸브"],
        consultant_final: "방문 필요",
      },
    };

    await repository.create("inq-1", createBody, context);
    await repository.markNotNeeded(
      "inq-1",
      {
        state_version: 5,
        reason_code: "RESOLVED_BY_CONSULTATION",
      },
      context,
    );
    await repository.saveSchedule(
      "visit-1",
      buildVisitScheduleRequest({
        stateVersion: 5,
        technicianId: "00000000-0000-4000-8000-000000000101",
        preferredDate: "2026-08-13",
        confirmedDate: "2026-08-14",
      }),
      context,
    );
    await repository.confirm("visit-1", { state_version: 6 }, context);

    expect(requester.mock.calls.map(([path, options]) => [path, options.method])).toEqual([
      ["/inquiries/inq-1/visits", "POST"],
      ["/inquiries/inq-1/visit-not-needed", "POST"],
      ["/visits/visit-1/schedule", "PATCH"],
      ["/visits/visit-1/confirm", "POST"],
    ]);
    expect(requester.mock.calls[0][1].body).not.toHaveProperty(
      "synthetic_technician_id",
    );
    expect(requester.mock.calls[2][1].body).toEqual({
      state_version: 5,
      synthetic_technician_id: "00000000-0000-4000-8000-000000000101",
      preferred_date: "2026-08-13",
      confirmed_date: "2026-08-14",
    });
    expect(requester.mock.calls[3][1].body).toEqual({ state_version: 6 });
  });

  it("날짜만 허용하고 시간 값은 거부한다", () => {
    expect(toNullableDateOnly("")).toBeNull();
    expect(toNullableDateOnly("2026-08-13")).toBe("2026-08-13");
    expect(() => toNullableDateOnly("2026-08-13T10:00")).toThrow(
      "YYYY-MM-DD",
    );
  });
});
