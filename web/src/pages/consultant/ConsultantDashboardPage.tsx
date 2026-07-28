import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createInquiryDetailPath } from "../../app/router/routePaths";
import EmptyState from "../../common/components/feedback/EmptyState";
import "./ConsultantDashboardPage.css";

type InquiryStatus =
  | "CONSULTATION_REQUIRED"
  | "CONSULTATION_IN_PROGRESS"
  | "REOPENED";

type RiskLevel = "GENERAL" | "CAUTION" | "DANGER";

interface InquiryListItem {
  inquiryId: string;
  customerDisplayName: string;
  productModel: string;
  symptomSummary: string;
  currentState: InquiryStatus;
  riskLevel: RiskLevel;
  receivedAt: string;
}

const MOCK_INQUIRIES: InquiryListItem[] = [
  {
    inquiryId: "DEMO-INQ-001",
    customerDisplayName: "김*수",
    productModel: "WPUJAC104DWH",
    symptomSummary: "출수량이 이전보다 줄어들었어요.",
    currentState: "CONSULTATION_REQUIRED",
    riskLevel: "GENERAL",
    receivedAt: "2026-07-27T09:20:00",
  },
  {
    inquiryId: "DEMO-INQ-002",
    customerDisplayName: "이*영",
    productModel: "WPUJAC104DWH",
    symptomSummary: "제품 하단에서 물이 새는 것 같아요.",
    currentState: "CONSULTATION_REQUIRED",
    riskLevel: "DANGER",
    receivedAt: "2026-07-27T09:45:00",
  },
  {
    inquiryId: "DEMO-INQ-003",
    customerDisplayName: "박*진",
    productModel: "WPUJAC104DWH",
    symptomSummary: "이전에 처리했지만 같은 증상이 다시 발생했어요.",
    currentState: "REOPENED",
    riskLevel: "CAUTION",
    receivedAt: "2026-07-27T10:10:00",
  },
];

const STATUS_LABELS: Record<InquiryStatus, string> = {
  CONSULTATION_REQUIRED: "상담 필요",
  CONSULTATION_IN_PROGRESS: "상담 진행 중",
  REOPENED: "문의 재개",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  GENERAL: "일반",
  CAUTION: "주의",
  DANGER: "위험",
};

function formatDateTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function ConsultantDashboardPage() {
  const navigate = useNavigate();

  const [searchKeyword, setSearchKeyword] = useState("");
  const [selectedRisk, setSelectedRisk] = useState<"ALL" | RiskLevel>("ALL");

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

      return matchesKeyword && matchesRisk;
    });
  }, [searchKeyword, selectedRisk]);

  const handleInquiryClick = (inquiryId: string) => {
    navigate(createInquiryDetailPath(inquiryId));
  };

  const handleResetFilters = () => {
    setSearchKeyword("");
    setSelectedRisk("ALL");
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
            <option value="GENERAL">일반</option>
            <option value="CAUTION">주의</option>
            <option value="DANGER">위험</option>
          </select>
        </label>
      </section>

      <section className="consultant-dashboard__content">
        {filteredInquiries.length === 0 ? (
          <EmptyState
            title="검색 결과가 없습니다."
            description="검색어나 위험도 조건을 변경한 뒤 다시 확인해 주세요."
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
                      <span className="status-badge">
                        {STATUS_LABELS[inquiry.currentState]}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`risk-badge risk-badge--${inquiry.riskLevel.toLowerCase()}`}
                      >
                        {RISK_LABELS[inquiry.riskLevel]}
                      </span>
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