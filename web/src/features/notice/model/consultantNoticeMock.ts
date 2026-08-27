import type {
  ConsultantNoticePageData,
  SyntheticConsultantDashboardData,
} from "./consultantNotice";

// Production builds resolve this safe module. Development and test builds
// replace it with web/tests/fixtures/consultantNoticeMock.ts through Vite.
export const MOCK_CONSULTANT_NOTICE_PAGE_DATA: ConsultantNoticePageData = {
  summary: {
    total: 0,
    new: 0,
    inProgress: 0,
    completed: 0,
  },
  notices: [],
};

export const MOCK_SYNTHETIC_CONSULTANT_DASHBOARD_DATA: SyntheticConsultantDashboardData = {
  dataClassification: "synthetic",
  generatedAt: "",
  ...MOCK_CONSULTANT_NOTICE_PAGE_DATA,
  consultants: [],
  technicians: [],
  inquiries: [],
};
