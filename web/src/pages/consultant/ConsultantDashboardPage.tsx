import { useMemo } from "react";
import {
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import PriorityBadge, {
  type PriorityBadgeVariant,
} from "../../common/components/badge/PriorityBadge";
import RiskBadge, {
  type RiskLevel,
} from "../../common/components/badge/RiskBadge";
import StatusBadge from "../../common/components/badge/StatusBadge";
import Pagination from "../../common/components/data-display/Pagination";
import EmptyState from "../../common/components/feedback/EmptyState";
import "./ConsultantDashboardPage.css";

type InquiryStatus =
  | "CONSULTATION_REQUIRED"
  | "CONSULTATION_IN_PROGRESS"
  | "REOPENED";

type InquirySort = "RECEIVED_DESC" | "RECEIVED_ASC";

const PAGE_SIZE = 2;

const RISK_LEVELS: readonly RiskLevel[] = [
  "general",
  "caution",
  "danger",
];

const INQUIRY_STATUSES: readonly InquiryStatus[] = [
  "CONSULTATION_REQUIRED",
  "CONSULTATION_IN_PROGRESS",
  "REOPENED",
];

const PRIORITY_VARIANTS: readonly PriorityBadgeVariant[] = [
  "default",
  "high",
  "urgent",
];

const INQUIRY_SORTS: readonly InquirySort[] = [
  "RECEIVED_DESC",
  "RECEIVED_ASC",
];

interface InquiryListItem {
  inquiryId: string;
  customerDisplayName: string;
  productModel: string;
  symptomSummary: string;
  currentState: InquiryStatus;
  riskLevel: RiskLevel;
  priorityLabel: string;
  priorityVariant: PriorityBadgeVariant;
  receivedAt: string;
}

const MOCK_INQUIRIES: InquiryListItem[] = [
  {
    inquiryId: "DEMO-INQ-001",
    customerDisplayName: "김*수",
    productModel: "WPUJAC104DWH",
    symptomSummary: "출수량이 이전보다 줄어들었어요.",
    currentState: "CONSULTATION_REQUIRED",
    riskLevel: "general",
    priorityLabel: "보통",
    priorityVariant: "default",
    receivedAt: "2026-07-27T09:20:00+09:00",
  },
  {
    inquiryId: "DEMO-INQ-002",
    customerDisplayName: "이*영",
    productModel: "WPUJAC104DWH",
    symptomSummary: "제품 하단에서 물이 새는 것 같아요.",
    currentState: "CONSULTATION_REQUIRED",
    riskLevel: "danger",
    priorityLabel: "긴급",
    priorityVariant: "urgent",
    receivedAt: "2026-07-27T09:45:00+09:00",
  },
  {
    inquiryId: "DEMO-INQ-003",
    customerDisplayName: "박*진",
    productModel: "WPUJAC104DWH",
    symptomSummary: "이전에 처리했지만 같은 증상이 다시 발생했어요.",
    currentState: "REOPENED",
    riskLevel: "caution",
    priorityLabel: "높음",
    priorityVariant: "high",
    receivedAt: "2026-07-27T10:10:00+09:00",
  },
];

const STATUS_LABELS: Record<InquiryStatus, string> = {
  CONSULTATION_REQUIRED: "상담 필요",
  CONSULTATION_IN_PROGRESS: "상담 진행 중",
  REOPENED: "문의 재개",
};

const STATUS_VARIANTS: Record<
  InquiryStatus,
  "default" | "progress" | "reopened"
> = {
  CONSULTATION_REQUIRED: "default",
  CONSULTATION_IN_PROGRESS: "progress",
  REOPENED: "reopened",
};

function formatDateTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getReceivedTimestamp(value: string): number {
  const timestamp = Date.parse(value);

  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function getValidatedParam<T extends string>(
  searchParams: URLSearchParams,
  key: string,
  allowedValues: readonly T[],
  fallback: T,
): T {
  const value = searchParams.get(key);

  return value && allowedValues.includes(value as T)
    ? (value as T)
    : fallback;
}

function getPageParam(searchParams: URLSearchParams): number {
  const value = Number(searchParams.get("page") ?? "1");

  return Number.isInteger(value) && value > 0 ? value : 1;
}

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  const searchKeyword = searchParams.get("q") ?? "";
  const selectedRisk = getValidatedParam(
    searchParams,
    "risk",
    RISK_LEVELS,
    "ALL" as const,
  );
  const selectedStatus = getValidatedParam(
    searchParams,
    "status",
    INQUIRY_STATUSES,
    "ALL" as const,
  );
  const selectedPriority = getValidatedParam(
    searchParams,
    "priority",
    PRIORITY_VARIANTS,
    "ALL" as const,
  );
  const selectedSort = getValidatedParam(
    searchParams,
    "sort",
    INQUIRY_SORTS,
    "RECEIVED_DESC",
  );
  const requestedPage = getPageParam(searchParams);

  const filteredInquiries = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();

    return MOCK_INQUIRIES.filter((inquiry) => {
      const matchesKeyword =
        keyword.length === 0 ||
        inquiry.inquiryId.toLowerCase().includes(keyword) ||
        inquiry.customerDisplayName.toLowerCase().includes(keyword) ||
        inquiry.productModel.toLowerCase().includes(keyword) ||
        inquiry.symptomSummary.toLowerCase().includes(keyword);

      const matchesRisk =
        selectedRisk === "ALL" || inquiry.riskLevel === selectedRisk;
      const matchesStatus =
        selectedStatus === "ALL" || inquiry.currentState === selectedStatus;
      const matchesPriority =
        selectedPriority === "ALL" ||
        inquiry.priorityVariant === selectedPriority;

      return (
        matchesKeyword &&
        matchesRisk &&
        matchesStatus &&
        matchesPriority
      );
    }).sort((left, right) => {
      const difference =
        getReceivedTimestamp(right.receivedAt) -
        getReceivedTimestamp(left.receivedAt);

      return selectedSort === "RECEIVED_DESC" ? difference : -difference;
    });
  }, [
    searchKeyword,
    selectedPriority,
    selectedRisk,
    selectedSort,
    selectedStatus,
  ]);

  const totalPages = Math.max(
    1,
    Math.ceil(filteredInquiries.length / PAGE_SIZE),
  );
  const currentPage = Math.min(requestedPage, totalPages);
  const currentPageInquiries = filteredInquiries.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );
  const hasActiveFilters =
    searchKeyword.trim().length > 0 ||
    selectedRisk !== "ALL" ||
    selectedStatus !== "ALL" ||
    selectedPriority !== "ALL";
  const hasChangedConditions =
    hasActiveFilters || selectedSort !== "RECEIVED_DESC";

  const updateSearchParam = (
    key: string,
    value: string,
    defaultValue: string,
  ) => {
    const nextParams = new URLSearchParams(searchParams);

    if (value === defaultValue || value.trim().length === 0) {
      nextParams.delete(key);
    } else {
      nextParams.set(key, value);
    }

    if (key !== "page") {
      nextParams.delete("page");
    }

    setSearchParams(nextParams, { replace: true });
  };

  const handleInquiryClick = (inquiryId: string) => {
    navigate(createInquiryDetailPath(inquiryId), {
      state: {
        returnTo: `${location.pathname}${location.search}`,
      },
    });
  };

  const handleResetFilters = () => {
    setSearchParams(new URLSearchParams(), { replace: true });
  };

  return (
    <main className="consultant-dashboard">
      <header className="consultant-dashboard__header">
        <div>
          <p className="consultant-dashboard__eyebrow">CONS-01</p>
          <h1>상담사 문의 목록</h1>
          <p>접수된 문의를 확인하고 처리할 문의를 선택하세요.</p>
        </div>

        <div className="consultant-dashboard__count">
          검색 결과 <strong>{filteredInquiries.length}</strong>건
        </div>
      </header>

      <section
        className="consultant-dashboard__filters"
        aria-label="문의 검색 및 필터"
      >
        <label>
          <span>문의 검색</span>

          <input
            type="search"
            value={searchKeyword}
            onChange={(event) =>
              updateSearchParam("q", event.target.value, "")
            }
            placeholder="문의 번호, 고객명, 제품, 증상 검색"
          />
        </label>

        <label>
          <span>위험도</span>

          <select
            value={selectedRisk}
            onChange={(event) =>
              updateSearchParam("risk", event.target.value, "ALL")
            }
          >
            <option value="ALL">전체</option>
            <option value="general">일반</option>
            <option value="caution">주의</option>
            <option value="danger">위험</option>
          </select>
        </label>

        <label>
          <span>상태</span>

          <select
            value={selectedStatus}
            onChange={(event) =>
              updateSearchParam("status", event.target.value, "ALL")
            }
          >
            <option value="ALL">전체</option>
            <option value="CONSULTATION_REQUIRED">상담 필요</option>
            <option value="CONSULTATION_IN_PROGRESS">상담 진행 중</option>
            <option value="REOPENED">문의 재개</option>
          </select>
        </label>

        <label>
          <span>우선순위</span>

          <select
            value={selectedPriority}
            onChange={(event) =>
              updateSearchParam("priority", event.target.value, "ALL")
            }
          >
            <option value="ALL">전체</option>
            <option value="default">보통</option>
            <option value="high">높음</option>
            <option value="urgent">긴급</option>
          </select>
        </label>

        <label>
          <span>정렬</span>

          <select
            value={selectedSort}
            onChange={(event) =>
              updateSearchParam(
                "sort",
                event.target.value,
                "RECEIVED_DESC",
              )
            }
          >
            <option value="RECEIVED_DESC">접수 시각 최신순</option>
            <option value="RECEIVED_ASC">접수 시각 오래된순</option>
          </select>
        </label>

        <div className="consultant-dashboard__filter-footer">
          <p className="consultant-dashboard__mock-notice">
            {`현재 목록과 우선순위 필터는 Mock 데이터 기준이며 페이지당 ${PAGE_SIZE}건을 표시합니다.`}
          </p>

          {hasChangedConditions && (
            <button
              type="button"
              className="consultant-dashboard__reset-button"
              onClick={handleResetFilters}
            >
              검색 조건 초기화
            </button>
          )}
        </div>
      </section>

      <section className="consultant-dashboard__content">
        {filteredInquiries.length === 0 ? (
          <EmptyState
            title={
              hasActiveFilters
                ? "검색 결과가 없습니다."
                : "접수된 문의가 없습니다."
            }
            description={
              hasActiveFilters
                ? "검색어나 필터 조건을 변경한 뒤 다시 확인해 주세요."
                : "새 문의가 접수되면 이 목록에 표시됩니다."
            }
          />
        ) : (
          <div className="consultant-dashboard__table-wrap">
            <table className="consultant-dashboard__table">
              <thead>
                <tr>
                  <th>문의 번호</th>
                  <th>고객</th>
                  <th>제품 모델</th>
                  <th>대표 증상</th>
                  <th>상태</th>
                  <th>위험도</th>
                  <th>우선순위</th>
                  <th>접수 시각</th>
                  <th aria-label="상세 보기" />
                </tr>
              </thead>

              <tbody>
                {currentPageInquiries.map((inquiry) => (
                  <tr key={inquiry.inquiryId}>
                    <td>
                      <strong>{inquiry.inquiryId}</strong>
                    </td>

                    <td>{inquiry.customerDisplayName}</td>
                    <td>{inquiry.productModel}</td>
                    <td>{inquiry.symptomSummary}</td>

                    <td>
                      <StatusBadge
                        label={STATUS_LABELS[inquiry.currentState]}
                        variant={STATUS_VARIANTS[inquiry.currentState]}
                      />
                    </td>

                    <td>
                      <RiskBadge level={inquiry.riskLevel} />
                    </td>

                    <td>
                      <PriorityBadge
                        label={inquiry.priorityLabel}
                        variant={inquiry.priorityVariant}
                      />
                    </td>

                    <td>{formatDateTime(inquiry.receivedAt)}</td>

                    <td>
                      <button
                        type="button"
                        className="detail-button"
                        onClick={() => handleInquiryClick(inquiry.inquiryId)}
                      >
                        상세 보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <Pagination
              page={currentPage}
              totalItems={filteredInquiries.length}
              totalPages={totalPages}
              onPageChange={(page) =>
                updateSearchParam("page", String(page), "1")
              }
            />
          </div>
        )}
      </section>
    </main>
  );
}
