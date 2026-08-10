import type {
  VisitMockAction,
  VisitTransitionErrors,
  VisitTransitionValues,
} from "../model/visitTransitionTypes";

const CREATE_REQUIRED_FIELDS: readonly (keyof VisitTransitionValues)[] = [
  "visitReason",
  "inspectionPriority",
  "notes",
  "safetyNotes",
];

const FIELD_MESSAGES: Record<keyof VisitTransitionValues, string> = {
  visitReason: "방문 사유를 입력해 주세요.",
  preferredDate: "고객 희망일을 선택해 주세요.",
  technicianId: "가상 방문기사를 선택해 주세요.",
  inspectionPriority: "점검 우선순위를 입력해 주세요.",
  notes: "기사 전달사항을 입력해 주세요.",
  safetyNotes: "안전 유의사항을 입력해 주세요.",
  confirmedDate: "가상 방문 확정일을 선택해 주세요.",
};

export function validateVisitTransition(
  values: VisitTransitionValues,
  action: VisitMockAction,
): VisitTransitionErrors {
  const errors: VisitTransitionErrors = {};

  CREATE_REQUIRED_FIELDS.forEach((field) => {
    if (!values[field].trim()) errors[field] = FIELD_MESSAGES[field];
  });

  if (action !== "CREATE_VISIT_REQUEST") {
    if (!values.technicianId.trim()) {
      errors.technicianId = FIELD_MESSAGES.technicianId;
    }
    if (!values.preferredDate.trim()) {
      errors.preferredDate = FIELD_MESSAGES.preferredDate;
    }
  }

  if (action === "CONFIRM_VISIT" && !values.confirmedDate.trim()) {
    errors.confirmedDate = FIELD_MESSAGES.confirmedDate;
  }

  if (
    values.preferredDate &&
    values.confirmedDate &&
    values.confirmedDate < values.preferredDate
  ) {
    errors.confirmedDate = "확정일은 고객 희망일보다 빠를 수 없습니다.";
  }

  return errors;
}
