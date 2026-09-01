import {
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

import ConsultantCompletionNotice from "../../features/consultation/components/ConsultantCompletionNotice";
import {
  CONSULTANT_COMPLETED_LIST_PATH,
  createConsultantCompletionState,
} from "../../features/consultation/model/consultantCompletionNavigation";
import { appEnv } from "../../app/config/env";
import { useAuth } from "../../app/providers/authContext";
import { ApiClientError } from "../../common/api/apiError";
import Pagination from "../../common/components/data-display/Pagination";
import ErrorState from "../../common/components/feedback/ErrorState";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import LoadingState from "../../common/components/feedback/LoadingState";
import FormSelect from "../../common/components/form/FormSelect";
import {
  toInquiryId,
  type InquiryId,
} from "../../entities/inquiry/inquiryIdentifiers";
import CompactConsultationDesk from "../../features/consultation/components/CompactConsultationDesk";
import ConsultantQueueSidebar from "../../features/consultation/components/ConsultantQueueSidebar";
import ConsultantHeaderBrand from "../../features/consultation/components/ConsultantHeaderBrand";
import ConsultantUserMenu from "../../features/consultation/components/ConsultantUserMenu";
import RemoteConsultantFirstDetailPanel from "../../features/consultation/components/RemoteConsultantFirstDetailPanel";
import UnassignedConsultationQueue from "../../features/consultation/components/UnassignedConsultationQueue";
import type { ConsultantInquiryBucket } from "../../features/consultation/components/ConsultantQueueSidebar";
import useCounselorQueueFilters from "../../features/consultation/hooks/useCounselorQueueFilters";
import { useConsultantInquiryListQuery } from "../../features/consultation/hooks/useConsultantWorkspaceQueries";
import type {
  ConsultantInquiryListQuery,
  ConsultantRiskLevelDto,
  ConsultantInquiryStatusDto,
} from "../../features/consultation/api/consultantWorkspaceRemoteTypes";
import {
  formatWorkspaceDateTime,
  getCounselorWorkBucket,
  WORK_BUCKET_LABELS,
} from "../../features/consultation/model/consultantWorkspaceModel";
import { formatProductModelAndName } from "../../features/consultation/model/productDisplayName";
import {
  rememberRecentConsultantInquiryId,
} from "../../features/consultation/model/recentConsultantInquiryIds";
import type {
  CounselorAllowedAction,
  CounselorSort,
  CounselorStatus,
  CounselorWorkBucket,
} from "../../features/consultation/model/consultantWorkspaceTypes";
import {
  consultantWorkspaceRepository,
  createConsultantWorkspaceRepository,
} from "../../features/consultation/repositories/consultantWorkspaceRepository";
import {
  consultantWorkspaceDataRepository,
  createMockConsultantWorkspaceDataRepository,
  createMockConsultantInquiryListViewModel,
} from "../../features/consultation/repositories/consultantWorkspaceDataRepository";
import "./ConsultantDashboardPage.css";
import "./ConsultantDashboardTheme.css";
import "./ConsultantInquiryPearlTheme.css";
import "../../common/styles/watercare-liquid-glass-theme.css";
import "../../common/styles/pearl-workspace-v2.css";
import "../../common/styles/water-glass-theme.css";
import "./ConsultantOperationsTone.css";
import "./ConsultantInquiryListPage.css";

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

type RiskSectionId = "all" | ConsultantRiskLevelDto;
const INQUIRY_LIST_PAGE_SIZE = 5;

const RISK_SECTIONS: readonly {
  id: RiskSectionId;
  label: string;
}[] = [
  { id: "all", label: "전체 문의" },
  { id: "danger", label: "긴급 문의" },
  { id: "caution", label: "주의 문의" },
  { id: "general", label: "일반 문의" },
];

function getInitialBucket(search: string): ConsultantInquiryBucket {
  const bucket = new URLSearchParams(search).get("bucket");
  return bucket === "ALL" || bucket === "IN_PROGRESS" || bucket === "COMPLETED"
    ? bucket
    : "ALL";
}

function getSelectedInquiryId(search: string): InquiryId | null {
  return toInquiryId(new URLSearchParams(search).get("inquiryId"));
}

function getBucketStatuses(
  bucket: ConsultantInquiryBucket,
): readonly ConsultantInquiryStatusDto[] {
  return bucket === "ALL"
    ? [
        ...BUCKET_STATUSES.NEW,
        ...BUCKET_STATUSES.IN_PROGRESS,
        ...BUCKET_STATUSES.COMPLETED,
      ]
    : BUCKET_STATUSES[bucket];
}

function getBucketLabel(bucket: ConsultantInquiryBucket): string {
  return bucket === "ALL" ? "전체 문의" : WORK_BUCKET_LABELS[bucket];
}

function formatBucketElapsedTime(
  status: CounselorStatus,
  waitingSeconds: number,
): string {
  const waitingMinutes = Math.max(1, Math.floor(waitingSeconds / 60));
  const bucket = getCounselorWorkBucket(status);

  if (bucket === "NEW") return `${waitingMinutes}분 전`;
  if (bucket === "IN_PROGRESS") {
    return `${Math.max(1, Math.floor(waitingMinutes / 60))}시간 전`;
  }
  return `${Math.max(1, Math.floor(waitingMinutes / 1_440))}일 전`;
}

function isNetworkError(error: unknown): boolean {
  return (
    error instanceof ApiClientError &&
    (error.kind === "NETWORK_ERROR" || error.kind === "TIMEOUT")
  );
}

export default function ConsultantInquiryListPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { filters, setFilters } = useCounselorQueueFilters();
  const [searchDraft, setSearchDraft] = useState<string | null>(null);
  const searchValue = searchDraft ?? filters.query;
  const [activeBucket, setActiveBucket] =
    useState<ConsultantInquiryBucket>(() => getInitialBucket(location.search));
  const [activeRiskSection, setActiveRiskSection] =
    useState<RiskSectionId>("all");
  const [selectedInquiryId, setSelectedInquiryId] =
    useState<InquiryId | null>(() => getSelectedInquiryId(location.search));
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
  const mockState = new URLSearchParams(location.search).get("mockState");
  const repositoryQuery = useMemo<ConsultantInquiryListQuery>(
    () => ({
      q: filters.query || undefined,
      status: getBucketStatuses(activeBucket),
      riskLevel:
        activeRiskSection !== "all"
          ? [activeRiskSection]
          : filters.risk !== "ALL" && filters.risk !== "UNKNOWN"
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
      size: INQUIRY_LIST_PAGE_SIZE,
    }),
    [
      activeBucket,
      activeRiskSection,
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
      status: [
        ...BUCKET_STATUSES.NEW,
        ...BUCKET_STATUSES.IN_PROGRESS,
        ...BUCKET_STATUSES.COMPLETED,
      ],
      page: 1,
      size: 100,
    }),
    [],
  );
  const overviewQuery = useConsultantInquiryListQuery(overviewRepositoryQuery);
  const remoteOverviewHasEmptyBucket =
    overviewQuery.status === "success" &&
    Object.values(BUCKET_STATUSES).some(
      (statuses) =>
        !overviewQuery.data?.items.some((inquiry) =>
          statuses.includes(inquiry.status),
        ),
    );
  const useDesignMockFallback =
    appEnv.enableDesignMockFallback &&
    import.meta.env.DEV &&
    consultantWorkspaceDataRepository.dataSource === "REMOTE" &&
    (remoteOverviewHasEmptyBucket ||
      listQuery.status === "error" ||
      overviewQuery.status === "error" ||
      (listQuery.status === "success" &&
        (listQuery.data?.pageInfo.total ?? 0) === 0));
  const useListMockData =
    consultantWorkspaceDataRepository.dataSource === "MOCK" ||
    useDesignMockFallback;
  const designMockWorkspaceRepository = useMemo(
    () => createConsultantWorkspaceRepository(true, "DESIGN_SCENARIOS"),
    [],
  );
  const designMockConsultantDataRepository = useMemo(
    () => createMockConsultantWorkspaceDataRepository("DESIGN_SCENARIOS"),
    [],
  );
  const activeWorkspaceRepository = useDesignMockFallback
    ? designMockWorkspaceRepository
    : consultantWorkspaceRepository;
  const queryData = useMemo(
    () =>
      useDesignMockFallback
        ? createMockConsultantInquiryListViewModel(
            repositoryQuery,
            "DESIGN_SCENARIOS",
          )
        : consultantWorkspaceDataRepository.dataSource === "MOCK"
          ? createMockConsultantInquiryListViewModel(repositoryQuery)
        : listQuery.data,
    [listQuery.data, repositoryQuery, useDesignMockFallback],
  );
  const overviewData = useMemo(
    () =>
      useDesignMockFallback
        ? createMockConsultantInquiryListViewModel(
            overviewRepositoryQuery,
            "DESIGN_SCENARIOS",
          )
        : consultantWorkspaceDataRepository.dataSource === "MOCK"
          ? createMockConsultantInquiryListViewModel(overviewRepositoryQuery)
          : overviewQuery.data,
    [overviewQuery.data, overviewRepositoryQuery, useDesignMockFallback],
  );
  const loadState = ["loading", "error", "forbidden"].includes(
    mockState ?? "",
  )
    ? (mockState as "loading" | "error" | "forbidden")
    : useListMockData
      ? "ready"
      : listQuery.isForbidden
        ? "forbidden"
        : listQuery.status === "loading"
          ? "loading"
          : listQuery.status === "error"
            ? "error"
            : "ready";
  const hasNetworkError =
    mockState === "error" || isNetworkError(listQuery.error);
  const sourceInquiries = useMemo(() => {
    if (mockState === "empty") return [];

    const inquiries = (queryData?.items ?? []).map((inquiry) => ({
      ...inquiry,
      ...inquiryStateUpdates[inquiry.inquiryId],
    }));

    if (activeBucket !== "ALL" || filters.sort !== "UPDATED_DESC") {
      return inquiries;
    }

    return [...inquiries].sort((left, right) => {
      const leftIsNew = getCounselorWorkBucket(left.status) === "NEW";
      const rightIsNew = getCounselorWorkBucket(right.status) === "NEW";
      return Number(rightIsNew) - Number(leftIsNew);
    });
  }, [
    activeBucket,
    filters.sort,
    inquiryStateUpdates,
    mockState,
    queryData?.items,
  ]);

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

    const params = new URLSearchParams(location.search);
    if (!params.has("inquiryId")) return true;

    params.delete("inquiryId");
    const nextSearch = params.toString();
    navigate(
      `${location.pathname}${nextSearch ? `?${nextSearch}` : ""}`,
      { replace: true },
    );
    return true;
  }, [
    hasUnsavedInquiryChanges,
    location.pathname,
    location.search,
    navigate,
  ]);

  const displayedRiskSection = activeRiskSection;
  const riskSummaryCounts = useMemo(() => {
    const bucketStatuses = getBucketStatuses(activeBucket);
    const query = filters.query.trim().toLowerCase();
    const counts: Record<RiskSectionId, number> = {
      all: 0,
      danger: 0,
      caution: 0,
      general: 0,
    };

    if (mockState === "empty") return counts;

    (overviewData?.items ?? []).forEach((inquiry) => {
      if (!bucketStatuses.includes(inquiry.status)) return;
      if (
        query &&
        ![
          inquiry.inquiryCode,
          inquiry.customerDisplayNameMasked,
          inquiry.symptomSummary,
        ]
          .join(" ")
          .toLowerCase()
          .includes(query)
      ) {
        return;
      }
      if (
        filters.risk !== "ALL" &&
        filters.risk !== "UNKNOWN" &&
        inquiry.riskLevel !== filters.risk.toLowerCase()
      ) {
        return;
      }
      if (
        filters.priority !== "ALL" &&
        filters.priority !== "UNKNOWN" &&
        inquiry.priority !== filters.priority
      ) {
        return;
      }
      const receivedDate = inquiry.receivedAt.slice(0, 10);
      if (filters.receivedFrom && receivedDate < filters.receivedFrom) return;
      if (filters.receivedTo && receivedDate > filters.receivedTo) return;

      counts[inquiry.riskLevel] += 1;
      counts.all += 1;
    });

    return counts;
  }, [
    activeBucket,
    filters.priority,
    filters.query,
    filters.receivedFrom,
    filters.receivedTo,
    filters.risk,
    mockState,
    overviewData?.items,
  ]);

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

  const bucketCounts = useMemo(
    () => {
      const statusCounts = overviewData?.statusCounts ?? queryData?.statusCounts;
      return Object.fromEntries(
        Object.entries(BUCKET_STATUSES).map(([bucket, statuses]) => [
          bucket,
          statuses.reduce(
            (total, status) => total + (statusCounts?.[status] ?? 0),
            0,
          ),
        ]),
      ) as Record<CounselorWorkBucket, number>;
    },
    [overviewData?.statusCounts, queryData?.statusCounts],
  );
  const queueTotalItems = mockState === "empty"
    ? 0
    : (queryData?.pageInfo.total ?? 0);
  const queuePage = {
    currentPage: queryData?.pageInfo.page ?? filters.page,
    items: sourceInquiries,
    totalItems: queueTotalItems,
    totalPages: Math.max(
      1,
      Math.ceil(queueTotalItems / INQUIRY_LIST_PAGE_SIZE),
    ),
  };
  const selectedBase = activeWorkspaceRepository.findInquiry(selectedInquiryId);
  const selectedInquiry = selectedBase
    ? {
        ...selectedBase,
        ...inquiryStateUpdates[selectedBase.inquiryId],
      }
    : null;
  const resetInquiryListPage = () => {
    if (filters.page !== 1) setFilters({ ...filters, page: 1 });
  };
  const changeBucket = (bucket: ConsultantInquiryBucket) => {
    if (!closeSelectedInquiry()) return;
    setActiveBucket(bucket);
    const params = new URLSearchParams(location.search);
    params.set("bucket", bucket);
    params.delete("page");
    params.delete("inquiryId");
    navigate(`${location.pathname}?${params.toString()}`, { replace: true });
  };

  const changeRiskSection = (riskLevel: RiskSectionId) => {
    if (!closeSelectedInquiry()) return;
    setActiveRiskSection(riskLevel);
    resetInquiryListPage();
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
      rememberRecentConsultantInquiryId(user.id, nextInquiryId);
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
      rememberRecentConsultantInquiryId(user.id, inquiryId);
    }

    setSelectedInquiryId(inquiryId);
  };

  const handleUnassignedConsultationClaimed = (rawInquiryId: string) => {
    const inquiryId = toInquiryId(rawInquiryId);
    if (!inquiryId) return;

    setActiveBucket("ALL");
    setActiveRiskSection("all");
    if (filters.page !== 1) {
      setFilters({ ...filters, page: 1 });
    }

    const params = new URLSearchParams(location.search);
    params.set("bucket", "ALL");
    params.delete("page");
    navigate(`${location.pathname}?${params.toString()}`, { replace: true });

    listQuery.retry();
    overviewQuery.retry();
    if (user?.id) {
      rememberRecentConsultantInquiryId(user.id, inquiryId);
    }
    setSelectedInquiryId(inquiryId);
  };

  return (
    <div className="simple-consultant-app consultant-queue-app consultant-inquiry-list-app">
      <main className="simple-consultant-main consultant-queue-main">
        <h1 id="simple-page-title" className="consultant-visually-hidden">
          고객 문의
        </h1>

        <header className="simple-topbar consultant-main-header consultant-unified-header">
          <ConsultantHeaderBrand />
          <ConsultantUserMenu className="simple-user" />
        </header>

        <ConsultantQueueSidebar
          activeBucket={activeBucket}
          bucketCounts={bucketCounts}
          onBucketChange={changeBucket}
        />

        <section
          id="consultant-queue-panel"
          className={`consultant-queue-panel${
            activeBucket === "ALL"
              ? " consultant-queue-panel--with-unassigned"
              : ""
          }`}
          role="tabpanel"
          aria-label={getBucketLabel(activeBucket)}
        >
          <ConsultantCompletionNotice
            navigationState={location.state}
            onOpenInquiry={openInquiry}
            onDismiss={() => navigate(`${location.pathname}${location.search}`, { replace: true, state: null })}
          />
          {activeBucket === "ALL" && (
            <UnassignedConsultationQueue
              dataRepository={
                useDesignMockFallback
                  ? designMockConsultantDataRepository
                  : consultantWorkspaceDataRepository
              }
              onClaimed={handleUnassignedConsultationClaimed}
            />
          )}

          <div
            className="consultant-list consultant-risk-columns"
            aria-label="상담 문의 목록"
          >
            {loadState === "loading" ? (
              <LoadingState
                title="상담 문의 목록을 불러오고 있습니다."
                description="잠시만 기다려 주세요."
              />
            ) : loadState === "error" ? (
              <ErrorState
                title={
                  hasNetworkError
                    ? "네트워크 오류가 발생했습니다."
                    : "상담 문의 목록을 불러오지 못했습니다."
                }
                description={
                  hasNetworkError
                    ? "네트워크 연결을 확인한 뒤 다시 시도해 주세요."
                    : "잠시 후 다시 시도해 주세요."
                }
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
            ) : (
              <>
                <div
                  className="consultant-risk-tabs"
                  role="tablist"
                  aria-label="문의 유형"
                >
                  {RISK_SECTIONS.map((section, index) => {
                    const isActive = displayedRiskSection === section.id;
                    const count = riskSummaryCounts[section.id];

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

                <div
                  className="consultant-category-filters"
                  aria-label="문의 목록 필터와 정렬"
                >
                  <form
                    className="consultant-category-filters__search"
                    role="search"
                    onSubmit={(event) => {
                      event.preventDefault();
                      setFilters({
                        ...filters,
                        query: searchValue.trim(),
                      });
                      setSearchDraft(null);
                    }}
                  >
                    <span>검색</span>
                    <div>
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
                        aria-label="문의 검색"
                        placeholder="문의 제목, 고객명, 문의번호 검색"
                        value={searchValue}
                        onChange={(event) => setSearchDraft(event.target.value)}
                      />
                      <button type="submit">검색</button>
                    </div>
                  </form>

                  <label className="consultant-category-filters__sort">
                    <span>정렬</span>
                    <div>
                      <FormSelect
                        aria-label="문의 정렬"
                        value={filters.sort}
                        onChange={(value) =>
                          setFilters({
                            ...filters,
                            sort: value as CounselorSort,
                          })
                        }
                        options={[
                          { value: "UPDATED_DESC", label: "최신순" },
                          { value: "UPDATED_ASC", label: "오래된순" },
                          { value: "RISK_DESC", label: "긴급도순" },
                          { value: "WAITING_DESC", label: "대기시간순" },
                        ]}
                      />
                    </div>
                  </label>
                </div>

                {RISK_SECTIONS.filter(
                  (section) => section.id === displayedRiskSection,
                ).map((section) => {
                const inquiries = section.id === "all"
                  ? queuePage.items
                  : queuePage.items.filter(
                      (inquiry) => inquiry.riskLevel === section.id,
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
                    <div className="consultant-risk-section__list">
                      {inquiries.length === 0 ? (
                        <p className="consultant-risk-section__empty">
                          문의가 없습니다.
                        </p>
                      ) : (
                        inquiries.map((inquiry) => (
                          <button
                            key={inquiry.inquiryId}
                            className={`v6-queue-item consultant-list-item consultant-list-item--risk-${inquiry.riskLevel}${
                              selectedInquiryId === inquiry.inquiryId
                                ? " is-selected"
                                : ""
                            }`}
                            type="button"
                            data-testid={`consultant-inquiry-${inquiry.inquiryId}`}
                            data-e2e-sensitive="true"
                            aria-pressed={
                              selectedInquiryId === inquiry.inquiryId
                            }
                            aria-label={`${inquiry.inquiryCode} ${inquiry.customerDisplayNameMasked} ${inquiry.symptomSummary} 상세 열기`}
                            onClick={() => openInquiry(inquiry.inquiryId)}
                          >
                            <span className="consultant-list-item__subject">
                              <strong className="consultant-list-item__title">
                                <span>{inquiry.symptomSummary}</span>
                                {getCounselorWorkBucket(inquiry.status) ===
                                  "NEW" && (
                                  <em className="consultant-list-item__new-badge">
                                    NEW
                                  </em>
                                )}
                              </strong>
                              <small className="consultant-list-item__product">
                                {formatProductModelAndName(inquiry.productModel)}
                              </small>
                            </span>

                            <time
                              className="consultant-list-item__received-at"
                              dateTime={inquiry.receivedAt}
                              title={formatWorkspaceDateTime(inquiry.receivedAt)}
                            >
                              {formatBucketElapsedTime(
                                inquiry.status,
                                inquiry.waitingSeconds,
                              )}
                            </time>

                            <span className="consultant-list-item__customer">
                              {inquiry.customerDisplayNameMasked}
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

          {loadState === "ready" && (
            <Pagination
              page={queuePage.currentPage}
              totalItems={queuePage.totalItems}
              totalPages={queuePage.totalPages}
              onPageChange={(page) => setFilters({ ...filters, page })}
            />
          )}
        </section>
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
            {useListMockData && selectedInquiry ? (
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
                      setActiveBucket(getCounselorWorkBucket(update.status));
                    }}
                  />
                </div>
              </>
            ) : !useListMockData ? (
              <RemoteConsultantFirstDetailPanel
                key={selectedInquiryId}
                inquiryId={selectedInquiryId}
                returnTo={`/consultant/inquiries${location.search}`}
                onClose={closeSelectedInquiry}
                onRefreshWorkspace={() => {
                  listQuery.retry();
                  overviewQuery.retry();
                }}
                onStatusChange={(status) => {
                  if (getCounselorWorkBucket(status) === "COMPLETED") {
                    changeBucket("COMPLETED");
                  }
                }}
                onSummaryConfirmed={(status) => {
                  setHasUnsavedInquiryChanges(false);
                  setActiveBucket("COMPLETED");
                  setActiveRiskSection("all");
                  setSelectedInquiryId(null);
                  setSearchDraft(null);
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
