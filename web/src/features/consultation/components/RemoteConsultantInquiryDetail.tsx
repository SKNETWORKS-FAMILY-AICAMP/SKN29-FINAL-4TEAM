import type { ConsultantInquiryDetailViewModel } from "../model/consultantWorkspaceRemoteMapper";
import { maskCustomerPhone } from "../../../common/privacy/customerPrivacy";
import {
  getManagementTypeLabel,
  getSubscriptionStatusLabel,
} from "../model/consultantWorkspaceRemoteMapper";
import RemoteConsultationActionPanel from "./RemoteConsultationActionPanel";

interface RemoteConsultantInquiryDetailProps {
  inquiry: ConsultantInquiryDetailViewModel;
  onOpenVisit?: (entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED") => void;
  onRefresh?: () => void;
}

const CONTRACT_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

interface RecentCareDatePresentation {
  dateTime: string | null;
  label: string;
}

function getUsageGuidanceStatusLabel(
  status: ConsultantInquiryDetailViewModel["guidanceAndActions"]["usageGuidanceStatus"],
): string {
  const labels = {
    NORMAL: "일반 사용 가능",
    PARTIAL_STOP: "일부 기능 사용 중지",
    TOTAL_STOP: "제품 전체 사용 중지",
    PENDING_CONSULTATION: "상담 확인 전 안내 보류",
  } as const;

  return status ? labels[status] : "안내 상태 미제공";
}

function getRecentCareDatePresentation(
  value: string | null,
): RecentCareDatePresentation {
  if (value === null) {
    return { dateTime: null, label: "관리 이력 없음" };
  }

  const matched = CONTRACT_DATE_PATTERN.exec(value);
  if (!matched) {
    return { dateTime: null, label: "최근 관리일 확인 필요" };
  }

  const year = Number(matched[1]);
  const month = Number(matched[2]);
  const day = Number(matched[3]);
  const lastDayOfMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (month < 1 || month > 12 || day < 1 || day > lastDayOfMonth) {
    return { dateTime: null, label: "최근 관리일 확인 필요" };
  }

  return {
    dateTime: value,
    label: `${year}. ${month}. ${day}.`,
  };
}

export default function RemoteConsultantInquiryDetail({
  inquiry,
  onOpenVisit,
  onRefresh,
}: RemoteConsultantInquiryDetailProps) {
  const productError = inquiry.sectionErrors.find(
    (error) => error.section === "product_and_care",
  );
  const usageGuidanceMessage =
    inquiry.guidanceAndActions.usageGuidanceMessage?.trim() ?? "";
  const recentCareDate = getRecentCareDatePresentation(
    inquiry.productAndCare?.recentCareDate ?? null,
  );

  return (
    <div className="remote-inquiry-detail" aria-label="실제 API 문의 상세">
      {inquiry.sectionErrors.length > 0 && (
        <div className="remote-inquiry-detail__errors" role="alert">
          <strong>일부 정보를 불러오지 못했습니다.</strong>
          {inquiry.sectionErrors.map((error) => (
            <p key={`${error.section}-${error.code}`}>{error.message}</p>
          ))}
        </div>
      )}

      <section
        className="remote-inquiry-detail__section"
        data-e2e-sensitive="true"
      >
        <h2>고객 정보</h2>
        <dl className="inquiry-v13-remote-summary">
          <div>
            <dt>고객명</dt>
            <dd>{inquiry.customer.displayName}</dd>
          </div>
          <div>
            <dt>연락처</dt>
            <dd>{maskCustomerPhone(inquiry.customer.phone)}</dd>
          </div>
          <div>
            <dt>위험도</dt>
            <dd>{inquiry.riskLevel}</dd>
          </div>
          <div>
            <dt>우선순위</dt>
            <dd>{inquiry.priority}</dd>
          </div>
        </dl>
      </section>

      <section
        className="remote-inquiry-detail__section"
        data-e2e-sensitive="true"
      >
        <h2>제품·관리 정보</h2>
        {productError ? (
          <p>제품·관리 정보를 확인할 수 없습니다.</p>
        ) : inquiry.productAndCare ? (
          <dl className="inquiry-v13-remote-summary">
            <div>
              <dt>제품 모델</dt>
              <dd>{inquiry.productAndCare.productModel}</dd>
            </div>
            <div>
              <dt>구독 상태</dt>
              <dd>{getSubscriptionStatusLabel(inquiry.productAndCare.subscriptionStatus)}</dd>
            </div>
            <div>
              <dt>관리 유형</dt>
              <dd>{getManagementTypeLabel(inquiry.productAndCare.managementType)}</dd>
            </div>
            <div>
              <dt>최근 관리일</dt>
              <dd>
                {recentCareDate.dateTime ? (
                  <time dateTime={recentCareDate.dateTime}>
                    {recentCareDate.label}
                  </time>
                ) : (
                  recentCareDate.label
                )}
              </dd>
            </div>
          </dl>
        ) : (
          <p>제품·관리 정보가 아직 제공되지 않았습니다.</p>
        )}
      </section>

      <section
        className="remote-inquiry-detail__section"
        data-e2e-sensitive="true"
      >
        <h2>증상·문진</h2>
        <p>{inquiry.symptomAndQuestionnaire.symptomSummary}</p>
        {inquiry.symptomAndQuestionnaire.answers.length > 0 && (
          <dl className="remote-inquiry-detail__answers">
            {inquiry.symptomAndQuestionnaire.answers.map((answer) => (
              <div key={answer.questionCode}>
                <dt>{answer.questionCode}</dt>
                <dd>{answer.answer}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section
        className="remote-inquiry-detail__section"
        data-e2e-sensitive="true"
      >
        <h2>사용 안내</h2>
        <strong>AI 안내 상태</strong>
        <p>
          {getUsageGuidanceStatusLabel(
            inquiry.guidanceAndActions.usageGuidanceStatus,
          )}
        </p>
        <strong>AI 안내 내용</strong>
        <p>
          {usageGuidanceMessage || "AI 안내 미제공 / 상담 검토 필요"}
        </p>
        <strong>제한 기능</strong>
        {inquiry.guidanceAndActions.restrictedFunctions.length > 0 ? (
          <ul>
            {inquiry.guidanceAndActions.restrictedFunctions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p>제한 정보 미제공</p>
        )}
        <strong>공개 근거</strong>
        <p>공개 근거 미제공 / 상담 검토 필요</p>
      </section>

      <section
        className="remote-inquiry-detail__section"
        data-e2e-sensitive="true"
      >
        <h2>상담·방문 정보</h2>
        {inquiry.consultation === null ? (
          <p>상담 기록이 아직 제공되지 않았습니다.</p>
        ) : (
          <dl className="inquiry-v13-remote-summary">
            <div>
              <dt>상담 결과</dt>
              <dd>{inquiry.consultation.resultCode}</dd>
            </div>
            <div>
              <dt>AI 요약 초안</dt>
              <dd>{inquiry.consultation.summary.aiDraftSummary ?? "미제공"}</dd>
            </div>
            <div>
              <dt>상담사 수정 요약</dt>
              <dd>{inquiry.consultation.summary.editedSummary ?? "미저장"}</dd>
            </div>
            <div>
              <dt>확정 요약</dt>
              <dd data-testid="consultation-detail-confirmed-summary">
                {inquiry.consultation.summary.confirmedSummary ?? "미확정"}
              </dd>
            </div>
            <div>
              <dt>상담 기록</dt>
              <dd data-testid="consultation-detail-note">
                {inquiry.consultation.consultationNote ?? "미저장"}
              </dd>
            </div>
            <div>
              <dt>고객 안내</dt>
              <dd data-testid="consultation-detail-customer-guidance">
                {inquiry.consultation.customerGuidance ?? "미저장"}
              </dd>
            </div>
          </dl>
        )}
        {inquiry.visit === null && <p>방문 기록이 아직 제공되지 않았습니다.</p>}
        {inquiry.stateHistory.length > 0 && (
          <>
            <strong>상태 변경 이력</strong>
            <ol>
              {inquiry.stateHistory.map((history) => (
                <li key={`${history.changedAt}-${history.toStatus}`}>
                  {history.fromStatus ?? "시작"} → {history.toStatus} ·{" "}
                  {history.actorRole}
                </li>
              ))}
            </ol>
          </>
        )}
      </section>

      <section className="remote-inquiry-detail__section">
        <h2>현재 가능한 작업</h2>
        {inquiry.workflow.allowedActions.length > 0 ? (
          <ul className="remote-inquiry-detail__actions">
            {inquiry.workflow.allowedActions.map((action) => (
              <li key={action.code}>{action.label}</li>
            ))}
          </ul>
        ) : (
          <p>현재 가능한 작업이 없습니다.</p>
        )}
        <p>Backend가 반환한 allowed_actions만 실행 버튼으로 제공합니다.</p>
      </section>

      {onOpenVisit && onRefresh && (
        <RemoteConsultationActionPanel
          inquiry={inquiry}
          onOpenVisit={onOpenVisit}
          onRefresh={onRefresh}
        />
      )}

      <section className="remote-inquiry-detail__section">
        <h2>문의 정보</h2>
        <dl className="inquiry-v13-remote-summary">
          <div>
            <dt>문의 번호</dt>
            <dd>{inquiry.inquiryCode}</dd>
          </div>
          <div>
            <dt>상태·버전</dt>
            <dd>{inquiry.status} · {inquiry.stateVersion}</dd>
          </div>
        </dl>
      </section>

    </div>
  );
}
