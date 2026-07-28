import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import PriorityBadge, {
  type PriorityBadgeVariant,
} from "../../common/components/badge/PriorityBadge";
import RiskBadge, {
  type RiskLevel,
} from "../../common/components/badge/RiskBadge";
import StatusBadge from "../../common/components/badge/StatusBadge";
import EmptyState from "../../common/components/feedback/EmptyState";
import "./ConsultantDashboardPage.css";

type InquiryStatus =
  | "CONSULTATION_REQUIRED"
  | "CONSULTATION_IN_PROGRESS"
  | "REOPENED";

type InquirySort = "RECEIVED_DESC" | "RECEIVED_ASC";

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

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();

  const [searchKeyword, setSearchKeyword] = useState("");
  const [selectedRisk, setSelectedRisk] = useState<"ALL" | RiskLevel>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<
    "ALL" | InquiryStatus
  >("ALL");
  const [selectedPriority, setSelectedPriority] = useState<
    "ALL" | PriorityBadgeVariant
  >("ALL");
  const [selectedSort, setSelectedSort] =
    useState<InquirySort>("RECEIVED_DESC");

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

  const handleInquiryClick = (inquiryId: string) => {
    navigate(createInquiryDetailPath(inquiryId));
  };

  const handleResetFilters = () => {
    setSearchKeyword("");
    setSelectedRisk("ALL");
    setSelectedStatus("ALL");
    setSelectedPriority("ALL");
    setSelectedSort("RECEIVED_DESC");
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
            onChange={(event) => setSearchKeyword(event.target.value)}
            placeholder="문의 번호, 고객명, 제품, 증상 검색"
          />
        </label>

        <label>
          <span>위험도</span>

          <select
            value={selectedRisk}
            onChange={(event) =>
              setSelectedRisk(event.target.value as "ALL" | RiskLevel)
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
              setSelectedStatus(
                event.target.value as "ALL" | InquiryStatus,
              )
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
              setSelectedPriority(
                event.target.value as "ALL" | PriorityBadgeVariant,
              )
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
              setSelectedSort(event.target.value as InquirySort)
            }
          >
            <option value="RECEIVED_DESC">접수 시각 최신순</option>
            <option value="RECEIVED_ASC">접수 시각 오래된순</option>
          </select>
        </label>

        <p className="consultant-dashboard__mock-notice">
          현재 목록과 우선순위 필터는 Mock 데이터 기준입니다.
        </p>
      </section>

      <section className="consultant-dashboard__content">
        {filteredInquiries.length === 0 ? (
          <EmptyState
            title="검색 결과가 없습니다."
            description="검색어나 필터 조건을 변경한 뒤 다시 확인해 주세요."
            actionLabel="검색 조건 초기화"
            onAction={handleResetFilters}
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
                {filteredInquiries.map((inquiry) => (
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
          </div>
        )}
      </section>
    </main>
  );
}
