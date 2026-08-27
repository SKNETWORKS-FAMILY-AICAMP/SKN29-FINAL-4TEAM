import { appEnv } from "../../../app/config/env";
import { ApiClientError } from "../../../common/api/apiError";
import { requestApi } from "../../../common/api/httpClient";
import {
  CONSULTANT_NOTICE_CATEGORY_LABELS,
  type ConsultantNotice,
  type ConsultantNoticeCategoryCode,
  type ConsultantNoticePageData,
  type SyntheticConsultantDashboardData,
} from "../model/consultantNotice";
import {
  MOCK_CONSULTANT_NOTICE_PAGE_DATA,
  MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA,
} from "../model/consultantNoticeMock";

interface ConsultantDashboardSummaryDto {
  total: number;
  new: number;
  in_progress: number;
  completed: number;
}

interface ConsultantDashboardNoticeDto {
  notice_id: string;
  notice_code: string;
  category_code: ConsultantNoticeCategoryCode;
  category: string;
  title: string;
  content: string;
  department: string;
  published_on: string;
}

interface ConsultantDashboardConsultantDto {
  user_id: string;
  name: string;
  department: string;
  position: string;
  extension: string;
  email: string;
}

interface ConsultantDashboardTechnicianDto {
  user_id: string;
  name: string;
  branch: string;
  phone: string;
  email: string;
}

interface ConsultantDashboardInquiryDto {
  inquiry_id: string;
  inquiry_code: string;
  bucket: "NEW" | "IN_PROGRESS" | "COMPLETED";
  status: string;
  risk_level: string;
  priority: string;
  title: string;
  detail: string;
  contact: string;
  address: string;
  customer_name: string;
  customer_code: string;
  product_name: string;
  product_code: string;
  warranty_status: "IN_WARRANTY" | "EXPIRED" | "NOT_REGISTERED";
  warranty_ends_on: string | null;
  warranty_label: string;
  previous_visit_count: number;
  received_at: string;
  updated_at: string;
}

interface ConsultantDashboardDto {
  data_classification: string;
  generated_at: string;
  summary: ConsultantDashboardSummaryDto;
  notices: readonly ConsultantDashboardNoticeDto[];
  consultants: readonly ConsultantDashboardConsultantDto[];
  technicians: readonly ConsultantDashboardTechnicianDto[];
  inquiries: readonly ConsultantDashboardInquiryDto[];
}

export function mapConsultantNoticeDto(
  dto: ConsultantDashboardNoticeDto,
): ConsultantNotice {
  return {
    noticeId: dto.notice_id,
    noticeCode: dto.notice_code,
    categoryCode: dto.category_code,
    category:
      dto.category || CONSULTANT_NOTICE_CATEGORY_LABELS[dto.category_code],
    title: dto.title,
    content: dto.content,
    department: dto.department,
    publishedOn: dto.published_on,
  };
}

export function mapSyntheticConsultantDashboardDto(
  dto: ConsultantDashboardDto,
): SyntheticConsultantDashboardData {
  if (dto.data_classification !== "synthetic") {
    throw new Error("상담사 Dashboard는 로컬 합성 데이터만 사용할 수 있습니다.");
  }

  return {
    dataClassification: "synthetic",
    generatedAt: dto.generated_at,
    summary: {
      total: dto.summary.total,
      new: dto.summary.new,
      inProgress: dto.summary.in_progress,
      completed: dto.summary.completed,
    },
    notices: dto.notices.map(mapConsultantNoticeDto),
    consultants: dto.consultants.map((consultant) => ({
      userId: consultant.user_id,
      name: consultant.name,
      department: consultant.department,
      position: consultant.position,
      extension: consultant.extension,
      email: consultant.email,
    })),
    technicians: dto.technicians.map((technician) => ({
      userId: technician.user_id,
      name: technician.name,
      branch: technician.branch,
      phone: technician.phone,
      email: technician.email,
    })),
    inquiries: dto.inquiries.map((inquiry) => ({
      inquiryId: inquiry.inquiry_id,
      inquiryCode: inquiry.inquiry_code,
      bucket: inquiry.bucket,
      status: inquiry.status,
      riskLevel: inquiry.risk_level,
      priority: inquiry.priority,
      title: inquiry.title,
      detail: inquiry.detail,
      contact: inquiry.contact,
      address: inquiry.address,
      customerName: inquiry.customer_name,
      customerCode: inquiry.customer_code,
      productName: inquiry.product_name,
      productCode: inquiry.product_code,
      warrantyStatus: inquiry.warranty_status,
      warrantyEndsOn: inquiry.warranty_ends_on,
      warrantyLabel: inquiry.warranty_label,
      previousVisitCount: inquiry.previous_visit_count,
      receivedAt: inquiry.received_at,
      updatedAt: inquiry.updated_at,
    })),
  };
}

export async function fetchSyntheticConsultantDashboardData(): Promise<SyntheticConsultantDashboardData> {
  const response = await requestApi<ConsultantDashboardDto>(
    "/consultant/dashboard",
  );
  if (!response.data) {
    throw new Error("상담사 Dashboard 응답에 데이터가 없습니다.");
  }
  return mapSyntheticConsultantDashboardDto(response.data);
}

export function canUseConsultantNoticeMock(
  useMockApi = appEnv.useMockApi,
  isDevelopment = import.meta.env.DEV,
) {
  return isDevelopment && useMockApi;
}

export function getDevelopmentConsultantDashboardData(): SyntheticConsultantDashboardData | null {
  return canUseConsultantNoticeMock()
    ? MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA
    : null;
}

export async function getSyntheticConsultantDashboardData(): Promise<SyntheticConsultantDashboardData> {
  const developmentMock = getDevelopmentConsultantDashboardData();
  if (developmentMock) return developmentMock;

  return fetchSyntheticConsultantDashboardData();
}

export async function getConsultantNoticePageData(): Promise<ConsultantNoticePageData> {
  if (canUseConsultantNoticeMock()) {
    return MOCK_CONSULTANT_NOTICE_PAGE_DATA;
  }

  const dashboard = await fetchSyntheticConsultantDashboardData();
  return {
    summary: dashboard.summary,
    notices: dashboard.notices,
  };
}

export async function fetchConsultantNoticeDetail(
  noticeId: string,
): Promise<ConsultantNotice> {
  const response = await requestApi<ConsultantDashboardNoticeDto>(
    `/consultant/notices/${encodeURIComponent(noticeId)}`,
  );
  if (!response.data) {
    throw new Error("상담사 공지 상세 응답에 데이터가 없습니다.");
  }
  return mapConsultantNoticeDto(response.data);
}

export async function getConsultantNoticeDetail(
  noticeId: string,
): Promise<ConsultantNotice> {
  if (!canUseConsultantNoticeMock()) {
    return fetchConsultantNoticeDetail(noticeId);
  }

  const notice = MOCK_CONSULTANT_NOTICE_PAGE_DATA.notices.find(
    (item) => item.noticeId === noticeId,
  );
  if (!notice) {
    throw new ApiClientError({
      kind: "NOT_FOUND",
      status: 404,
      code: "RESOURCE_NOT_FOUND",
      message: "공지사항을 찾을 수 없습니다.",
    });
  }
  return notice;
}
