import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import Pagination from "../../common/components/data-display/Pagination";
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
import type { ConsultantInquiryBucket } from "../../features/consultation/components/ConsultantQueueSidebar";
import useCounselorQueueFilters from "../../features/consultation/hooks/useCounselorQueueFilters";
import { useConsultantInquiryListQuery } from "../../features/consultation/hooks/useConsultantWorkspaceQueries";
import type {
  ConsultantInquiryListQuery,
  ConsultantRiskLevelDto,
  ConsultantInquiryStatusDto,
} from "../../features/consultation/api/consultantWorkspaceRemoteTypes";
import {
  COUNSELOR_QUEUE_PAGE_SIZE,
  formatWorkspaceDateTime,
  getCounselorWorkBucket,
  WORK_BUCKET_LABELS,
} from "../../features/consultation/model/consultantWorkspaceModel";
import {
  classifyInquiryCategory,
  INQUIRY_CATEGORY_TREE,
} from "../../features/consultation/model/consultantInquiryCategories";
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

const RISK_SECTIONS: readonly {
  id: ConsultantRiskLevelDto;
  label: string;
}[] = [
  { id: "danger", label: "긴급 문의" },
  { id: "caution", label: "주의 문의" },
  { id: "general", label: "일반 문의" },
];

function getInitialBucket(search: string): ConsultantInquiryBucket {
  const bucket = new URLSearchParams(search).get("bucket");
  return bucket === "ALL" || bucket === "IN_PROGRESS" || bucket === "COMPLETED"
    ? bucket
    : "NEW";
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

function formatRelativeReceivedTime(receivedAt: string): string {
  const receivedTime = new Date(receivedAt).getTime();
  if (!Number.isFinite(receivedTime)) return "시간 확인 필요";

  const elapsedMinutes = Math.max(
    0,
    Math.floor((Date.now() - receivedTime) / 60_000),
  );
  if (elapsedMinutes < 1) return "방금 전";
  if (elapsedMinutes < 60) return `${elapsedMinutes}분 전`;

  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) return `${elapsedHours}시간 전`;

  const elapsedDays = Math.floor(elapsedHours / 24);
  if (elapsedDays < 30) return `${elapsedDays}일 전`;

  const elapsedMonths = Math.floor(elapsedDays / 30);
  return `${elapsedMonths}개월 전`;
}

export default function ConsultantInquiryListPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { filters, hasChangedConditions, resetFilters, setFilters } =
    useCounselorQueueFilters();
  const [activeBucket, setActiveBucket] =
    useState<ConsultantInquiryBucket>(() => getInitialBucket(location.search));
  const [categoryFilters, setCategoryFilters] = useState({
    major: "",
    middle: "",
    minor: "",
  });
  const [activeRiskSection, setActiveRiskSection] =
    useState<ConsultantRiskLevelDto>("danger");
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
  const hasCategoryFilter = Boolean(categoryFilters.major);

  const mockState = new URLSearchParams(location.search).get("mockState");
  const repositoryQuery = useMemo<ConsultantInquiryListQuery>(
    () => ({
      q: filters.query || undefined,
      status: getBucketStatuses(activeBucket),
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
      page: hasCategoryFilter ? 1 : filters.page,
      size: hasCategoryFilter ? 100 : COUNSELOR_QUEUE_PAGE_SIZE,
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
      hasCategoryFilter,
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
  const selectedMajorCategory = INQUIRY_CATEGORY_TREE.find(
    (category) => category.label === categoryFilters.major,
  );
  const selectedMiddleCategory = selectedMajorCategory?.children.find(
    (category) => category.label === categoryFilters.middle,
  );
  const riskSummaryCounts = useMemo(() => {
    const bucketStatuses = getBucketStatuses(activeBucket);
    const query = filters.query.trim().toLowerCase();
    const counts: Record<ConsultantRiskLevelDto, number> = {
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

      const category = classifyInquiryCategory(inquiry.symptomSummary);
      if (
        (categoryFilters.major && category.major !== categoryFilters.major) ||
        (categoryFilters.middle && category.middle !== categoryFilters.middle) ||
        (categoryFilters.minor && category.minor !== categoryFilters.minor)
      ) {
        return;
      }

      counts[inquiry.riskLevel] += 1;
    });

    return counts;
  }, [
    activeBucket,
    categoryFilters.major,
    categoryFilters.middle,
    categoryFilters.minor,
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
  const selectedBase = activeWorkspaceRepository.findInquiry(selectedInquiryId);
  const selectedInquiry = selectedBase
    ? {
        ...selectedBase,
        ...inquiryStateUpdates[selectedBase.inquiryId],
      }
    : null;
  const changeBucket = (bucket: ConsultantInquiryBucket) => {
    setActiveBucket(bucket);
    const params = new URLSearchParams(location.search);
    params.set("bucket", bucket);
    params.delete("page");
    navigate(`${location.pathname}?${params.toString()}`, { replace: true });
    setCategoryFilters({ major: "", middle: "", minor: "" });
    setSelectedInquiryId(null);
  };

  const changeRiskSection = (riskLevel: ConsultantRiskLevelDto) => {
    setActiveRiskSection(riskLevel);
    setSelectedInquiryId(null);
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

    if (useListMockData) {
      setSelectedInquiryId(inquiryId);
      return;
    }
    navigate(createInquiryDetailPath(inquiryId), {
      state: { returnTo: `/consultant/inquiries${location.search}` },
    });
  };

  return (
    <div className="simple-consultant-app consultant-queue-app consultant-inquiry-list-app">
      <main className="simple-consultant-main consultant-queue-main">
        <h1 id="simple-page-title" className="consultant-visually-hidden">
          고객 문의
        </h1>

        <header className="simple-topbar consultant-main-header consultant-unified-header">
          <ConsultantUserMenu className="simple-user" />
        </header>

        <ConsultantQueueSidebar
          activeBucket={activeBucket}
          bucketCounts={bucketCounts}
          onBucketChange={changeBucket}
        />

        <section
          id="consultant-queue-panel"
          className="consultant-queue-panel"
          role="tabpanel"
          aria-label={getBucketLabel(activeBucket)}
        >
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
                    : `${getBucketLabel(activeBucket)}가 없습니다.`
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
                  <label>
                    <span>대분류</span>
                    <select
                      aria-label="문의 대분류"
                      value={categoryFilters.major}
                      onChange={(event) => {
                        setCategoryFilters({
                          major: event.target.value,
                          middle: "",
                          minor: "",
                        });
                        setSelectedInquiryId(null);
                      }}
                    >
                      <option value="">전체 대분류</option>
                      {INQUIRY_CATEGORY_TREE.map((category) => (
                        <option key={category.label} value={category.label}>
                          {category.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <span aria-hidden="true">›</span>

                  <label>
                    <span>중분류</span>
                    <select
                      aria-label="문의 중분류"
                      value={categoryFilters.middle}
                      disabled={!selectedMajorCategory}
                      onChange={(event) => {
                        setCategoryFilters((current) => ({
                          ...current,
                          middle: event.target.value,
                          minor: "",
                        }));
                        setSelectedInquiryId(null);
                      }}
                    >
                      <option value="">
                        {selectedMajorCategory
                          ? "전체 중분류"
                          : "대분류를 먼저 선택"}
                      </option>
                      {selectedMajorCategory?.children.map((category) => (
                        <option key={category.label} value={category.label}>
                          {category.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <span aria-hidden="true">›</span>

                  <label>
                    <span>소분류</span>
                    <select
                      aria-label="문의 소분류"
                      value={categoryFilters.minor}
                      disabled={!selectedMiddleCategory}
                      onChange={(event) => {
                        setCategoryFilters((current) => ({
                          ...current,
                          minor: event.target.value,
                        }));
                        setSelectedInquiryId(null);
                      }}
                    >
                      <option value="">
                        {selectedMiddleCategory
                          ? "전체 소분류"
                          : "중분류를 먼저 선택"}
                      </option>
                      {selectedMiddleCategory?.children.map((category) => (
                        <option key={category} value={category}>
                          {category}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="consultant-category-filters__search">
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
                        value={filters.query}
                        onChange={(event) =>
                          setFilters({ ...filters, query: event.target.value })
                        }
                      />
                    </div>
                  </label>

                  <label className="consultant-category-filters__sort">
                    <span>정렬</span>
                    <div>
                      <select
                        aria-label="문의 정렬"
                        value={filters.sort}
                        onChange={(event) =>
                          setFilters({
                            ...filters,
                            sort: event.target.value as CounselorSort,
                          })
                        }
                      >
                        <option value="UPDATED_DESC">최신순</option>
                        <option value="UPDATED_ASC">오래된순</option>
                      </select>
                      <svg
                        aria-hidden="true"
                        focusable="false"
                        viewBox="0 0 24 24"
                      >
                        <path d="m7 9.5 5 5 5-5" />
                      </svg>
                    </div>
                  </label>

                  {(categoryFilters.major ||
                    categoryFilters.middle ||
                    categoryFilters.minor) && (
                    <button
                      type="button"
                      onClick={() => {
                        setCategoryFilters({ major: "", middle: "", minor: "" });
                        setSelectedInquiryId(null);
                      }}
                    >
                      카테고리 초기화
                    </button>
                  )}
                </div>

                {RISK_SECTIONS.filter(
                  (section) => section.id === displayedRiskSection,
                ).map((section) => {
                const sectionInquiries = queuePage.items.filter(
                  (inquiry) => inquiry.riskLevel === section.id,
                );
                const inquiries = sectionInquiries.filter(
                  (inquiry) => {
                    const category = classifyInquiryCategory(
                      inquiry.symptomSummary,
                    );
                    return (
                      (!categoryFilters.major ||
                        category.major === categoryFilters.major) &&
                      (!categoryFilters.middle ||
                        category.middle === categoryFilters.middle) &&
                      (!categoryFilters.minor ||
                        category.minor === categoryFilters.minor)
                    );
                  },
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
                          선택한 카테고리에 해당하는 문의가 없습니다.
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
                            <span className="consultant-list-item__subject">
                              {inquiry.symptomSummary}
                            </span>

                            <time
                              className="consultant-list-item__received-at"
                              dateTime={inquiry.receivedAt}
                              title={formatWorkspaceDateTime(inquiry.receivedAt)}
                            >
                              {formatRelativeReceivedTime(inquiry.receivedAt)}
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

          {loadState === "ready" && queuePage.totalItems > 0 && !hasCategoryFilter && (
            <Pagination
              page={queuePage.currentPage}
              totalItems={queuePage.totalItems}
              totalPages={queuePage.totalPages}
              onPageChange={(page) => setFilters({ ...filters, page })}
            />
          )}
        </section>
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
                  setActiveBucket(getCounselorWorkBucket(update.status));
                }}
                onOpenFullDetail={() =>
                  navigate(createInquiryDetailPath(selectedInquiry.inquiryId), {
                    state: { returnTo: `/consultant/inquiries${location.search}` },
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
