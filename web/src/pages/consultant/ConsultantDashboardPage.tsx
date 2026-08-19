import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import Pagination from "../../common/components/data-display/Pagination";
import {
  formatContractDateTimePrecise,
} from "../../common/date-time/contractDateTime";
import EmptyState from "../../common/components/feedback/EmptyState";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import {
  toInquiryId,
  type InquiryId,
} from "../../entities/inquiry/inquiryIdentifiers";
import CompactConsultationDesk from "../../features/consultation/components/CompactConsultationDesk";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import ConsultantUserMenu from "../../features/consultation/components/ConsultantUserMenu";
import useCounselorQueueFilters from "../../features/consultation/hooks/useCounselorQueueFilters";
import { useConsultantInquiryListQuery } from "../../features/consultation/hooks/useConsultantWorkspaceQueries";
import type {
  ConsultantInquiryListQuery,
  ConsultantRiskLevelDto,
  ConsultantInquiryStatusDto,
} from "../../features/consultation/api/consultantWorkspaceRemoteTypes";
import {
  COUNSELOR_QUEUE_PAGE_SIZE,
  PRIORITY_LABELS,
  getCounselorWorkBucket,
  formatWaitingTime,
  STATUS_LABELS,
  WORK_BUCKET_LABELS,
} from "../../features/consultation/model/consultantWorkspaceModel";
import type {
  CounselorAllowedAction,
  CounselorInquiry,
  CounselorStatus,
  CounselorWorkBucket,
} from "../../features/consultation/model/consultantWorkspaceTypes";
import type { ConsultantInquiryListItemViewModel } from "../../features/consultation/model/consultantWorkspaceRemoteMapper";
import {
  consultantWorkspaceRepository,
  createConsultantWorkspaceRepository,
} from "../../features/consultation/repositories/consultantWorkspaceRepository";
import {
  consultantWorkspaceDataRepository,
  createMockConsultantInquiryListViewModel,
} from "../../features/consultation/repositories/consultantWorkspaceDataRepository";
import "./ConsultantDashboardPage.css";
import "./ConsultantDashboardTheme.css";
import "./ConsultantInquiryPearlTheme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";
import "../../common/styles/water-glass-theme.css";
import "./ConsultantOperationsTone.css";
import "./ConsultantWorkDashboard.css";

const BUCKET_STATUSES: Record<
  CounselorWorkBucket,
  readonly ConsultantInquiryStatusDto[]
> = {
  NEW: ["CONSULTATION_REQUIRED", "REOPENED"],
  IN_PROGRESS: [
    "DRAFT",
    "QUESTIONNAIRE_IN_PROGRESS",
    "AI_GUIDANCE",
    "CONSULTATION_IN_PROGRESS",
    "VISIT_REVIEW_PENDING",
    "VISIT_SCHEDULING",
    "VISIT_SCHEDULED",
    "COMPLETION_PENDING",
    "REVISIT_REQUIRED",
  ],
  COMPLETED: ["RESOLVED", "CANCELLED"],
};

const ACTIVE_WORK_STATUSES = [
  ...BUCKET_STATUSES.NEW,
  ...BUCKET_STATUSES.IN_PROGRESS,
] as const;

const RISK_SECTIONS: readonly {
  id: ConsultantRiskLevelDto;
  label: string;
}[] = [
  { id: "danger", label: "긴급 문의" },
  { id: "caution", label: "주의 문의" },
  { id: "general", label: "일반 문의" },
];

type RiskSectionStatusFilter = "ALL" | ConsultantInquiryStatusDto;
type WorkFocus = "ALL" | "NEW" | "IN_PROGRESS" | "AI_REVIEW";
type AiReviewDecision = "APPROVED" | "REJECTED";
type DashboardInquiryListItem = Omit<
  ConsultantInquiryListItemViewModel,
  "status" | "allowedActions"
> & {
  status: CounselorStatus;
  allowedActions: readonly { code: string; label: string }[];
};

const RISK_LABELS: Record<ConsultantRiskLevelDto, string> = {
  danger: "긴급",
  caution: "주의",
  general: "일반",
};

const WORK_FOCUS_OPTIONS: readonly {
  id: WorkFocus;
  label: string;
}[] = [
  { id: "ALL", label: "전체 문의" },
  { id: "NEW", label: "새 문의" },
  { id: "IN_PROGRESS", label: "처리 중인 문의" },
];

const DASHBOARD_NOTICES = [
  { category: "긴급", title: "긴급 문의 응대 절차 안내", department: "고객케어팀", date: "2026.08.18" },
  { category: "이벤트", title: "고객 만족도 조사 참여 이벤트", department: "고객경험팀", date: "2026.08.18" },
  { category: "시스템", title: "상담 시스템 정기 점검 안내", department: "시스템운영팀", date: "2026.08.17" },
  { category: "근무", title: "8월 상담 근무 일정 확인 요청", department: "고객케어팀", date: "2026.08.16" },
  { category: "복지", title: "임직원 건강검진 신청 안내", department: "경영지원팀", date: "2026.08.15" },
  { category: "교육", title: "정수기 안전 점검 상담 교육", department: "품질관리팀", date: "2026.08.14" },
] as const;

const DASHBOARD_DEPARTMENTS = [
  "고객케어팀",
  "품질관리팀",
  "방문지원팀",
  "시스템운영팀",
] as const;

const DASHBOARD_EMPLOYEE_CONTACTS = [
  { name: "김하윤", department: "고객케어팀", position: "팀장", extension: "02-3274-9501", email: "hayoon.kim@waterbridge.co.kr" },
  { name: "한예나", department: "고객케어팀", position: "상담사", extension: "02-3274-9502", email: "yena.han@waterbridge.co.kr" },
  { name: "임현우", department: "품질관리팀", position: "매니저", extension: "02-3274-9503", email: "hyunwoo.lim@waterbridge.co.kr" },
  { name: "박지우", department: "품질관리팀", position: "담당", extension: "02-3274-9504", email: "jiwoo.park@waterbridge.co.kr" },
  { name: "이서연", department: "방문지원팀", position: "매니저", extension: "02-3274-9505", email: "seoyeon.lee@waterbridge.co.kr" },
  { name: "최지우", department: "방문지원팀", position: "담당", extension: "02-3274-9506", email: "jiwoo.choi@waterbridge.co.kr" },
  { name: "정하윤", department: "시스템운영팀", position: "매니저", extension: "02-3274-9507", email: "hayoon.jeong@waterbridge.co.kr" },
  { name: "강민준", department: "시스템운영팀", position: "담당", extension: "02-3274-9508", email: "minjun.kang@waterbridge.co.kr" },
] as const;

const VISIT_TECHNICIAN_DIRECTORY = "방문기사 연락처";

const DASHBOARD_VISIT_TECHNICIAN_CONTACTS = [
  { name: "오민석", branch: "서울동부지사", contact: "010-2501-5001", email: "minseok.oh@waterbridge.co.kr" },
  { name: "서지훈", branch: "서울서부지사", contact: "010-2501-5002", email: "jihoon.seo@waterbridge.co.kr" },
  { name: "윤도현", branch: "경기남부지사", contact: "010-2501-5003", email: "dohyun.yoon@waterbridge.co.kr" },
  { name: "배수아", branch: "경기북부지사", contact: "010-2501-5004", email: "sua.bae@waterbridge.co.kr" },
] as const;

function getWaitingMinutes(inquiry: DashboardInquiryListItem) {
  return Math.max(0, Math.floor(inquiry.waitingSeconds / 60));
}

function requiresImmediateCall(inquiry: DashboardInquiryListItem) {
  if (["RESOLVED", "CANCELLED"].includes(inquiry.status)) return false;
  const canStartConsultation = inquiry.allowedActions.some((action) =>
    ["START_CONSULTATION", "RESUME_CONSULTATION"].includes(action.code),
  );
  return (
    canStartConsultation ||
    inquiry.status === "REOPENED" ||
    inquiry.status === "CONSULTATION_REQUIRED" ||
    (inquiry.riskLevel === "danger" &&
      inquiry.status === "CONSULTATION_IN_PROGRESS")
  );
}

function getCallReason(inquiry: DashboardInquiryListItem) {
  if (["RESOLVED", "CANCELLED"].includes(inquiry.status)) {
    return "처리 이력 확인";
  }
  if (inquiry.riskLevel === "danger") return "안전 위험 확인 필요";
  if (inquiry.status === "REOPENED") return "동일 증상 재문의";
  if (inquiry.status === "CONSULTATION_REQUIRED") return "상담 연결 요청";
  if (inquiry.priority === "URGENT") return "긴급 처리 요청";
  return "현재 단계 확인";
}

function getNextActionLabel(inquiry: DashboardInquiryListItem) {
  return inquiry.allowedActions[0]?.label ?? STATUS_LABELS[inquiry.status];
}

function getWorkPriorityScore(inquiry: DashboardInquiryListItem) {
  const riskScore = { danger: 300, caution: 200, general: 100 };
  const priorityScore = { URGENT: 80, HIGH: 50, NORMAL: 20, LOW: 0 };
  return (
    (requiresImmediateCall(inquiry) ? 1000 : 0) +
    riskScore[inquiry.riskLevel] +
    priorityScore[inquiry.priority] +
    Math.min(180, getWaitingMinutes(inquiry))
  );
}

function isAiReviewCandidate(
  inquiry: DashboardInquiryListItem,
  detail?: CounselorInquiry,
) {
  if (["RESOLVED", "CANCELLED"].includes(inquiry.status)) return false;
  if (detail) {
    return (
      detail.aiStatus === "COMPLETED" &&
      !detail.confirmedSummary &&
      [
        "CONSULTATION_REQUIRED",
        "CONSULTATION_IN_PROGRESS",
        "VISIT_REVIEW_PENDING",
      ].includes(inquiry.status)
    );
  }
  return inquiry.allowedActions.some((action) =>
    ["UPDATE_CONSULTATION_SUMMARY", "CONFIRM_CONSULTATION_SUMMARY"].includes(
      action.code,
    ),
  );
}

const INITIAL_RISK_SECTION_STATUS_FILTERS: Record<
  ConsultantRiskLevelDto,
  RiskSectionStatusFilter
> = {
  danger: "ALL",
  caution: "ALL",
  general: "ALL",
};

function getInitialBucket(search: string): CounselorWorkBucket {
  const bucket = new URLSearchParams(search).get("bucket");
  return bucket === "IN_PROGRESS" || bucket === "COMPLETED" ? bucket : "NEW";
}

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { filters, hasChangedConditions, resetFilters, setFilters } =
    useCounselorQueueFilters();
  const [activeBucket, setActiveBucket] =
    useState<CounselorWorkBucket>(() => getInitialBucket(location.search));
  const [riskSectionStatusFilters, setRiskSectionStatusFilters] = useState(
    INITIAL_RISK_SECTION_STATUS_FILTERS,
  );
  const [openRiskStatusFilter, setOpenRiskStatusFilter] =
    useState<ConsultantRiskLevelDto | null>(null);
  const [activeRiskSection, setActiveRiskSection] =
    useState<ConsultantRiskLevelDto>("danger");
  const [workFocus, setWorkFocus] = useState<WorkFocus>("NEW");
  const [selectedContactDepartment, setSelectedContactDepartment] =
    useState<string | null>(null);
  const [contactQuery, setContactQuery] = useState("");
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [reviewDrafts, setReviewDrafts] = useState<Record<string, string>>({});
  const [reviewDecisions, setReviewDecisions] = useState<
    Record<string, AiReviewDecision>
  >({});
  const [reviewNotice, setReviewNotice] = useState<string | null>(null);
  const [selectedInquiryId, setSelectedInquiryId] =
    useState<InquiryId | null>(null);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const [inquiryStateUpdates, setInquiryStateUpdates] = useState<
    Record<
      string,
      {
        status: CounselorStatus;
        stateVersion: number;
        allowedActions: readonly CounselorAllowedAction[];
      }
    >
  >({});

  const mockState = new URLSearchParams(location.search).get("mockState");
  const repositoryQuery = useMemo<ConsultantInquiryListQuery>(
    () => ({
      q: filters.query || undefined,
      status: BUCKET_STATUSES[activeBucket],
      riskLevel:
        filters.risk !== "ALL" && filters.risk !== "UNKNOWN"
          ? [filters.risk.toLowerCase() as "general" | "caution" | "danger"]
          : undefined,
      priority:
        filters.priority !== "ALL" && filters.priority !== "UNKNOWN"
          ? [filters.priority]
          : undefined,
      from: filters.receivedFrom || undefined,
      to: filters.receivedTo || undefined,
      sort: filters.sort,
      page: filters.page,
      size: COUNSELOR_QUEUE_PAGE_SIZE,
    }),
    [
      activeBucket,
      filters.page,
      filters.priority,
      filters.query,
      filters.receivedFrom,
      filters.receivedTo,
      filters.risk,
      filters.sort,
    ],
  );
  const listQuery = useConsultantInquiryListQuery(repositoryQuery);
  const overviewRepositoryQuery = useMemo<ConsultantInquiryListQuery>(
    () => ({
      status: ACTIVE_WORK_STATUSES,
      sort: "RISK_DESC",
      page: 1,
      size: 100,
    }),
    [],
  );
  const overviewQuery = useConsultantInquiryListQuery(overviewRepositoryQuery);
  const remoteOverviewHasEmptyWorkBucket =
    overviewQuery.status === "success" &&
    (!overviewQuery.data?.items.some((inquiry) =>
      BUCKET_STATUSES.NEW.includes(inquiry.status),
    ) ||
      !overviewQuery.data?.items.some((inquiry) =>
        BUCKET_STATUSES.IN_PROGRESS.includes(inquiry.status),
      ));
  const useDesignMockFallback =
    import.meta.env.DEV &&
    consultantWorkspaceDataRepository.dataSource === "REMOTE" &&
    (remoteOverviewHasEmptyWorkBucket ||
      listQuery.status === "error" ||
      overviewQuery.status === "error" ||
      (listQuery.status === "success" &&
        (listQuery.data?.pageInfo.total ?? 0) === 0));
  const useDashboardMockData =
    consultantWorkspaceDataRepository.dataSource === "MOCK" ||
    useDesignMockFallback;
  const designMockWorkspaceRepository = useMemo(
    () => createConsultantWorkspaceRepository(true, "DESIGN_SCENARIOS"),
    [],
  );
  const activeWorkspaceRepository = useDesignMockFallback
    ? designMockWorkspaceRepository
    : consultantWorkspaceRepository;
  const queryData = useMemo(
    () => {
      if (useDesignMockFallback) {
        return createMockConsultantInquiryListViewModel(
          repositoryQuery,
          "DESIGN_SCENARIOS",
        );
      }
      return consultantWorkspaceDataRepository.dataSource === "MOCK"
        ? createMockConsultantInquiryListViewModel(repositoryQuery)
        : listQuery.data;
    },
    [listQuery.data, repositoryQuery, useDesignMockFallback],
  );
  const overviewData = useMemo(
    () => {
      if (useDesignMockFallback) {
        return createMockConsultantInquiryListViewModel(
          overviewRepositoryQuery,
          "DESIGN_SCENARIOS",
        );
      }
      return consultantWorkspaceDataRepository.dataSource === "MOCK"
        ? createMockConsultantInquiryListViewModel(overviewRepositoryQuery)
        : overviewQuery.data;
    },
    [overviewQuery.data, overviewRepositoryQuery, useDesignMockFallback],
  );
  const loadState = ["loading", "error", "forbidden"].includes(
    mockState ?? "",
  )
    ? (mockState as "loading" | "error" | "forbidden")
    : useDashboardMockData
      ? "ready"
      : listQuery.isForbidden
        ? "forbidden"
        : listQuery.status === "loading"
          ? "loading"
          : listQuery.status === "error"
            ? "error"
            : "ready";
  const sourceInquiries = useMemo(
    () =>
      mockState === "empty"
        ? []
        : (queryData?.items ?? []).map((inquiry) => ({
            ...inquiry,
            ...inquiryStateUpdates[inquiry.inquiryId],
          })),
    [inquiryStateUpdates, mockState, queryData?.items],
  );

  const displayedRiskSection =
    sourceInquiries.length === 0 ||
    sourceInquiries.some((inquiry) => inquiry.riskLevel === activeRiskSection)
      ? activeRiskSection
      : (RISK_SECTIONS.find((section) =>
          sourceInquiries.some((inquiry) => inquiry.riskLevel === section.id),
        )?.id ?? activeRiskSection);

  useEffect(() => {
    document.body.classList.add("compact-consultant-body");
    return () => document.body.classList.remove("compact-consultant-body");
  }, []);

  useEffect(() => {
    if (!openRiskStatusFilter) return;

    const closeFilter = (event: PointerEvent) => {
      if (
        event.target instanceof Element &&
        event.target.closest(".consultant-risk-section__filter")
      ) {
        return;
      }
      setOpenRiskStatusFilter(null);
    };
    const closeFilterOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenRiskStatusFilter(null);
    };

    document.addEventListener("pointerdown", closeFilter);
    window.addEventListener("keydown", closeFilterOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeFilter);
      window.removeEventListener("keydown", closeFilterOnEscape);
    };
  }, [openRiskStatusFilter]);

  useEffect(() => {
    if (!selectedInquiryId) return;

    document.body.classList.add("consultant-detail-open");
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedInquiryId(null);
    };
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.classList.remove("consultant-detail-open");
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [selectedInquiryId]);

  const bucketCounts = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(BUCKET_STATUSES).map(([bucket, statuses]) => [
          bucket,
          statuses.reduce(
            (total, status) => total + (queryData?.statusCounts[status] ?? 0),
            0,
          ),
        ]),
      ) as Record<CounselorWorkBucket, number>,
    [queryData?.statusCounts],
  );
  const queuePage = {
    currentPage: queryData?.pageInfo.page ?? filters.page,
    items: sourceInquiries,
    totalItems: mockState === "empty" ? 0 : (queryData?.pageInfo.total ?? 0),
    totalPages: Math.max(
      1,
      Math.ceil(
        (mockState === "empty" ? 0 : (queryData?.pageInfo.total ?? 0)) /
          (queryData?.pageInfo.size ?? COUNSELOR_QUEUE_PAGE_SIZE),
      ),
    ),
  };
  const overviewItems: readonly DashboardInquiryListItem[] =
    overviewData?.items ?? queuePage.items;
  const mockInquiryDetails = useMemo(
    () =>
      new Map<string, CounselorInquiry>(
        activeWorkspaceRepository
          .listConsultantQueue()
          .map((inquiry) => [inquiry.inquiryId, inquiry] as const),
      ),
    [activeWorkspaceRepository],
  );
  const aiReviewCandidates = overviewItems
    .filter(
      (inquiry) =>
        !reviewDecisions[inquiry.inquiryId] &&
        isAiReviewCandidate(
          inquiry,
          mockInquiryDetails.get(inquiry.inquiryId),
        ),
    )
    .sort((left, right) => {
      const riskScore = { danger: 3, caution: 2, general: 1 };
      return (
        riskScore[right.riskLevel] - riskScore[left.riskLevel] ||
        right.waitingSeconds - left.waitingSeconds
      );
    })
    .slice(0, useDashboardMockData ? 30 : undefined);
  const selectedReview =
    aiReviewCandidates.find(
      (inquiry) => inquiry.inquiryId === selectedReviewId,
    ) ??
    aiReviewCandidates[0] ??
    null;
  const selectedReviewDetail = selectedReview
    ? mockInquiryDetails.get(selectedReview.inquiryId)
    : undefined;
  const selectedReviewDraft = selectedReview
    ? (reviewDrafts[selectedReview.inquiryId] ??
      selectedReviewDetail?.aiSummaryRevision ??
      selectedReviewDetail?.aiSummaryOriginal ??
      "")
    : "";
  const totalInquiryCount =
    bucketCounts.NEW + bucketCounts.IN_PROGRESS + bucketCounts.COMPLETED;
  const aiReviewCandidateIds = new Set(
    aiReviewCandidates.map((inquiry) => inquiry.inquiryId),
  );
  const selectedBase = activeWorkspaceRepository.findInquiry(selectedInquiryId);
  const selectedInquiry = selectedBase
    ? {
        ...selectedBase,
        ...inquiryStateUpdates[selectedBase.inquiryId],
      }
    : null;
  const changeRiskSection = (riskLevel: ConsultantRiskLevelDto) => {
    setActiveRiskSection(riskLevel);
    setOpenRiskStatusFilter(null);
    setSelectedInquiryId(null);
  };

  const changeWorkFocus = (focus: WorkFocus) => {
    if (focus === "NEW") {
      setActiveBucket("NEW");
    } else if (focus === "IN_PROGRESS") {
      setActiveBucket("IN_PROGRESS");
    }
    setWorkFocus(focus);
    setRiskSectionStatusFilters(INITIAL_RISK_SECTION_STATUS_FILTERS);
    setOpenRiskStatusFilter(null);
    setSelectedInquiryId(null);
    if (filters.page !== 1) setFilters({ ...filters, page: 1 });
  };

  const matchesWorkFocus = (inquiry: DashboardInquiryListItem) => {
    if (inquiry.status === "UNKNOWN") return false;
    if (workFocus === "NEW") return BUCKET_STATUSES.NEW.includes(inquiry.status);
    if (workFocus === "IN_PROGRESS") {
      return BUCKET_STATUSES.IN_PROGRESS.includes(inquiry.status);
    }
    if (workFocus === "AI_REVIEW") {
      return aiReviewCandidateIds.has(inquiry.inquiryId);
    }
    return true;
  };

  const finishAiReview = (decision: AiReviewDecision, revised: boolean) => {
    if (!selectedReview) return;
    if (revised && !selectedReviewDraft.trim()) {
      setReviewNotice("수정한 요약 내용을 입력해 주세요.");
      return;
    }
    setReviewDecisions((current) => ({
      ...current,
      [selectedReview.inquiryId]: decision,
    }));
    setReviewNotice(
      decision === "REJECTED"
        ? `${selectedReview.inquiryCode} 요약을 반려했습니다.`
        : revised
          ? `${selectedReview.inquiryCode} 요약을 수정 승인했습니다.`
          : `${selectedReview.inquiryCode} 요약을 승인했습니다.`,
    );
    setSelectedReviewId(null);
  };

  const handleRiskTabKeyDown = (
    event: ReactKeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) => {
    let nextIndex: number;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % RISK_SECTIONS.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex =
        (currentIndex - 1 + RISK_SECTIONS.length) % RISK_SECTIONS.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = RISK_SECTIONS.length - 1;
    } else {
      return;
    }

    event.preventDefault();
    const nextSection = RISK_SECTIONS[nextIndex];
    changeRiskSection(nextSection.id);
    window.requestAnimationFrame(() => {
      document.getElementById(`consultant-risk-tab-${nextSection.id}`)?.focus();
    });
  };

  const advanceToNextInquiry = () => {
    if (!selectedInquiry || queuePage.items.length < 2) {
      setSelectedInquiryId(null);
      return;
    }

    const currentIndex = queuePage.items.findIndex(
      (item) => item.inquiryId === selectedInquiry.inquiryId,
    );
    const nextInquiry =
      currentIndex < 0
        ? queuePage.items[0]
        : queuePage.items[currentIndex + 1] ?? queuePage.items[0];
    setSelectedInquiryId(toInquiryId(nextInquiry.inquiryId));
  };

  const openInquiry = (rawInquiryId: string) => {
    const inquiryId = toInquiryId(rawInquiryId);
    if (!inquiryId) return;

    if (useDashboardMockData) {
      setSelectedInquiryId(inquiryId);
      return;
    }
    navigate(createInquiryDetailPath(inquiryId), {
      state: { returnTo: `/consultant/dashboard${location.search}` },
    });
  };

  const openInquiryList = (
    bucket: "ALL" | "NEW" | "IN_PROGRESS",
    query = "",
  ) => {
    const params = new URLSearchParams({ bucket });
    if (query.trim()) params.set("q", query.trim());
    navigate(`/consultant/inquiries?${params.toString()}`);
  };

  const normalizedContactQuery = contactQuery.trim().toLowerCase();
  const isVisitTechnicianDirectory =
    selectedContactDepartment === VISIT_TECHNICIAN_DIRECTORY;
  const visibleContactEmployees = DASHBOARD_EMPLOYEE_CONTACTS.filter(
    (employee) =>
      (!selectedContactDepartment ||
        employee.department === selectedContactDepartment) &&
      (!normalizedContactQuery ||
        Object.values(employee).some((value) =>
          value.toLowerCase().includes(normalizedContactQuery),
        )),
  );
  const visibleVisitTechnicians = DASHBOARD_VISIT_TECHNICIAN_CONTACTS.filter(
    (technician) =>
      !normalizedContactQuery ||
      Object.values(technician).some((value) =>
        value.toLowerCase().includes(normalizedContactQuery),
      ),
  );
  const showContactTable =
    selectedContactDepartment !== null || normalizedContactQuery.length > 0;

  return (
    <div className="simple-consultant-app consultant-queue-app consultant-dashboard-app">
      <main className="simple-consultant-main consultant-queue-main">
        <h1 id="simple-page-title" className="consultant-visually-hidden">
          고객 문의
        </h1>

        <header className="simple-topbar consultant-main-header consultant-unified-header">
          <ConsultantUserMenu className="simple-user" />
        </header>

        <ConsultantQueueSidebar
          activeBucket={null}
          bucketCounts={bucketCounts}
          dashboardActive
        />

        <section
          id="consultant-dashboard-panel"
          className="counselor-home-summary"
          aria-labelledby="counselor-home-title"
        >
          <div className="counselor-home-summary__intro">
            <h1 id="counselor-home-title">
              <span>반갑습니다!</span>
              <br />
              <span className="counselor-home-summary__greeting-subline">
                오늘도 좋은 하루 되세요 😊
              </span>
            </h1>
          </div>

          <div className="counselor-home-metrics" aria-label="업무 요약">
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--total"
              onClick={() => openInquiryList("ALL")}
            >
              <span>전체 문의 수</span>
              <strong>{totalInquiryCount}</strong>
              <small className="counselor-home-metric__trend">
                <b>↑ +8</b>
                <span>전날 대비</span>
              </small>
            </button>
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--work"
              onClick={() => openInquiryList("NEW")}
            >
              <span>새 문의</span>
              <strong>{bucketCounts.NEW}</strong>
              <small className="counselor-home-metric__trend">
                <b>↑ +5</b>
                <span>전날 대비</span>
              </small>
            </button>
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--waiting"
              onClick={() => openInquiryList("IN_PROGRESS")}
            >
              <span>처리 중인 문의</span>
              <strong>{bucketCounts.IN_PROGRESS}</strong>
              <small className="counselor-home-metric__trend">
                <b>↓ -2</b>
                <span>전날 대비</span>
              </small>
            </button>
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--ai"
              onClick={() => openInquiryList("IN_PROGRESS")}
            >
              <span>AI 검토</span>
              <strong>{aiReviewCandidates.length}</strong>
              <small className="counselor-home-metric__trend">
                <b>↑ +3</b>
                <span>전날 대비</span>
              </small>
            </button>
          </div>
        </section>

        <section className="counselor-dashboard-info" aria-label="사내 업무 정보">
          <article className="counselor-dashboard-info__panel">
            <header>
              <h2>공지사항</h2>
            </header>
            <ul className="counselor-dashboard-notices">
              {DASHBOARD_NOTICES.map((notice) => (
                <li key={notice.title}>
                  <div>
                    <div className="counselor-dashboard-notices__headline">
                      <em data-category={notice.category}>{notice.category}</em>
                      <strong>{notice.title}</strong>
                    </div>
                    <span>{notice.department}</span>
                  </div>
                  <time dateTime={notice.date.replaceAll(".", "-")}>{notice.date}</time>
                </li>
              ))}
            </ul>
          </article>

          <article className="counselor-dashboard-info__panel">
            <header>
              <h2>직원 연락처</h2>
              <div className="counselor-dashboard-contact-tools">
                <label>
                  <svg
                    aria-hidden="true"
                    focusable="false"
                    viewBox="0 0 24 24"
                  >
                    <circle cx="10.5" cy="10.5" r="6.25" />
                    <path d="m15.25 15.25 4.5 4.5" />
                  </svg>
                  <input
                    type="search"
                    aria-label="직원 연락처 검색"
                    value={contactQuery}
                    onChange={(event) => setContactQuery(event.target.value)}
                  />
                </label>
              {showContactTable && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedContactDepartment(null);
                    setContactQuery("");
                  }}
                >
                  조직도
                </button>
              )}
              </div>
            </header>
            {showContactTable ? (
              <div className="counselor-dashboard-contact-table-wrap">
                <strong className="counselor-dashboard-contact-table__title">
                  {selectedContactDepartment ?? "검색 결과"}
                </strong>
                <table
                  className={`counselor-dashboard-contact-table counselor-dashboard-contact-table--${
                    isVisitTechnicianDirectory ? "visit" : "employee"
                  }`}
                >
                  <thead>
                    {isVisitTechnicianDirectory ? (
                      <tr>
                        <th>직원명</th>
                        <th>지사</th>
                        <th>연락처</th>
                        <th>이메일</th>
                      </tr>
                    ) : (
                      <tr>
                        <th>직원명</th>
                        <th>부서명</th>
                        <th>직책</th>
                        <th>내선번호</th>
                        <th>이메일</th>
                      </tr>
                    )}
                  </thead>
                  <tbody>
                    {isVisitTechnicianDirectory
                      ? visibleVisitTechnicians.map((technician) => (
                          <tr key={technician.email}>
                            <td>{technician.name}</td>
                            <td>{technician.branch}</td>
                            <td>{technician.contact}</td>
                            <td>
                              <a href={`mailto:${technician.email}`}>
                                {technician.email}
                              </a>
                            </td>
                          </tr>
                        ))
                      : visibleContactEmployees.map((employee) => (
                          <tr key={employee.email}>
                            <td>{employee.name}</td>
                            <td>{employee.department}</td>
                            <td>{employee.position}</td>
                            <td>{employee.extension}</td>
                            <td>
                              <a href={`mailto:${employee.email}`}>
                                {employee.email}
                              </a>
                            </td>
                          </tr>
                        ))}
                    {(isVisitTechnicianDirectory
                      ? visibleVisitTechnicians.length === 0
                      : visibleContactEmployees.length === 0) && (
                      <tr>
                        <td colSpan={isVisitTechnicianDirectory ? 4 : 5}>
                          검색 결과가 없습니다.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="counselor-dashboard-org" aria-label="조직도">
                <div className="counselor-dashboard-org__root">
                  <div>
                    <strong>고객지원본부</strong>
                  </div>
                </div>
                <span className="counselor-dashboard-org__stem" aria-hidden="true" />
                <div className="counselor-dashboard-org__departments">
                  {DASHBOARD_DEPARTMENTS.map((department) => (
                    <button
                      key={department}
                      type="button"
                      className="counselor-dashboard-org__department"
                      onClick={() => setSelectedContactDepartment(department)}
                    >
                      <div>
                        <b>{department}</b>
                        <small>
                          {
                            DASHBOARD_EMPLOYEE_CONTACTS.filter(
                              (employee) => employee.department === department,
                            ).length
                          }
                          명 · 연락처 보기
                        </small>
                      </div>
                      <i aria-hidden="true">›</i>
                    </button>
                  ))}
                </div>
                <div className="counselor-dashboard-org__field-directory">
                  <span className="counselor-dashboard-org__field-stem" aria-hidden="true" />
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedContactDepartment(VISIT_TECHNICIAN_DIRECTORY)
                    }
                  >
                    <div>
                      <b>방문기사 연락처</b>
                    </div>
                    <strong>
                      {DASHBOARD_VISIT_TECHNICIAN_CONTACTS.length}명
                      <i aria-hidden="true">›</i>
                    </strong>
                  </button>
                </div>
              </div>
            )}
          </article>
        </section>

        <div hidden>

        <section
          id="consultant-queue-panel"
          className="consultant-queue-panel"
          role="tabpanel"
          aria-label={WORK_BUCKET_LABELS[activeBucket]}
        >
          <div
            className="consultant-list consultant-risk-columns"
            aria-label="상담 문의 목록"
          >
            <header className="counselor-work-queue__header">
              <div>
                <h2>처리 필요한 업무</h2>
              </div>
              <nav className="counselor-work-focus" aria-label="업무 빠른 필터">
                {WORK_FOCUS_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className={workFocus === option.id ? "is-active" : ""}
                    aria-pressed={workFocus === option.id}
                    onClick={() => changeWorkFocus(option.id)}
                  >
                    {option.label}
                  </button>
                ))}
              </nav>
            </header>
            {loadState === "loading" ? (
              <LoadingState
                title="상담 문의 목록을 불러오고 있습니다."
                description="잠시만 기다려 주세요."
              />
            ) : loadState === "error" ? (
              <ErrorState
                title="상담 문의 목록을 불러오지 못했습니다."
                description="잠시 후 다시 시도해 주세요."
                onRetry={
                  mockState === "error"
                    ? () => navigate("/consultant/inquiries", { replace: true })
                    : listQuery.retry
                }
              />
            ) : loadState === "forbidden" ? (
              <ForbiddenState
                title="상담 문의 목록을 볼 권한이 없습니다."
                description="상담사 역할과 담당 범위를 확인해 주세요."
              />
            ) : queuePage.items.length === 0 ? (
              <EmptyState
                title={
                  hasChangedConditions
                    ? "검색 조건에 맞는 문의가 없습니다."
                    : `${WORK_BUCKET_LABELS[activeBucket]}가 없습니다.`
                }
                description={
                  hasChangedConditions
                    ? "검색어를 바꾸거나 초기화해 주세요."
                    : activeBucket === "NEW"
                      ? "새 문의가 들어오면 여기에 바로 표시됩니다."
                      : "현재 해당 상태의 문의가 없습니다."
                }
                actionLabel={hasChangedConditions ? "검색 초기화" : undefined}
                onAction={hasChangedConditions ? resetFilters : undefined}
              />
            ) : (
              <>
                <div
                  className="consultant-risk-tabs"
                  role="tablist"
                  aria-label="문의 유형"
                >
                  {RISK_SECTIONS.map((section, index) => {
                    const isActive = displayedRiskSection === section.id;
                    const count = queuePage.items.filter(
                      (inquiry) => inquiry.riskLevel === section.id,
                    ).length;

                    return (
                      <button
                        key={section.id}
                        id={`consultant-risk-tab-${section.id}`}
                        className={`consultant-risk-tab consultant-risk-tab--${section.id}${
                          isActive ? " is-active" : ""
                        }`}
                        type="button"
                        role="tab"
                        aria-selected={isActive}
                        aria-controls={`consultant-risk-panel-${section.id}`}
                        tabIndex={isActive ? 0 : -1}
                        onClick={() => changeRiskSection(section.id)}
                        onKeyDown={(event) =>
                          handleRiskTabKeyDown(event, index)
                        }
                      >
                        <span>{section.label}</span>
                        <b className="consultant-risk-tab__count">{count}</b>
                      </button>
                    );
                  })}
                </div>

                {RISK_SECTIONS.filter(
                  (section) => section.id === displayedRiskSection,
                ).map((section) => {
                const sectionInquiries = queuePage.items.filter(
                  (inquiry) => inquiry.riskLevel === section.id,
                );
                const statusFilter = riskSectionStatusFilters[section.id];
                const availableStatuses = BUCKET_STATUSES[activeBucket].filter(
                  (status) =>
                    sectionInquiries.some(
                      (inquiry) => inquiry.status === status,
                    ),
                );
                const inquiries = sectionInquiries
                  .filter(
                    (inquiry) =>
                      (statusFilter === "ALL" ||
                        inquiry.status === statusFilter) &&
                      matchesWorkFocus(inquiry),
                  )
                  .sort(
                    (left, right) =>
                      getWorkPriorityScore(right) - getWorkPriorityScore(left),
                  );

                return (
                  <section
                    key={section.id}
                    id={`consultant-risk-panel-${section.id}`}
                    className={`consultant-risk-section consultant-risk-section--${section.id}`}
                    role="tabpanel"
                    aria-labelledby={`consultant-risk-tab-${section.id}`}
                    tabIndex={0}
                  >
                    {activeBucket !== "NEW" && (
                      <header className="consultant-risk-section__head">
                        <div className="consultant-risk-section__tools">
                          <span className="consultant-risk-section__count">
                            {inquiries.length}
                          </span>
                          <div className="consultant-risk-section__filter">
                            <button
                              type="button"
                              className="consultant-risk-section__filter-trigger"
                              aria-label={`${section.label} 상태 필터`}
                              aria-haspopup="listbox"
                              aria-expanded={openRiskStatusFilter === section.id}
                              aria-controls={`consultant-risk-filter-${section.id}`}
                              onClick={() =>
                                setOpenRiskStatusFilter((current) =>
                                  current === section.id ? null : section.id,
                                )
                              }
                            >
                              <span>
                                {statusFilter === "ALL"
                                  ? "전체 상태"
                                  : STATUS_LABELS[statusFilter]}
                              </span>
                              <svg
                                viewBox="0 0 16 16"
                                aria-hidden="true"
                                focusable="false"
                              >
                                <path d="m4 6 4 4 4-4" />
                              </svg>
                            </button>

                            {openRiskStatusFilter === section.id && (
                              <div
                                id={`consultant-risk-filter-${section.id}`}
                                className="consultant-risk-section__filter-menu"
                                role="listbox"
                                aria-label={`${section.label} 상태 선택`}
                              >
                                {(["ALL", ...availableStatuses] as const).map(
                                  (status) => {
                                    const isSelected = statusFilter === status;
                                    return (
                                      <button
                                        key={status}
                                        type="button"
                                        role="option"
                                        aria-selected={isSelected}
                                        onClick={() => {
                                          setRiskSectionStatusFilters(
                                            (current) => ({
                                              ...current,
                                              [section.id]: status,
                                            }),
                                          );
                                          setOpenRiskStatusFilter(null);
                                          setSelectedInquiryId(null);
                                        }}
                                      >
                                        <span
                                          className="consultant-risk-section__filter-check"
                                          aria-hidden="true"
                                        >
                                          {isSelected ? "✓" : ""}
                                        </span>
                                        <span>
                                          {status === "ALL"
                                            ? "전체 상태"
                                            : STATUS_LABELS[status]}
                                        </span>
                                      </button>
                                    );
                                  },
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </header>
                    )}

                    <div className="consultant-risk-section__list">
                      {inquiries.length === 0 ? (
                        <p className="consultant-risk-section__empty">
                          {statusFilter === "ALL"
                            ? "해당 문의가 없습니다."
                            : "선택한 상태의 문의가 없습니다."}
                        </p>
                      ) : (
                        inquiries.map((inquiry) => (
                          <button
                            key={inquiry.inquiryId}
                            className={`v6-queue-item consultant-list-item${
                              selectedInquiryId === inquiry.inquiryId
                                ? " is-selected"
                                : ""
                            }`}
                            type="button"
                            aria-pressed={
                              selectedInquiryId === inquiry.inquiryId
                            }
                            aria-label={`${inquiry.inquiryCode} ${inquiry.customerDisplayNameMasked} ${inquiry.symptomSummary} 상세 열기`}
                            onClick={() => openInquiry(inquiry.inquiryId)}
                          >
                            <span className="consultant-list-item__signals">
                              <b
                                className={`consultant-signal consultant-signal--${inquiry.riskLevel}`}
                              >
                                {RISK_LABELS[inquiry.riskLevel]}
                              </b>
                              <b className={`consultant-priority consultant-priority--${inquiry.priority.toLowerCase()}`}>
                                우선 {PRIORITY_LABELS[inquiry.priority]}
                              </b>
                              {requiresImmediateCall(inquiry) && (
                                <em>전화 연결 필요</em>
                              )}
                            </span>
                            <span className="consultant-list-item__subject">
                              <strong>{inquiry.symptomSummary}</strong>
                              <small>{inquiry.inquiryCode}</small>
                            </span>

                            <span className="consultant-list-item__customer">
                              <strong>{inquiry.customerDisplayNameMasked}</strong>
                              <small>{inquiry.productModel}</small>
                            </span>

                            <span className="consultant-list-item__progress">
                              <strong>{STATUS_LABELS[inquiry.status]}</strong>
                              <small>
                                <time dateTime={inquiry.receivedAt}>
                                  접수 {formatContractDateTimePrecise(
                                    inquiry.receivedAt,
                                  ) ?? "시각 확인 불가"}
                                </time>
                                {" · "}경과 {formatWaitingTime(
                                  getWaitingMinutes(inquiry),
                                )}
                              </small>
                            </span>

                            <span className="consultant-list-item__next">
                              <small>{getCallReason(inquiry)}</small>
                              <strong>{getNextActionLabel(inquiry)}</strong>
                            </span>
                          </button>
                        ))
                      )}
                    </div>
                  </section>
                );
                })}
              </>
            )}
          </div>

          <aside className="counselor-ai-review" aria-labelledby="counselor-ai-review-title">
            <header className="counselor-ai-review__header">
              <div>
                <span>AI QUALITY CHECK</span>
                <h2 id="counselor-ai-review-title">AI 요약 검수</h2>
              </div>
              <b>{aiReviewCandidates.length}</b>
            </header>

            {reviewNotice && (
              <p className="counselor-ai-review__notice" role="status">
                {reviewNotice}
              </p>
            )}

            {!selectedReview ? (
              <div className="counselor-ai-review__empty">
                <span aria-hidden="true">✓</span>
                <strong>현재 검수할 요약이 없습니다.</strong>
                <p>새 AI 요약이 생성되면 원문과 함께 표시됩니다.</p>
              </div>
            ) : (
              <>
                <div className="counselor-ai-review__case">
                  <div>
                    <b
                      className={`consultant-signal consultant-signal--${selectedReview.riskLevel}`}
                    >
                      {RISK_LABELS[selectedReview.riskLevel]}
                    </b>
                    <span>{selectedReview.inquiryCode}</span>
                  </div>
                  <strong>{selectedReview.customerDisplayNameMasked}</strong>
                  <p>{selectedReview.productModel}</p>
                </div>

                <section className="counselor-ai-compare" aria-label="고객 원문과 AI 요약 비교">
                  <article>
                    <header>
                      <span>01</span>
                      <strong>고객 원문</strong>
                    </header>
                    <blockquote>{selectedReview.symptomSummary}</blockquote>
                  </article>
                  <article>
                    <header>
                      <span>02</span>
                      <strong>AI 요약 초안</strong>
                    </header>
                    {selectedReviewDetail ? (
                      <textarea
                        aria-label="AI 요약 수정본"
                        value={selectedReviewDraft}
                        onChange={(event) =>
                          setReviewDrafts((current) => ({
                            ...current,
                            [selectedReview.inquiryId]: event.target.value,
                          }))
                        }
                      />
                    ) : (
                      <div className="counselor-ai-review__integration">
                        <strong>요약 상세 연동 필요</strong>
                        <p>
                          목록에는 검수 행동만 제공됩니다. 원문·AI 초안 비교는 상담 상세 API 연동 후 활성화됩니다.
                        </p>
                      </div>
                    )}
                  </article>
                </section>

                <div className="counselor-ai-review__checklist" aria-label="요약 확인 항목">
                  <span>증상</span>
                  <span>안전 신호</span>
                  <span>고객 요청</span>
                  <span>다음 행동</span>
                </div>

                <div className="counselor-ai-review__actions">
                  <button
                    type="button"
                    className="is-reject"
                    disabled={!selectedReviewDetail}
                    onClick={() => finishAiReview("REJECTED", false)}
                  >
                    반려
                  </button>
                  <button
                    type="button"
                    disabled={!selectedReviewDetail}
                    onClick={() => finishAiReview("APPROVED", true)}
                  >
                    수정 승인
                  </button>
                  <button
                    type="button"
                    className="is-primary"
                    disabled={!selectedReviewDetail}
                    onClick={() => finishAiReview("APPROVED", false)}
                  >
                    승인
                  </button>
                </div>

                {aiReviewCandidates.length > 1 && (
                  <div className="counselor-ai-review__queue">
                    <span>다음 검수</span>
                    {aiReviewCandidates.slice(0, 4).map((inquiry) => (
                      <button
                        key={inquiry.inquiryId}
                        type="button"
                        className={
                          inquiry.inquiryId === selectedReview.inquiryId
                            ? "is-active"
                            : ""
                        }
                        aria-label={`${inquiry.inquiryCode} AI 요약 검수`}
                        onClick={() => setSelectedReviewId(inquiry.inquiryId)}
                      >
                        {inquiry.customerDisplayNameMasked}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </aside>

          {loadState === "ready" && queuePage.totalItems > 0 && (
            <Pagination
              page={queuePage.currentPage}
              totalItems={queuePage.totalItems}
              totalPages={queuePage.totalPages}
              onPageChange={(page) => setFilters({ ...filters, page })}
            />
          )}
        </section>
        </div>
      </main>

      {selectedInquiry && (
        <div className="consultant-detail-layer">
          <button
            type="button"
            className="consultant-detail-backdrop"
            aria-label="문의 상세 닫기"
            onClick={() => setSelectedInquiryId(null)}
          />
          <section
            className="consultant-detail-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="consultant-detail-title"
          >
            <header className="consultant-detail-drawer__head">
              <div>
                <small>{selectedInquiry.inquiryCode}</small>
                <h2 id="consultant-detail-title">
                  {selectedInquiry.customerName} · {selectedInquiry.symptomLabel}
                </h2>
                <p>선택한 문의의 상담과 기사 일정을 여기에서 처리합니다.</p>
              </div>
              <button
                type="button"
                aria-label="문의 상세 닫기"
                onClick={() => setSelectedInquiryId(null)}
              >
                <span aria-hidden="true">×</span>
              </button>
            </header>

            <div className="consultant-detail-drawer__body">
              <CompactConsultationDesk
                key={selectedInquiry.inquiryId}
                inquiry={selectedInquiry}
                autoAdvance={autoAdvance}
                onAutoAdvanceChange={setAutoAdvance}
                onAdvanceToNext={advanceToNextInquiry}
                onInquiryStateChange={(update) => {
                  setInquiryStateUpdates((current) => ({
                    ...current,
                    [selectedInquiry.inquiryId]: update,
                  }));
                  const nextBucket = getCounselorWorkBucket(update.status);
                  setActiveBucket(nextBucket);
                  setWorkFocus(
                    nextBucket === "NEW"
                      ? "NEW"
                      : nextBucket === "IN_PROGRESS"
                        ? "IN_PROGRESS"
                        : "ALL",
                  );
                }}
                onOpenFullDetail={() =>
                  navigate(createInquiryDetailPath(selectedInquiry.inquiryId), {
                    state: { returnTo: `/consultant/dashboard${location.search}` },
                  })
                }
              />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
