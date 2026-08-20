import { describe, expect, it } from "vitest";

import { getConsultantDashboardDate } from "../../src/features/consultation/model/consultantDashboardDate";
import { getConsultantDisplayName } from "../../src/features/consultation/model/consultantDisplayName";

describe("consultant dashboard presentation", () => {
  it("서울 날짜를 고정된 대시보드 형식으로 표시한다", () => {
    expect(
      getConsultantDashboardDate(new Date("2026-08-19T15:30:00.000Z")),
    ).toEqual({
      dateTime: "2026-08-20",
      label: "2026. 08. 20. (목)",
    });
  });

  it("디자인 상담사 이름을 한예나로 표시하고 빈 이름은 보완한다", () => {
    expect(getConsultantDisplayName("합성 상담사 001")).toBe("한예나");
    expect(getConsultantDisplayName("  테스트 상담원  ")).toBe("테스트 상담원");
    expect(getConsultantDisplayName("   ")).toBe("상담사");
  });
});
