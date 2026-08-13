import { describe, expect, it, vi } from "vitest";

import type { ApiResponse } from "../../src/common/api/apiResponse";
import type {
  ConsultantInquiryDetailDto,
  ConsultantInquiryListDataDto,
} from "../../src/features/consultation/api/consultantWorkspaceRemoteTypes";
import { CONSULTANT_QUEUE_INQUIRIES } from "../../src/features/consultation/model/consultantWorkspaceMock";
import {
  buildConsultantInquiryListPath,
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
      },
      product_and_care: {
        product_model: "SYN-WP-01",
        subscription_status: "ACTIVE",
        management_type: "VISIT_CARE",
        recent_care_date: null,
      },
      symptom_and_questionnaire: {
        symptom_summary: "누수가 있어요",
        answers: [],
      },
      guidance_and_actions: {
        usage_guidance_status: "PENDING_CONSULTATION",
        usage_guidance_message: null,
        restricted_functions: [],
      },
      consultation: {
        consultation_id: "30000000-0000-4000-8000-000000000301",
        result_code: "COMPLETED_NO_VISIT",
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
      visit: null,
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
      subscriptionStatus: "ACTIVE",
      managementType: "VISIT_CARE",
      recentCareDate: null,
    });
    expect(result.data.workflow.allowedActions[0]).toMatchObject({
      code: "START_CONSULTATION",
      operationId: "startConsultation",
      requiresConfirmation: false,
    });
    expect(result.data.consultation).toMatchObject({
      consultationId: "30000000-0000-4000-8000-000000000301",
      resultCode: "COMPLETED_NO_VISIT",
      summary: {
        aiDraftSummary: "AI 초안",
        editedSummary: "상담사 수정 요약",
        confirmedSummary: "확정 요약",
      },
      consultationNote: "고객 상태 확인",
      customerGuidance: "정상 사용 안내",
    });
  });
});
