import type { CounselorAllowedAction } from "../model/consultantWorkspaceTypes";
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
    throw new ConsultationMockError({
      kind: "CONFLICT",
      message:
        "다른 담당자가 먼저 문의를 변경했습니다. 작성 내용은 유지했으며 최신 상태를 반영했습니다.",
      currentStatus: "CONSULTATION_IN_PROGRESS",
      currentStateVersion: request.state_version + 1,
      allowedActions: currentAllowedActions,
      correlationId: request.correlation_id,
    });
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

  return {
    message: "Mock 저장 완료 · 최신 문의 정보를 다시 불러왔습니다.",
    stateVersion: request.state_version + 1,
    correlationId: request.correlation_id,
  };
}

