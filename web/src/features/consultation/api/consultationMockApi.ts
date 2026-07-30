import type { CounselorAllowedAction } from "../model/consultantWorkspaceTypes";
import {
  mapWorkflowActionSuccess,
  mapWorkflowConflict,
} from "../../workflow-action/model/workflowActionMapper";
import type {
  WorkflowActionSuccessDto,
  WorkflowAllowedActionDto,
  WorkflowConflictErrorDto,
} from "../../workflow-action/model/workflowActionDtos";
import type {
  CounselorActionCode,
  CounselorStatus,
} from "../model/consultantWorkspaceTypes";
import type {
  ConsultationActionErrorDetails,
  ConsultationActionSuccess,
  ConsultationMockScenario,
  ProvisionalConsultationActionRequest,
} from "../model/consultationTypes";

export class ConsultationMockError extends Error {
  readonly details: ConsultationActionErrorDetails;

  constructor(details: ConsultationActionErrorDetails) {
    super(details.message);
    this.name = "ConsultationMockError";
    this.details = details;
  }
}

function waitForMockResponse() {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, 350);
  });
}

export async function submitConsultationMock(
  request: ProvisionalConsultationActionRequest,
  scenario: ConsultationMockScenario,
  currentAllowedActions: readonly CounselorAllowedAction[],
): Promise<ConsultationActionSuccess> {
  await waitForMockResponse();

  if (scenario === "FORBIDDEN") {
    throw new ConsultationMockError({
      kind: "FORBIDDEN",
      message: "이 문의를 처리할 권한이 없습니다. 담당자와 역할을 확인해 주세요.",
      correlationId: request.correlation_id,
    });
  }

  if (scenario === "CONFLICT") {
    const errorDto: WorkflowConflictErrorDto<CounselorActionCode> = {
      code: "STATE-CONFLICT-01",
      message:
        "다른 담당자가 먼저 문의를 변경했습니다. 작성 내용은 유지했으며 최신 상태를 반영했습니다.",
      details: {
        current_status: "CONSULTATION_IN_PROGRESS",
        current_state_version: request.state_version + 1,
        allowed_actions: currentAllowedActions.map((action) => action.code),
      },
    };
    throw new ConsultationMockError(
      mapWorkflowConflict<CounselorActionCode, CounselorStatus>(
        errorDto,
        request.correlation_id,
        currentAllowedActions,
      ),
    );
  }

  if (scenario === "DUPLICATE_EVENT") {
    const errorDto: WorkflowConflictErrorDto<CounselorActionCode> = {
      code: "DUPLICATE-EVENT-01",
      message:
        "같은 Idempotency-Key에 다른 요청 내용이 사용되었습니다. 새 작업으로 다시 시도해 주세요.",
      details: {},
    };
    throw new ConsultationMockError(
      mapWorkflowConflict<CounselorActionCode, CounselorStatus>(
        errorDto,
        request.correlation_id,
        currentAllowedActions,
      ),
    );
  }

  if (scenario === "VALIDATION_ERROR") {
    throw new ConsultationMockError({
      kind: "VALIDATION_ERROR",
      message: "서버가 입력값을 확인하지 못했습니다. 표시된 항목을 확인해 주세요.",
      fieldErrors: {
        consultationResult: "Mock 서버 검증 오류입니다. 상담 결과를 보완해 주세요.",
      },
      correlationId: request.correlation_id,
    });
  }

  if (scenario === "NETWORK_ERROR") {
    throw new ConsultationMockError({
      kind: "NETWORK_ERROR",
      message: "네트워크에 연결하지 못했습니다. 입력 내용은 유지되며 다시 시도할 수 있습니다.",
      correlationId: request.correlation_id,
    });
  }

  const allowedActionDtos: readonly WorkflowAllowedActionDto<CounselorActionCode>[] =
    currentAllowedActions.map((action) => ({
      code: action.code,
      label: action.label,
      operation_id: action.operationId,
      style: action.style,
      requires_confirmation: action.requiresConfirmation,
      confirmation_message: action.confirmationMessage,
    }));
  const successDto: WorkflowActionSuccessDto<CounselorActionCode> = {
    message:
      request.action_code === "START_CONSULTATION"
        ? "상담을 시작했습니다. 확인한 내용을 상담 기록에 입력해 주세요."
        : request.action_code === "VISIT_REVIEW_REQUIRED"
          ? "방문 필요를 확인했습니다. 기사와 방문 일정을 바로 조율해 주세요."
        : "Mock 저장 완료 · 최신 문의 정보를 다시 불러왔습니다.",
    state_version: request.state_version + 1,
    allowed_actions: allowedActionDtos,
  };

  return mapWorkflowActionSuccess(successDto, request.correlation_id);
}

export interface ConsultationDetailSnapshot {
  inquiryId: string;
  stateVersion: number;
  allowedActions: readonly CounselorAllowedAction[];
  refreshedAt: string;
}

export async function reloadConsultationDetailMock(
  inquiryId: string,
  result: ConsultationActionSuccess,
): Promise<ConsultationDetailSnapshot> {
  return {
    inquiryId,
    stateVersion: result.stateVersion,
    allowedActions: result.allowedActions,
    refreshedAt: new Date().toISOString(),
  };
}

