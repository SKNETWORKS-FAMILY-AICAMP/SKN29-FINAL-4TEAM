import { describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../../src/common/api/apiError";
import type { ApiResponse } from "../../src/common/api/apiResponse";
import type {
  ConsultantInquiryDetailDto,
  ConsultantInquiryListDataDto,
  UnassignedConsultationQueueDataDto,
} from "../../src/features/consultation/api/consultantWorkspaceRemoteTypes";
import {
  CONSULTANT_QUEUE_INQUIRIES,
  UNASSIGNED_CONSULTANT_INQUIRIES,
} from "../fixtures/consultantWorkspaceMock";
import {
  buildConsultantInquiryListPath,
  buildUnassignedConsultationQueuePath,
  createMockConsultantWorkspaceDataRepository,
  createRemoteConsultantWorkspaceDataRepository,
  type ConsultantApiRequester,
} from "../../src/features/consultation/repositories/consultantWorkspaceDataRepository";

function successResponse<T>(data: T): ApiResponse<T> {
  return {
    success: true,
    data,
    error: null,
    metadata: { correlation_id: "corr-test" },
  };
}

describe("상담사 실제 API 전환 Repository", () => {
  it("계약에 있는 조회 조건만 API 주소에 넣는다", () => {
    const path = buildConsultantInquiryListPath({
      q: "누수",
      status: ["CONSULTATION_REQUIRED", "VISIT_SCHEDULING"],
      riskLevel: ["danger"],
      priority: ["URGENT"],
      from: "2026-08-01",
      to: "2026-08-10",
      sort: "WAITING_DESC",
      page: 2,
      size: 10,
    });
    const url = new URL(path, "http://localhost");

    expect(url.pathname).toBe("/inquiries");
    expect(url.searchParams.get("q")).toBe("누수");
    expect(url.searchParams.getAll("status")).toEqual([
      "CONSULTATION_REQUIRED",
      "VISIT_SCHEDULING",
    ]);
    expect(url.searchParams.getAll("risk_level")).toEqual(["danger"]);
    expect(url.searchParams.getAll("priority")).toEqual(["URGENT"]);
    expect(url.searchParams.get("from")).toBe("2026-08-01");
    expect(url.searchParams.get("to")).toBe("2026-08-10");
    expect(url.searchParams.get("sort")).toBe("WAITING_DESC");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("size")).toBe("10");
  });

  it("미배정 대기열 전용 조회 조건만 별도 API 주소에 넣는다", () => {
    const path = buildUnassignedConsultationQueuePath({
      q: "누수",
      riskLevel: ["caution", "danger"],
      priority: ["HIGH", "URGENT"],
      from: "2026-08-20",
      to: "2026-08-24",
      sort: "WAITING_DESC",
      page: 2,
      size: 10,
    });
    const url = new URL(path, "http://localhost");

    expect(url.pathname).toBe("/inquiries/unassigned-consultations");
    expect(url.searchParams.get("q")).toBe("누수");
    expect(url.searchParams.getAll("risk_level")).toEqual([
      "caution",
      "danger",
    ]);
    expect(url.searchParams.getAll("priority")).toEqual(["HIGH", "URGENT"]);
    expect(url.searchParams.get("from")).toBe("2026-08-20");
    expect(url.searchParams.get("to")).toBe("2026-08-24");
    expect(url.searchParams.get("sort")).toBe("WAITING_DESC");
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.get("size")).toBe("10");
    expect(url.searchParams.has("status")).toBe(false);
  });

  it("Remote 목록 응답을 화면용 이름으로 바꾸고 correlation id를 보존한다", async () => {
    const dto: ConsultantInquiryListDataDto = {
      items: [
        {
          inquiry_id: "b7df3cd0-c9d6-42bd-b93e-a70ee24c6f21",
          inquiry_code: "INQ-001",
          status: "CONSULTATION_REQUIRED",
          state_version: 3,
          risk_level: "danger",
          priority: "URGENT",
          symptom_summary: "누수가 있어요",
          customer_display_name_masked: "합성 고객 001",
          product_model: "WPU-JAC104D",
          current_assignee_type: "CONSULTANT",
          received_at: "2026-08-10T09:00:00+09:00",
          updated_at: "2026-08-10T09:10:00+09:00",
          waiting_seconds: 600,
          allowed_actions: [],
        },
      ],
      page_info: { page: 1, size: 20, total: 1 },
      status_counts: { CONSULTATION_REQUIRED: 1 },
    };
    const requester = vi.fn(async () => successResponse(dto)) as ConsultantApiRequester;
    const repository = createRemoteConsultantWorkspaceDataRepository(requester);

    const result = await repository.listInquiries({ page: 1, size: 20 });

    expect(requester).toHaveBeenCalledWith("/inquiries?page=1&size=20");
    expect(result.correlationId).toBe("corr-test");
    expect(result.data.items[0]).toMatchObject({
      inquiryId: dto.items[0].inquiry_id,
      symptomSummary: "누수가 있어요",
      waitingSeconds: 600,
    });
  });

  it("Remote 미배정 대기열을 별도 화면 모델로 바꾸고 집계값을 만들지 않는다", async () => {
    const dto: UnassignedConsultationQueueDataDto = {
      items: [
        {
          inquiry_id: "b7df3cd0-c9d6-42bd-b93e-a70ee24c6f22",
          inquiry_code: "INQ-002",
          status: "CONSULTATION_REQUIRED",
          state_version: 3,
          risk_level: "caution",
          priority: "HIGH",
          symptom_summary: "출수량이 줄었어요",
          customer_display_name_masked: "합성고객 0*",
          product_model: "WPUJAC104DWH",
          current_assignee_type: "NONE",
          received_at: "2026-08-23T04:10:00Z",
          updated_at: "2026-08-23T04:20:00Z",
          waiting_seconds: 600,
          allowed_actions: [
            {
              code: "CLAIM_CONSULTATION",
              label: "상담 배정받기",
              operation_id: "claimConsultation",
              style: "PRIMARY",
              requires_confirmation: false,
              confirmation_message: null,
            },
          ],
        },
      ],
      page_info: { page: 1, size: 20, total: 1 },
    };
    const requester = vi.fn(async () => successResponse(dto)) as ConsultantApiRequester;
    const repository = createRemoteConsultantWorkspaceDataRepository(requester);

    const result = await repository.listUnassignedConsultations({
      page: 1,
      size: 20,
    });

    expect(requester).toHaveBeenCalledWith(
      "/inquiries/unassigned-consultations?page=1&size=20",
    );
    expect(result.correlationId).toBe("corr-test");
    expect(result.data).not.toHaveProperty("statusCounts");
    expect(result.data.items[0]).toMatchObject({
      inquiryId: dto.items[0].inquiry_id,
      status: "CONSULTATION_REQUIRED",
      currentAssigneeType: "NONE",
      productModel: "WPUJAC104DWH",
      allowedActions: [
        {
          code: "CLAIM_CONSULTATION",
          operationId: "claimConsultation",
        },
      ],
    });
  });

  it("Remote 실패를 Mock 성공으로 바꾸지 않는다", async () => {
    const expected = new Error("backend blocked");
    const requester = vi.fn(async () => {
      throw expected;
    }) as ConsultantApiRequester;
    const repository = createRemoteConsultantWorkspaceDataRepository(requester);

    await expect(repository.listInquiries()).rejects.toBe(expected);
  });

  it("명시적 Mock은 계약 형태로 목록과 상세를 제공하되 주소는 노출하지 않는다", async () => {
    const repository = createMockConsultantWorkspaceDataRepository();
    const inquiry = CONSULTANT_QUEUE_INQUIRIES[0];

    const list = await repository.listInquiries({ size: 1 });
    const detail = await repository.getInquiryDetail(inquiry.inquiryId);

    expect(repository.dataSource).toBe("MOCK");
    expect(list.data.items).toHaveLength(1);
    expect(detail.data.customer.displayName).toBe(inquiry.customerDisplayName);
    expect(detail.data).not.toHaveProperty("serviceAddress");
    expect(detail.data.customer).not.toHaveProperty("serviceAddress");
  });

  it("명시적 Mock 미배정 대기열은 배정 목록과 겹치지 않는 전용 합성 문의를 쓴다", async () => {
    const repository = createMockConsultantWorkspaceDataRepository(
      "DESIGN_SCENARIOS",
    );

    const queue = await repository.listUnassignedConsultations({
      page: 1,
      size: 3,
    });

    expect(queue.data.items.length).toBeGreaterThan(0);
    expect(queue.data.items.length).toBeLessThanOrEqual(3);
    expect(queue.data.items[0]).toMatchObject({
      status: "CONSULTATION_REQUIRED",
      currentAssigneeType: "NONE",
      allowedActions: [
        {
          code: "CLAIM_CONSULTATION",
          operationId: "claimConsultation",
        },
      ],
    });
    expect(queue.data.items[0]).not.toHaveProperty("customerPhone");
    expect(queue.data).not.toHaveProperty("statusCounts");
    expect(UNASSIGNED_CONSULTANT_INQUIRIES).toHaveLength(3);
    expect(
      queue.data.items.some((unassigned) =>
        CONSULTANT_QUEUE_INQUIRIES.some(
          (assigned) => assigned.inquiryId === unassigned.inquiryId,
        ),
      ),
    ).toBe(false);
    expect(
      UNASSIGNED_CONSULTANT_INQUIRIES.map((item) => item.manualModel),
    ).toEqual(["WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"]);
  });

  it("디자인 Mock 데이터셋은 상태별 다건 문의를 명시적으로 제공한다", async () => {
    const repository = createMockConsultantWorkspaceDataRepository(
      "DESIGN_SCENARIOS",
    );

    const newInquiries = await repository.listInquiries({
      status: ["CONSULTATION_REQUIRED", "REOPENED"],
      page: 1,
      size: 100,
    });
    const inProgressInquiries = await repository.listInquiries({
      status: ["CONSULTATION_IN_PROGRESS", "VISIT_SCHEDULED"],
      page: 1,
      size: 100,
    });

    expect(newInquiries.data.pageInfo.total).toBeGreaterThan(0);
    expect(inProgressInquiries.data.pageInfo.total).toBeGreaterThan(0);
  });

  it("Remote 상세 조회는 공개 inquiry id만 주소에 사용한다", async () => {
    const dto: ConsultantInquiryDetailDto = {
      inquiry: {
        inquiry_id: "b7df3cd0-c9d6-42bd-b93e-a70ee24c6f21",
        inquiry_code: "INQ-001",
        status: "CONSULTATION_REQUIRED",
        state_version: 3,
        risk_level: "danger",
        priority: "URGENT",
        received_at: "2026-08-10T09:00:00+09:00",
        updated_at: "2026-08-10T09:10:00+09:00",
      },
      customer: {
        is_synthetic: true,
        display_name: "합성 고객 001",
        phone: "010-****-0001",
        phone_masked: "010-****-0001",
      },
      product_and_care: {
        product_model: "SYN-WP-01",
        product_model_name: "합성 시연용 정수기",
        subscription_status: "ACTIVE",
        management_type: "VISIT_CARE",
        recent_care_date: "2026-08-01",
      },
      symptom_and_questionnaire: {
        symptom_summary: "누수가 있어요",
        answers: [
          {
            question_code: "SYN-Q-01",
            question_text: "누수가 계속 발생하나요?",
            answer: "네, 계속 발생합니다.",
          },
        ],
      },
      guidance_and_actions: {
        usage_guidance_status: "PENDING_CONSULTATION",
        usage_guidance_display_label: "상담 확인 필요",
        usage_guidance_message: null,
        restricted_functions: [],
      },
      consultation: {
        consultation_id: "30000000-0000-4000-8000-000000000301",
        result_code: "VISIT_REQUIRED",
        summary: {
          ai_draft_summary: "AI 초안",
          edited_summary: "상담사 수정 요약",
          confirmed_summary: "확정 요약",
          confirmed_at: "2026-08-10T09:09:00+09:00",
        },
        consultation_note: "고객 상태 확인",
        additional_check: "필터 상태 확인",
        customer_guidance: "정상 사용 안내",
        usage_guidance_status: "NORMAL",
      },
      visit: {
        visit_id: "40000000-0000-4000-8000-000000000401",
        inquiry_id: "b7df3cd0-c9d6-42bd-b93e-a70ee24c6f21",
        schedule: {
          preferred_date: "2026-08-11",
          confirmed_date: "2026-08-12",
          schedule_status: "CONFIRMED",
          synthetic_technician_id:
            "50000000-0000-4000-8000-000000000501",
        },
        technician: {
          is_synthetic: true,
          technician_id: "50000000-0000-4000-8000-000000000501",
          display_name: "합성 기사 001",
          phone: "010-0000-0501",
        },
      },
      state_history: [],
      workflow: {
        status: "CONSULTATION_REQUIRED",
        state_version: 3,
        allowed_actions: [
          {
            code: "START_CONSULTATION",
            label: "상담 시작",
            operation_id: "startConsultation",
            style: "PRIMARY",
            requires_confirmation: false,
            confirmation_message: null,
          },
        ],
      },
      section_errors: [],
    };
    const requester = vi.fn(async () => successResponse(dto)) as ConsultantApiRequester;
    const repository = createRemoteConsultantWorkspaceDataRepository(requester);

    const result = await repository.getInquiryDetail(dto.inquiry.inquiry_id);

    expect(requester).toHaveBeenCalledWith(
      `/inquiries/${dto.inquiry.inquiry_id}`,
    );
    expect(result.data.productAndCare).toEqual({
      productModel: "SYN-WP-01",
      productModelName: "합성 시연용 정수기",
      subscriptionStatus: "ACTIVE",
      managementType: "VISIT_CARE",
      recentCareDate: "2026-08-01",
    });
    expect(result.data.customer.phoneMasked).toBe("010-****-0001");
    expect(result.data.symptomAndQuestionnaire.answers[0]).toMatchObject({
      questionCode: "SYN-Q-01",
      questionText: "누수가 계속 발생하나요?",
    });
    expect(result.data.guidanceAndActions.usageGuidanceDisplayLabel).toBe(
      "상담 확인 필요",
    );
    expect(result.data.visit).toMatchObject({
      visitId: "40000000-0000-4000-8000-000000000401",
      schedule: {
        confirmedDate: "2026-08-12",
        scheduleStatus: "CONFIRMED",
      },
      technician: { displayName: "합성 기사 001" },
    });
    expect(result.data.workflow.allowedActions[0]).toMatchObject({
      code: "START_CONSULTATION",
      operationId: "startConsultation",
      requiresConfirmation: false,
    });
    expect(result.data.consultation).toMatchObject({
      consultationId: "30000000-0000-4000-8000-000000000301",
      resultCode: "VISIT_REQUIRED",
      summary: {
        aiDraftSummary: "AI 초안",
        editedSummary: "상담사 수정 요약",
        confirmedSummary: "확정 요약",
      },
      consultationNote: "고객 상태 확인",
      customerGuidance: "정상 사용 안내",
    });
  });

  it("비배정·미존재 문의를 같은 404로 처리하고 고객용 API를 우회 호출하지 않는다", async () => {
    const requester = vi.fn(async () => {
      throw new ApiClientError({
        kind: "NOT_FOUND",
        status: 404,
        code: "INQUIRY_NOT_FOUND",
        message: "문의를 찾을 수 없습니다.",
      });
    }) as ConsultantApiRequester;
    const repository = createRemoteConsultantWorkspaceDataRepository(requester);
    const unassignedInquiryId = "b7df3cd0-c9d6-42bd-b93e-a70ee24c6f99";
    const missingInquiryId = "ed7222d0-42e8-48eb-84be-9b0d45f51f65";

    for (const inquiryId of [unassignedInquiryId, missingInquiryId]) {
      await expect(repository.getInquiryDetail(inquiryId)).rejects.toMatchObject({
        kind: "NOT_FOUND",
        status: 404,
        code: "INQUIRY_NOT_FOUND",
      });
    }

    expect(requester).toHaveBeenCalledTimes(2);
    expect(requester).toHaveBeenCalledWith(`/inquiries/${unassignedInquiryId}`);
    expect(requester).toHaveBeenCalledWith(`/inquiries/${missingInquiryId}`);

    const requestedPaths = requester.mock.calls.flat().join(" ");
    expect(requestedPaths).not.toMatch(/(?:^|\/)me(?:\/|\?|$)/);
    expect(requestedPaths).not.toMatch(/subscriptions|care[-_/]?(?:records|history)?/i);
  });
});
