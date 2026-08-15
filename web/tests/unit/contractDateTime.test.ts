import { describe, expect, it } from "vitest";

import {
  formatContractDateTimeLong,
  formatContractDateTimePrecise,
  formatContractDateTimeShort,
} from "../../src/common/date-time/contractDateTime";

describe("계약 일시 표시", () => {
  it("+09:00 경계 시각을 다른 날짜로 변환하지 않는다", () => {
    expect(formatContractDateTimeLong("2026-07-29T00:15:00+09:00")).toBe(
      "2026년 7월 29일 오전 12:15",
    );
    expect(formatContractDateTimeLong("2026-07-29T23:50:00+09:00")).toBe(
      "2026년 7월 29일 오후 11:50",
    );
  });

  it("목록용 표시도 API의 월·일·시각을 그대로 사용한다", () => {
    expect(formatContractDateTimeShort("2026-07-29T09:20:00+09:00")).toBe(
      "07. 29. 오전 09:20",
    );
  });

  it("상담 문의 접수시각은 초 단위까지 계약 원문을 보존한다", () => {
    expect(
      formatContractDateTimePrecise("2026-08-15T14:23:07+09:00"),
    ).toBe("2026-08-15 14:23:07");
    expect(formatContractDateTimePrecise("2026-08-15T04:10Z")).toBe(
      "2026-08-15 04:10:00",
    );
  });

  it("계약 형식이 아닌 값은 표시값을 만들지 않는다", () => {
    expect(formatContractDateTimeLong("invalid-date")).toBeNull();
    expect(formatContractDateTimeShort("2026-07-29")).toBeNull();
    expect(formatContractDateTimePrecise("2026-07-29")).toBeNull();
  });
});
