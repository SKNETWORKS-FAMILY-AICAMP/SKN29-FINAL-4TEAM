import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import { useAuth } from "../../app/providers/authContext";
import consultantAvatar from "../../assets/images/water-bridge-consultant.png";
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
import useCounselorQueueFilters from "../../features/consultation/hooks/useCounselorQueueFilters";
import { useConsultantInquiryListQuery } from "../../features/consultation/hooks/useConsultantWorkspaceQueries";
import type {
  ConsultantInquiryListQuery,
  ConsultantRiskLevelDto,
  ConsultantInquiryStatusDto,
} from "../../features/consultation/api/consultantWorkspaceRemoteTypes";
import {
  COUNSELOR_QUEUE_PAGE_SIZE,
  getCounselorWorkBucket,
  STATUS_LABELS,
  WORK_BUCKET_LABELS,
} from "../../features/consultation/model/consultantWorkspaceModel";
import type {
  CounselorAllowedAction,
  CounselorStatus,
  CounselorWorkBucket,
} from "../../features/consultation/model/consultantWorkspaceTypes";
import { consultantWorkspaceRepository } from "../../features/consultation/repositories/consultantWorkspaceRepository";
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

type RiskSectionStatusFilter = "ALL" | ConsultantInquiryStatusDto;

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
  const { filters, hasChangedConditions, resetFilters, setFilters } =
    useCounselorQueueFilters();
  const isQueryComposingRef = useRef(false);
  const [queryInput, setQueryInput] = useState(filters.query);
  const [activeBucket, setActiveBucket] =
    useState<CounselorWorkBucket>(() => getInitialBucket(location.search));
  const [riskSectionStatusFilters, setRiskSectionStatusFilters] = useState(
    INITIAL_RISK_SECTION_STATUS_FILTERS,
  );
  const [openRiskStatusFilter, setOpenRiskStatusFilter] =
    useState<ConsultantRiskLevelDto | null>(null);
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
  const queryData = useMemo(
    () =>
      consultantWorkspaceDataRepository.dataSource === "MOCK"
        ? createMockConsultantInquiryListViewModel(repositoryQuery)
        : listQuery.data,
    [listQuery.data, repositoryQuery],
  );
  const loadState = ["loading", "error", "forbidden"].includes(
    mockState ?? "",
  )
    ? (mockState as "loading" | "error" | "forbidden")
    : consultantWorkspaceDataRepository.dataSource === "MOCK"
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
    if (!isQueryComposingRef.current) {
      setQueryInput(filters.query);
    }
  }, [filters.query]);

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
  const selectedBase = consultantWorkspaceRepository.findInquiry(selectedInquiryId);
  const selectedInquiry = selectedBase
    ? {
        ...selectedBase,
        ...inquiryStateUpdates[selectedBase.inquiryId],
      }
    : null;
  const changeBucket = (bucket: CounselorWorkBucket) => {
    setActiveBucket(bucket);
    setRiskSectionStatusFilters(INITIAL_RISK_SECTION_STATUS_FILTERS);
    setOpenRiskStatusFilter(null);
    setSelectedInquiryId(null);
    if (filters.page !== 1) setFilters({ ...filters, page: 1 });
  };

  const changeRiskSection = (riskLevel: ConsultantRiskLevelDto) => {
    setActiveRiskSection(riskLevel);
    setOpenRiskStatusFilter(null);
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

    if (consultantWorkspaceDataRepository.dataSource === "MOCK") {
      setSelectedInquiryId(inquiryId);
      return;
    }
    navigate(createInquiryDetailPath(inquiryId), {
      state: { returnTo: `/consultant/inquiries${location.search}` },
    });
  };

  return (
    <div className="simple-consultant-app consultant-queue-app">
      <main className="simple-consultant-main consultant-queue-main">
        <h1 id="simple-page-title" className="consultant-visually-hidden">
          고객 문의
        </h1>

        <header className="simple-topbar consultant-main-header">
          <div className="consultant-queue-tools consultant-header-search">
            <label className="simple-search">
              <span aria-hidden="true">⌕</span>
              <input
                type="search"
                aria-label="문의 검색"
                value={queryInput}
                onCompositionStart={() => {
                  isQueryComposingRef.current = true;
                }}
                onCompositionEnd={(event) => {
                  isQueryComposingRef.current = false;
                  const query = event.currentTarget.value;
                  setQueryInput(query);
                  setFilters({ ...filters, query, page: 1 });
                }}
                onChange={(event) => {
                  const query = event.target.value;
                  setQueryInput(query);
                  if (!isQueryComposingRef.current) {
                    setFilters({ ...filters, query, page: 1 });
                  }
                }}
                placeholder="고객명, 증상, 문의번호 검색"
              />
            </label>
            {hasChangedConditions && (
              <button type="button" onClick={resetFilters}>
                검색 초기화
              </button>
            )}
          </div>

          <div className="simple-user">
            <span className="simple-user__avatar-frame" aria-hidden="true">
              <img
                className="simple-user__avatar-image"
                src={consultantAvatar}
                alt=""
              />
            </span>
            <strong className="simple-user__name">
              {user?.displayName ?? "상담사"}
            </strong>
            <svg
              className="simple-user__chevron"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <path d="m4.5 6 3.5 3.5L11.5 6" />
            </svg>
          </div>
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
          aria-label={WORK_BUCKET_LABELS[activeBucket]}
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
                        className={`consultant-risk-tab${
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
                        <b>{count}</b>
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
                const inquiries = sectionInquiries.filter(
                  (inquiry) =>
                    statusFilter === "ALL" || inquiry.status === statusFilter,
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
                    <header className="consultant-risk-section__head">
                      <h2 id={`consultant-risk-section-${section.id}`}>
                        {section.label} 목록
                      </h2>
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
                            <span className="consultant-list-item__subject">
                              {inquiry.symptomSummary}
                            </span>

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

          {loadState === "ready" && queuePage.totalItems > 0 && (
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
