import { describe, expect, it } from "vitest";

import {
  parseInquiryCode,
  parseInquiryId,
  toInquiryId,
} from "../../src/entities/inquiry/inquiryIdentifiers";

describe("문의 식별자", () => {
  const inquiryId = "205850d3-763c-5256-9d39-82da21be0c31";

  it("공개 리소스 ID는 UUID만 허용한다", () => {
    expect(parseInquiryId(inquiryId)).toBe(inquiryId);
    expect(toInquiryId(inquiryId)).toBe(inquiryId);
  });

  it("표시용 문의 번호를 공개 리소스 ID로 허용하지 않는다", () => {
    expect(toInquiryId("INQ-20260704-0013")).toBeNull();
    expect(() => parseInquiryId("DEMO-INQ-001")).toThrow(
      "문의 공개 ID가 UUID 형식이 아닙니다",
    );
  });

  it("표시용 문의 번호는 별도 코드로 보존한다", () => {
    expect(parseInquiryCode("INQ-20260704-0013")).toBe(
      "INQ-20260704-0013",
    );
  });
});
