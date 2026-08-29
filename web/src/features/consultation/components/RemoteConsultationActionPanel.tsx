import { useMemo, useState } from "react";

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
}

const UNIFIED_CONSULTATION_RECORD_MAX_LENGTH = 2000;

function presentConsultationAction(
  action: CounselorAllowedAction,
): CounselorAllowedAction {
  if (action.code === "UPDATE_CONSULTATION_SUMMARY") {
    return { ...action, label: "상담 내용 수정" };
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

  if (entries.length === 1) return entries[0].value;
  return entries
    .map(({ label, value }) => `${label}\n${value}`)
    .join("\n\n");
}

export default function RemoteConsultationActionPanel({ inquiry, onOpenVisit, onRefresh, onStatusChange }: Props) {
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
  const [isConsultationRecordEdited, setIsConsultationRecordEdited] =
    useState(false);
  const [isSummaryEditing, setIsSummaryEditing] = useState(false);
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

  const updateUnifiedConsultationRecord = (value: string) => {
    setConsultationRecord(value);
    setIsConsultationRecordEdited(true);
    form.updateField("consultationNote", value);
    // Backend와 고객 앱은 기존 공개 계약의 세 필드를 각각 소비한다. 화면은
    // 하나로 합치되 새 입력은 동일한 원문으로 매핑해 어느 경로에서도 빠지지
    // 않게 한다.
    form.updateField("customerGuidance", value);
    form.updateField("additionalCheck", value);
  };

  const handleAction = async (action: CounselorAllowedAction) => {
    const presentedAction = presentConsultationAction(action);
    if (
      action.code === "UPDATE_CONSULTATION_SUMMARY" &&
      !isSummaryEditing
    ) {
      setIsSummaryEditing(true);
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
    let valuesForAction = isConsultationRecordEdited
      ? form.values
      : {
          ...form.values,
          consultationNote: consultationRecord,
          customerGuidance: consultationRecord,
          additionalCheck: consultationRecord,
        };
    if (action.code === "CONFIRM_CONSULTATION_SUMMARY") {
      valuesForAction = { ...valuesForAction, summaryConfirmed: true };
      form.updateField("summaryConfirmed", true);
    }
    if (!form.validate(action.code, valuesForAction)) return;
    const outcome = await save.execute({
      action: presentedAction,
      values: valuesForAction,
      scenario: "SUCCESS",
    });
    if (outcome.ok) {
      if (action.code === "UPDATE_CONSULTATION_SUMMARY") {
        setIsSummaryEditing(false);
      }
      if ("result" in outcome) {
        onStatusChange?.(outcome.result.status);
      }
      onRefresh();
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
                maxLength={UNIFIED_CONSULTATION_RECORD_MAX_LENGTH}
                value={consultationRecord}
                onChange={(event) =>
                  updateUnifiedConsultationRecord(event.target.value)
                }
              />
              {form.fieldErrors.consultationNote && (
                <span className="v6-field-error">
                  {form.fieldErrors.consultationNote}
                </span>
              )}
              {!form.fieldErrors.consultationNote &&
                (form.fieldErrors.customerGuidance ||
                  form.fieldErrors.additionalCheck) && (
                  <span className="v6-field-error">
                    {form.fieldErrors.customerGuidance ??
                      form.fieldErrors.additionalCheck}
                  </span>
                )}
            </label>
          </section>
          <section className="v6-action-form-section v6-action-form-section--summary">
            <label className="v6-form-field">
              상담 내용 수정본
              <textarea
                data-testid="consultation-field-summaryRevision"
                name="summaryRevision"
                disabled={!isSummaryEditing}
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
        {save.allowedActions.map((action) => {
          const presentedAction = presentConsultationAction(action);
          const label =
            action.code === "UPDATE_CONSULTATION_SUMMARY" && isSummaryEditing
              ? "수정 내용 저장"
              : presentedAction.label;

          return (
            <button key={action.code} className={`v6-button v6-button--${action.style === "PRIMARY" ? "primary" : "secondary"} v6-button--full`} type="button" data-action-code={action.code} disabled={save.isSaving} onClick={() => handleAction(action)}>
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
