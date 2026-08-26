import type { ConsultantInquiryDetailViewModel } from "../model/consultantWorkspaceRemoteMapper";
import {
  getManagementTypeLabel,
  getSubscriptionStatusLabel,
} from "../model/consultantWorkspaceRemoteMapper";
import {
  formatWorkspaceDateTime,
  normalizeCounselorRisk,
  normalizeCounselorStatus,
  RISK_LABELS,
  STATUS_LABELS,
} from "../model/consultantWorkspaceModel";
import { hasRemoteConsultationAction } from "../model/remoteConsultationActions";
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

const VISIT_SCHEDULE_STATUS_LABELS: Readonly<Record<string, string>> = {
  ASSIGNING: "기사 배정 중",
  SCHEDULING: "일정 조율 중",
  CONFIRMED: "방문 일정 확정",
  IN_PROGRESS: "방문 진행 중",
  COMPLETED: "방문 완료",
  FOLLOW_UP_REQUIRED: "추가 방문 필요",
  CANCELLED: "방문 취소",
};

const CONSULTATION_RESULT_LABELS: Readonly<Record<string, string>> = {
  PENDING: "상담 결과 검토 중",
  COMPLETED_NO_VISIT: "방문 없이 상담 완료",
  VISIT_REQUIRED: "방문 서비스 필요",
  REOPENED_FOLLOWUP: "재상담·후속 확인 필요",
};

const ACTOR_ROLE_LABELS: Readonly<Record<string, string>> = {
  CUSTOMER: "고객",
  CONSULTANT: "상담사",
  TECHNICIAN: "방문기사",
  OPERATOR: "운영 담당자",
  SYSTEM: "시스템",
};

const USAGE_GUIDANCE_STATUS_LABELS: Readonly<Record<string, string>> = {
  NORMAL: "정상 사용 가능",
  PARTIAL_STOP: "일부 기능 사용 중단",
  TOTAL_STOP: "제품 사용 중단",
  PENDING_CONSULTATION: "상담 확인 필요",
};

function getRecentCareDatePresentation(
  value: string | null,
  emptyLabel = "관리 이력 없음",
  invalidLabel = "최근 관리일 확인 필요",
): RecentCareDatePresentation {
  if (value === null) {
    return { dateTime: null, label: emptyLabel };
  }

  const matched = CONTRACT_DATE_PATTERN.exec(value);
  if (!matched) {
    return { dateTime: null, label: invalidLabel };
  }

  const year = Number(matched[1]);
  const month = Number(matched[2]);
  const day = Number(matched[3]);
  const lastDayOfMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  if (month < 1 || month > 12 || day < 1 || day > lastDayOfMonth) {
    return { dateTime: null, label: invalidLabel };
  }

  return {
    dateTime: value,
    label: `${year}. ${month}. ${day}.`,
  };
}

function formatElapsedSince(receivedAt: string): string {
  const receivedAtMs = Date.parse(receivedAt);
  if (!Number.isFinite(receivedAtMs)) return "접수 시간 확인 필요";

  const elapsedMinutes = Math.max(
    0,
    Math.floor((Date.now() - receivedAtMs) / 60_000),
  );
  if (elapsedMinutes < 1) return "방금 접수";
  if (elapsedMinutes < 60) return `접수 ${elapsedMinutes}분 경과`;

  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) {
    const remainingMinutes = elapsedMinutes % 60;
    return remainingMinutes > 0
      ? `접수 ${elapsedHours}시간 ${remainingMinutes}분 경과`
      : `접수 ${elapsedHours}시간 경과`;
  }

  const elapsedDays = Math.floor(elapsedHours / 24);
  const remainingHours = elapsedHours % 24;
  return remainingHours > 0
    ? `접수 ${elapsedDays}일 ${remainingHours}시간 경과`
    : `접수 ${elapsedDays}일 경과`;
}

function getSafeContractLabel(value: string, label: string, fallback: string) {
  return label === value ? fallback : label;
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
  const usageGuidanceDisplayLabel =
    inquiry.guidanceAndActions.usageGuidanceDisplayLabel?.trim() ||
    (inquiry.guidanceAndActions.usageGuidanceStatus
      ? USAGE_GUIDANCE_STATUS_LABELS[
          inquiry.guidanceAndActions.usageGuidanceStatus
        ]
      : null) ||
    "안내 상태 미제공";
  const isVisitRequired =
    inquiry.consultation?.resultCode === "VISIT_REQUIRED";
  const visitPreferredDate = getRecentCareDatePresentation(
    inquiry.visit?.schedule.preferredDate ?? null,
    "희망일 미정",
    "희망일 확인 필요",
  );
  const visitConfirmedDate = getRecentCareDatePresentation(
    inquiry.visit?.schedule.confirmedDate ?? null,
    "확정일 미정",
    "확정일 확인 필요",
  );
  const normalizedRisk = normalizeCounselorRisk(inquiry.riskLevel);
  const statusLabel = STATUS_LABELS[
    normalizeCounselorStatus(inquiry.workflow.status)
  ];
  const riskLabel = RISK_LABELS[normalizedRisk];
  const productName =
    inquiry.productAndCare?.productModelName ?? "제품 정보 확인 필요";
  const hasConsultationHistory =
    inquiry.consultation !== null || inquiry.stateHistory.length > 0;
  const showActionPanel = Boolean(
    onOpenVisit && onRefresh && hasRemoteConsultationAction(inquiry),
  );

  return (
    <div className="remote-inquiry-detail" aria-label="상담 문의 상세">
      {inquiry.sectionErrors.length > 0 && (
        <div className="remote-inquiry-detail__errors" role="alert">
          <strong>일부 정보를 불러오지 못했습니다.</strong>
          {inquiry.sectionErrors.map((error) => (
            <p key={`${error.section}-${error.code}`}>{error.message}</p>
          ))}
        </div>
      )}

      <section
        className="remote-inquiry-detail__overview"
        aria-labelledby="remote-inquiry-customer-title"
        data-e2e-sensitive="true"
      >
        <div className="remote-inquiry-detail__badges" aria-label="문의 상태 요약">
          <span className={`remote-inquiry-detail__badge is-risk-${normalizedRisk.toLowerCase()}`}>
            {riskLabel} 문의
          </span>
          <span className="remote-inquiry-detail__badge is-status">
            {statusLabel}
          </span>
        </div>
        <h2 id="remote-inquiry-customer-title">
          {inquiry.customer.displayName}
        </h2>
        <p className="remote-inquiry-detail__symptom-summary">
          {inquiry.symptomAndQuestionnaire.symptomSummary}
        </p>
        <dl className="remote-inquiry-detail__overview-meta">
          <div>
            <dt>연락처</dt>
            <dd>{inquiry.customer.phoneMasked}</dd>
          </div>
          <div>
            <dt>제품</dt>
            <dd>{productName}</dd>
          </div>
          <div>
            <dt>접수 정보</dt>
            <dd>
              <time
                dateTime={inquiry.receivedAt}
                title={formatWorkspaceDateTime(inquiry.receivedAt)}
              >
                {formatElapsedSince(inquiry.receivedAt)}
              </time>
            </dd>
          </div>
        </dl>
      </section>

      <div
        className={`remote-inquiry-detail__workspace${
          showActionPanel ? "" : " is-single-column"
        }`}
      >
        <div className="remote-inquiry-detail__content">
          <section
            className="remote-inquiry-detail__section"
            data-e2e-sensitive="true"
          >
            <h2>고객 증상과 답변</h2>
            <p className="remote-inquiry-detail__symptom-detail">
              {inquiry.symptomAndQuestionnaire.symptomSummary}
            </p>
            {inquiry.symptomAndQuestionnaire.answers.length > 0 ? (
              <dl className="remote-inquiry-detail__answers">
                {inquiry.symptomAndQuestionnaire.answers.map((answer) => (
                  <div key={answer.questionCode}>
                    <dt>{answer.questionText}</dt>
                    <dd>{answer.answer}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="remote-inquiry-detail__empty-copy">
                등록된 문진 답변이 없습니다.
              </p>
            )}
          </section>

          <section
            className={`remote-inquiry-detail__section remote-inquiry-detail__section--guidance is-risk-${normalizedRisk.toLowerCase()}`}
            data-e2e-sensitive="true"
          >
            <span className="remote-inquiry-detail__section-kicker">
              먼저 확인
            </span>
            <h2>고객에게 안내할 내용</h2>
            <div className="remote-inquiry-detail__guidance-status">
              <strong>제품 사용 상태</strong>
              <p>{usageGuidanceDisplayLabel}</p>
            </div>
            <strong>고객 안내 내용</strong>
            <p>
              {usageGuidanceMessage ||
                "AI 안내가 없습니다. 고객 증상과 상담 지침을 직접 확인해 주세요."}
            </p>
            <strong>사용하면 안 되는 기능</strong>
            {inquiry.guidanceAndActions.restrictedFunctions.length > 0 ? (
              <ul>
                {inquiry.guidanceAndActions.restrictedFunctions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>현재 제공된 제한 기능 정보가 없습니다.</p>
            )}
            <p className="remote-inquiry-detail__evidence-empty">
              공식 근거는 아직 제공되지 않았습니다.
            </p>
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
                  <dd>
                    {getSafeContractLabel(
                      inquiry.productAndCare.subscriptionStatus,
                      getSubscriptionStatusLabel(
                        inquiry.productAndCare.subscriptionStatus,
                      ),
                      "구독 상태 확인 필요",
                    )}
                  </dd>
                </div>
                <div>
                  <dt>관리 유형</dt>
                  <dd>
                    {getSafeContractLabel(
                      inquiry.productAndCare.managementType,
                      getManagementTypeLabel(
                        inquiry.productAndCare.managementType,
                      ),
                      "관리 유형 확인 필요",
                    )}
                  </dd>
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

          {(isVisitRequired || inquiry.visit) && (
            <section
              className="remote-inquiry-detail__section"
              data-e2e-sensitive="true"
            >
              <h2>방문 정보</h2>
              <dl className="inquiry-v13-remote-summary">
                <div>
                  <dt>방문 필요 여부</dt>
                  <dd>{isVisitRequired ? "방문 필요" : "방문 검토 중"}</dd>
                </div>
                <div>
                  <dt>방문 등록 상태</dt>
                  <dd>
                    {inquiry.visit
                      ? "방문 정보 등록됨"
                      : "방문 정보 등록 대기"}
                  </dd>
                </div>
                {inquiry.visit && (
                  <>
                    <div>
                      <dt>일정 상태</dt>
                      <dd>
                        {VISIT_SCHEDULE_STATUS_LABELS[
                          inquiry.visit.schedule.scheduleStatus
                        ] ?? "방문 일정 확인 필요"}
                      </dd>
                    </div>
                    <div>
                      <dt>희망 방문일</dt>
                      <dd>
                        {visitPreferredDate.dateTime ? (
                          <time dateTime={visitPreferredDate.dateTime}>
                            {visitPreferredDate.label}
                          </time>
                        ) : (
                          visitPreferredDate.label
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>확정 방문일</dt>
                      <dd>
                        {visitConfirmedDate.dateTime ? (
                          <time dateTime={visitConfirmedDate.dateTime}>
                            {visitConfirmedDate.label}
                          </time>
                        ) : (
                          visitConfirmedDate.label
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>담당 기사</dt>
                      <dd>
                        {inquiry.visit.technician?.displayName ?? "기사 미배정"}
                      </dd>
                    </div>
                  </>
                )}
              </dl>
            </section>
          )}

          {hasConsultationHistory && (
            <details className="remote-inquiry-detail__history">
              <summary>이전 상담 기록·처리 이력</summary>
              {inquiry.consultation && (
                <dl className="inquiry-v13-remote-summary">
                  <div>
                    <dt>상담 결과</dt>
                    <dd>
                      {CONSULTATION_RESULT_LABELS[
                        inquiry.consultation.resultCode
                      ] ?? "상담 결과 확인 필요"}
                    </dd>
                  </div>
                  <div>
                    <dt>최종 상담 요약</dt>
                    <dd data-testid="consultation-detail-confirmed-summary">
                      {inquiry.consultation.summary.confirmedSummary ??
                        inquiry.consultation.summary.editedSummary ??
                        inquiry.consultation.summary.aiDraftSummary ??
                        "아직 확정된 요약이 없습니다."}
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
              {inquiry.stateHistory.length > 0 && (
                <ol className="remote-inquiry-detail__history-list">
                  {inquiry.stateHistory.map((history) => (
                    <li key={`${history.changedAt}-${history.toStatus}`}>
                      <span>
                        {history.fromStatus
                          ? STATUS_LABELS[
                              normalizeCounselorStatus(history.fromStatus)
                            ]
                          : "접수"}
                        {" → "}
                        {
                          STATUS_LABELS[
                            normalizeCounselorStatus(history.toStatus)
                          ]
                        }
                      </span>
                      <small>
                        {ACTOR_ROLE_LABELS[history.actorRole] ?? "담당자"} ·{" "}
                        {formatWorkspaceDateTime(history.changedAt)}
                      </small>
                    </li>
                  ))}
                </ol>
              )}
            </details>
          )}
        </div>

        {showActionPanel && onOpenVisit && onRefresh && (
          <RemoteConsultationActionPanel
            inquiry={inquiry}
            onOpenVisit={onOpenVisit}
            onRefresh={onRefresh}
          />
        )}
      </div>
    </div>
  );
}
