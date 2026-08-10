import type { ConsultantInquiryDetailViewModel } from "../model/consultantWorkspaceRemoteMapper";
import {
  getManagementTypeLabel,
  getSubscriptionStatusLabel,
} from "../model/consultantWorkspaceRemoteMapper";

interface RemoteConsultantInquiryDetailProps {
  inquiry: ConsultantInquiryDetailViewModel;
}

export default function RemoteConsultantInquiryDetail({
  inquiry,
}: RemoteConsultantInquiryDetailProps) {
  const productError = inquiry.sectionErrors.find(
    (error) => error.section === "product_and_care",
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

      <section className="remote-inquiry-detail__section">
        <h2>문의·고객 정보</h2>
        <dl className="inquiry-v13-remote-summary">
          <div>
            <dt>문의 번호</dt>
            <dd>{inquiry.inquiryCode}</dd>
          </div>
          <div>
            <dt>고객명</dt>
            <dd>{inquiry.customer.displayName}</dd>
          </div>
          <div>
            <dt>연락처</dt>
            <dd>{inquiry.customer.phone}</dd>
          </div>
          <div>
            <dt>상태·버전</dt>
            <dd>{inquiry.status} · {inquiry.stateVersion}</dd>
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

      <section className="remote-inquiry-detail__section">
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
              <dd>{inquiry.productAndCare.recentCareDate ?? "관리 이력 없음"}</dd>
            </div>
          </dl>
        ) : (
          <p>제품·관리 정보가 아직 제공되지 않았습니다.</p>
        )}
      </section>

      <section className="remote-inquiry-detail__section">
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

      <section className="remote-inquiry-detail__section">
        <h2>사용 안내</h2>
        <p>{inquiry.guidanceAndActions.usageGuidanceStatus ?? "안내 상태 미제공"}</p>
        {inquiry.guidanceAndActions.usageGuidanceMessage && (
          <p>{inquiry.guidanceAndActions.usageGuidanceMessage}</p>
        )}
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
      </section>

      <section className="remote-inquiry-detail__section">
        <h2>상담·방문 정보</h2>
        {inquiry.consultation === null && <p>상담 기록이 아직 제공되지 않았습니다.</p>}
        {inquiry.visit === null && <p>방문 기록이 아직 제공되지 않았습니다.</p>}
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
        <p>상담·방문 저장 API가 준비될 때까지 실행 버튼은 제공하지 않습니다.</p>
      </section>

      {inquiry.stateHistory.length > 0 && (
        <section className="remote-inquiry-detail__section">
          <h2>상태 변경 이력</h2>
          <ol>
            {inquiry.stateHistory.map((history) => (
              <li key={`${history.changedAt}-${history.toStatus}`}>
                {history.fromStatus ?? "시작"} → {history.toStatus} · {history.actorRole}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
