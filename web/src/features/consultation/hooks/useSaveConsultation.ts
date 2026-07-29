import { useState } from "react";

import { IdempotencyOperationTracker } from "../../../common/api/idempotencyOperation";
import { createRequestContext } from "../../../common/api/requestContext";
import {
  ConsultationMockError,
  submitConsultationMock,
} from "../api/consultationMockApi";
import type {
  CounselorAllowedAction,
  CounselorInquiry,
} from "../model/consultantWorkspaceTypes";
import type {
  ConsultationActionErrorDetails,
  ConsultationActionSuccess,
  ConsultationFormValues,
  ConsultationMockScenario,
  ProvisionalConsultationActionRequest,
} from "../model/consultationTypes";

interface ExecuteConsultationArgs {
  action: CounselorAllowedAction;
  values: ConsultationFormValues;
  scenario: ConsultationMockScenario;
}

export function useSaveConsultation(inquiry: CounselorInquiry) {
  const [isSaving, setIsSaving] = useState(false);
  const [success, setSuccess] = useState<ConsultationActionSuccess | null>(null);
  const [error, setError] = useState<ConsultationActionErrorDetails | null>(null);
  const [currentStatus, setCurrentStatus] = useState(inquiry.status);
  const [stateVersion, setStateVersion] = useState(inquiry.stateVersion);
  const [allowedActions, setAllowedActions] = useState(inquiry.allowedActions);
  const [operationTracker] = useState(
    () => new IdempotencyOperationTracker(),
  );

  const execute = async ({
    action,
    values,
    scenario,
  }: ExecuteConsultationArgs) => {
    if (
      action.requiresConfirmation &&
      action.confirmationMessage &&
      !window.confirm(action.confirmationMessage)
    ) {
      return { ok: false as const, cancelled: true as const };
    }

    const requestPayload: Omit<
      ProvisionalConsultationActionRequest,
      "idempotency_key" | "correlation_id"
    > = {
      inquiry_id: inquiry.inquiryId,
      action_code: action.code,
      operation_id: action.operationId,
      state_version: stateVersion,
      consultation_note: values.consultationNote.trim(),
      additional_check: values.additionalCheck.trim(),
      customer_guidance: values.customerGuidance.trim(),
      consultation_result: values.consultationResult.trim(),
      summary_revision: values.summaryRevision.trim(),
      summary_confirmed: values.summaryConfirmed,
      visit_required: values.visitRequired,
      usage_guidance_status: values.usageStatus,
    };
    const operationSignature = JSON.stringify(requestPayload);
    const idempotencyKey = operationTracker.begin(operationSignature);
    const context = createRequestContext({ idempotencyKey });
    const request: ProvisionalConsultationActionRequest = {
      ...requestPayload,
      idempotency_key: context.idempotencyKey,
      correlation_id: context.correlationId,
    };

    setIsSaving(true);
    setSuccess(null);
    setError(null);

    try {
      const result = await submitConsultationMock(
        request,
        scenario,
        allowedActions,
      );
      operationTracker.finish();
      setSuccess(result);
      setStateVersion(result.stateVersion);
      setAllowedActions(result.allowedActions);
      return { ok: true as const, result };
    } catch (caught) {
      const nextError =
        caught instanceof ConsultationMockError
          ? caught.details
          : {
              kind: "NETWORK_ERROR" as const,
              message: "알 수 없는 연결 오류가 발생했습니다. 입력 내용은 유지됩니다.",
            };

      setError(nextError);
      operationTracker.fail(nextError.kind === "NETWORK_ERROR");
      if (
        nextError.kind === "CONFLICT" &&
        nextError.conflictCode === "STATE-CONFLICT-01"
      ) {
        if (nextError.currentStatus) {
          setCurrentStatus(nextError.currentStatus);
        }
        setStateVersion(nextError.currentStateVersion);
        setAllowedActions(nextError.allowedActions);
      }
      return { ok: false as const, error: nextError };
    } finally {
      setIsSaving(false);
    }
  };

  return {
    isSaving,
    success,
    error,
    currentStatus,
    stateVersion,
    allowedActions,
    execute,
  };
}
