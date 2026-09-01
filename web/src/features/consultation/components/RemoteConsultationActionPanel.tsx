import { useEffect, useMemo, useState } from "react";

import FormSelect from "../../../common/components/form/FormSelect";
import { useConsultationForm } from "../hooks/useConsultationForm";
import { useSaveConsultation } from "../hooks/useSaveConsultation";
import { isRemoteConsultationActionCode } from "../model/remoteConsultationActions";
import type {
  CounselorAllowedAction,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";
import type { ConsultantInquiryDetailViewModel } from "../model/consultantWorkspaceRemoteMapper";

interface Props {
  inquiry: ConsultantInquiryDetailViewModel;
  onOpenVisit: (entryAction?: "VISIT_REVIEW_REQUIRED" | "VISIT_NEEDED") => void;
  onRefresh: () => void;
  onStatusChange?: (status: CounselorStatus) => void;
  onSummaryConfirmed?: (status: CounselorStatus) => void;
  onUnsavedChangesChange?: (hasUnsavedChanges: boolean) => void;
}

const UNIFIED_CONSULTATION_RECORD_MAX_LENGTH = 2000;

function presentConsultationAction(
  action: CounselorAllowedAction,
): CounselorAllowedAction {
  if (action.code === "UPDATE_CONSULTATION_SUMMARY") {
    return { ...action, label: "편집 시작" };
  }
  if (action.code === "CONFIRM_CONSULTATION_SUMMARY") {
    return {
      ...action,
      label: "상담 내용 확정",
      confirmationMessage: "상담을 확정하시겠습니까?",
    };
  }
  return action;
}

function buildUnifiedConsultationRecord(
  consultation: ConsultantInquiryDetailViewModel["consultation"],
) {
  if (!consultation) return "";

  const seenValues = new Set<string>();
  const entries = [
    ["상담 기록", consultation.consultationNote],
    ["고객 안내 내용", consultation.customerGuidance],
    ["추가 확인사항", consultation.additionalCheck],
  ].flatMap(([label, rawValue]) => {
    const value = rawValue?.trim();
    if (!value || seenValues.has(value)) return [];
    seenValues.add(value);
    return [{ label, value }];
  });

  if (entries.length === 0) {
    return consultation.summary.editedSummary ??
      consultation.summary.confirmedSummary ??
      consultation.summary.aiDraftSummary ?? "";
  }
  if (entries.length === 1) return entries[0].value;
  return entries
    .map(({ label, value }) => `${label}\n${value}`)
    .join("\n\n");
}

interface ConsultationDraftSnapshot {
  record: string;
  usageStatus: string;
  visitRequired: string;
}

export default function RemoteConsultationActionPanel({ inquiry, onOpenVisit, onRefresh, onStatusChange, onSummaryConfirmed, onUnsavedChangesChange }: Props) {
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
  const [consultationRecord, setConsultationRecord] = useState(() =>
    buildUnifiedConsultationRecord(consultation),
  );
  const [editingBaseline, setEditingBaseline] =
    useState<ConsultationDraftSnapshot | null>(null);
  const [savedSummary, setSavedSummary] = useState<{
    record: string;
    stateVersion: number;
  } | null>(null);
  const form = useConsultationForm(
    {
      consultationNote: consultation?.consultationNote ?? "",
      additionalCheck: consultation?.additionalCheck ?? "",
      customerGuidance: consultation?.customerGuidance ?? "",
      consultationResult: "",
      summaryRevision: buildUnifiedConsultationRecord(consultation),
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
  const visibleActions = save.allowedActions.filter((action) =>
    action.code !== "VISIT_REVIEW_REQUIRED" && action.code !== "VISIT_NEEDED",
  );
  // The confirmation API confirms the stored summary, not the form values.
  // A successful save can precede the refreshed detail; a newer detail wins.
  const serverSummary = (
    consultation?.summary.editedSummary ?? consultation?.summary.confirmedSummary
  )?.trim() ?? null;
  const persistedSummary = savedSummary && savedSummary.stateVersion > inquiry.workflow.stateVersion
    ? savedSummary.record
    : serverSummary;
  const requiresSummarySave = showSummaryForm && (
    !persistedSummary || persistedSummary !== consultationRecord.trim()
  );
  const isStartOnly =
    !showSummaryForm &&
    visibleActions.length === 1 &&
    visibleActions[0]?.code === "START_CONSULTATION";
  const isSummaryEditing = editingBaseline !== null;
  const hasUnsavedChanges = Boolean(
    editingBaseline &&
      (editingBaseline.record !== consultationRecord ||
        editingBaseline.visitRequired !== form.values.visitRequired ||
        editingBaseline.usageStatus !== form.values.usageStatus),
  );

  useEffect(() => {
    onUnsavedChangesChange?.(hasUnsavedChanges);
  }, [hasUnsavedChanges, onUnsavedChangesChange]);

  useEffect(
    () => () => onUnsavedChangesChange?.(false),
    [onUnsavedChangesChange],
  );

  const updateUnifiedConsultationRecord = (value: string) => {
    setConsultationRecord(value);
    form.updateField("consultationNote", value);
    // Backend와 고객 앱은 기존 공개 계약의 세 필드를 각각 소비한다. 화면은
    // 하나로 합치되 저장은 동일한 원문으로 매핑해 어느 경로에서도 빠지지
    // 않게 한다.
    form.updateField("customerGuidance", value);
    form.updateField("additionalCheck", value);
    form.updateField("summaryRevision", value);
  };

  const handleAction = async (action: CounselorAllowedAction) => {
    const presentedAction = presentConsultationAction(action);
    if (action.code === "CONFIRM_CONSULTATION_SUMMARY" && requiresSummarySave) return;
    if (
      action.code === "UPDATE_CONSULTATION_SUMMARY" &&
      !isSummaryEditing
    ) {
      setEditingBaseline({
        record: consultationRecord,
        usageStatus: form.values.usageStatus,
        visitRequired: form.values.visitRequired,
      });
      return;
    }
    if (action.code === "VISIT_REVIEW_REQUIRED" || action.code === "VISIT_NEEDED") {
      onOpenVisit(action.code);
      return;
    }
    if (["VISIT_NOT_NEEDED", "UPDATE_VISIT_SCHEDULE", "CONFIRM_VISIT"].includes(action.code)) {
      onOpenVisit();
      return;
    }
    // 확인 다이얼로그는 useSaveConsultation에서 한 번만 처리한다. 여기에서도
    // 확인하면 requires_confirmation 작업이 이중 팝업으로 실행된다.
    let valuesForAction = {
      ...form.values,
      consultationNote: consultationRecord,
      customerGuidance: consultationRecord,
      additionalCheck: consultationRecord,
      summaryRevision: consultationRecord,
    };
    if (action.code === "CONFIRM_CONSULTATION_SUMMARY") {
      valuesForAction = { ...valuesForAction, summaryConfirmed: true };
    }
    if (!form.validate(action.code, valuesForAction)) return;
    const outcome = await save.execute({
      action: presentedAction,
      values: valuesForAction,
      scenario: "SUCCESS",
    });
    if (outcome.ok) {
      if (action.code === "UPDATE_CONSULTATION_SUMMARY") {
        if ("result" in outcome && typeof outcome.result.stateVersion === "number") {
          setSavedSummary({
            record: valuesForAction.summaryRevision.trim(),
            stateVersion: outcome.result.stateVersion,
          });
        }
        setEditingBaseline(null);
      }
      if (action.code === "CONFIRM_CONSULTATION_SUMMARY") {
        form.updateField("summaryConfirmed", true);
      }
      if ("result" in outcome) {
        onStatusChange?.(outcome.result.status);
      }
      onRefresh();
      if (action.code === "CONFIRM_CONSULTATION_SUMMARY" && "result" in outcome) {
        onSummaryConfirmed?.(outcome.result.status);
      }
    }
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
            <label className="v6-form-field">
              상담 기록
              <textarea
                data-testid="consultation-field-consultationNote"
                name="consultationNote"
                aria-label="상담 기록"
                aria-describedby={requiresSummarySave ? "consultation-summary-save-note" : undefined}
                disabled={!isSummaryEditing || save.isSaving}
                maxLength={UNIFIED_CONSULTATION_RECORD_MAX_LENGTH}
                value={consultationRecord}
                onChange={(event) =>
                  updateUnifiedConsultationRecord(event.target.value)
                }
              />
              {requiresSummarySave && (
                <small id="consultation-summary-save-note" className="v6-action-note">
                  {isSummaryEditing
                    ? "수정 내용을 저장한 뒤 상담 내용을 확정할 수 있습니다."
                    : "‘편집 시작’을 눌러 상담 기록을 확인하고 저장해 주세요."}
                </small>
              )}
              {form.fieldErrors.consultationNote && (
                <span className="v6-field-error">
                  {form.fieldErrors.consultationNote}
                </span>
              )}
              {!form.fieldErrors.consultationNote &&
                (form.fieldErrors.customerGuidance ||
                  form.fieldErrors.additionalCheck ||
                  form.fieldErrors.summaryRevision) && (
                  <span className="v6-field-error">
                    {form.fieldErrors.customerGuidance ??
                      form.fieldErrors.additionalCheck ??
                      form.fieldErrors.summaryRevision}
                  </span>
                )}
            </label>
          </section>
          <div className="v6-action-form-decisions">
            <label className="v6-form-field">
              방문 필요 여부
              <FormSelect
                aria-label="방문 필요 여부"
                value={form.values.visitRequired}
                disabled={!isSummaryEditing || save.isSaving}
                onChange={(value) => form.updateField("visitRequired", value as typeof form.values.visitRequired)}
                options={[
                  { value: "UNDECIDED", label: "미결정" },
                  { value: "REQUIRED", label: "방문 필요" },
                  { value: "NOT_REQUIRED", label: "방문 불필요" },
                ]}
              />
            </label>
            <label className="v6-form-field">
              제품 사용 상태
              <FormSelect
                aria-label="제품 사용 상태"
                value={form.values.usageStatus}
                disabled={!isSummaryEditing || save.isSaving}
                onChange={(value) => form.updateField("usageStatus", value as typeof form.values.usageStatus)}
                options={[
                  { value: "NORMAL", label: "정상 사용 가능" },
                  { value: "PARTIAL_STOP", label: "일부 기능 사용 중단" },
                  { value: "TOTAL_STOP", label: "제품 사용 중단" },
                  { value: "PENDING_CONSULTATION", label: "상담 확인 필요" },
                ]}
              />
            </label>
          </div>
        </form>
      )}
      {!showSummaryForm && visibleActions.length === 0 && (
        <p className="v6-action-note">현재 진행할 상담 작업이 없습니다.</p>
      )}
      <div className="v6-action-buttons">
        {visibleActions.map((action) => {
          const presentedAction = presentConsultationAction(action);
          const label =
            action.code === "UPDATE_CONSULTATION_SUMMARY" && isSummaryEditing
              ? "수정 내용 저장"
              : presentedAction.label;
          const isConfirmationBlocked = action.code === "CONFIRM_CONSULTATION_SUMMARY" && requiresSummarySave;

          return (
            <button key={action.code} className={`v6-button v6-button--${action.style === "PRIMARY" ? "primary" : "secondary"} v6-button--full`} type="button" data-action-code={action.code} aria-describedby={isConfirmationBlocked ? "consultation-summary-save-note" : undefined} disabled={save.isSaving || isConfirmationBlocked || (isSummaryEditing && action.code !== "UPDATE_CONSULTATION_SUMMARY")} onClick={() => handleAction(action)}>
              {save.isSaving ? "처리 중" : label}
            </button>
          );
        })}
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
