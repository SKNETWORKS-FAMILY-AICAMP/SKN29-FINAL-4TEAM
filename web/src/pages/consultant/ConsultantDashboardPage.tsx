import {
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  CONSULTANT_COMPLETED_LIST_PATH,
  createConsultantCompletionState,
} from "../../features/consultation/model/consultantCompletionNavigation";

import { appEnv } from "../../app/config/env";
import { useAuth } from "../../app/providers/authContext";
import { ROUTE_PATHS } from "../../app/router/routePaths";
import { ApiClientError } from "../../common/api/apiError";
import Pagination from "../../common/components/data-display/Pagination";
import {
  formatContractDateTimePrecise,
} from "../../common/date-time/contractDateTime";
import EmptyState from "../../common/components/feedback/EmptyState";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import FormSelect from "../../common/components/form/FormSelect";
import {
  toInquiryId,
  type InquiryId,
} from "../../entities/inquiry/inquiryIdentifiers";
import CompactConsultationDesk from "../../features/consultation/components/CompactConsultationDesk";
import HumanReviewQueue from "../../features/consultation/components/HumanReviewQueue";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import ConsultantHeaderBrand from "../../features/consultation/components/ConsultantHeaderBrand";
import ConsultantUserMenu from "../../features/consultation/components/ConsultantUserMenu";
import RemoteConsultantFirstDetailPanel from "../../features/consultation/components/RemoteConsultantFirstDetailPanel";
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
import { getConsultantDashboardDate } from "../../features/consultation/model/consultantDashboardDate";
import { getConsultantDisplayName } from "../../features/consultation/model/consultantDisplayName";
import { formatProductModelAndName } from "../../features/consultation/model/productDisplayName";
import {
  readRecentConsultantInquiryIds,
  rememberRecentConsultantInquiryId,
} from "../../features/consultation/model/recentConsultantInquiryIds";
import type {
  CounselorAllowedAction,
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
import {
  getDevelopmentConsultantDashboardData,
  getSyntheticConsultantDashboardData,
} from "../../features/notice/api/consultantNoticeApi";
import type { SyntheticConsultantDashboardData } from "../../features/notice/model/consultantNotice";
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

const DASHBOARD_OVERVIEW_QUERY: ConsultantInquiryListQuery = {
  status: [
    ...BUCKET_STATUSES.NEW,
    ...BUCKET_STATUSES.IN_PROGRESS,
    ...BUCKET_STATUSES.COMPLETED,
  ],
  page: 1,
  size: 100,
};

const RISK_SECTIONS: readonly {
  id: ConsultantRiskLevelDto;
  label: string;
}[] = [
  { id: "danger", label: "긴급 문의" },
  { id: "caution", label: "주의 문의" },
  { id: "general", label: "일반 문의" },
];

type RiskSectionStatusFilter = "ALL" | ConsultantInquiryStatusDto;
type WorkFocus = "ALL" | "NEW" | "IN_PROGRESS";
type RecentInquiryLoadState = "loading" | "ready" | "error";
type DashboardLoadState =
  | "loading"
  | "ready"
  | "unauthorized"
  | "forbidden"
  | "server_error"
  | "error";
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

interface RecentInquiryPreview {
  inquiryId: InquiryId;
  title: string;
  status: ConsultantInquiryStatusDto;
  riskLevel: ConsultantRiskLevelDto;
}

interface RecentInquiryResult {
  requestKey: string;
  previews: readonly RecentInquiryPreview[];
  failed: boolean;
}

const WORK_FOCUS_OPTIONS: readonly {
  id: WorkFocus;
  label: string;
}[] = [
  { id: "ALL", label: "전체 문의" },
  { id: "NEW", label: "새 문의" },
  { id: "IN_PROGRESS", label: "처리 중인 문의" },
];

const VISIT_TECHNICIAN_DIRECTORY = "방문기사 연락처";
const MAX_DASHBOARD_NOTICE_ITEMS = 5;
const DEVELOPMENT_DASHBOARD_DATA = getDevelopmentConsultantDashboardData();

function getDashboardLoadState(error: unknown): DashboardLoadState {
  if (!(error instanceof ApiClientError)) return "error";
  if (error.status === 401) return "unauthorized";
  if (error.status === 403) return "forbidden";
  if (error.status !== undefined && error.status >= 500) return "server_error";
  return "error";
}

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
  const { user } = useAuth();
  const consultantDisplayName = getConsultantDisplayName(user?.displayName);
  const [dashboardNow, setDashboardNow] = useState(() => new Date());
  const dashboardDate = useMemo(
    () => getConsultantDashboardDate(dashboardNow),
    [dashboardNow],
  );
  const { filters, hasChangedConditions, resetFilters, setFilters } =
    useCounselorQueueFilters();
  const [activeBucket, setActiveBucket] =
    useState<CounselorWorkBucket>(() => getInitialBucket(location.search));
  const [riskSectionStatusFilters, setRiskSectionStatusFilters] = useState(
    INITIAL_RISK_SECTION_STATUS_FILTERS,
  );
  const [activeRiskSection, setActiveRiskSection] =
    useState<ConsultantRiskLevelDto>("danger");
  const [workFocus, setWorkFocus] = useState<WorkFocus>("NEW");
  const [selectedContactDepartment, setSelectedContactDepartment] =
    useState<string | null>(null);
  const [contactQuery, setContactQuery] = useState("");
  const [dashboardData, setDashboardData] =
    useState<SyntheticConsultantDashboardData | null>(() =>
      DEVELOPMENT_DASHBOARD_DATA,
    );
  const [dashboardLoadState, setDashboardLoadState] =
    useState<DashboardLoadState>(() =>
      DEVELOPMENT_DASHBOARD_DATA ? "ready" : "loading",
    );
  const [dashboardRetryCount, setDashboardRetryCount] = useState(0);
  const [recentInquiryIds, setRecentInquiryIds] = useState<readonly InquiryId[]>(
    () =>
      user?.id ? readRecentConsultantInquiryIds(user.id) : [],
  );
  const [recentInquiryResult, setRecentInquiryResult] =
    useState<RecentInquiryResult>({
      requestKey: "",
      previews: [],
      failed: false,
    });
  const recentInquiryRequestKey = recentInquiryIds.join("|");
  const hasCurrentRecentInquiryResult =
    recentInquiryResult.requestKey === recentInquiryRequestKey;
  const recentInquiryPreviews = hasCurrentRecentInquiryResult
    ? recentInquiryResult.previews
    : [];
  const recentInquiryLoadState: RecentInquiryLoadState =
    recentInquiryIds.length === 0
      ? "ready"
      : !hasCurrentRecentInquiryResult
        ? "loading"
        : recentInquiryResult.failed
          ? "error"
          : "ready";

  useEffect(() => {
    const timerId = window.setInterval(() => setDashboardNow(new Date()), 60_000);

    return () => window.clearInterval(timerId);
  }, []);

  useEffect(() => {
    if (DEVELOPMENT_DASHBOARD_DATA) return;
    let active = true;

    getSyntheticConsultantDashboardData().then(
      (result) => {
        if (!active) return;
        setDashboardData(result);
        setDashboardLoadState("ready");
      },
      (error: unknown) => {
        if (!active) return;
        setDashboardData(null);
        setDashboardLoadState(getDashboardLoadState(error));
      },
    );

    return () => {
      active = false;
    };
  }, [dashboardRetryCount]);

  useEffect(() => {
    if (recentInquiryIds.length === 0) return;

    let active = true;

    void Promise.all(
      recentInquiryIds.map(async (recentInquiryId) => {
        try {
          const result =
            await consultantWorkspaceDataRepository.getInquiryDetail(
              recentInquiryId,
            );
          const inquiryId = toInquiryId(result.data.inquiryId);
          if (!inquiryId) return null;

          return {
            inquiryId,
            title: result.data.symptomAndQuestionnaire.symptomSummary,
            status: result.data.status,
            riskLevel: result.data.riskLevel,
          } satisfies RecentInquiryPreview;
        } catch {
          return null;
        }
      }),
    ).then((previews) => {
      if (!active) return;
      const availablePreviews = previews.filter(
        (preview): preview is RecentInquiryPreview => preview !== null,
      );
      setRecentInquiryResult({
        requestKey: recentInquiryRequestKey,
        previews: availablePreviews,
        failed: availablePreviews.length === 0,
      });
    });

    return () => {
      active = false;
    };
  }, [recentInquiryIds, recentInquiryRequestKey]);

  const [selectedInquiryId, setSelectedInquiryId] =
    useState<InquiryId | null>(null);
  const [hasUnsavedInquiryChanges, setHasUnsavedInquiryChanges] =
    useState(false);
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
  const closeSelectedInquiry = useCallback(() => {
    if (
      hasUnsavedInquiryChanges &&
      !window.confirm(
        "저장하지 않은 상담 내용이 있습니다. 닫으면 작성 내용이 사라집니다. 닫으시겠습니까?",
      )
    ) {
      return false;
    }

    setHasUnsavedInquiryChanges(false);
    setSelectedInquiryId(null);
    return true;
  }, [hasUnsavedInquiryChanges]);

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
  const overviewQuery = useConsultantInquiryListQuery(
    DASHBOARD_OVERVIEW_QUERY,
  );
  const useDesignMockFallback =
    appEnv.enableDesignMockFallback &&
    import.meta.env.DEV &&
    consultantWorkspaceDataRepository.dataSource === "REMOTE" &&
    (listQuery.status === "error" ||
      (listQuery.status === "success" &&
        (listQuery.data?.pageInfo.total ?? 0) === 0));
  const useOverviewDesignMockFallback =
    appEnv.enableDesignMockFallback &&
    import.meta.env.DEV &&
    consultantWorkspaceDataRepository.dataSource === "REMOTE" &&
    (overviewQuery.status === "error" ||
      (overviewQuery.status === "success" &&
        (overviewQuery.data?.pageInfo.total ?? 0) === 0));
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
    () =>
      useOverviewDesignMockFallback
        ? createMockConsultantInquiryListViewModel(
            DASHBOARD_OVERVIEW_QUERY,
            "DESIGN_SCENARIOS",
          )
        : consultantWorkspaceDataRepository.dataSource === "MOCK"
          ? createMockConsultantInquiryListViewModel(DASHBOARD_OVERVIEW_QUERY)
          : overviewQuery.data,
    [overviewQuery.data, useOverviewDesignMockFallback],
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
    if (!selectedInquiryId) return;

    document.body.classList.add("consultant-detail-open");
    const closeOnEscape = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !document.querySelector(".consultation-history-modal")
      ) {
        closeSelectedInquiry();
      }
    };
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.classList.remove("consultant-detail-open");
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [closeSelectedInquiry, selectedInquiryId]);

  useEffect(() => {
    if (!hasUnsavedInquiryChanges) return;

    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [hasUnsavedInquiryChanges]);

  const bucketCounts = useMemo(() => {
    if (!overviewData) return undefined;

    return Object.fromEntries(
      Object.entries(BUCKET_STATUSES).map(([bucket, statuses]) => [
        bucket,
        statuses.reduce(
          (total, status) =>
            total + (overviewData.statusCounts[status] ?? 0),
          0,
        ),
      ]),
    ) as Record<CounselorWorkBucket, number>;
  }, [overviewData]);
  const totalInquiryCount = overviewData?.pageInfo.total;
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
  const selectedBase = activeWorkspaceRepository.findInquiry(selectedInquiryId);
  const selectedInquiry = selectedBase
    ? {
        ...selectedBase,
        ...inquiryStateUpdates[selectedBase.inquiryId],
      }
    : null;
  const changeRiskSection = (riskLevel: ConsultantRiskLevelDto) => {
    if (!closeSelectedInquiry()) return;
    setActiveRiskSection(riskLevel);
  };

  const changeWorkFocus = (focus: WorkFocus) => {
    if (!closeSelectedInquiry()) return;
    if (focus === "NEW") {
      setActiveBucket("NEW");
    } else if (focus === "IN_PROGRESS") {
      setActiveBucket("IN_PROGRESS");
    }
    setWorkFocus(focus);
    setRiskSectionStatusFilters(INITIAL_RISK_SECTION_STATUS_FILTERS);
    if (filters.page !== 1) setFilters({ ...filters, page: 1 });
  };

  const matchesWorkFocus = (inquiry: DashboardInquiryListItem) => {
    if (inquiry.status === "UNKNOWN") return false;
    if (workFocus === "NEW") return BUCKET_STATUSES.NEW.includes(inquiry.status);
    if (workFocus === "IN_PROGRESS") {
      return BUCKET_STATUSES.IN_PROGRESS.includes(inquiry.status);
    }
    return true;
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
      closeSelectedInquiry();
      return;
    }

    const currentIndex = queuePage.items.findIndex(
      (item) => item.inquiryId === selectedInquiry.inquiryId,
    );
    const nextInquiry =
      currentIndex < 0
        ? queuePage.items[0]
        : queuePage.items[currentIndex + 1] ?? queuePage.items[0];
    const nextInquiryId = toInquiryId(nextInquiry.inquiryId);
    if (!nextInquiryId) return;
    if (user?.id) {
      setRecentInquiryIds(
        rememberRecentConsultantInquiryId(user.id, nextInquiryId),
      );
    }
    setSelectedInquiryId(nextInquiryId);
  };

  const openInquiry = (rawInquiryId: string) => {
    const inquiryId = toInquiryId(rawInquiryId);
    if (!inquiryId) return;
    if (
      selectedInquiryId &&
      selectedInquiryId !== inquiryId &&
      !closeSelectedInquiry()
    ) {
      return;
    }

    if (user?.id) {
      setRecentInquiryIds(
        rememberRecentConsultantInquiryId(user.id, inquiryId),
      );
    }

    setSelectedInquiryId(inquiryId);
  };

  const handleReviewedInquiryClaimed = (rawInquiryId: string) => {
    setActiveBucket("NEW");
    setWorkFocus("NEW");
    setRiskSectionStatusFilters(INITIAL_RISK_SECTION_STATUS_FILTERS);
    if (filters.page !== 1) setFilters({ ...filters, page: 1 });
    listQuery.retry();
    overviewQuery.retry();
    openInquiry(rawInquiryId);
  };

  const openInquiryList = (
    bucket: "ALL" | "NEW" | "IN_PROGRESS" | "COMPLETED",
    query = "",
  ) => {
    const params = new URLSearchParams({ bucket });
    if (query.trim()) params.set("q", query.trim());
    navigate(`/consultant/inquiries?${params.toString()}`);
  };

  const normalizedContactQuery = contactQuery.trim().toLowerCase();
  const isVisitTechnicianDirectory =
    selectedContactDepartment === VISIT_TECHNICIAN_DIRECTORY;
  const dashboardConsultants = dashboardData?.consultants ?? [];
  const dashboardTechnicians = dashboardData?.technicians ?? [];
  const dashboardNotices =
    dashboardData?.notices.slice(0, MAX_DASHBOARD_NOTICE_ITEMS) ?? [];
  const dashboardDepartments = [
    ...new Set(dashboardConsultants.map((consultant) => consultant.department)),
  ];
  const visibleContactEmployees = dashboardConsultants.filter(
    (employee) =>
      (!selectedContactDepartment ||
        employee.department === selectedContactDepartment) &&
      (!normalizedContactQuery ||
        Object.values(employee).some((value) =>
          value.toLowerCase().includes(normalizedContactQuery),
        )),
  );
  const visibleVisitTechnicians = dashboardTechnicians.filter(
    (technician) =>
      !normalizedContactQuery ||
      Object.values(technician).some((value) =>
        value.toLowerCase().includes(normalizedContactQuery),
      ),
  );
  const showContactTable =
    selectedContactDepartment !== null || normalizedContactQuery.length > 0;
  const retryDashboard = () => {
    setDashboardLoadState("loading");
    setDashboardRetryCount((current) => current + 1);
  };

  return (
    <div className="simple-consultant-app consultant-queue-app consultant-dashboard-app">
      <main className="simple-consultant-main consultant-queue-main">
        <h1 id="simple-page-title" className="consultant-visually-hidden">
          고객 문의
        </h1>

        <header className="simple-topbar consultant-main-header consultant-unified-header">
          <ConsultantHeaderBrand />
          <ConsultantUserMenu className="simple-user" />
        </header>

        <ConsultantQueueSidebar
          activeBucket={null}
          bucketCounts={bucketCounts}
          totalCount={totalInquiryCount}
          dashboardActive
        />

        <section
          id="consultant-dashboard-panel"
          className="counselor-home-summary"
          aria-labelledby="counselor-home-title"
        >
          <div className="counselor-home-summary__intro">
            <h1 id="counselor-home-title">
              {consultantDisplayName}님 반갑습니다!
            </h1>
            <p className="counselor-home-summary__greeting-subline">
              오늘도 좋은 하루 되세요 😊
            </p>
            <time
              className="counselor-home-summary__date"
              dateTime={dashboardDate.dateTime}
            >
              {dashboardDate.label}
            </time>
          </div>

          <div className="counselor-home-metrics" aria-label="업무 요약">
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--total"
              disabled={!overviewData}
              onClick={() => openInquiryList("ALL")}
            >
              <span>전체 문의 수</span>
              <strong>{totalInquiryCount ?? "—"}</strong>
            </button>
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--work"
              disabled={!overviewData}
              onClick={() => openInquiryList("ALL")}
            >
              <span>새 문의</span>
              <strong>{bucketCounts?.NEW ?? "—"}</strong>
            </button>
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--waiting"
              disabled={!overviewData}
              onClick={() => openInquiryList("IN_PROGRESS")}
            >
              <span>처리 중인 문의</span>
              <strong>{bucketCounts?.IN_PROGRESS ?? "—"}</strong>
            </button>
            <button
              type="button"
              className="counselor-home-metric counselor-home-metric--completed"
              disabled={!overviewData}
              onClick={() => openInquiryList("COMPLETED")}
            >
              <span>처리 완료된 문의</span>
              <strong>{bucketCounts?.COMPLETED ?? "—"}</strong>
            </button>
          </div>
        </section>

        <section className="counselor-dashboard-info" aria-label="사내 업무 정보">
          <article className="counselor-dashboard-info__panel counselor-dashboard-info__panel--recent">
            <header>
              <h2>최근 본 문의</h2>
            </header>
            {recentInquiryLoadState === "loading" ? (
              <p className="counselor-dashboard-recent__state" role="status">
                최근 본 문의를 불러오고 있습니다.
              </p>
            ) : recentInquiryLoadState === "error" ? (
              <p className="counselor-dashboard-recent__state" role="status">
                최근 본 문의를 표시하지 못했습니다.
              </p>
            ) : recentInquiryPreviews.length === 0 ? (
              <div className="counselor-dashboard-recent__empty">
                <strong>아직 본 문의가 없습니다.</strong>
                <span>문의 목록에서 상세를 열면 여기에 표시됩니다.</span>
              </div>
            ) : (
              <ul
                className="counselor-dashboard-recent"
                aria-label="최근 본 문의 목록"
              >
                {recentInquiryPreviews.map((inquiry) => (
                  <li key={inquiry.inquiryId}>
                    <button
                      type="button"
                      className="counselor-dashboard-recent__item"
                      data-risk={inquiry.riskLevel}
                      data-testid={`consultant-recent-inquiry-${inquiry.inquiryId}`}
                      data-e2e-sensitive="true"
                      onClick={() => openInquiry(inquiry.inquiryId)}
                      aria-label={`${inquiry.title} 다시 열기`}
                    >
                      <span
                        className="counselor-dashboard-recent__rail"
                        data-risk={inquiry.riskLevel}
                        aria-hidden="true"
                      />
                      <span className="counselor-dashboard-recent__copy">
                        <strong className="counselor-dashboard-recent__title">
                          {inquiry.title}
                        </strong>
                        <small className="counselor-dashboard-recent__meta">
                          {RISK_LABELS[inquiry.riskLevel]}
                        </small>
                      </span>
                      <span
                        className="counselor-dashboard-recent__status"
                        data-status={inquiry.status}
                      >
                        {STATUS_LABELS[inquiry.status]}
                      </span>
                      <i
                        className="counselor-dashboard-recent__arrow"
                        aria-hidden="true"
                      >
                        ›
                      </i>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="counselor-dashboard-info__panel counselor-dashboard-info__panel--notices">
            <header>
              <h2>공지사항</h2>
              <button
                type="button"
                className="counselor-dashboard-notices__more"
                aria-label="공지사항 전체 보기"
                onClick={() => navigate(ROUTE_PATHS.consultantNotices)}
              >
                <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>
            </header>
            {dashboardLoadState === "loading" ? (
              <LoadingState
                title="대시보드 공지를 불러오고 있습니다."
                description="Backend에서 최신 공지 정보를 확인하고 있습니다."
              />
            ) : dashboardLoadState === "unauthorized" ? (
              <ForbiddenState
                title="로그인이 만료되어 공지를 불러올 수 없습니다."
                description="다시 로그인한 뒤 대시보드를 확인해 주세요."
                actionLabel="로그인 화면으로"
                onAction={() => navigate(ROUTE_PATHS.login)}
              />
            ) : dashboardLoadState === "forbidden" ? (
              <ForbiddenState
                title="대시보드 공지를 볼 권한이 없습니다."
                description="상담사 계정과 활성 상태를 확인해 주세요."
              />
            ) : dashboardLoadState === "server_error" ? (
              <ErrorState
                title="대시보드 공지 서버에 일시적인 오류가 발생했습니다."
                description="잠시 후 다시 시도해 주세요."
                onRetry={retryDashboard}
              />
            ) : dashboardLoadState === "error" ? (
              <ErrorState
                title="대시보드 공지를 불러오지 못했습니다."
                description="네트워크 연결을 확인한 뒤 다시 시도해 주세요."
                onRetry={retryDashboard}
              />
            ) : dashboardNotices.length === 0 ? (
              <EmptyState
                title="등록된 공지사항이 없습니다."
                description="새 공지가 등록되면 이 영역에 표시됩니다."
              />
            ) : (
              <ul className="counselor-dashboard-notices">
                {dashboardNotices.map((notice) => (
                  <li key={notice.noticeId}>
                    <button
                      type="button"
                      className="counselor-dashboard-notices__item"
                      aria-label={`${notice.title} 상세 보기`}
                      onClick={() =>
                        navigate(
                          `${ROUTE_PATHS.consultantNotices}?noticeId=${encodeURIComponent(notice.noticeId)}`,
                        )
                      }
                    >
                      <div>
                        <div className="counselor-dashboard-notices__headline">
                          <em data-category={notice.category}>
                            {notice.category}
                          </em>
                          <strong>{notice.title}</strong>
                        </div>
                      </div>
                      <span className="counselor-dashboard-notices__meta">
                        <span>{notice.department}</span>
                        <i aria-hidden="true">|</i>
                        <time dateTime={notice.publishedOn}>
                          {notice.publishedOn.replaceAll("-", ".")}
                        </time>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </article>

          <article className="counselor-dashboard-info__panel counselor-dashboard-info__panel--contacts">
            <header>
              <h2>직원 연락처</h2>
              <div className="counselor-dashboard-contact-tools">
                <button
                  type="button"
                  aria-label="직원 연락처 전체 보기"
                  className="counselor-dashboard-contacts-all"
                  onClick={() => navigate(ROUTE_PATHS.consultantContacts)}
                >
                  전체 보기
                  <span aria-hidden="true">›</span>
                </button>
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
                    placeholder="검색"
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
            {dashboardLoadState === "loading" ? (
              <LoadingState
                title="직원 연락처를 불러오고 있습니다."
                description="Backend에서 최신 직원 정보를 확인하고 있습니다."
              />
            ) : dashboardLoadState === "unauthorized" ? (
              <ForbiddenState
                title="로그인이 만료되어 직원 연락처를 불러올 수 없습니다."
                description="다시 로그인한 뒤 대시보드를 확인해 주세요."
                actionLabel="로그인 화면으로"
                onAction={() => navigate(ROUTE_PATHS.login)}
              />
            ) : dashboardLoadState === "forbidden" ? (
              <ForbiddenState
                title="직원 연락처를 볼 권한이 없습니다."
                description="상담사 계정과 활성 상태를 확인해 주세요."
              />
            ) : dashboardLoadState === "server_error" ? (
              <ErrorState
                title="직원 연락처 서버에 일시적인 오류가 발생했습니다."
                description="잠시 후 다시 시도해 주세요."
                onRetry={retryDashboard}
              />
            ) : dashboardLoadState === "error" ? (
              <ErrorState
                title="직원 연락처를 불러오지 못했습니다."
                description="네트워크 연결을 확인한 뒤 다시 시도해 주세요."
                onRetry={retryDashboard}
              />
            ) : dashboardConsultants.length === 0 &&
              dashboardTechnicians.length === 0 ? (
              <EmptyState
                title="표시할 직원 연락처가 없습니다."
                description="Backend에 등록된 직원 연락처가 없습니다."
              />
            ) : showContactTable ? (
              <div className="counselor-dashboard-contact-table-wrap">
                <button
                  type="button"
                  className="counselor-dashboard-contact-table__back"
                  onClick={() => {
                    setSelectedContactDepartment(null);
                    setContactQuery("");
                  }}
                >
                  <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24">
                    <path d="m14.5 6-6 6 6 6" />
                  </svg>
                  <span>뒤로가기</span>
                </button>
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
                            <td>{technician.phone}</td>
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
                  {dashboardDepartments.map((department) => (
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
                            dashboardConsultants.filter(
                              (employee) => employee.department === department,
                            ).length
                          }
                          명
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
                      {dashboardTechnicians.length}명
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
                            <FormSelect
                              id={`consultant-risk-filter-${section.id}`}
                              aria-label={`${section.label} 상태 필터`}
                              value={statusFilter}
                              options={[
                                { value: "ALL", label: "전체 상태" },
                                ...availableStatuses.map((status) => ({ value: status, label: STATUS_LABELS[status] })),
                                ...(statusFilter !== "ALL" && !availableStatuses.includes(statusFilter)
                                  ? [{ value: statusFilter, label: STATUS_LABELS[statusFilter], disabled: true }]
                                  : []),
                              ]}
                              onChange={(value) => {
                                if (!closeSelectedInquiry()) return;
                                setRiskSectionStatusFilters((current) => ({
                                  ...current,
                                  [section.id]: value as RiskSectionStatusFilter,
                                }));
                              }}
                            />
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
                              <small>
                                {formatProductModelAndName(inquiry.productModel)}
                              </small>
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

          {useDashboardMockData ? (
            <aside className="counselor-ai-review" aria-labelledby="counselor-ai-review-title">
              <header className="counselor-ai-review__header">
                <div>
                  <span>AI QUALITY CHECK</span>
                  <h2 id="counselor-ai-review-title">AI 요약 검수</h2>
                </div>
                <b>—</b>
              </header>
              <div className="counselor-ai-review__empty">
                <span aria-hidden="true">○</span>
                <strong>디자인 Mock에서는 검수 저장을 사용하지 않습니다.</strong>
              </div>
            </aside>
          ) : (
            <HumanReviewQueue onClaimed={handleReviewedInquiryClaimed} />
          )}

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

      {selectedInquiryId && (
        <div className="consultant-detail-layer">
          <button
            type="button"
            className="consultant-detail-backdrop"
            aria-label="문의 상세 닫기"
            onClick={closeSelectedInquiry}
          />
          <section
            className="consultant-detail-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="consultant-detail-title"
          >
            {useDashboardMockData && selectedInquiry ? (
              <>
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
                    onClick={closeSelectedInquiry}
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
                  />
                </div>
              </>
            ) : !useDashboardMockData ? (
              <RemoteConsultantFirstDetailPanel
                key={selectedInquiryId}
                inquiryId={selectedInquiryId}
                returnTo={`/consultant/dashboard${location.search}`}
                onClose={closeSelectedInquiry}
                onRefreshWorkspace={() => {
                  listQuery.retry();
                  setDashboardRetryCount((current) => current + 1);
                }}
                onStatusChange={(status) => {
                  if (getCounselorWorkBucket(status) === "COMPLETED") {
                    navigate("/consultant/inquiries?bucket=COMPLETED");
                  }
                }}
                onSummaryConfirmed={(status) => {
                  setHasUnsavedInquiryChanges(false);
                  navigate(CONSULTANT_COMPLETED_LIST_PATH, {
                    state: createConsultantCompletionState("CONSULTATION_CONFIRMED", selectedInquiryId, status),
                  });
                }}
                onUnsavedChangesChange={setHasUnsavedInquiryChanges}
              />
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}
