import { afterEach, describe, expect, it, vi } from "vitest";

import * as httpClient from "../../src/common/api/httpClient";
import {
  fetchSyntheticConsultantDashboardData,
  mapSyntheticConsultantDashboardDto,
} from "../../src/features/notice/api/consultantNoticeApi";

const DASHBOARD_DTO = {
  data_classification: "synthetic",
  generated_at: "2026-08-20T10:00:00+09:00",
  summary: { total: 1, new: 1, in_progress: 0, completed: 0 },
  notices: [
    {
      notice_id: "00000000-0000-4000-8000-000000000001",
      notice_code: "NOTICE-001",
      category_code: "WORK" as const,
      category: "근무",
      title: "합성 공지",
      content: "로컬 G4 전용 공지",
      department: "고객케어팀",
      published_on: "2026-08-20",
    },
  ],
  consultants: [
    {
      user_id: "00000000-0000-4000-8000-000000000002",
      name: "합성 상담사",
      department: "고객케어팀",
      position: "상담사",
      extension: "02-0000-0001",
      email: "consultant@example.test",
    },
  ],
  technicians: [
    {
      user_id: "00000000-0000-4000-8000-000000000003",
      name: "합성 기사",
      branch: "합성 지사",
      phone: "010-0000-0001",
      email: "technician@example.test",
    },
  ],
  inquiries: [
    {
      inquiry_id: "00000000-0000-4000-8000-000000000004",
      inquiry_code: "WEB-G4-INQ-001",
      bucket: "NEW" as const,
      status: "CONSULTATION_REQUIRED",
      risk_level: "caution",
      priority: "NORMAL",
      title: "합성 문의",
      detail: "합성 문의 상세",
      contact: "010-0000-0002",
      address: "합성 주소",
      customer_name: "합성 고객",
      customer_code: "SYN-CUSTOMER-001",
      product_name: "합성 정수기",
      product_code: "SYN-PRODUCT-001",
      warranty_status: "IN_WARRANTY" as const,
      warranty_ends_on: "2027-08-20",
      warranty_label: "무상보증 2027년 8월까지",
      previous_visit_count: 0,
      received_at: "2026-08-20T09:00:00+09:00",
      updated_at: "2026-08-20T09:10:00+09:00",
    },
  ],
};

afterEach(() => vi.restoreAllMocks());

describe("로컬 합성 상담사 Dashboard API", () => {
  it("정확한 Runtime 경로를 호출하고 다섯 응답 영역을 매핑한다", async () => {
    const request = vi
      .spyOn(httpClient, "requestApi")
      .mockResolvedValue({ data: DASHBOARD_DTO, status: 200 });

    const result = await fetchSyntheticConsultantDashboardData();

    expect(request).toHaveBeenCalledWith("/consultant/dashboard");
    expect(result.summary).toEqual({
      total: 1,
      new: 1,
      inProgress: 0,
      completed: 0,
    });
    expect(result.notices[0]?.noticeCode).toBe("NOTICE-001");
    expect(result.consultants[0]?.extension).toBe("02-0000-0001");
    expect(result.technicians[0]).toMatchObject({
      userId: "00000000-0000-4000-8000-000000000003",
      phone: "010-0000-0001",
    });
    expect(result.inquiries[0]?.inquiryCode).toBe("WEB-G4-INQ-001");
  });

  it("synthetic 이외 분류는 화면 데이터로 사용하지 않는다", () => {
    expect(() =>
      mapSyntheticConsultantDashboardDto({
        ...DASHBOARD_DTO,
        data_classification: "production",
      }),
    ).toThrow("로컬 합성 데이터만");
  });
});
