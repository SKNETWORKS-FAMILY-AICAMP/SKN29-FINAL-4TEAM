import type {
  VisitMockAction,
  VisitTransitionErrors,
  VisitTransitionValues,
} from "../model/visitTransitionTypes";

const REQUIRED_FIELDS: readonly (keyof VisitTransitionValues)[] = [
  "visitReason",
  "desiredAt",
  "technicianId",
  "inspectionPriority",
  "notes",
  "safetyNotes",
];

const FIELD_MESSAGES: Record<keyof VisitTransitionValues, string> = {
  visitReason: "방문 사유를 입력해 주세요.",
  desiredAt: "고객 희망일을 선택해 주세요.",
  technicianId: "가상 방문기사를 선택해 주세요.",
  inspectionPriority: "점검 우선순위를 입력해 주세요.",
  notes: "기사 전달사항을 입력해 주세요.",
  safetyNotes: "안전 유의사항을 입력해 주세요.",
  confirmedAt: "가상 방문 확정일을 선택해 주세요.",
};

export function validateVisitTransition(
  values: VisitTransitionValues,
  action: VisitMockAction,
): VisitTransitionErrors {
  const errors: VisitTransitionErrors = {};

  REQUIRED_FIELDS.forEach((field) => {
    if (!values[field].trim()) errors[field] = FIELD_MESSAGES[field];
  });

  if (action === "CONFIRM_VISIT" && !values.confirmedAt.trim()) {
    errors.confirmedAt = FIELD_MESSAGES.confirmedAt;
  }

  if (
    values.desiredAt &&
    values.confirmedAt &&
    new Date(values.confirmedAt).getTime() < new Date(values.desiredAt).getTime()
  ) {
    errors.confirmedAt = "확정일은 고객 희망일보다 빠를 수 없습니다.";
  }

  return errors;
}
