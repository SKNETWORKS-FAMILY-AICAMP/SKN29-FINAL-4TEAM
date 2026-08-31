import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createDesignPreviewApi,
  DESIGN_PREVIEW_INQUIRY_IDS,
  DESIGN_PREVIEW_READ_ONLY_MESSAGE,
  type DesignPreviewResponse,
} from "../../preview/designPreviewApi";
import type {
  ConsultantInquiryDetailDto,
  ConsultantInquiryListDataDto,
  UnassignedConsultationQueueDataDto,
} from "../../src/features/consultation/api/consultantWorkspaceRemoteTypes";

function dataOf<T>(response: DesignPreviewResponse): T {
  expect(response.status).toBe(200);
  expect(response.body.success).toBe(true);
  expect(response.body.error).toBeNull();
  expect(response.body.metadata.correlation_id).toBeTruthy();
  return response.body.data as T;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => {
    throw new Error("디자인 데이터 처리기는 실제 네트워크에 접근할 수 없습니다.");
  }));
});

afterEach(() => {
  expect(fetch).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

describe("로컬 미리보기 API 데이터 경계", () => {
  it("실제 목록 DTO와 동일한 집계·페이지 정보 및 별도 미배정 목록을 반환한다", () => {
    const handle = createDesignPreviewApi();
    const assigned = dataOf<ConsultantInquiryListDataDto>(handle({
      url: "/api/v1/inquiries?page=1&size=100",
      method: "GET",
    }));
    const unassigned = dataOf<UnassignedConsultationQueueDataDto>(handle({
      url: "/api/v1/inquiries/unassigned-consultations?size=100",
      method: "GET",
    }));

    expect(assigned.page_info.total).toBe(15);
    expect(assigned.items).toHaveLength(15);
    expect(Object.values(assigned.status_counts).reduce((sum, count) => sum + count, 0)).toBe(15);
    expect(assigned.status_counts.CONSULTATION_REQUIRED).toBe(2);
    expect(assigned.status_counts.REOPENED).toBe(1);
    expect(assigned.status_counts.RESOLVED).toBe(3);
    expect(assigned.status_counts.CANCELLED).toBe(1);
    expect(unassigned.page_info.total).toBe(4);
    expect(unassigned.items).toHaveLength(4);
    expect(unassigned.items.every((item) => item.current_assignee_type === "NONE")).toBe(true);
    expect(assigned.items.some((item) => item.inquiry_id === DESIGN_PREVIEW_INQUIRY_IDS.unassigned)).toBe(false);
  });

  it("검색·상태·페이지는 샘플 목록에 적용하고 업무 집계는 유지한다", () => {
    const handle = createDesignPreviewApi();
    const overview = dataOf<ConsultantInquiryListDataDto>(handle({
      url: "/api/v1/inquiries?size=100",
      method: "GET",
    }));
    const completed = dataOf<ConsultantInquiryListDataDto>(handle({
      url: "/api/v1/inquiries?status=RESOLVED,CANCELLED&page=2&size=2",
      method: "GET",
    }));
    const searched = dataOf<ConsultantInquiryListDataDto>(handle({
      url: "/api/v1/inquiries?q=PREVIEW-0001&size=100",
      method: "GET",
    }));
    const empty = dataOf<ConsultantInquiryListDataDto>(handle({
      url: "/api/v1/inquiries?q=no-matching-preview-inquiry",
      method: "GET",
    }));

    expect(completed.page_info).toEqual({ page: 2, size: 2, total: 4 });
    expect(completed.items).toHaveLength(2);
    expect(completed.items.every((item) => ["RESOLVED", "CANCELLED"].includes(item.status))).toBe(true);
    expect(searched.page_info.total).toBe(1);
    expect(searched.items[0].inquiry_id).toBe(DESIGN_PREVIEW_INQUIRY_IDS.new);
    expect(empty.items).toEqual([]);
    expect(empty.page_info.total).toBe(0);
    expect(empty.status_counts).toEqual(overview.status_counts);
  });

  it("실제 상세 DTO로 제품·AI 안내·상담 기록·권한을 제공하고 응답끼리 데이터를 공유하지 않는다", () => {
    const handle = createDesignPreviewApi();
    const request = {
      url: `/api/v1/inquiries/${DESIGN_PREVIEW_INQUIRY_IDS.inProgress}`,
      method: "GET",
    };
    const detail = dataOf<ConsultantInquiryDetailDto>(handle(request));

    expect(detail.inquiry.status).toBe("CONSULTATION_IN_PROGRESS");
    expect(detail.workflow.state_version).toBe(detail.inquiry.state_version);
    expect(detail.product_and_care?.product_model).toBeTruthy();
    expect(detail.product_and_care?.product_model_name).toBeTruthy();
    expect(detail.symptom_and_questionnaire.answers.length).toBeGreaterThan(0);
    expect(detail.guidance_and_actions.usage_guidance_message).toBeTruthy();
    expect(detail.consultation?.consultation_note).toBeTruthy();
    expect(detail.workflow.allowed_actions.map((action) => action.code)).toContain("UPDATE_CONSULTATION_SUMMARY");

    detail.inquiry.state_version = 999;
    detail.customer.display_name = "응답 객체를 편집한 이름";

    const untouched = dataOf<ConsultantInquiryDetailDto>(handle(request));
    expect(untouched.inquiry.state_version).not.toBe(999);
    expect(untouched.customer.display_name).not.toBe("응답 객체를 편집한 이름");
  });

  it("공지 목록과 상세, 전화 고객 검색을 운영 서버 없이 읽을 수 있다", () => {
    const handle = createDesignPreviewApi();
    const dashboard = dataOf<{
      summary: { total: number; new: number; in_progress: number; completed: number };
      notices: { notice_id: string; title: string; content: string }[];
      consultants: unknown[];
      technicians: unknown[];
    }>(handle({ url: "/api/v1/consultant/dashboard", method: "GET" }));
    const notice = dashboard.notices[0];

    expect(dashboard.summary).toEqual({ total: 15, new: 3, in_progress: 8, completed: 4 });
    expect(dashboard.consultants.length).toBeGreaterThan(0);
    expect(dashboard.technicians.length).toBeGreaterThan(0);
    expect(dataOf(handle({
      url: `/api/v1/consultant/notices/${notice.notice_id}`,
      method: "GET",
    }))).toMatchObject(notice);

    const candidates = dataOf<{ items: { customer_display_name: string; phone_masked: string }[]; returned_count: number }>(handle({
      url: "/api/v1/consultant/customer-subscriptions/search",
      method: "POST",
      body: { query: "0001", limit: 10 },
    }));
    expect(candidates.returned_count).toBe(1);
    expect(candidates.items[0].customer_display_name).toBe("김민준");
    expect(candidates.items[0].phone_masked).toContain("****");
  });

  it.each([
    ["POST", `/api/v1/inquiries/${DESIGN_PREVIEW_INQUIRY_IDS.new}/start-consultation`],
    ["PATCH", `/api/v1/inquiries/${DESIGN_PREVIEW_INQUIRY_IDS.inProgress}/consultation-summary`],
    ["POST", `/api/v1/inquiries/${DESIGN_PREVIEW_INQUIRY_IDS.completed}/finalize`],
    ["POST", "/api/v1/consultant/phone-inquiries"],
    ["POST", "/api/v1/auth/login"],
    ["DELETE", `/api/v1/inquiries/${DESIGN_PREVIEW_INQUIRY_IDS.new}`],
  ])("%s %s 변경 요청은 전달하거나 샘플을 변경하지 않는다", (method, url) => {
    const handle = createDesignPreviewApi();
    const readRequest = { url: "/api/v1/inquiries?size=100", method: "GET" };
    const before = handle(readRequest);
    const response = handle({ method, url, body: { state_version: 3 } });

    expect(response.status).toBe(405);
    expect(response.body).toMatchObject({
      success: false,
      data: null,
      error: { code: "PREVIEW_READ_ONLY", message: DESIGN_PREVIEW_READ_ONLY_MESSAGE },
    });
    expect(handle(readRequest)).toEqual(before);
  });

  it.each([
    "/api/v1/not-implemented",
    "/api/v1/inquiries/not-a-preview-inquiry",
    "/api/v1/inquiries/%E0%A4%A",
    "/api/v1/consultant/notices/not-a-preview-notice",
  ])("미지원 요청 %s는 오류 응답만 반환하고 실서버로 fallback하지 않는다", (url) => {
    const response = createDesignPreviewApi()({ url, method: "GET" });

    expect([400, 404]).toContain(response.status);
    expect(response.body.success).toBe(false);
    expect(response.body.data).toBeNull();
    expect(response.body.error?.code).toMatch(/^PREVIEW_/);
  });
});
