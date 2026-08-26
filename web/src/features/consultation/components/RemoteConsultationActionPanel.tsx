import { useMemo } from "react";

import { useConsultationForm } from "../hooks/useConsultationForm";
import { useSaveConsultation } from "../hooks/useSaveConsultation";
import { isRemoteConsultationActionCode } from "../model/remoteConsultationActions";
import type { CounselorAllowedAction } from "../model/consultantWorkspaceTypes";
import type { ConsultantInquiryDetailViewModel } from "../model/consultantWorkspaceRemoteMapper";

interface Props {
  inquiry: ConsultantInquiryDetailViewModel;
  onOpenVisit: (entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED") => void;
  onRefresh: () => void;
}

export default function RemoteConsultationActionPanel({ inquiry, onOpenVisit, onRefresh }: Props) {
  const actions = useMemo<CounselorAllowedAction[]>(
    () => inquiry.workflow.allowedActions.flatMap((action) =>
      isRemoteConsultationActionCode(action.code)
        ? [{ ...action, code: action.code }]
        : [],
    ),
    [inquiry.workflow.allowedActions],
  );
  const runtimeInquiry = useMemo(() => ({
    inquiryId: inquiry.inquiryId,
    status: inquiry.workflow.status,
    stateVersion: inquiry.workflow.stateVersion,
    allowedActions: actions,
  }), [
    actions,
    inquiry.inquiryId,
    inquiry.workflow.stateVersion,
    inquiry.workflow.status,
  ]);
  const consultation = inquiry.consultation;
  const form = useConsultationForm(
    {
      consultationNote: consultation?.consultationNote ?? "",
      additionalCheck: consultation?.additionalCheck ?? "",
      customerGuidance: consultation?.customerGuidance ?? "",
      consultationResult: "",
      summaryRevision:
        consultation?.summary.confirmedSummary ??
        consultation?.summary.editedSummary ??
        consultation?.summary.aiDraftSummary ??
        "",
      summaryConfirmed: Boolean(consultation?.summary.confirmedAt),
      visitRequired: consultation?.resultCode === "VISIT_REQUIRED"
        ? "REQUIRED"
        : consultation?.resultCode === "COMPLETED_NO_VISIT"
          ? "NOT_REQUIRED"
          : "UNDECIDED",
      usageStatus:
        consultation?.usageGuidanceStatus ??
        inquiry.guidanceAndActions.usageGuidanceStatus ??
        "PENDING_CONSULTATION",
    },
    { requireConsultationResult: false },
  );
  const save = useSaveConsultation(runtimeInquiry, { dataSource: "REMOTE" });
  const showSummaryForm = save.allowedActions.some(
    (action) => action.code === "UPDATE_CONSULTATION_SUMMARY",
  );
  const isStartOnly =
    !showSummaryForm &&
    save.allowedActions.length === 1 &&
    save.allowedActions[0]?.code === "START_CONSULTATION";

  const handleAction = async (action: CounselorAllowedAction) => {
    if (action.code === "VISIT_REVIEW_REQUIRED" || action.code === "VISIT_NEEDED") {
      onOpenVisit(action.code);
      return;
    }
    if (["VISIT_NOT_NEEDED", "UPDATE_VISIT_SCHEDULE", "CONFIRM_VISIT"].includes(action.code)) {
      onOpenVisit();
      return;
    }
    if (
      action.requiresConfirmation &&
      !window.confirm(
        action.confirmationMessage ?? `${action.label} 작업을 진행하시겠습니까?`,
      )
    ) {
      return;
    }
    if (!form.validate(action.code)) return;
    const outcome = await save.execute({ action, values: form.values, scenario: "SUCCESS" });
    if (outcome.ok) onRefresh();
    if (
      !outcome.ok &&
      "error" in outcome &&
      outcome.error?.kind === "CONFLICT"
    ) {
      onRefresh();
    }
    if ("error" in outcome && outcome.error && "fieldErrors" in outcome.error) {
      form.setServerFieldErrors(outcome.error.fieldErrors ?? {});
    }
  };

  return (
    <aside
      className={`v6-action-panel${isStartOnly ? " is-start-only" : ""}`}
      aria-label="상담 처리 작업"
      data-testid="consultation-current-status"
      data-workflow-status={save.currentStatus}
      data-state-version={save.stateVersion}
    >
      {showSummaryForm && (
        <form
          data-e2e-sensitive="true"
          onSubmit={(event) => event.preventDefault()}
          noValidate
        >
          <section className="v6-action-form-section">
            <h4>상담 내용</h4>
            {([
              ["consultationNote", "상담 기록"],
              ["customerGuidance", "고객 안내 내용"],
            ] as const).map(([field, label]) => (
              <label className="v6-form-field" key={field}>
                {label}
                <textarea
                  data-testid={`consultation-field-${field}`}
                  name={field}
                  value={form.values[field]}
                  onChange={(event) =>
                    form.updateField(field, event.target.value)
                  }
                />
                {form.fieldErrors[field] && <span className="v6-field-error">{form.fieldErrors[field]}</span>}
              </label>
            ))}
          </section>
          <details className="v6-action-form-details">
            <summary>추가 확인사항 입력</summary>
            <label className="v6-form-field">
              추가 확인사항
              <textarea
                data-testid="consultation-field-additionalCheck"
                name="additionalCheck"
                value={form.values.additionalCheck}
                onChange={(event) =>
                  form.updateField("additionalCheck", event.target.value)
                }
              />
              {form.fieldErrors.additionalCheck && (
                <span className="v6-field-error">
                  {form.fieldErrors.additionalCheck}
                </span>
              )}
            </label>
          </details>
          <section className="v6-action-form-section">
            <h4>상담 요약 확인</h4>
            <label className="v6-form-field">
              상담 요약 수정본
              <textarea
                data-testid="consultation-field-summaryRevision"
                name="summaryRevision"
                value={form.values.summaryRevision}
                onChange={(event) =>
                  form.updateField("summaryRevision", event.target.value)
                }
              />
              {form.fieldErrors.summaryRevision && (
                <span className="v6-field-error">
                  {form.fieldErrors.summaryRevision}
                </span>
              )}
            </label>
            <label className="v6-summary-confirmation">
              <input
                type="checkbox"
                aria-label="상담 요약 검토·확정"
                checked={form.values.summaryConfirmed}
                onChange={(event) =>
                  form.updateField("summaryConfirmed", event.target.checked)
                }
              />
              <span>
                <strong>상담 요약 확인 완료</strong>
                <small>위 상담 요약을 검토했다면 체크해 주세요.</small>
              </span>
              {form.fieldErrors.summaryConfirmed && (
                <span className="v6-field-error">
                  {form.fieldErrors.summaryConfirmed}
                </span>
              )}
            </label>
          </section>
          <div className="v6-action-form-decisions">
            <label className="v6-form-field">
              방문 필요 여부
              <select value={form.values.visitRequired} onChange={(event) => form.updateField("visitRequired", event.target.value as typeof form.values.visitRequired)}>
                <option value="UNDECIDED">미결정</option>
                <option value="REQUIRED">방문 필요</option>
                <option value="NOT_REQUIRED">방문 불필요</option>
              </select>
            </label>
            <label className="v6-form-field">
              제품 사용 상태
              <select value={form.values.usageStatus} onChange={(event) => form.updateField("usageStatus", event.target.value as typeof form.values.usageStatus)}>
                <option value="NORMAL">정상 사용 가능</option>
                <option value="PARTIAL_STOP">일부 기능 사용 중단</option>
                <option value="TOTAL_STOP">제품 사용 중단</option>
                <option value="PENDING_CONSULTATION">상담 확인 필요</option>
              </select>
            </label>
          </div>
        </form>
      )}
      <div className="v6-action-buttons">
        {save.allowedActions.map((action) => (
          <button key={action.code} className={`v6-button v6-button--${action.style === "PRIMARY" ? "primary" : "secondary"} v6-button--full`} type="button" data-action-code={action.code} disabled={save.isSaving} onClick={() => handleAction(action)}>
            {save.isSaving ? "처리 중" : action.label}
          </button>
        ))}
      </div>
      {save.success && (
        <p className="v6-action-message is-success" role="status">
          {save.success.message}
        </p>
      )}
      {save.error && (
        <p
          className={`v6-action-message is-${save.error.kind.toLowerCase()}`}
          role="alert"
        >
          {save.error.message}
          {save.error.correlationId && (
            <small>확인 번호: {save.error.correlationId}</small>
          )}
        </p>
      )}
      {save.error?.kind === "CONFLICT" && (
        <>
          <p className="v6-action-conflict-note">
            작성 중인 내용은 유지했습니다. 최신 상태를 확인한 뒤 다시 진행해 주세요.
          </p>
          <button className="v6-button v6-button--secondary v6-button--full" type="button" onClick={onRefresh}>최신 상태 다시 불러오기</button>
        </>
      )}
    </aside>
  );
}
