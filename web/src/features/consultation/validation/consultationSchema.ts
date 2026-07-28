import type { CounselorActionCode } from "../model/consultantWorkspaceTypes";
import type {
  ConsultationFieldErrors,
  ConsultationFormValues,
} from "../model/consultationTypes";

function isBlank(value: string) {
  return value.trim().length === 0;
}

export function validateConsultation(
  values: ConsultationFormValues,
  actionCode: CounselorActionCode,
): ConsultationFieldErrors {
  const errors: ConsultationFieldErrors = {};

  if (
    actionCode === "UPDATE_CONSULTATION_SUMMARY" &&
    isBlank(values.consultationNote) &&
    isBlank(values.summaryRevision)
  ) {
    errors.consultationNote = "상담 기록 또는 상담사 수정 요약을 입력해 주세요.";
  }

  if (actionCode === "CONFIRM_CONSULTATION_SUMMARY") {
    if (isBlank(values.summaryRevision)) {
      errors.summaryRevision = "확정할 상담사 수정 요약을 입력해 주세요.";
    }
    if (!values.summaryConfirmed) {
      errors.summaryConfirmed = "상담사 검토·확정 여부를 체크해 주세요.";
    }
  }

  if (
    actionCode === "CONSULTATION_COMPLETED" ||
    actionCode === "VISIT_REVIEW_REQUIRED"
  ) {
    if (isBlank(values.consultationNote)) {
      errors.consultationNote = "상담 기록을 입력해 주세요.";
    }
    if (isBlank(values.customerGuidance)) {
      errors.customerGuidance = "고객에게 안내한 내용을 입력해 주세요.";
    }
    if (values.visitRequired === "UNDECIDED") {
      errors.visitRequired = "방문 필요 여부를 선택해 주세요.";
    }
  }

  if (actionCode === "CONSULTATION_COMPLETED") {
    if (isBlank(values.consultationResult)) {
      errors.consultationResult = "상담 결과를 입력해 주세요.";
    }
    if (!values.summaryConfirmed) {
      errors.summaryConfirmed = "상담 요약을 검토·확정해 주세요.";
    }
  }

  if (
    actionCode === "VISIT_REVIEW_REQUIRED" &&
    values.visitRequired !== "REQUIRED"
  ) {
    errors.visitRequired = "방문 필요를 선택해야 검토 단계로 전환할 수 있습니다.";
  }

  return errors;
}

