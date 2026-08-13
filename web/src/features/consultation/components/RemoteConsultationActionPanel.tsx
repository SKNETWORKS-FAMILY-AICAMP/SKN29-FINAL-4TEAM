import { useMemo } from "react";

import { useConsultationForm } from "../hooks/useConsultationForm";
import { useSaveConsultation } from "../hooks/useSaveConsultation";
import type { CounselorActionCode, CounselorAllowedAction } from "../model/consultantWorkspaceTypes";
import type { ConsultantInquiryDetailViewModel } from "../model/consultantWorkspaceRemoteMapper";

interface Props {
  inquiry: ConsultantInquiryDetailViewModel;
  onOpenVisit: (entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED") => void;
  onRefresh: () => void;
}

const ACTION_CODES = new Set<CounselorActionCode>([
  "START_CONSULTATION", "UPDATE_CONSULTATION_SUMMARY",
  "CONFIRM_CONSULTATION_SUMMARY", "CONSULTATION_COMPLETED",
  "VISIT_REVIEW_REQUIRED", "VISIT_NEEDED", "VISIT_NOT_NEEDED",
  "UPDATE_VISIT_SCHEDULE", "CONFIRM_VISIT",
]);

export default function RemoteConsultationActionPanel({ inquiry, onOpenVisit, onRefresh }: Props) {
  const actions = useMemo<CounselorAllowedAction[]>(
    () => inquiry.workflow.allowedActions.flatMap((action) =>
      ACTION_CODES.has(action.code as CounselorActionCode)
        ? [{ ...action, code: action.code as CounselorActionCode }]
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

  const handleAction = async (action: CounselorAllowedAction) => {
    if (action.code === "VISIT_REVIEW_REQUIRED" || action.code === "VISIT_NEEDED") {
      onOpenVisit(action.code);
      return;
    }
    if (["VISIT_NOT_NEEDED", "UPDATE_VISIT_SCHEDULE", "CONFIRM_VISIT"].includes(action.code)) {
      onOpenVisit();
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
    <aside className="v6-action-panel" aria-label="상담 처리 작업">
      <div className="v6-action-panel__head">
        <small>COUNSEL DESK · REMOTE</small>
        <h3>상담 처리</h3>
        <p>{inquiry.inquiryCode} · stateVersion {save.stateVersion}</p>
        <small>currentStatus {save.currentStatus}</small>
      </div>
      {showSummaryForm && (
        <form onSubmit={(event) => event.preventDefault()} noValidate>
          {([
            ["consultationNote", "상담 기록"],
            ["additionalCheck", "추가 확인사항"],
            ["customerGuidance", "고객 안내"],
            ["summaryRevision", "확정 요약"],
          ] as const).map(([field, label]) => (
            <label className="v6-form-field" key={field}>
              {label}
              <textarea value={form.values[field]} onChange={(event) => form.updateField(field, event.target.value)} />
              {form.fieldErrors[field] && <span className="v6-field-error">{form.fieldErrors[field]}</span>}
            </label>
          ))}
          <label className="v6-form-field">
            <span>
              <input
                type="checkbox"
                checked={form.values.summaryConfirmed}
                onChange={(event) =>
                  form.updateField("summaryConfirmed", event.target.checked)
                }
              />
              상담 요약 검토·확정
            </span>
            {form.fieldErrors.summaryConfirmed && (
              <span className="v6-field-error">
                {form.fieldErrors.summaryConfirmed}
              </span>
            )}
          </label>
          <label className="v6-form-field">
            방문 필요 여부
            <select value={form.values.visitRequired} onChange={(event) => form.updateField("visitRequired", event.target.value as typeof form.values.visitRequired)}>
              <option value="UNDECIDED">미결정</option>
              <option value="REQUIRED">방문 필요</option>
              <option value="NOT_REQUIRED">방문 불필요</option>
            </select>
          </label>
          <label className="v6-form-field">
            사용 안내 상태
            <select value={form.values.usageStatus} onChange={(event) => form.updateField("usageStatus", event.target.value as typeof form.values.usageStatus)}>
              <option value="NORMAL">정상 사용</option>
              <option value="PARTIAL_STOP">부분 사용 중지</option>
              <option value="TOTAL_STOP">전체 사용 중지</option>
              <option value="PENDING_CONSULTATION">상담 확인 전 보류</option>
            </select>
          </label>
        </form>
      )}
      <div className="v6-action-buttons">
        {save.allowedActions.map((action) => (
          <button key={action.code} className={`v6-button v6-button--${action.style === "PRIMARY" ? "primary" : "secondary"} v6-button--full`} type="button" disabled={save.isSaving} onClick={() => handleAction(action)}>
            {save.isSaving ? "처리 중" : action.label}
          </button>
        ))}
      </div>
      {save.success && <p className="v6-action-message is-success" role="status">{save.success.message}</p>}
      {save.error && <p className="v6-action-message" role="alert">{save.error.message}</p>}
      {save.error?.kind === "CONFLICT" && (
        <button className="v6-button v6-button--secondary v6-button--full" type="button" onClick={onRefresh}>최신 상태 다시 불러오기</button>
      )}
    </aside>
  );
}
