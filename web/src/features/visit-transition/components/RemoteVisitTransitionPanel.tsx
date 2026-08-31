import { useMemo, useRef, useState } from "react";

import { ApiClientError } from "../../../common/api/apiError";
import { IdempotencyOperationTracker } from "../../../common/api/idempotencyOperation";
import { createRequestContext } from "../../../common/api/requestContext";
import FormSelect from "../../../common/components/form/FormSelect";
import type { ConsultantInquiryDetailViewModel, RemoteAllowedAction } from "../../consultation/model/consultantWorkspaceRemoteMapper";
import type { ConsultantDashboardTechnician } from "../../notice/model/consultantNotice";
import type { VisitTransitionValues } from "../model/visitTransitionTypes";
import {
  buildVisitScheduleRequest,
  createRemoteVisitWriteRepository,
  toNullableDateOnly,
  type VisitTransitionResultDto,
  type VisitWriteRepository,
} from "../repositories/visitWriteRepository";

export type TechnicianSourceStatus =
  | "loading"
  | "ready"
  | "empty"
  | "forbidden"
  | "error";

interface Props {
  inquiry: ConsultantInquiryDetailViewModel;
  onRefresh: () => void;
  onRetryTechnicians: () => void;
  technicianSourceStatus: TechnicianSourceStatus;
  technicians: readonly ConsultantDashboardTechnician[];
  writeRepository?: VisitWriteRepository;
}

const defaultWriteRepository = createRemoteVisitWriteRepository();

function visitIdFromResource(resource: unknown): string | null {
  if (!resource || typeof resource !== "object") return null;
  const visitId = (resource as Record<string, unknown>).visit_id;
  return typeof visitId === "string" ? visitId : null;
}

function visitIdFromDetail(
  visit: ConsultantInquiryDetailViewModel["visit"],
): string | null {
  return visit?.visitId ?? null;
}

function technicianIdFromDetail(
  visit: ConsultantInquiryDetailViewModel["visit"],
): string {
  return visit?.schedule.syntheticTechnicianId ?? "";
}

export default function RemoteVisitTransitionPanel({
  inquiry,
  onRefresh,
  onRetryTechnicians,
  technicianSourceStatus,
  technicians,
  writeRepository = defaultWriteRepository,
}: Props) {
  const [values, setValues] = useState<VisitTransitionValues>(() =>
    ({
      visitReason: "",
      preferredDate: "",
      technicianId: technicianIdFromDetail(inquiry.visit),
      inspectionPriority: inquiry.symptomAndQuestionnaire.symptomSummary,
      notes: "",
      safetyNotes: "",
      confirmedDate: "",
    }),
  );
  const [stateVersion, setStateVersion] = useState(inquiry.stateVersion);
  const [actions, setActions] = useState<readonly RemoteAllowedAction[]>(inquiry.workflow.allowedActions);
  const [visitId, setVisitId] = useState(() => visitIdFromDetail(inquiry.visit));
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const savingRef = useRef(false);
  const [tracker] = useState(() => new IdempotencyOperationTracker());
  const actionCodes = useMemo(() => new Set(actions.map((action) => action.code)), [actions]);
  const availableTechnicianIds = useMemo(
    () => new Set(technicians.map((technician) => technician.userId)),
    [technicians],
  );
  const hasAssignedTechnicianFallback = Boolean(
    values.technicianId && !availableTechnicianIds.has(values.technicianId),
  );
  const hasSelectableTechnicians =
    technicianSourceStatus === "ready" && technicians.length > 0;
  const hasValidTechnicianSelection =
    hasSelectableTechnicians &&
    availableTechnicianIds.has(values.technicianId);

  const update = (field: keyof VisitTransitionValues, value: string) => {
    setValues((current) => ({ ...current, [field]: value }));
  };

  const requireValues = (fields: readonly (keyof VisitTransitionValues)[]) => {
    const missing = fields.find((field) => !values[field].trim());
    if (missing) {
      setError("필수 방문 정보를 모두 입력해 주세요.");
      return false;
    }
    if (
      values.preferredDate &&
      values.confirmedDate &&
      values.confirmedDate < values.preferredDate
    ) {
      setError("확정일은 고객 희망일보다 빠를 수 없습니다.");
      return false;
    }
    return true;
  };

  const execute = async (
    signature: string,
    request: (context: ReturnType<typeof createRequestContext>) => Promise<{ data: VisitTransitionResultDto | null }>,
  ) => {
    if (savingRef.current) return;
    const context = createRequestContext({ idempotencyKey: tracker.begin(signature) });
    savingRef.current = true;
    setIsSaving(true);
    setMessage(null);
    setError(null);
    try {
      const response = await request(context);
      if (!response.data) throw new Error("서버 상태 변경 결과가 없습니다.");
      tracker.finish();
      setStateVersion(response.data.state_version);
      setActions(response.data.allowed_actions.map((action) => ({
        code: action.code,
        label: action.label,
        operationId: action.operation_id,
        style: action.style,
        requiresConfirmation: action.requires_confirmation,
        confirmationMessage: action.confirmation_message,
      })));
      setVisitId((current) => visitIdFromResource(response.data?.resource) ?? current);
      setMessage(response.data.message);
      onRefresh();
    } catch (caught) {
      const retryable = caught instanceof ApiClientError && ["NETWORK_ERROR", "TIMEOUT", "SERVER_ERROR"].includes(caught.kind);
      tracker.fail(retryable);
      if (caught instanceof ApiClientError && caught.kind === "CONFLICT") {
        const version = caught.details.current_state_version;
        if (typeof version === "number") setStateVersion(version);
      }
      setError(caught instanceof Error ? caught.message : "방문 처리 중 오류가 발생했습니다.");
    } finally {
      savingRef.current = false;
      setIsSaving(false);
    }
  };

  const requestReview = () => {
    if (!requireValues(["visitReason"])) return;
    void execute(JSON.stringify(["review", stateVersion, values.visitReason]),
      (context) => writeRepository.requestReview(inquiry.inquiryId, {
      state_version: stateVersion,
      reason_code: "PHYSICAL_INSPECTION_REQUIRED",
      reason_detail: values.visitReason.trim() || null,
    }, context));
  };
  const markNotNeeded = () => {
    if (!requireValues(["notes"])) return;
    void execute(JSON.stringify(["not-needed", stateVersion, values.notes]),
      (context) => writeRepository.markNotNeeded(inquiry.inquiryId, {
      state_version: stateVersion,
      reason_code: "RESOLVED_BY_CONSULTATION",
      reason_detail: values.notes.trim() || null,
    }, context));
  };
  const createVisit = () => {
    if (!requireValues(["visitReason", "inspectionPriority", "notes", "safetyNotes"])) return;
    const productModel = inquiry.productAndCare?.productModel;
    if (!productModel) {
      setError("제품 정보가 없는 문의는 방문 인계 자료를 생성할 수 없습니다.");
      return;
    }
    void execute(JSON.stringify(["create", stateVersion, values]),
      (context) => writeRepository.create(inquiry.inquiryId, {
      state_version: stateVersion,
      visit_reason: values.visitReason.trim(),
      preferred_date: toNullableDateOnly(values.preferredDate),
      usage_guidance_status: inquiry.guidanceAndActions.usageGuidanceStatus ?? "PENDING_CONSULTATION",
      handoff: {
        product_summary: productModel,
        symptom_summary: inquiry.symptomAndQuestionnaire.symptomSummary,
        action_summary: values.notes.trim(),
        risk_summary: values.safetyNotes.trim(),
        priority_check_items: [values.inspectionPriority.trim()],
        consultant_final: values.visitReason.trim(),
      },
    }, context));
  };
  const saveSchedule = () => {
    if (!visitId) {
      setError("서버 상세 응답에서 visit_id를 확인할 수 없습니다.");
      return;
    }
    if (!hasValidTechnicianSelection) {
      setError("Dashboard에서 조회된 활성 합성 방문기사를 선택해 주세요.");
      return;
    }
    if (!requireValues(["technicianId", "preferredDate"])) return;
    void execute(
      JSON.stringify(["schedule", visitId, stateVersion, values.technicianId, values.preferredDate, values.confirmedDate]),
      (context) => writeRepository.saveSchedule(visitId, buildVisitScheduleRequest({
        stateVersion,
        technicianId: values.technicianId,
        preferredDate: values.preferredDate,
        confirmedDate: values.confirmedDate,
      }), context),
    );
  };
  const confirmVisit = () => {
    if (!visitId) {
      setError("서버 상세 응답에서 visit_id를 확인할 수 없습니다.");
      return;
    }
    if (!requireValues(["confirmedDate"])) return;
    void execute(
      JSON.stringify(["confirm", visitId, stateVersion]),
      (context) => writeRepository.confirm(visitId, { state_version: stateVersion }, context),
    );
  };

  const needsReview = actionCodes.has("VISIT_REVIEW_REQUIRED");
  const canCreate = actionCodes.has("VISIT_NEEDED");

  return (
    <section className="v6-panel" aria-label="실제 방문 전환 처리">
      <header className="v6-action-panel__head">
        <small>VISIT FLOW · REMOTE</small>
        <h2>방문 전환 및 일정</h2>
        <p>stateVersion {stateVersion}{visitId ? ` · visit ${visitId}` : ""}</p>
      </header>
      <label className="v6-form-field">방문 사유<textarea value={values.visitReason} onChange={(event) => update("visitReason", event.target.value)} /></label>
      <label className="v6-form-field">기사 전달사항<textarea value={values.notes} onChange={(event) => update("notes", event.target.value)} /></label>
      <label className="v6-form-field">안전 유의사항<textarea value={values.safetyNotes} onChange={(event) => update("safetyNotes", event.target.value)} /></label>
      <label className="v6-form-field">점검 우선순위<input value={values.inspectionPriority} onChange={(event) => update("inspectionPriority", event.target.value)} /></label>
      <label className="v6-form-field">고객 희망일<input type="date" value={values.preferredDate} onChange={(event) => update("preferredDate", event.target.value)} /></label>
      <div className="v6-form-field">
        <label htmlFor="remote-visit-technician">방문 기사</label>
        <FormSelect
          id="remote-visit-technician"
          aria-label="방문기사"
          data-testid="visit-technician-select"
          disabled={isSaving || !hasSelectableTechnicians}
          value={values.technicianId}
          onChange={(value) => update("technicianId", value)}
          options={[
            { value: "", label: "방문기사를 선택해 주세요." },
            ...(hasAssignedTechnicianFallback ? [{
              value: values.technicianId,
              label: "현재 배정 기사 · 선택 목록 외",
              disabled: true,
            }] : []),
            ...technicians.map((technician) => ({
              value: technician.userId,
              label: `${technician.name} · ${technician.branch}`,
            })),
          ]}
        />
        {technicianSourceStatus === "loading" && (
          <small role="status">방문기사 목록을 불러오고 있습니다.</small>
        )}
        {technicianSourceStatus === "empty" && (
          <small role="status">선택 가능한 합성 방문기사가 없습니다.</small>
        )}
        {technicianSourceStatus === "forbidden" && (
          <small role="alert">방문기사 목록을 조회할 권한이 없습니다.</small>
        )}
        {technicianSourceStatus === "error" && (
          <span>
            <small role="alert">방문기사 목록을 불러오지 못했습니다.</small>
            <button
              className="v6-button v6-button--secondary"
              type="button"
              onClick={onRetryTechnicians}
            >
              기사 목록 다시 불러오기
            </button>
          </span>
        )}
      </div>
      <label className="v6-form-field">확정일<input type="date" value={values.confirmedDate} onChange={(event) => update("confirmedDate", event.target.value)} /></label>
      <div className="v6-action-buttons">
        {needsReview && <button className="v6-button v6-button--primary" type="button" disabled={isSaving} onClick={requestReview}>방문 필요 검토 요청</button>}
        {actionCodes.has("VISIT_NOT_NEEDED") && <button className="v6-button v6-button--secondary" type="button" disabled={isSaving} onClick={markNotNeeded}>방문 불필요 확정</button>}
        {canCreate && <button className="v6-button v6-button--primary" type="button" disabled={isSaving} onClick={createVisit}>방문 생성</button>}
        {actionCodes.has("UPDATE_VISIT_SCHEDULE") && <button className="v6-button v6-button--primary" type="button" data-action-code="UPDATE_VISIT_SCHEDULE" disabled={isSaving || !hasValidTechnicianSelection} onClick={saveSchedule}>기사·일정 저장</button>}
        {actionCodes.has("CONFIRM_VISIT") && <button className="v6-button v6-button--primary" type="button" disabled={isSaving} onClick={confirmVisit}>방문 확정</button>}
      </div>
      {message && <p className="v6-action-message is-success" role="status">{message}</p>}
      {error && <p className="v6-action-message" role="alert">{error} 입력 내용은 유지됩니다.</p>}
    </section>
  );
}
