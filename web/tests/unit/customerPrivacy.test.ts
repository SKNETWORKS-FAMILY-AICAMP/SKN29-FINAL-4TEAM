import { describe, expect, it } from "vitest";

import { maskCustomerPhone } from "../../src/common/privacy/customerPrivacy";

describe("고객 개인정보 표시", () => {
  it("휴대전화의 가운데 번호만 가린다", () => {
    expect(maskCustomerPhone("010-1234-5678")).toBe("010-****-5678");
    expect(maskCustomerPhone("01012345678")).toBe("010-****-5678");
    expect(maskCustomerPhone("010-****-5678 (합성)")).toBe(
      "010-****-5678 (합성)",
    );
  });
});
