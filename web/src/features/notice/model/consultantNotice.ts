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

export interface ConsultantDashboardConsultant {
  userId: string;
  name: string;
  department: string;
  position: string;
  extension: string;
  email: string;
}

export interface ConsultantDashboardTechnician {
  userId: string;
  name: string;
  branch: string;
  phone: string;
  email: string;
}

export interface ConsultantDashboardInquiry {
  inquiryId: string;
  inquiryCode: string;
  bucket: "NEW" | "IN_PROGRESS" | "COMPLETED";
  status: string;
  riskLevel: string;
  priority: string;
  title: string;
  detail: string;
  contact: string;
  address: string;
  customerName: string;
  customerCode: string;
  productName: string;
  productCode: string;
  warrantyStatus: "IN_WARRANTY" | "EXPIRED" | "NOT_REGISTERED";
  warrantyEndsOn: string | null;
  warrantyLabel: string;
  previousVisitCount: number;
  receivedAt: string;
  updatedAt: string;
}

/**
 * OpenAPI에 등록된 로컬 합성 Web G4 전용 Dashboard projection이다.
 * 운영형 일반 Dashboard 데이터로 확대하지 않는다.
 */
export interface SyntheticConsultantDashboardData
  extends ConsultantNoticePageData {
  dataClassification: "synthetic";
  generatedAt: string;
  consultants: readonly ConsultantDashboardConsultant[];
  technicians: readonly ConsultantDashboardTechnician[];
  inquiries: readonly ConsultantDashboardInquiry[];
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

export const MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA: SyntheticConsultantDashboardData = {
  dataClassification: "synthetic",
  generatedAt: "2026-08-20T00:00:00+09:00",
  ...MOCK_CONSULTANT_NOTICE_PAGE_DATA,
  consultants: [
    {
      userId: "mock-consultant-001",
      name: "김하윤",
      department: "고객케어팀",
      position: "팀장",
      extension: "02-3274-9501",
      email: "hayoon.kim@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-002",
      name: "한예나",
      department: "고객케어팀",
      position: "상담사",
      extension: "02-3274-9502",
      email: "yena.han@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-003",
      name: "임현우",
      department: "품질관리팀",
      position: "매니저",
      extension: "02-3274-9503",
      email: "hyunwoo.lim@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-004",
      name: "박지우",
      department: "품질관리팀",
      position: "담당",
      extension: "02-3274-9504",
      email: "jiwoo.park@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-005",
      name: "이서연",
      department: "방문지원팀",
      position: "매니저",
      extension: "02-3274-9505",
      email: "seoyeon.lee@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-006",
      name: "최지우",
      department: "방문지원팀",
      position: "담당",
      extension: "02-3274-9506",
      email: "jiwoo.choi@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-007",
      name: "정하윤",
      department: "시스템운영팀",
      position: "매니저",
      extension: "02-3274-9507",
      email: "hayoon.jeong@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-008",
      name: "강민준",
      department: "시스템운영팀",
      position: "담당",
      extension: "02-3274-9508",
      email: "minjun.kang@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-009",
      name: "김예린",
      department: "고객케어팀",
      position: "선임 상담사",
      extension: "02-3274-9509",
      email: "yerin.kim@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-010",
      name: "문서준",
      department: "고객케어팀",
      position: "상담사",
      extension: "02-3274-9510",
      email: "seojun.moon@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-011",
      name: "신채원",
      department: "품질관리팀",
      position: "선임",
      extension: "02-3274-9511",
      email: "chaewon.shin@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-012",
      name: "윤태호",
      department: "품질관리팀",
      position: "담당",
      extension: "02-3274-9512",
      email: "taeho.yoon@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-013",
      name: "조은서",
      department: "방문지원팀",
      position: "선임",
      extension: "02-3274-9513",
      email: "eunseo.cho@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-014",
      name: "백도윤",
      department: "방문지원팀",
      position: "담당",
      extension: "02-3274-9514",
      email: "doyoon.baek@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-015",
      name: "서유진",
      department: "시스템운영팀",
      position: "선임",
      extension: "02-3274-9515",
      email: "yujin.seo@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-016",
      name: "남지호",
      department: "시스템운영팀",
      position: "담당",
      extension: "02-3274-9516",
      email: "jiho.nam@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-017",
      name: "송다인",
      department: "고객경험팀",
      position: "팀장",
      extension: "02-3274-9517",
      email: "dain.song@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-018",
      name: "전시우",
      department: "고객경험팀",
      position: "매니저",
      extension: "02-3274-9518",
      email: "siwoo.jeon@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-019",
      name: "고민서",
      department: "고객경험팀",
      position: "담당",
      extension: "02-3274-9519",
      email: "minseo.ko@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-020",
      name: "황재민",
      department: "상담운영팀",
      position: "팀장",
      extension: "02-3274-9520",
      email: "jaemin.hwang@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-021",
      name: "안서아",
      department: "상담운영팀",
      position: "매니저",
      extension: "02-3274-9521",
      email: "seoa.ahn@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-022",
      name: "유건우",
      department: "상담운영팀",
      position: "담당",
      extension: "02-3274-9522",
      email: "geonwoo.yoo@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-023",
      name: "장수빈",
      department: "교육지원팀",
      position: "팀장",
      extension: "02-3274-9523",
      email: "subin.jang@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-024",
      name: "권나윤",
      department: "교육지원팀",
      position: "선임",
      extension: "02-3274-9524",
      email: "nayoon.kwon@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-025",
      name: "홍준서",
      department: "서비스기획팀",
      position: "팀장",
      extension: "02-3274-9525",
      email: "junseo.hong@waterbridge.co.kr",
    },
    {
      userId: "mock-consultant-026",
      name: "노아린",
      department: "서비스기획팀",
      position: "매니저",
      extension: "02-3274-9526",
      email: "arin.noh@waterbridge.co.kr",
    },
  ],
  technicians: [
    {
      userId: "mock-technician-001",
      name: "오민석",
      branch: "서울동부지사",
      phone: "010-2501-5001",
      email: "minseok.oh@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-002",
      name: "서지훈",
      branch: "서울서부지사",
      phone: "010-2501-5002",
      email: "jihoon.seo@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-003",
      name: "윤도현",
      branch: "경기남부지사",
      phone: "010-2501-5003",
      email: "dohyun.yoon@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-004",
      name: "배수아",
      branch: "경기북부지사",
      phone: "010-2501-5004",
      email: "sua.bae@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-005",
      name: "김성현",
      branch: "서울동부지사",
      phone: "010-2501-5005",
      email: "sunghyun.kim@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-006",
      name: "정유나",
      branch: "서울서부지사",
      phone: "010-2501-5006",
      email: "yuna.jeong@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-007",
      name: "한도윤",
      branch: "경기남부지사",
      phone: "010-2501-5007",
      email: "doyoon.han@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-008",
      name: "임채린",
      branch: "경기북부지사",
      phone: "010-2501-5008",
      email: "chaerin.lim@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-009",
      name: "박건호",
      branch: "부산경남지사",
      phone: "010-2501-5009",
      email: "geonho.park@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-010",
      name: "이하은",
      branch: "대전충청지사",
      phone: "010-2501-5010",
      email: "haeun.lee@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-011",
      name: "최현준",
      branch: "대구경북지사",
      phone: "010-2501-5011",
      email: "hyunjun.choi@waterbridge.co.kr",
    },
    {
      userId: "mock-technician-012",
      name: "양소희",
      branch: "광주전라지사",
      phone: "010-2501-5012",
      email: "sohee.yang@waterbridge.co.kr",
    },
  ],
  inquiries: [],
};
