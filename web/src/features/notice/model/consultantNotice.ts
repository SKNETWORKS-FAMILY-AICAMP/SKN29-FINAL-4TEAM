export type ConsultantNoticeCategoryCode =
  | "EMERGENCY"
  | "EVENT"
  | "SYSTEM"
  | "WORK"
  | "WELFARE"
  | "TRAINING";

export interface ConsultantNotice {
  noticeId: string;
  noticeCode: string;
  categoryCode: ConsultantNoticeCategoryCode;
  category: string;
  title: string;
  content: string;
  department: string;
  publishedOn: string;
}

export interface ConsultantNoticeSummary {
  total: number;
  new: number;
  inProgress: number;
  completed: number;
}

export interface ConsultantNoticePageData {
  summary: ConsultantNoticeSummary;
  notices: readonly ConsultantNotice[];
}

export const CONSULTANT_NOTICE_CATEGORY_LABELS: Readonly<
  Record<ConsultantNoticeCategoryCode, string>
> = {
  EMERGENCY: "긴급",
  EVENT: "이벤트",
  SYSTEM: "시스템",
  WORK: "근무",
  WELFARE: "복지",
  TRAINING: "교육",
};

export const CONSULTANT_NOTICE_FIXTURES: readonly ConsultantNotice[] = [
  {
    noticeId: "notice-emergency-001",
    noticeCode: "SYN-WEB-DASH-NOTICE-001",
    categoryCode: "EMERGENCY",
    category: "긴급",
    title: "긴급 문의 응대 절차 안내",
    content:
      "누수·감전·이상 냄새 등 안전 위험 문의는 고객에게 제품 사용 중지를 먼저 안내하고 긴급 상담 절차로 연결해 주세요.",
    department: "고객케어팀",
    publishedOn: "2026-08-18",
  },
  {
    noticeId: "notice-event-001",
    noticeCode: "SYN-WEB-DASH-NOTICE-002",
    categoryCode: "EVENT",
    category: "이벤트",
    title: "고객 만족도 조사 참여 이벤트",
    content:
      "상담 종료 고객에게 만족도 조사 참여 방법을 안내하되 응답을 강요하거나 상담 결과와 연계하지 말아 주세요.",
    department: "고객경험팀",
    publishedOn: "2026-08-18",
  },
  {
    noticeId: "notice-system-001",
    noticeCode: "SYN-WEB-DASH-NOTICE-003",
    categoryCode: "SYSTEM",
    category: "시스템",
    title: "상담 시스템 정기 점검 안내",
    content:
      "정기 점검 시간에는 신규 문의 저장이 지연될 수 있으므로 처리 중인 문의의 상태와 문의번호를 먼저 확인해 주세요.",
    department: "시스템운영팀",
    publishedOn: "2026-08-17",
  },
  {
    noticeId: "notice-work-001",
    noticeCode: "SYN-WEB-DASH-NOTICE-004",
    categoryCode: "WORK",
    category: "근무",
    title: "8월 상담 근무 일정 확인 요청",
    content:
      "팀별 근무표와 긴급 문의 당번을 확인하고 일정 변경이 필요한 경우 고객케어팀에 알려 주세요.",
    department: "고객케어팀",
    publishedOn: "2026-08-16",
  },
  {
    noticeId: "notice-welfare-001",
    noticeCode: "SYN-WEB-DASH-NOTICE-005",
    categoryCode: "WELFARE",
    category: "복지",
    title: "임직원 건강검진 신청 안내",
    content:
      "대상자는 사내 복지 절차에 따라 검진 일정을 신청하고 근무 일정과 겹치는 경우 사전에 조정해 주세요.",
    department: "경영지원팀",
    publishedOn: "2026-08-15",
  },
  {
    noticeId: "notice-training-001",
    noticeCode: "SYN-WEB-DASH-NOTICE-006",
    categoryCode: "TRAINING",
    category: "교육",
    title: "정수기 안전 점검 상담 교육",
    content:
      "제품별 안전 점검 문구와 방문 전환 기준을 숙지하고 확정 진단이나 임의 분해 안내를 하지 말아 주세요.",
    department: "품질관리팀",
    publishedOn: "2026-08-14",
  },
] as const;

export const MOCK_CONSULTANT_NOTICE_PAGE_DATA: ConsultantNoticePageData = {
  summary: {
    total: 90,
    new: 30,
    inProgress: 30,
    completed: 30,
  },
  notices: CONSULTANT_NOTICE_FIXTURES,
};
