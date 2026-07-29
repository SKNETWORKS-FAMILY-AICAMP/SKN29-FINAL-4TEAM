import { useState } from "react";

import RiskBadge from "../../../common/components/badge/RiskBadge";
import StatusBadge from "../../../common/components/badge/StatusBadge";
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
} from "../model/consultantWorkspaceTypes";

interface CompactConsultationDeskProps {
  inquiry: CounselorInquiry | null;
  onOpenFullDetail: () => void;
  onOpenVisit: (
    entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED",
  ) => void;
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
  onOpenFullDetail,
  onOpenVisit,
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
      onOpenFullDetail={onOpenFullDetail}
      onOpenVisit={onOpenVisit}
    />
  );
}

function CompactConsultationDeskContent({
  inquiry,
  onOpenFullDetail,
  onOpenVisit,
}: CompactConsultationDeskProps & { inquiry: CounselorInquiry }) {
  const [isAdvancedOpen, setAdvancedOpen] = useState(false);
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
  const isConsultationForm = inquiry.status === "CONSULTATION_IN_PROGRESS";
  const summaryAction = save.allowedActions.find(
    (action) => action.code === "CONFIRM_CONSULTATION_SUMMARY",
  );
  const visibleActions = save.allowedActions.filter(
    (action) => action.code !== "CONFIRM_CONSULTATION_SUMMARY",
  );

  const handleAction = async (action: CounselorAllowedAction) => {
    if (!form.validate(action.code)) {
      if (
        action.code === "CONSULTATION_COMPLETED" ||
        action.code === "CONFIRM_CONSULTATION_SUMMARY"
      ) {
        setAdvancedOpen(true);
      }
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
    if (
      outcome &&
      !("error" in outcome) &&
      (action.code === "VISIT_REVIEW_REQUIRED" || action.code === "VISIT_NEEDED")
    ) {
      onOpenVisit(action.code);
    }
  };

  return (
    <section className="simple-desk" aria-label="선택 문의 처리">
      <header className="simple-case-head">
        <div>
          <span className="simple-badge-row">
            <StatusBadge
              label={STATUS_LABELS[inquiry.status]}
              size="compact"
              variant={getStatusBadgeVariant(inquiry.status)}
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

      <section className="simple-next-step">
        <span>지금 할 일</span>
        <strong>{inquiry.routingReason}</strong>
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
            <h3>{isConsultationForm ? "상담 기록" : "다음 처리"}</h3>
          </div>
          <span>상태 버전 {save.stateVersion}</span>
        </header>

        {isConsultationForm ? (
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
            </fieldset>

            <details
              className="simple-more-fields"
              open={isAdvancedOpen}
              onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
            >
              <summary>완료 내용과 AI 요약 확인</summary>
              <div className="simple-more-fields__grid">
                <label>
                  <span>고객 안내</span>
                  <textarea
                    aria-label="고객 안내"
                    value={form.values.customerGuidance}
                    aria-invalid={Boolean(form.fieldErrors.customerGuidance)}
                    onChange={(event) => form.updateField("customerGuidance", event.target.value)}
                  />
                  <FieldError message={form.fieldErrors.customerGuidance} />
                </label>
                <label>
                  <span>처리 결과</span>
                  <textarea
                    aria-label="처리 결과"
                    value={form.values.consultationResult}
                    aria-invalid={Boolean(form.fieldErrors.consultationResult)}
                    onChange={(event) => form.updateField("consultationResult", event.target.value)}
                    placeholder="고객이 확인한 결과를 한 줄로 적으세요."
                  />
                  <FieldError message={form.fieldErrors.consultationResult} />
                </label>
                <label className="simple-summary-field">
                  <span>AI 상담 요약</span>
                  <textarea
                    aria-label="AI 상담 요약"
                    value={form.values.summaryRevision}
                    aria-invalid={Boolean(form.fieldErrors.summaryRevision)}
                    onChange={(event) => form.updateField("summaryRevision", event.target.value)}
                  />
                  <FieldError message={form.fieldErrors.summaryRevision} />
                </label>
              </div>
              {summaryAction && (
                <button
                  className="simple-summary-action"
                  type="button"
                  disabled={save.isSaving}
                  onClick={() => handleAction(summaryAction)}
                >
                  AI 요약만 확정
                </button>
              )}
            </details>

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
          </form>
        ) : (
          <div className="simple-readonly-action">
            <strong>{STATUS_LABELS[inquiry.status]}</strong>
            <p>
              {inquiry.feedbackResolved
                ? inquiry.feedbackComment
                : getNextStep(inquiry.status)}
            </p>
          </div>
        )}

        <div className="simple-action-buttons">
          {visibleActions.length === 0 ? (
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
