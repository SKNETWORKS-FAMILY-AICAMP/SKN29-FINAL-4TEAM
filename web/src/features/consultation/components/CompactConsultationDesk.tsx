import { useState } from "react";

import RiskBadge from "../../../common/components/badge/RiskBadge";
import StatusBadge from "../../../common/components/badge/StatusBadge";
import InlineVisitScheduler from "../../visit-transition/components/InlineVisitScheduler";
import { useConsultationForm } from "../hooks/useConsultationForm";
import { useSaveConsultation } from "../hooks/useSaveConsultation";
import {
  formatWorkspaceDateTime,
  getStatusBadgeVariant,
  STATUS_LABELS,
} from "../model/consultantWorkspaceModel";
import type {
  CounselorAllowedAction,
  CounselorInquiry,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";

interface CompactConsultationDeskProps {
  inquiry: CounselorInquiry | null;
  autoAdvance: boolean;
  onAutoAdvanceChange: (checked: boolean) => void;
  onAdvanceToNext: () => void;
  onInquiryStateChange: (update: {
    status: CounselorStatus;
    stateVersion: number;
    allowedActions: readonly CounselorAllowedAction[];
  }) => void;
  onOpenFullDetail: () => void;
}

function FieldError({ message }: { message?: string }) {
  return message ? <small className="simple-field-error">{message}</small> : null;
}

function getUsageLabel(status: CounselorInquiry["usageStatus"]) {
  if (status === "TOTAL_STOP") return "제품 사용을 즉시 중지하세요";
  if (status === "PARTIAL_STOP") return "증상 관련 기능만 중지하세요";
  if (status === "PENDING_CONSULTATION") return "상담 전 임의 조치를 안내하지 마세요";
  return "현재는 일반 사용이 가능합니다";
}

function getNextStep(status: CounselorInquiry["status"]) {
  const nextSteps: Partial<Record<CounselorInquiry["status"], string>> = {
    CONSULTATION_REQUIRED: "고객과 연결되면 상담을 시작하세요.",
    CONSULTATION_IN_PROGRESS: "안내로 해결할지, 방문 검토가 필요한지 결정하세요.",
    VISIT_REVIEW_PENDING: "방문 필요 여부를 확정하세요.",
    VISIT_SCHEDULING: "고객과 방문 일정을 조율하고 확정하세요.",
    VISIT_SCHEDULED: "방문 결과가 등록될 때까지 기다리세요.",
    COMPLETION_PENDING: "고객 해결 확인 후 문의를 최종 완료하세요.",
    REVISIT_REQUIRED: "재방문 일정을 다시 조율하세요.",
    REOPENED: "상담 대기열로 복귀시켜 다시 확인하세요.",
    RESOLVED: "처리가 완료된 문의입니다.",
    CANCELLED: "취소되어 추가 처리가 필요하지 않습니다.",
  };

  return nextSteps[status] ?? "현재 상태와 허용된 작업을 확인하세요.";
}

export default function CompactConsultationDesk({
  inquiry,
  autoAdvance,
  onAutoAdvanceChange,
  onAdvanceToNext,
  onInquiryStateChange,
  onOpenFullDetail,
}: CompactConsultationDeskProps) {
  if (!inquiry) {
    return (
      <section className="simple-desk simple-desk--empty">
        <span aria-hidden="true">☰</span>
        <strong>처리할 문의를 선택해 주세요.</strong>
        <p>왼쪽 목록에서 문의 하나를 선택하면 됩니다.</p>
      </section>
    );
  }

  return (
    <CompactConsultationDeskContent
      inquiry={inquiry}
      autoAdvance={autoAdvance}
      onAutoAdvanceChange={onAutoAdvanceChange}
      onAdvanceToNext={onAdvanceToNext}
      onInquiryStateChange={onInquiryStateChange}
      onOpenFullDetail={onOpenFullDetail}
    />
  );
}

function CompactConsultationDeskContent({
  inquiry,
  autoAdvance,
  onAutoAdvanceChange,
  onAdvanceToNext,
  onInquiryStateChange,
  onOpenFullDetail,
}: CompactConsultationDeskProps & { inquiry: CounselorInquiry }) {
  const [isVisitSchedulerOpen, setVisitSchedulerOpen] = useState(false);
  const [visitDesiredAt, setVisitDesiredAt] = useState("");
  const [visitNotes, setVisitNotes] = useState("");
  const [addressConfirmed, setAddressConfirmed] = useState(false);
  const [visitFieldErrors, setVisitFieldErrors] = useState<{
    addressConfirmed?: string;
    visitDesiredAt?: string;
  }>({});
  const [visitSnapshot, setVisitSnapshot] = useState<{
    status: CounselorStatus;
    stateVersion: number;
    allowedActions: readonly CounselorAllowedAction[];
  } | null>(null);
  const form = useConsultationForm({
    consultationNote: "",
    additionalCheck: "",
    customerGuidance: inquiry.usageMessage,
    consultationResult: "",
    summaryRevision: inquiry.aiSummaryOriginal,
    summaryConfirmed: false,
    visitRequired: "UNDECIDED",
    usageStatus: inquiry.usageStatus,
  });
  const save = useSaveConsultation(inquiry);
  const displayStatus = visitSnapshot?.status ?? save.currentStatus;
  const displayStateVersion =
    visitSnapshot?.stateVersion ?? save.stateVersion;
  const currentAllowedActions =
    visitSnapshot?.allowedActions ?? save.allowedActions;
  const isConsultationForm =
    !isVisitSchedulerOpen && displayStatus === "CONSULTATION_IN_PROGRESS";
  const visibleActions = currentAllowedActions.filter(
    (action) => action.code !== "CONFIRM_CONSULTATION_SUMMARY",
  );
  const draftAction = currentAllowedActions.find(
    (action) => action.code === "UPDATE_CONSULTATION_SUMMARY",
  );
  const completionAction = currentAllowedActions.find((action) =>
    form.values.visitRequired === "REQUIRED"
      ? action.code === "VISIT_REVIEW_REQUIRED"
      : form.values.visitRequired === "NOT_REQUIRED"
        ? action.code === "CONSULTATION_COMPLETED"
        : false,
  );

  const handleAction = async (action: CounselorAllowedAction) => {
    if (action.code === "VISIT_REVIEW_REQUIRED") {
      const nextVisitErrors: typeof visitFieldErrors = {};
      if (!visitDesiredAt) {
        nextVisitErrors.visitDesiredAt = "고객의 방문 희망 일시를 선택해 주세요.";
      }
      if (!addressConfirmed) {
        nextVisitErrors.addressConfirmed = "방문 주소를 고객과 확인해 주세요.";
      }
      setVisitFieldErrors(nextVisitErrors);
      if (Object.keys(nextVisitErrors).length > 0) return;
    }

    if (!form.validate(action.code)) {
      return;
    }

    const outcome = await save.execute({
      action,
      values: form.values,
      scenario: "SUCCESS",
    });
    const serverError = outcome && "error" in outcome ? outcome.error : undefined;
    if (serverError && "fieldErrors" in serverError && serverError.fieldErrors) {
      form.setServerFieldErrors(serverError.fieldErrors);
    }
    if (outcome?.ok) {
      onInquiryStateChange({
        status: outcome.currentStatus,
        stateVersion: outcome.stateVersion,
        allowedActions: outcome.allowedActions,
      });
      if (action.code === "CONSULTATION_COMPLETED" && autoAdvance) {
        onAdvanceToNext();
      }
    }
    if (
      outcome?.ok &&
      (action.code === "VISIT_REVIEW_REQUIRED" || action.code === "VISIT_NEEDED")
    ) {
      setVisitSnapshot({
        status: outcome.currentStatus,
        stateVersion: outcome.stateVersion,
        allowedActions: outcome.allowedActions,
      });
      setVisitSchedulerOpen(true);
    }
  };

  return (
    <section
      className={`simple-desk${isVisitSchedulerOpen ? " is-scheduling" : ""}${
        isConsultationForm ? " is-consulting" : ""
      }${
        isConsultationForm && form.values.visitRequired !== "UNDECIDED"
          ? " is-decided"
          : ""
      }`}
      aria-label="선택 문의 처리"
    >
      <header className="simple-case-head">
        <div>
          <span className="simple-badge-row">
            <StatusBadge
              label={STATUS_LABELS[displayStatus]}
              size="compact"
              variant={getStatusBadgeVariant(displayStatus)}
            />
            <RiskBadge level={inquiry.riskLevel.toLowerCase()} size="compact" />
          </span>
          <h2>{inquiry.symptomLabel}</h2>
          <p>
            {inquiry.customerName} · {inquiry.productCode} · {inquiry.inquiryCode}
          </p>
        </div>
        <button type="button" onClick={onOpenFullDetail}>
          전체 기록 보기
        </button>
      </header>

      <dl className="simple-mini-profile" aria-label="고객 및 제품 빠른 정보">
        <div>
          <dt>연락처</dt>
          <dd>{inquiry.customerPhone}</dd>
        </div>
        <div className="is-address">
          <dt>방문 주소</dt>
          <dd>{inquiry.serviceAddress}</dd>
        </div>
        <div>
          <dt>보증</dt>
          <dd>{inquiry.warrantyLabel}</dd>
        </div>
        <div>
          <dt>이전 방문</dt>
          <dd>{inquiry.previousVisitCount}회</dd>
        </div>
      </dl>

      <section className="simple-next-step">
        <span>지금 할 일</span>
        <strong>{getNextStep(displayStatus)}</strong>
      </section>

      <div className="simple-focus-grid">
        <article className="simple-customer-voice">
          <small>고객 문의</small>
          <blockquote>“{inquiry.customerMessage}”</blockquote>
          <p>접수 {formatWorkspaceDateTime(inquiry.createdAt)}</p>
        </article>

        <article
          className={`simple-guidance${
            inquiry.riskLevel === "DANGER" ? " is-danger" : ""
          }`}
        >
          <small>고객에게 먼저 안내</small>
          <strong>{getUsageLabel(inquiry.usageStatus)}</strong>
          <p>{inquiry.usageMessage}</p>
          <span>
            {inquiry.aiOutcome} · 공식 근거 {inquiry.evidence.length}건
          </span>
        </article>
      </div>

      <section className="simple-action-panel">
        <header>
          <div>
            <small>QUICK ACTION</small>
            <h3>
              {isVisitSchedulerOpen
                ? "기사 배정"
                : isConsultationForm
                  ? "상담 기록"
                  : "다음 처리"}
            </h3>
          </div>
          <span>상태 버전 {displayStateVersion}</span>
        </header>

        {isVisitSchedulerOpen ? (
          <InlineVisitScheduler
            inquiry={inquiry}
            stateVersion={displayStateVersion}
            initialDesiredAt={visitDesiredAt}
            onBack={() => setVisitSchedulerOpen(false)}
            onStateChange={(update) => {
              setVisitSnapshot(update);
              onInquiryStateChange(update);
            }}
          />
        ) : isConsultationForm ? (
          <form className="simple-consultation-form" onSubmit={(event) => event.preventDefault()} noValidate>
            <label className="simple-main-note">
              <span>상담 기록 <b>필수</b></span>
              <textarea
                aria-label="상담 기록 (필수)"
                value={form.values.consultationNote}
                aria-invalid={Boolean(form.fieldErrors.consultationNote)}
                onChange={(event) => form.updateField("consultationNote", event.target.value)}
                placeholder="고객에게 확인한 내용과 조치만 간단히 적으세요."
              />
              <FieldError message={form.fieldErrors.consultationNote} />
            </label>

            <fieldset className="simple-visit-choice">
              <legend>방문 여부</legend>
              <label>
                <input
                  type="radio"
                  name="visitRequired"
                  checked={form.values.visitRequired === "NOT_REQUIRED"}
                  onChange={() => form.updateField("visitRequired", "NOT_REQUIRED")}
                />
                <span>방문 불필요</span>
              </label>
              <label>
                <input
                  type="radio"
                  name="visitRequired"
                  checked={form.values.visitRequired === "REQUIRED"}
                  onChange={() => form.updateField("visitRequired", "REQUIRED")}
                />
                <span>방문 필요</span>
              </label>
              <FieldError message={form.fieldErrors.visitRequired} />
              <p
                className={`simple-visit-choice__hint${
                  form.values.visitRequired === "UNDECIDED" ? "" : " is-ready"
                }`}
                role="status"
              >
                {form.values.visitRequired === "REQUIRED"
                  ? "선택 완료 · 기사와 방문 일정을 바로 배정할 수 있습니다."
                  : form.values.visitRequired === "NOT_REQUIRED"
                    ? "선택 완료 · 상담 결과를 확인하고 처리를 완료하세요."
                    : "방문 여부를 선택하면 다음 처리 버튼이 표시됩니다."}
              </p>
            </fieldset>

            <section className="simple-ai-assist" aria-labelledby="simple-ai-summary-title">
              <header>
                <div>
                  <small>AI ASSIST</small>
                  <h4 id="simple-ai-summary-title">AI 상담 요약</h4>
                </div>
                <span>항상 표시</span>
              </header>
              <label>
                <span>AI 요약 수정본</span>
                <textarea
                  aria-label="AI 상담 요약"
                  value={form.values.summaryRevision}
                  aria-invalid={Boolean(form.fieldErrors.summaryRevision)}
                  onChange={(event) => form.updateField("summaryRevision", event.target.value)}
                />
                <FieldError message={form.fieldErrors.summaryRevision} />
              </label>
              <label className="simple-confirm">
                <input
                  type="checkbox"
                  checked={form.values.summaryConfirmed}
                  onChange={(event) =>
                    form.updateField("summaryConfirmed", event.target.checked)
                  }
                />
                <span>AI 요약을 확인했습니다</span>
                <FieldError message={form.fieldErrors.summaryConfirmed} />
              </label>
            </section>

            {form.values.visitRequired === "NOT_REQUIRED" && (
              <label className="simple-result-field">
                <span>상담 결과 <b>필수</b></span>
                <textarea
                  aria-label="상담 결과 (필수)"
                  value={form.values.consultationResult}
                  aria-invalid={Boolean(form.fieldErrors.consultationResult)}
                  onChange={(event) => form.updateField("consultationResult", event.target.value)}
                  placeholder="고객이 확인한 해결 결과를 한 줄로 적으세요."
                />
                <FieldError message={form.fieldErrors.consultationResult} />
              </label>
            )}

            {form.values.visitRequired === "REQUIRED" && (
              <section className="simple-visit-followup" aria-labelledby="simple-visit-followup-title">
                <header>
                  <div>
                    <small>NEXT STEP</small>
                    <h4 id="simple-visit-followup-title">방문 접수 정보</h4>
                  </div>
                  <span>기사 배정에 전달</span>
                </header>
                <div>
                  <label>
                    <span>방문 희망 일시 <b>필수</b></span>
                    <input
                      type="datetime-local"
                      aria-label="방문 희망 일시"
                      value={visitDesiredAt}
                      aria-invalid={Boolean(visitFieldErrors.visitDesiredAt)}
                      onChange={(event) => {
                        setVisitDesiredAt(event.target.value);
                        setVisitFieldErrors((current) => ({
                          ...current,
                          visitDesiredAt: undefined,
                        }));
                      }}
                    />
                    <FieldError message={visitFieldErrors.visitDesiredAt} />
                  </label>
                  <label>
                    <span>기사 전달 메모</span>
                    <input
                      type="text"
                      aria-label="기사 전달 메모"
                      value={visitNotes}
                      onChange={(event) => setVisitNotes(event.target.value)}
                      placeholder="현장에서 먼저 확인할 내용을 적으세요."
                    />
                  </label>
                </div>
                <label className="simple-address-confirm">
                  <input
                    type="checkbox"
                    checked={addressConfirmed}
                    onChange={(event) => {
                      setAddressConfirmed(event.target.checked);
                      setVisitFieldErrors((current) => ({
                        ...current,
                        addressConfirmed: undefined,
                      }));
                    }}
                  />
                  <span>
                    <b>방문 주소 확인</b>
                    {inquiry.serviceAddress}
                  </span>
                </label>
                <FieldError message={visitFieldErrors.addressConfirmed} />
              </section>
            )}
          </form>
        ) : (
          <div className="simple-readonly-action">
            <strong>{STATUS_LABELS[displayStatus]}</strong>
            <p>
              {inquiry.feedbackResolved
                ? inquiry.feedbackComment
                : getNextStep(displayStatus)}
            </p>
          </div>
        )}

        {!isVisitSchedulerOpen && (
          <div className="simple-action-buttons">
            {isConsultationForm ? (
              <>
                <label className="simple-auto-advance">
                  <input
                    type="checkbox"
                    checked={autoAdvance}
                    onChange={(event) => onAutoAdvanceChange(event.target.checked)}
                  />
                  <span>완료 후 다음 문의 자동 열기</span>
                </label>
                {draftAction && (
                  <button
                    type="button"
                    disabled={save.isSaving}
                    onClick={() => handleAction(draftAction)}
                  >
                    임시 저장
                  </button>
                )}
                <button
                  className="is-primary"
                  type="button"
                  disabled={save.isSaving || !completionAction}
                  onClick={() => completionAction && handleAction(completionAction)}
                >
                  {save.isSaving ? "처리 중…" : "상담 처리 완료"}
                </button>
              </>
            ) : visibleActions.length === 0 ? (
              <span>지금은 상담사가 처리할 작업이 없습니다.</span>
            ) : (
              visibleActions.map((action) => (
                <button
                  key={action.code}
                  className={action.style === "PRIMARY" ? "is-primary" : ""}
                  type="button"
                  disabled={save.isSaving}
                  onClick={() => handleAction(action)}
                >
                  {save.isSaving ? "처리 중…" : action.label}
                </button>
              ))
            )}
          </div>
        )}

        {save.success && (
          <p className="simple-action-message is-success" role="status">
            {save.success.message}
          </p>
        )}
        {save.error && (
          <p className="simple-action-message is-error" role="alert">
            {save.error.message}
          </p>
        )}
      </section>
    </section>
  );
}
