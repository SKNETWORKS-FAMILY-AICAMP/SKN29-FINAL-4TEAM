import { useRef, useState } from "react";

import { appEnv } from "../../../app/config/env";
import { ApiClientError } from "../../../common/api/apiError";
import { IdempotencyOperationTracker } from "../../../common/api/idempotencyOperation";
import { createRequestContext } from "../../../common/api/requestContext";
import {
  ConsultationMockError,
  reloadConsultationDetailMock,
  submitConsultationMock,
} from "../api/consultationMockApi";
import type {
  CounselorActionCode,
  CounselorAllowedAction,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";
import type {
  ConsultationActionErrorDetails,
  ConsultationActionSuccess,
  ConsultationFormValues,
  ConsultationMockScenario,
  ProvisionalConsultationActionRequest,
} from "../model/consultationTypes";
import {
  createRemoteConsultationWriteRepository,
  type ConsultationWriteRepository,
  type StateTransitionResultDto,
} from "../repositories/consultationWriteRepository";

export interface ConsultationRuntimeInquiry {
  inquiryId: string;
  status: CounselorStatus;
  stateVersion: number;
  allowedActions: readonly CounselorAllowedAction[];
}

interface ExecuteConsultationArgs {
  action: CounselorAllowedAction;
  values: ConsultationFormValues;
  scenario: ConsultationMockScenario;
}

interface UseSaveConsultationOptions {
  dataSource?: "MOCK" | "REMOTE";
  remoteRepository?: ConsultationWriteRepository;
}

const remoteRepository = createRemoteConsultationWriteRepository();
const ACTION_CODES = new Set<CounselorActionCode>([
  "START_CONSULTATION",
  "UPDATE_CONSULTATION_SUMMARY",
  "CONFIRM_CONSULTATION_SUMMARY",
  "CONSULTATION_COMPLETED",
  "VISIT_REVIEW_REQUIRED",
  "VISIT_NEEDED",
  "VISIT_NOT_NEEDED",
  "UPDATE_VISIT_SCHEDULE",
  "CONFIRM_VISIT",
  "RESUME_CONSULTATION",
  "FINALIZE_INQUIRY",
]);

function mapAllowedActions(
  actions: StateTransitionResultDto["allowed_actions"],
): CounselorAllowedAction[] {
  return actions.flatMap((action) => {
    if (!ACTION_CODES.has(action.code as CounselorActionCode)) return [];
    return [{
      code: action.code as CounselorActionCode,
      label: action.label,
      operationId: action.operation_id,
      style: action.style,
      requiresConfirmation: action.requires_confirmation,
      confirmationMessage: action.confirmation_message,
    }];
  });
}

function resultCode(values: ConsultationFormValues) {
  if (values.visitRequired === "REQUIRED") return "VISIT_REQUIRED" as const;
  if (values.visitRequired === "NOT_REQUIRED") return "COMPLETED_NO_VISIT" as const;
  return "PENDING" as const;
}

export function useSaveConsultation(
  inquiry: ConsultationRuntimeInquiry,
  options: UseSaveConsultationOptions = {},
) {
  const dataSource = options.dataSource ?? (appEnv.useMockApi ? "MOCK" : "REMOTE");
  const writeRepository = options.remoteRepository ?? remoteRepository;
  const [isSaving, setIsSaving] = useState(false);
  const [success, setSuccess] = useState<ConsultationActionSuccess | null>(null);
  const [error, setError] = useState<ConsultationActionErrorDetails | null>(null);
  const [localSnapshot, setLocalSnapshot] =
    useState<ConsultationRuntimeInquiry | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const savingRef = useRef(false);
  const [operationTracker] = useState(() => new IdempotencyOperationTracker());
  const useLocalSnapshot =
    localSnapshot?.inquiryId === inquiry.inquiryId &&
    localSnapshot.stateVersion > inquiry.stateVersion;
  const currentStatus = useLocalSnapshot
    ? localSnapshot.status
    : inquiry.status;
  const stateVersion = useLocalSnapshot
    ? localSnapshot.stateVersion
    : inquiry.stateVersion;
  const allowedActions = useLocalSnapshot
    ? localSnapshot.allowedActions
    : inquiry.allowedActions;

  const execute = async ({ action, values, scenario }: ExecuteConsultationArgs) => {
    if (savingRef.current) {
      return { ok: false as const, duplicateClick: true as const };
    }
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
    const context = createRequestContext({
      idempotencyKey: operationTracker.begin(operationSignature),
    });
    const request: ProvisionalConsultationActionRequest = {
      ...requestPayload,
      idempotency_key: context.idempotencyKey,
      correlation_id: context.correlationId,
    };

    savingRef.current = true;
    setIsSaving(true);
    setSuccess(null);
    setError(null);

    try {
      if (dataSource === "REMOTE") {
        const stateBody = { state_version: stateVersion };
        let response;
        switch (action.code) {
          case "START_CONSULTATION":
            response = await writeRepository.start(inquiry.inquiryId, stateBody, context);
            break;
          case "UPDATE_CONSULTATION_SUMMARY": {
            const summary = values.summaryRevision.trim();
            response = await writeRepository.saveSummary(
              inquiry.inquiryId,
              {
                ...stateBody,
                ...(summary ? { summary } : {}),
                consultation_note: values.consultationNote.trim(),
                additional_check: values.additionalCheck.trim(),
                customer_guidance: values.customerGuidance.trim(),
                result_code: resultCode(values),
                usage_guidance_status: values.usageStatus,
              },
              context,
            );
            break;
          }
          case "CONFIRM_CONSULTATION_SUMMARY":
            response = await writeRepository.confirmSummary(inquiry.inquiryId, stateBody, context);
            break;
          case "CONSULTATION_COMPLETED":
            response = await writeRepository.complete(inquiry.inquiryId, stateBody, context);
            break;
          default: {
            const blockedError: ConsultationActionErrorDetails = {
              kind: "RUNTIME_BLOCKED",
              message: "방문 관련 작업은 방문 전환 화면에서 진행해 주세요.",
            };
            operationTracker.fail(false);
            setError(blockedError);
            return { ok: false as const, error: blockedError };
          }
        }
        if (!response.data) {
          throw new ApiClientError({
            kind: "PARSE_ERROR",
            message: "서버 응답에 상태 변경 결과가 없습니다.",
            correlationId: response.metadata.correlation_id,
          });
        }
        const nextAllowedActions = mapAllowedActions(response.data.allowed_actions);
        const result: ConsultationActionSuccess = {
          message: response.data.message,
          status: response.data.status,
          stateVersion: response.data.state_version,
          allowedActions: nextAllowedActions,
          correlationId: response.metadata.correlation_id,
        };
        operationTracker.finish();
        setSuccess(result);
        setLocalSnapshot({
          inquiryId: inquiry.inquiryId,
          status: result.status,
          stateVersion: result.stateVersion,
          allowedActions: nextAllowedActions,
        });
        setLastRefreshedAt(new Date().toISOString());
        return {
          ok: true as const,
          result,
          currentStatus: result.status,
          stateVersion: result.stateVersion,
          allowedActions: nextAllowedActions,
        };
      }

      const result = await submitConsultationMock(request, scenario, currentStatus, allowedActions);
      const latestDetail = await reloadConsultationDetailMock(inquiry.inquiryId, result);
      operationTracker.finish();
      setSuccess(result);
      setLocalSnapshot({
        inquiryId: inquiry.inquiryId,
        status: result.status,
        stateVersion: latestDetail.stateVersion,
        allowedActions: latestDetail.allowedActions,
      });
      setLastRefreshedAt(latestDetail.refreshedAt);
      return {
        ok: true as const,
        result,
        currentStatus: result.status,
        stateVersion: latestDetail.stateVersion,
        allowedActions: latestDetail.allowedActions,
      };
    } catch (caught) {
      let nextError: ConsultationActionErrorDetails;
      if (caught instanceof ConsultationMockError) {
        nextError = caught.details;
      } else if (caught instanceof ApiClientError && caught.kind === "CONFLICT") {
        const version = caught.details.current_state_version;
        const status = caught.details.current_status;
        const codes = Array.isArray(caught.details.allowed_actions)
          ? caught.details.allowed_actions.filter((item): item is string => typeof item === "string")
          : [];
        if (caught.code === "STATE-CONFLICT-01" && typeof version === "number") {
          const codeSet = new Set(codes);
          nextError = {
            kind: "CONFLICT",
            conflictCode: "STATE-CONFLICT-01",
            message: caught.message,
            currentStatus: typeof status === "string" ? status as CounselorStatus : null,
            currentStateVersion: version,
            allowedActionCodes: codes as CounselorActionCode[],
            allowedActions: allowedActions.filter((item) => codeSet.has(item.code)),
            correlationId: caught.correlationId ?? context.correlationId,
          };
        } else {
          nextError = {
            kind: "CONFLICT",
            conflictCode: "DUPLICATE-EVENT-01",
            message: caught.message,
            correlationId: caught.correlationId ?? context.correlationId,
          };
        }
      } else if (caught instanceof ApiClientError) {
        const kind = caught.kind === "PARSE_ERROR" || caught.kind === "CONFLICT"
          ? "UNKNOWN_ERROR"
          : caught.kind;
        nextError = {
          kind,
          message: caught.message,
          correlationId: caught.correlationId,
        };
      } else {
        nextError = {
          kind: "NETWORK_ERROR",
          message: "알 수 없는 연결 오류가 발생했습니다. 입력 내용은 유지됩니다.",
        };
      }

      setError(nextError);
      operationTracker.fail(
        nextError.kind === "NETWORK_ERROR" ||
          nextError.kind === "TIMEOUT" ||
          nextError.kind === "SERVER_ERROR",
      );
      if (nextError.kind === "CONFLICT" && nextError.conflictCode === "STATE-CONFLICT-01") {
        setLocalSnapshot({
          inquiryId: inquiry.inquiryId,
          status: nextError.currentStatus ?? currentStatus,
          stateVersion: nextError.currentStateVersion,
          allowedActions: nextError.allowedActions,
        });
      }
      return { ok: false as const, error: nextError };
    } finally {
      savingRef.current = false;
      setIsSaving(false);
    }
  };

  return {
    isSaving,
    isWriteEnabled: true,
    success,
    error,
    currentStatus,
    stateVersion,
    allowedActions,
    lastRefreshedAt,
    execute,
  };
}
