import { describe, expect, it } from "vitest";

import {
  formatProductModelAndName,
  getProductDisplayName,
} from "../../src/features/consultation/model/productDisplayName";

describe("productDisplayName", () => {
  it.each([
    ["WPUJAC104DWH", "초소형 직수 냉온 정수기"],
    ["WPU-JAC104D", "초소형 직수 냉온 정수기"],
    ["WPUIAC425SNW", "원코크 플러스 얼음물 정수기"],
    ["WPU-IAC425", "원코크 플러스 얼음물 정수기"],
    ["WPU-IAC425-BLK", "원코크 플러스 얼음물 정수기"],
    ["WPUIAC606SNW", "MEGA ICE mini 얼음 냉온정수기"],
    ["WPU-IAC606", "MEGA ICE mini 얼음 냉온정수기"],
  ])("%s 모델의 제품명을 반환한다", (modelCode, productName) => {
    expect(getProductDisplayName(modelCode)).toBe(productName);
    expect(formatProductModelAndName(modelCode)).toBe(
      `${modelCode} · ${productName}`,
    );
  });

  it("API가 제공한 제품명을 우선한다", () => {
    expect(
      formatProductModelAndName("WPUJAC104DWH", "API 제공 제품명"),
    ).toBe("WPUJAC104DWH · API 제공 제품명");
  });

  it("API 이름이 모델 코드와 같으면 알려진 제품명으로 보완한다", () => {
    expect(
      formatProductModelAndName("WPU-JAC104D", "WPU-JAC104D"),
    ).toBe("WPU-JAC104D · 초소형 직수 냉온 정수기");
  });

  it("API 이름이 괄호가 포함된 축약 모델 코드면 실제 제품명으로 보완한다", () => {
    expect(
      formatProductModelAndName("WPUJAC104DWH", "WPU-JAC104 (D)"),
    ).toBe("WPUJAC104DWH · 초소형 직수 냉온 정수기");
  });

  it("알 수 없는 모델은 모델 코드만 안전하게 표시한다", () => {
    expect(getProductDisplayName("UNKNOWN-100")).toBeNull();
    expect(formatProductModelAndName("UNKNOWN-100")).toBe("UNKNOWN-100");
  });
});
