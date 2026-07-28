import { describe, expect, it } from "vitest";

import type { ConsultationFormValues } from "../../src/features/consultation/model/consultationTypes";
import { validateConsultation } from "../../src/features/consultation/validation/consultationSchema";

const EMPTY_VALUES: ConsultationFormValues = {
  consultationNote: "",
  additionalCheck: "",
  customerGuidance: "",
  consultationResult: "",
  summaryRevision: "",
  summaryConfirmed: false,
  visitRequired: "UNDECIDED",
  usageStatus: "NORMAL",
};

describe("validateConsultation", () => {
  it("임시 저장은 상담 기록 또는 수정 요약 중 하나를 요구한다", () => {
    expect(
      validateConsultation(EMPTY_VALUES, "UPDATE_CONSULTATION_SUMMARY"),
    ).toHaveProperty("consultationNote");

    expect(
      validateConsultation(
        { ...EMPTY_VALUES, summaryRevision: "상담사가 보완한 요약" },
        "UPDATE_CONSULTATION_SUMMARY",
      ),
    ).toEqual({});
  });

  it("상담 완료에 필요한 기록·안내·결과·방문 여부·확정을 검사한다", () => {
    expect(
      validateConsultation(EMPTY_VALUES, "CONSULTATION_COMPLETED"),
    ).toEqual({
      consultationNote: "상담 기록을 입력해 주세요.",
      customerGuidance: "고객에게 안내한 내용을 입력해 주세요.",
      consultationResult: "상담 결과를 입력해 주세요.",
      summaryConfirmed: "상담 요약을 검토·확정해 주세요.",
      visitRequired: "방문 필요 여부를 선택해 주세요.",
    });
  });

  it("방문 검토 행동은 방문 필요 선택일 때만 허용한다", () => {
    const baseValues: ConsultationFormValues = {
      ...EMPTY_VALUES,
      consultationNote: "추가 확인 완료",
      customerGuidance: "안전 안내 완료",
    };

    expect(
      validateConsultation(
        { ...baseValues, visitRequired: "NOT_REQUIRED" },
        "VISIT_REVIEW_REQUIRED",
      ),
    ).toHaveProperty("visitRequired");

    expect(
      validateConsultation(
        { ...baseValues, visitRequired: "REQUIRED" },
        "VISIT_REVIEW_REQUIRED",
      ),
    ).toEqual({});
  });
});

