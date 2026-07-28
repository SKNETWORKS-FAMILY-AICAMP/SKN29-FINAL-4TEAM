import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  createVisitTransitionPath,
  ROUTE_PATHS,
} from "../../app/router/routePaths";
import ForbiddenState from "../../common/components/feedback/ForbiddenState";
import "./InquiryDetailPage.css";

type RiskLevel = "GENERAL" | "CAUTION" | "DANGER";

type AllowedAction =
  | "SAVE_RESPONSE_DRAFT"
  | "SEND_RESPONSE"
  | "REQUEST_VISIT";

interface EvidenceItem {
  documentTitle: string;
  revision: string;
  page: number;
  summary: string;
  verificationStatus: "VERIFIED" | "REVIEW_REQUIRED";
}

interface StatusHistoryItem {
  status: string;
  event: string;
  actor: string;
  occurredAt: string;
}

interface InquiryDetail {
  inquiryId: string;
  customerDisplayName: string;
  maskedPhone: string;
  productModel: string;
  subscriptionType: string;
  careType: string;
  symptomSummary: string;
  customerMessage: string;
  questionnaireAnswer: string;
  currentStateLabel: string;
  riskLevel: RiskLevel;
  riskLabel: string;
  priorityLabel: string;
  aiSummary: string;
  responseDraft: string;
  stateVersion: number;
  allowedActions: AllowedAction[];
  evidence: EvidenceItem[];
  statusHistory: StatusHistoryItem[];
}

const MOCK_INQUIRY_DETAILS: Record<string, InquiryDetail> = {
  "DEMO-INQ-001": {
    inquiryId: "DEMO-INQ-001",
    customerDisplayName: "김*수",
    maskedPhone: "010-****-1234",
    productModel: "WPUJAC104DWH",
    subscriptionType: "정기 구독",
    careType: "방문 관리",
    symptomSummary: "출수량이 이전보다 줄어들었어요.",
    customerMessage:
      "며칠 전부터 정수기에서 나오는 물의 양이 이전보다 적어진 것 같습니다.",
    questionnaireAnswer:
      "냉수와 정수 모두 출수량이 줄었으며, 제품 외부 누수는 확인되지 않았습니다.",
    currentStateLabel: "상담 필요",
    riskLevel: "GENERAL",
    riskLabel: "일반",
    priorityLabel: "보통",
    aiSummary:
      "출수량 저하 문의입니다. 필터 사용 기간과 출수구 막힘 여부를 우선 확인하고, 해결되지 않을 경우 방문 점검 전환을 검토해 주세요.",
    responseDraft:
      "안녕하세요, 고객님. 출수량 감소로 불편을 드려 죄송합니다. 먼저 출수구 주변에 이물질이 있는지 확인해 주세요. 동일 증상이 계속되면 방문 점검을 도와드리겠습니다.",
    stateVersion: 3,
    allowedActions: [
      "SAVE_RESPONSE_DRAFT",
      "SEND_RESPONSE",
      "REQUEST_VISIT",
    ],
    evidence: [
      {
        documentTitle: "JAC104D 사용 설명서",
        revision: "Rev. 1.0",
        page: 24,
        summary:
          "출수량이 감소한 경우 필터 사용 기간과 출수구 상태를 확인하도록 안내합니다.",
        verificationStatus: "VERIFIED",
      },
    ],
    statusHistory: [
      {
        status: "문의 접수",
        event: "고객 문의 등록",
        actor: "고객",
        occurredAt: "2026-07-27 09:20",
      },
      {
        status: "AI 안내 완료",
        event: "AI 증상 분석 및 상담 연결",
        actor: "시스템",
        occurredAt: "2026-07-27 09:21",
      },
      {
        status: "상담 필요",
        event: "상담사 확인 대기",
        actor: "시스템",
        occurredAt: "2026-07-27 09:22",
      },
    ],
  },

  "DEMO-INQ-002": {
    inquiryId: "DEMO-INQ-002",
    customerDisplayName: "이*영",
    maskedPhone: "010-****-5678",
    productModel: "WPUJAC104DWH",
    subscriptionType: "정기 구독",
    careType: "방문 관리",
    symptomSummary: "제품 하단에서 물이 새는 것 같아요.",
    customerMessage:
      "제품 아래쪽 바닥에 물이 고여 있습니다. 현재는 사용을 멈춘 상태입니다.",
    questionnaireAnswer:
      "제품 하단에서 물이 확인되었으며, 전원 플러그 주변에는 물이 닿지 않았습니다.",
    currentStateLabel: "상담 필요",
    riskLevel: "DANGER",
    riskLabel: "위험",
    priorityLabel: "긴급",
    aiSummary:
      "누수 의심 문의입니다. 고객에게 제품 사용 중지를 유지하도록 안내하고, 임의 분해나 부품 교체를 안내하지 마세요. 상담사 확인 후 방문 점검 전환이 필요합니다.",
    responseDraft:
      "안녕하세요, 고객님. 안전을 위해 제품 사용을 중지한 상태를 유지해 주세요. 제품을 직접 분해하거나 부품을 교체하지 마시고, 방문 점검을 접수해 드리겠습니다.",
    stateVersion: 4,
    allowedActions: ["SAVE_RESPONSE_DRAFT", "REQUEST_VISIT"],
    evidence: [
      {
        documentTitle: "JAC104D 안전 사용 안내",
        revision: "Rev. 1.0",
        page: 6,
        summary:
          "누수 의심 시 제품 사용을 중지하고 고객센터 또는 서비스 담당자에게 문의하도록 안내합니다.",
        verificationStatus: "VERIFIED",
      },
    ],
    statusHistory: [
      {
        status: "문의 접수",
        event: "고객 누수 문의 등록",
        actor: "고객",
        occurredAt: "2026-07-27 09:45",
      },
      {
        status: "위험 감지",
        event: "누수 위험 시나리오 감지",
        actor: "시스템",
        occurredAt: "2026-07-27 09:46",
      },
      {
        status: "상담 필요",
        event: "긴급 상담사 연결 요청",
        actor: "시스템",
        occurredAt: "2026-07-27 09:46",
      },
    ],
  },

  "DEMO-INQ-003": {
    inquiryId: "DEMO-INQ-003",
    customerDisplayName: "박*진",
    maskedPhone: "010-****-9012",
    productModel: "WPUJAC104DWH",
    subscriptionType: "정기 구독",
    careType: "방문 관리",
    symptomSummary: "이전에 처리했지만 같은 증상이 다시 발생했어요.",
    customerMessage:
      "지난 상담 이후 잠시 괜찮았지만 같은 증상이 다시 발생했습니다.",
    questionnaireAnswer:
      "이전 안내에 따라 제품을 재시작했으나 증상이 다시 나타났습니다.",
    currentStateLabel: "문의 재개",
    riskLevel: "CAUTION",
    riskLabel: "주의",
    priorityLabel: "높음",
    aiSummary:
      "동일 증상이 재발한 문의입니다. 이전 상담 기록과 고객 조치 결과를 확인하고, 반복 안내보다 방문 점검 필요 여부를 우선 검토해 주세요.",
    responseDraft:
      "안녕하세요, 고객님. 같은 증상이 다시 발생해 불편을 드려 죄송합니다. 이전 상담 이력을 확인했으며, 정확한 점검을 위해 방문 서비스 전환을 안내드리겠습니다.",
    stateVersion: 5,
    allowedActions: [
      "SAVE_RESPONSE_DRAFT",
      "SEND_RESPONSE",
      "REQUEST_VISIT",
    ],
    evidence: [],
    statusHistory: [
      {
        status: "상담 완료",
        event: "초기 상담 안내 완료",
        actor: "상담사",
        occurredAt: "2026-07-25 14:10",
      },
      {
        status: "문의 재개",
        event: "고객 미해결 피드백 제출",
        actor: "고객",
        occurredAt: "2026-07-27 10:10",
      },
    ],
  },
};

function getRiskClassName(riskLevel: RiskLevel): string {
  return `inquiry-detail__badge inquiry-detail__badge--${riskLevel.toLowerCase()}`;
}

function getVerificationLabel(
  status: EvidenceItem["verificationStatus"],
): string {
  return status === "VERIFIED" ? "검증 완료" : "검토 필요";
}

export default function InquiryDetailPage() {
  const navigate = useNavigate();
  const { inquiryId } = useParams<{ inquiryId: string }>();

  const inquiry = inquiryId
    ? MOCK_INQUIRY_DETAILS[inquiryId]
    : undefined;

  const isForbidden = inquiryId === "DEMO-INQ-FORBIDDEN";  

  const [responseDraft, setResponseDraft] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  useEffect(() => {
    setResponseDraft(inquiry?.responseDraft ?? "");
    setActionMessage("");
  }, [inquiry]);

  if (isForbidden) {
  return (
    <main className="inquiry-detail">
      <ForbiddenState
        title="이 문의에 접근할 권한이 없습니다."
        description="담당 상담사이거나 해당 문의의 조회 권한이 있는지 확인해 주세요."
        actionLabel="문의 목록으로 돌아가기"
        onAction={() =>
          navigate(ROUTE_PATHS.consultantInquiryList)
        }
      />
    </main>
  );
}

  if (!inquiry) {
    return (
      <main className="inquiry-detail">
        <section className="inquiry-detail__not-found">
          <p className="inquiry-detail__eyebrow">CONS-02</p>
          <h1>문의를 찾을 수 없습니다.</h1>
          <p>문의 번호를 다시 확인해 주세요.</p>

          <button
            type="button"
            onClick={() =>
              navigate(ROUTE_PATHS.consultantInquiryList)
            }
          >
            문의 목록으로 돌아가기
          </button>
        </section>
      </main>
    );
  }

  const canPerform = (action: AllowedAction): boolean =>
    inquiry.allowedActions.includes(action);

  const handleSaveDraft = () => {
    setActionMessage(
      `답변 초안을 임시 저장했습니다. 현재 상태 버전: ${inquiry.stateVersion}`,
    );
  };

  const handleSendResponse = () => {
    if (responseDraft.trim().length === 0) {
      setActionMessage("고객에게 보낼 답변을 입력해 주세요.");
      return;
    }

    setActionMessage(
      "Mock 답변 발송 요청이 완료되었습니다. 실제 API 연동 전에는 고객에게 전송되지 않습니다.",
    );
  };

  const handleRequestVisit = () => {
    navigate(createVisitTransitionPath(inquiry.inquiryId), {
      state: {
        stateVersion: inquiry.stateVersion,
        symptomSummary: inquiry.symptomSummary,
      },
    });
  };

  return (
    <main className="inquiry-detail">
      <header className="inquiry-detail__header">
        <div>
          <p className="inquiry-detail__eyebrow">CONS-02</p>
          <h1>문의 상세</h1>
          <p>{inquiry.inquiryId}</p>
        </div>

        <button
          type="button"
          className="inquiry-detail__back-button"
          onClick={() =>
            navigate(ROUTE_PATHS.consultantInquiryList)
          }
        >
          목록으로 돌아가기
        </button>
      </header>

      {inquiry.riskLevel === "DANGER" && (
        <section
          className="inquiry-detail__danger-alert"
          role="alert"
        >
          <strong>위험 문의입니다.</strong>
          <p>
            제품 사용 중지를 유지하도록 안내하고 임의 분해나
            부품 교체 방법을 제공하지 마세요.
          </p>
        </section>
      )}

      <section
        className="inquiry-detail__summary"
        aria-label="문의 요약"
      >
        <article>
          <span>현재 상태</span>
          <strong>{inquiry.currentStateLabel}</strong>
        </article>

        <article>
          <span>위험도</span>
          <strong className={getRiskClassName(inquiry.riskLevel)}>
            {inquiry.riskLabel}
          </strong>
        </article>

        <article>
          <span>우선순위</span>
          <strong>{inquiry.priorityLabel}</strong>
        </article>

        <article>
          <span>현재 담당</span>
          <strong>상담사</strong>
        </article>
      </section>

      <div className="inquiry-detail__grid">
        <section className="inquiry-detail__card">
          <h2>고객 정보</h2>

          <dl className="inquiry-detail__data-list">
            <div>
              <dt>고객 표시명</dt>
              <dd>{inquiry.customerDisplayName}</dd>
            </div>

            <div>
              <dt>연락처</dt>
              <dd>{inquiry.maskedPhone}</dd>
            </div>
          </dl>
        </section>

        <section className="inquiry-detail__card">
          <h2>제품 정보</h2>

          <dl className="inquiry-detail__data-list">
            <div>
              <dt>제품 모델</dt>
              <dd>{inquiry.productModel}</dd>
            </div>

            <div>
              <dt>구독 유형</dt>
              <dd>{inquiry.subscriptionType}</dd>
            </div>

            <div>
              <dt>관리 유형</dt>
              <dd>{inquiry.careType}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="inquiry-detail__card">
        <h2>대표 증상</h2>
        <p>{inquiry.symptomSummary}</p>
      </section>

      <section className="inquiry-detail__card">
        <h2>고객 문의 원문</h2>
        <p>{inquiry.customerMessage}</p>
      </section>

      <section className="inquiry-detail__card">
        <h2>문진 및 추가 답변</h2>
        <p>{inquiry.questionnaireAnswer}</p>
      </section>

      <section className="inquiry-detail__card">
        <div className="inquiry-detail__card-title">
          <h2>AI 상담 요약</h2>
          <span>AI 초안</span>
        </div>

        <p>{inquiry.aiSummary}</p>

        <p className="inquiry-detail__helper-text">
          AI가 작성한 초안입니다. 상담사가 확인하고 수정한 뒤
          고객 안내에 사용해야 합니다.
        </p>
      </section>

      <section className="inquiry-detail__card">
        <h2>공식 근거</h2>

        {inquiry.evidence.length === 0 ? (
          <div className="inquiry-detail__empty">
            <strong>표시할 공식 근거가 없습니다.</strong>
            <p>
              근거가 없는 경우 AI 초안을 공식 안내처럼 사용하지
              마세요.
            </p>
          </div>
        ) : (
          <div className="inquiry-detail__evidence-list">
            {inquiry.evidence.map((item) => (
              <article
                key={`${item.documentTitle}-${item.page}`}
                className="inquiry-detail__evidence"
              >
                <div className="inquiry-detail__evidence-header">
                  <strong>{item.documentTitle}</strong>
                  <span>
                    {getVerificationLabel(
                      item.verificationStatus,
                    )}
                  </span>
                </div>

                <p>
                  {item.revision} · {item.page}페이지
                </p>
                <p>{item.summary}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="inquiry-detail__card">
        <h2>상담 답변 작성</h2>

        <label
          className="inquiry-detail__response-label"
          htmlFor="response-draft"
        >
          고객에게 보낼 답변
        </label>

        <textarea
          id="response-draft"
          className="inquiry-detail__response-textarea"
          value={responseDraft}
          onChange={(event) =>
            setResponseDraft(event.target.value)
          }
          rows={7}
        />

        <div className="inquiry-detail__response-meta">
          <span>상태 버전: {inquiry.stateVersion}</span>
          <span>{responseDraft.length}자</span>
        </div>

        {inquiry.riskLevel === "DANGER" && (
          <p className="inquiry-detail__response-warning">
            위험 문의는 일반 답변 발송보다 방문 전환을 우선
            검토해 주세요.
          </p>
        )}

        <div className="inquiry-detail__action-buttons">
          {canPerform("SAVE_RESPONSE_DRAFT") && (
            <button
              type="button"
              className="inquiry-detail__action-button inquiry-detail__action-button--secondary"
              onClick={handleSaveDraft}
            >
              임시 저장
            </button>
          )}

          {canPerform("SEND_RESPONSE") && (
            <button
              type="button"
              className="inquiry-detail__action-button inquiry-detail__action-button--primary"
              onClick={handleSendResponse}
              disabled={responseDraft.trim().length === 0}
            >
              고객 답변 발송
            </button>
          )}

          {canPerform("REQUEST_VISIT") && (
            <button
              type="button"
              className="inquiry-detail__action-button inquiry-detail__action-button--visit"
              onClick={handleRequestVisit}
            >
              방문 점검으로 전환
            </button>
          )}
        </div>

        {actionMessage && (
          <p
            className="inquiry-detail__action-message"
            aria-live="polite"
          >
            {actionMessage}
          </p>
        )}

        <p className="inquiry-detail__mock-notice">
          현재는 Mock 화면입니다. 실제 발송 및 상태 전환 API는
          연결되지 않았습니다.
        </p>
      </section>

      <section className="inquiry-detail__card">
        <h2>상태 이력</h2>

        <ol className="inquiry-detail__history">
          {inquiry.statusHistory.map((history, index) => (
            <li
              key={`${history.status}-${history.occurredAt}`}
            >
              <div className="inquiry-detail__history-index">
                {index + 1}
              </div>

              <div>
                <strong>{history.status}</strong>
                <p>{history.event}</p>
                <span>
                  {history.actor} · {history.occurredAt}
                </span>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
