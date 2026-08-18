import { describe, expect, it } from "vitest";

import { classifyInquiryCategory } from "../../src/features/consultation/model/consultantInquiryCategories";

describe("상담 문의 카테고리 분류", () => {
  it.each([
    [
      "정수기에서 물이 안 나와요. 무엇을 먼저 봐야 하나요?",
      ["제품 작동 이상", "출수 문제", "물이 안 나옴"],
    ],
    [
      "정수기 아래에 물이 고여 있고 지금도 조금씩 번집니다.",
      ["안전·긴급 문제", "누수", "제품 아래 누수"],
    ],
    [
      "휴대폰 앱으로 필터 남은 기간을 확인하는 방법을 알려주세요.",
      ["사용 방법·기능", "앱·IoT", "앱 필터 확인"],
    ],
    [
      "냉수 뒤에 윙 소리가 나고 출수할 때 툭 소리가 한 번 납니다.",
      ["제품 작동 이상", "소음·진동", "팬·컴프레서 소음"],
    ],
  ])("문의 문구를 3단계 카테고리로 분류한다", (summary, expected) => {
    const category = classifyInquiryCategory(summary);

    expect([category.major, category.middle, category.minor]).toEqual(expected);
  });

  it("알 수 없는 문의는 기타 분류로 안전하게 모은다", () => {
    expect(classifyInquiryCategory("확인이 필요한 문의입니다.")).toEqual({
      major: "기타",
      middle: "복합·미분류",
      minor: "분류 필요",
    });
  });
});
