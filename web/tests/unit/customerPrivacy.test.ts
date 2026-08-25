import { describe, expect, it } from "vitest";

import {
  maskCustomerName,
  maskCustomerPhone,
} from "../../src/common/privacy/customerPrivacy";

describe("고객 개인정보 표시", () => {
  it("이름은 첫 글자와 마지막 글자만 표시한다", () => {
    expect(maskCustomerName("최지용")).toBe("최*용");
    expect(maskCustomerName("최지용 (합성)")).toBe("최*용 (합성)");
    expect(maskCustomerName("김용")).toBe("김*");
  });

  it("휴대전화의 가운데 번호만 가린다", () => {
    expect(maskCustomerPhone("010-1234-5678")).toBe("010-****-5678");
    expect(maskCustomerPhone("01012345678")).toBe("010-****-5678");
    expect(maskCustomerPhone("010-****-5678 (합성)")).toBe(
      "010-****-5678 (합성)",
    );
  });
});
