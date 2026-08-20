import { appEnv } from "../../../app/config/env";
import { requestApi } from "../../../common/api/httpClient";
import {
  CONSULTANT_NOTICE_CATEGORY_LABELS,
  MOCK_CONSULTANT_NOTICE_PAGE_DATA,
  type ConsultantNotice,
  type ConsultantNoticeCategoryCode,
  type ConsultantNoticePageData,
} from "../model/consultantNotice";

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

interface ConsultantDashboardDto {
  summary: ConsultantDashboardSummaryDto;
  notices: readonly ConsultantDashboardNoticeDto[];
}

function mapNotice(dto: ConsultantDashboardNoticeDto): ConsultantNotice {
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

export async function getConsultantNoticePageData(): Promise<ConsultantNoticePageData> {
  if (appEnv.useMockApi) {
    return MOCK_CONSULTANT_NOTICE_PAGE_DATA;
  }

  const response = await requestApi<ConsultantDashboardDto>(
    "/operations/consultant/dashboard",
  );
  if (!response.data) {
    throw new Error("공지사항 응답에 데이터가 없습니다.");
  }

  return {
    summary: {
      total: response.data.summary.total,
      new: response.data.summary.new,
      inProgress: response.data.summary.in_progress,
      completed: response.data.summary.completed,
    },
    notices: response.data.notices.map(mapNotice),
  };
}
