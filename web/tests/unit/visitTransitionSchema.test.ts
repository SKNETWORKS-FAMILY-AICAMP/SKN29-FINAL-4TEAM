import { describe, expect, it } from "vitest";

import type { VisitTransitionValues } from "../../src/features/visit-transition/model/visitTransitionTypes";
import { validateVisitTransition } from "../../src/features/visit-transition/validation/visitTransitionSchema";

const VALID_VALUES: VisitTransitionValues = {
  visitReason: "현장 점검이 필요합니다.",
  preferredDate: "2026-07-29",
  technicianId: "00000000-0000-4000-8000-000000000101",
  inspectionPriority: "누수 여부를 먼저 확인합니다.",
  notes: "고객 통화 후 방문해 주세요.",
  safetyNotes: "전원 차단 여부를 확인해 주세요.",
  confirmedDate: "",
};

describe("validateVisitTransition", () => {
  it("일정 조율 저장에 필요한 기본 필드를 검사한다", () => {
    expect(
      validateVisitTransition(
        { ...VALID_VALUES, preferredDate: "", technicianId: "" },
        "SAVE_SCHEDULE",
      ),
    ).toEqual({
      preferredDate: "고객 희망일을 선택해 주세요.",
      technicianId: "가상 방문기사를 선택해 주세요.",
    });
  });

  it("방문 확정에는 가상 방문 확정일을 추가로 요구한다", () => {
    expect(validateVisitTransition(VALID_VALUES, "CONFIRM_VISIT")).toEqual({
      confirmedDate: "가상 방문 확정일을 선택해 주세요.",
    });
  });

  it("확정일이 고객 희망일보다 빠르면 오류를 반환한다", () => {
    expect(
      validateVisitTransition(
        {
          ...VALID_VALUES,
          preferredDate: "2026-07-30",
          confirmedDate: "2026-07-29",
        },
        "CONFIRM_VISIT",
      ),
    ).toEqual({
      confirmedDate: "확정일은 고객 희망일보다 빠를 수 없습니다.",
    });
  });

  it("방문 생성 단계에서는 기사와 일정이 없어도 된다", () => {
    expect(
      validateVisitTransition(
        {
          ...VALID_VALUES,
          technicianId: "",
          preferredDate: "",
          confirmedDate: "",
        },
        "CREATE_VISIT_REQUEST",
      ),
    ).toEqual({});
  });
});
