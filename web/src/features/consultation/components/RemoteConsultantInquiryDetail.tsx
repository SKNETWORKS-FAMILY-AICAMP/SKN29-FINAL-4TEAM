import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

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
import { formatProductModelAndName } from "../model/productDisplayName";
import { hasRemoteConsultationAction } from "../model/remoteConsultationActions";
import type { CounselorStatus } from "../model/consultantWorkspaceTypes";
import ConsultationStepNavigator from "./ConsultationStepNavigator";
import RemoteConsultationActionPanel from "./RemoteConsultationActionPanel";
import "./RemoteConsultantInquiryDetail.css";

interface RemoteConsultantInquiryDetailProps {
  inquiry: ConsultantInquiryDetailViewModel;
  onOpenVisit?: (entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED") => void;
  onRefresh?: () => void;
  onStatusChange?: (status: CounselorStatus) => void;
  onSummaryConfirmed?: (status: CounselorStatus) => void;
  onUnsavedChangesChange?: (hasUnsavedChanges: boolean) => void;
}

const CONTRACT_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

interface RecentCareDatePresentation {
  dateTime: string | null;
  label: string;
}

interface SymptomDetailItem {
  label: string;
  value: string;
}

const SYMPTOM_DETAIL_PREFIXES = [
  "발생 조건",
  "제품 표시 문구·오류 코드",
] as const;

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

function getSymptomDetailItems(summary: string): SymptomDetailItem[] {
  const inquiryLines: string[] = [];
  const structuredItems: SymptomDetailItem[] = [];

  summary
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const prefix = SYMPTOM_DETAIL_PREFIXES.find((candidate) =>
        line.startsWith(`${candidate}:`),
      );
      if (!prefix) {
        inquiryLines.push(line);
        return;
      }

      structuredItems.push({
        label: prefix,
        value: line.slice(prefix.length + 1).trim() || "입력 내용 없음",
      });
    });

  return [
    {
      label: "문의내용",
      value: inquiryLines.join("\n") || "문의 내용 확인 필요",
    },
    ...structuredItems,
  ];
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

interface ConsultationHistoryModalProps {
  inquiry: ConsultantInquiryDetailViewModel;
  onClose: () => void;
}

function ConsultationHistoryModal({
  inquiry,
  onClose,
}: ConsultationHistoryModalProps) {
  const consultation = inquiry.consultation;

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return createPortal(
    <div className="consultation-history-modal">
      <button
        type="button"
        className="consultation-history-modal__backdrop"
        aria-label="상담 기록 팝업 닫기"
        onClick={onClose}
      />
      <section
        className="consultation-history-modal__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="consultation-history-modal-title"
      >
        <header className="consultation-history-modal__head">
          <div>
            <small>상담 상세</small>
            <h2 id="consultation-history-modal-title">
              이전 상담 기록·처리 이력
            </h2>
          </div>
          <button
            type="button"
            className="consultation-history-modal__close"
            aria-label="상담 기록 팝업 닫기"
            onClick={onClose}
            autoFocus
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <div className="consultation-history-modal__body" data-e2e-sensitive="true">
          {consultation ? (
            <>
              <section className="consultation-history-modal__section">
                <h3>상담 결과와 요약</h3>
                <dl className="consultation-history-modal__content-list">
                  <div>
                    <dt>상담 결과</dt>
                    <dd>
                      {CONSULTATION_RESULT_LABELS[consultation.resultCode] ??
                        "상담 결과 확인 필요"}
                    </dd>
                  </div>
                  <div>
                    <dt>AI 상담 요약 초안</dt>
                    <dd>{consultation.summary.aiDraftSummary ?? "미저장"}</dd>
                  </div>
                  <div>
                    <dt>상담사 수정 요약</dt>
                    <dd>{consultation.summary.editedSummary ?? "미저장"}</dd>
                  </div>
                  <div>
                    <dt>확정 상담 요약</dt>
                    <dd data-testid="consultation-detail-confirmed-summary">
                      {consultation.summary.confirmedSummary ?? "미확정"}
                    </dd>
                  </div>
                  <div>
                    <dt>요약 확정 일시</dt>
                    <dd>
                      {consultation.summary.confirmedAt
                        ? formatWorkspaceDateTime(
                            consultation.summary.confirmedAt,
                          )
                        : "미확정"}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="consultation-history-modal__section">
                <h3>상담 내용</h3>
                <dl className="consultation-history-modal__content-list">
                  <div>
                    <dt>상담 기록</dt>
                    <dd data-testid="consultation-detail-note">
                      {consultation.consultationNote ?? "미저장"}
                    </dd>
                  </div>
                  <div>
                    <dt>고객 안내 내용</dt>
                    <dd data-testid="consultation-detail-customer-guidance">
                      {consultation.customerGuidance ?? "미저장"}
                    </dd>
                  </div>
                  <div>
                    <dt>추가 확인사항</dt>
                    <dd data-testid="consultation-detail-additional-check">
                      {consultation.additionalCheck ?? "미저장"}
                    </dd>
                  </div>
                  <div>
                    <dt>제품 사용 상태</dt>
                    <dd>
                      {consultation.usageGuidanceStatus
                        ? USAGE_GUIDANCE_STATUS_LABELS[
                            consultation.usageGuidanceStatus
                          ]
                        : "미저장"}
                    </dd>
                  </div>
                </dl>
              </section>
            </>
          ) : (
            <p className="consultation-history-modal__empty">
              저장된 상담 내용은 아직 없습니다.
            </p>
          )}

          <section className="consultation-history-modal__section">
            <h3>처리 이력</h3>
            {inquiry.stateHistory.length > 0 ? (
              <ol className="remote-inquiry-detail__history-list">
                {inquiry.stateHistory.map((history, index) => (
                  <li
                    key={`${history.changedAt}-${history.toStatus}-${history.actorRole}-${index}`}
                  >
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
            ) : (
              <p className="consultation-history-modal__empty">
                저장된 처리 이력이 없습니다.
              </p>
            )}
          </section>
        </div>
      </section>
    </div>,
    document.body,
  );
}

export default function RemoteConsultantInquiryDetail({
  inquiry,
  onOpenVisit,
  onRefresh,
  onStatusChange,
  onSummaryConfirmed,
  onUnsavedChangesChange,
}: RemoteConsultantInquiryDetailProps) {
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const historyTriggerRef = useRef<HTMLButtonElement>(null);
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
  const normalizedRisk = normalizeCounselorRisk(inquiry.riskLevel);
  const normalizedStatus = normalizeCounselorStatus(inquiry.workflow.status);
  const statusLabel = STATUS_LABELS[normalizedStatus];
  const riskLabel = RISK_LABELS[normalizedRisk];
  const productName = inquiry.productAndCare
    ? formatProductModelAndName(
        inquiry.productAndCare.productModel,
        inquiry.productAndCare.productModelName,
      )
    : "제품 정보 확인 필요";
  const symptomDetailItems = getSymptomDetailItems(
    inquiry.symptomAndQuestionnaire.symptomSummary,
  );
  const hasConsultationHistory =
    inquiry.consultation !== null || inquiry.stateHistory.length > 0;
  const isCompletedInquiry =
    normalizedStatus === "RESOLVED" || normalizedStatus === "CANCELLED";
  const showCompletionSummary =
    isCompletedInquiry || normalizedStatus === "COMPLETION_PENDING";
  const showActionPanel = Boolean(
    !isCompletedInquiry &&
      onOpenVisit &&
      onRefresh &&
      hasRemoteConsultationAction(inquiry),
  );
  const completionHistory = [...inquiry.stateHistory]
    .reverse()
    .find(
      (history) =>
        normalizeCounselorStatus(history.toStatus) === normalizedStatus,
    );
  const unavailableCompletionValue = "백엔드에서 제공되지 않음";
  const closeHistory = () => {
    setIsHistoryOpen(false);
    historyTriggerRef.current?.focus();
  };

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
        <div className="remote-inquiry-detail__heading">
          <h2 id="remote-inquiry-customer-title">
            {inquiry.customer.displayName}
          </h2>
          <div className="remote-inquiry-detail__badges" aria-label="문의 상태 요약">
            <span className={`remote-inquiry-detail__badge is-risk-${normalizedRisk.toLowerCase()}`}>
              {riskLabel} 문의
            </span>
            <span className="remote-inquiry-detail__badge-separator" aria-hidden="true">
              |
            </span>
            <span className="remote-inquiry-detail__badge is-status">
              {statusLabel}
            </span>
          </div>
        </div>
        <p className="remote-inquiry-detail__symptom-summary">
          {inquiry.symptomAndQuestionnaire.symptomSummary}
        </p>
        <dl className="remote-inquiry-detail__overview-meta">
          <div>
            <dt className="consultant-visually-hidden">연락처</dt>
            <dd>{inquiry.customer.phoneDisplay}</dd>
          </div>
          <div>
            <dt className="consultant-visually-hidden">제품</dt>
            <dd>{productName}</dd>
          </div>
          <div>
            <dt className="consultant-visually-hidden">접수 정보</dt>
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

      <ConsultationStepNavigator
        key={inquiry.inquiryId}
        initialStepId={showCompletionSummary ? "action" : undefined}
        steps={[
          {
            id: "inquiry",
            title: "고객 문의 · 제품 확인",
            description: "",
            content: (
              <div className="consultation-stepper__step-grid">
                <section
                  className="remote-inquiry-detail__section"
                  data-e2e-sensitive="true"
                >
                  <h2>고객 증상과 답변</h2>
                  <dl
                    className="remote-inquiry-detail__symptom-detail"
                    aria-label="고객 문의 세부 내용"
                  >
                    {symptomDetailItems.map((item) => (
                      <div key={item.label}>
                        <dt>{item.label}:</dt>
                        <dd>{item.value}</dd>
                      </div>
                    ))}
                  </dl>
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
                        <dd>{productName}</dd>
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
              </div>
            ),
          },
          {
            id: "guidance",
            title: "AI 상담 · 이전 상담 기록 확인",
            description: "",
            content: (
              <div className="consultation-stepper__step-stack">
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
                      {inquiry.guidanceAndActions.restrictedFunctions.map(
                        (item) => <li key={item}>{item}</li>,
                      )}
                    </ul>
                  ) : (
                    <p>현재 제공된 제한 기능 정보가 없습니다.</p>
                  )}
                  <p className="remote-inquiry-detail__evidence-empty">
                    공식 근거는 아직 제공되지 않았습니다.
                  </p>
                </section>

                {hasConsultationHistory && (
                  <section className="remote-inquiry-detail__history-launcher">
                    <div>
                      <h2>이전 상담 기록·처리 이력</h2>
                      <p>
                        상담 내용과 상태 변경 내역을 상세 화면에서 확인합니다.
                      </p>
                    </div>
                    <button
                      ref={historyTriggerRef}
                      type="button"
                      className="v6-button v6-button--secondary"
                      onClick={() => setIsHistoryOpen(true)}
                    >
                      상세 보기
                    </button>
                  </section>
                )}
              </div>
            ),
          },
          {
            id: "action",
            title: "상담 진행",
            description: "",
            content: (
              <div className="consultation-stepper__step-stack">
                {showActionPanel && onOpenVisit && onRefresh && (
                  <RemoteConsultationActionPanel
                    inquiry={inquiry}
                    onOpenVisit={onOpenVisit}
                    onRefresh={onRefresh}
                    onStatusChange={onStatusChange}
                    onSummaryConfirmed={onSummaryConfirmed}
                    onUnsavedChangesChange={onUnsavedChangesChange}
                  />
                )}
                {showCompletionSummary && (
                  <section
                    className="remote-inquiry-detail__completion-summary"
                    aria-labelledby="consultation-completion-summary-title"
                    data-testid="consultation-completion-summary"
                    data-e2e-sensitive="true"
                  >
                    <div className="remote-inquiry-detail__completion-heading">
                      <div>
                        <small>처리 결과</small>
                        <h2 id="consultation-completion-summary-title">
                          {statusLabel}
                        </h2>
                      </div>
                      <span className="remote-inquiry-detail__completion-badge">
                        {isCompletedInquiry ? "완료" : "상담 확정"}
                      </span>
                    </div>
                    <dl className="remote-inquiry-detail__completion-list">
                      <div>
                        <dt>완료 결과</dt>
                        <dd>{statusLabel}</dd>
                      </div>
                      <div>
                        <dt>완료 사유</dt>
                        <dd>
                          {inquiry.consultation
                            ? (CONSULTATION_RESULT_LABELS[
                                inquiry.consultation.resultCode
                              ] ?? unavailableCompletionValue)
                            : unavailableCompletionValue}
                        </dd>
                      </div>
                      <div>
                        <dt>고객 최종 선택</dt>
                        <dd>{unavailableCompletionValue}</dd>
                      </div>
                      <div>
                        <dt>{isCompletedInquiry ? "완료 시간" : "상담 확정 시간"}</dt>
                        <dd>
                          {completionHistory
                            ? formatWorkspaceDateTime(
                                completionHistory.changedAt,
                              )
                            : unavailableCompletionValue}
                        </dd>
                      </div>
                      <div className="is-wide">
                        <dt>확정 상담 내용</dt>
                        <dd>
                          {inquiry.consultation?.summary.confirmedSummary ??
                            unavailableCompletionValue}
                        </dd>
                      </div>
                      <div className="is-wide">
                        <dt>고객 안내 내용</dt>
                        <dd>
                          {inquiry.consultation?.customerGuidance ??
                            unavailableCompletionValue}
                        </dd>
                      </div>
                      <div>
                        <dt>상담 내용 확정 시간</dt>
                        <dd>
                          {inquiry.consultation?.summary.confirmedAt
                            ? formatWorkspaceDateTime(
                                inquiry.consultation.summary.confirmedAt,
                              )
                            : unavailableCompletionValue}
                        </dd>
                      </div>
                    </dl>
                  </section>
                )}
                {!showActionPanel && !showCompletionSummary && (
                  <div className="consultation-stepper__empty-action">
                    <strong>현재 진행할 상담 작업이 없습니다.</strong>
                    <p>처리 이력과 최신 문의 상태를 확인해 주세요.</p>
                  </div>
                )}
              </div>
            ),
          },
        ]}
      />

      {isHistoryOpen && (
        <ConsultationHistoryModal inquiry={inquiry} onClose={closeHistory} />
      )}
    </div>
  );
}
