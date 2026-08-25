import { describe, expect, it } from "vitest";

import { parseInquiryId } from "../../src/entities/inquiry/inquiryIdentifiers";
import {
  clearRecentConsultantInquiryIds,
  getRecentConsultantInquiryIdsStorageKey,
  MAX_RECENT_CONSULTANT_INQUIRY_IDS,
  readRecentConsultantInquiryIds,
  rememberRecentConsultantInquiryId,
  type RecentConsultantInquiryIdStorage,
} from "../../src/features/consultation/model/recentConsultantInquiryIds";

const CONSULTANT_A = "STAFF-CONS-A";
const CONSULTANT_B = "STAFF-CONS-B";
const INQUIRY_IDS = [
  parseInquiryId("00000000-0000-4000-8000-000000000001"),
  parseInquiryId("00000000-0000-4000-8000-000000000002"),
  parseInquiryId("00000000-0000-4000-8000-000000000003"),
  parseInquiryId("00000000-0000-4000-8000-000000000004"),
  parseInquiryId("00000000-0000-4000-8000-000000000005"),
  parseInquiryId("00000000-0000-4000-8000-000000000006"),
] as const;

function createStorage(): RecentConsultantInquiryIdStorage & {
  values: Map<string, string>;
} {
  const values = new Map<string, string>();
  return {
    values,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => void values.set(key, value),
    removeItem: (key) => void values.delete(key),
  };
}

describe("recentConsultantInquiryIds", () => {
  it("최신 문의를 맨 앞에 두고 중복을 제거하며 최대 다섯 건만 유지한다", () => {
    const storage = createStorage();

    INQUIRY_IDS.forEach((inquiryId) =>
      rememberRecentConsultantInquiryId(CONSULTANT_A, inquiryId, storage),
    );

    expect(readRecentConsultantInquiryIds(CONSULTANT_A, storage)).toEqual([
      INQUIRY_IDS[5],
      INQUIRY_IDS[4],
      INQUIRY_IDS[3],
      INQUIRY_IDS[2],
      INQUIRY_IDS[1],
    ]);
    expect(MAX_RECENT_CONSULTANT_INQUIRY_IDS).toBe(5);

    rememberRecentConsultantInquiryId(CONSULTANT_A, INQUIRY_IDS[2], storage);

    expect(readRecentConsultantInquiryIds(CONSULTANT_A, storage)).toEqual([
      INQUIRY_IDS[2],
      INQUIRY_IDS[5],
      INQUIRY_IDS[4],
      INQUIRY_IDS[3],
      INQUIRY_IDS[1],
    ]);
  });

  it("상담원별 저장 키를 분리한다", () => {
    const storage = createStorage();

    rememberRecentConsultantInquiryId(CONSULTANT_A, INQUIRY_IDS[0], storage);
    rememberRecentConsultantInquiryId(CONSULTANT_B, INQUIRY_IDS[1], storage);

    expect(getRecentConsultantInquiryIdsStorageKey(CONSULTANT_A)).not.toBe(
      getRecentConsultantInquiryIdsStorageKey(CONSULTANT_B),
    );
    expect(readRecentConsultantInquiryIds(CONSULTANT_A, storage)).toEqual([
      INQUIRY_IDS[0],
    ]);
    expect(readRecentConsultantInquiryIds(CONSULTANT_B, storage)).toEqual([
      INQUIRY_IDS[1],
    ]);
  });

  it("저장 값은 UUID 문자열 배열만 사용하고 잘못된 항목은 읽지 않는다", () => {
    const storage = createStorage();
    const storageKey = getRecentConsultantInquiryIdsStorageKey(CONSULTANT_A);
    if (!storageKey) throw new Error("테스트 저장 키를 만들 수 없습니다.");

    storage.setItem(
      storageKey,
      JSON.stringify([
        INQUIRY_IDS[0],
        { inquiryId: INQUIRY_IDS[1], customerName: "저장 금지" },
        "not-a-uuid",
        INQUIRY_IDS[0],
        INQUIRY_IDS[2],
      ]),
    );

    expect(readRecentConsultantInquiryIds(CONSULTANT_A, storage)).toEqual([
      INQUIRY_IDS[0],
      INQUIRY_IDS[2],
    ]);

    rememberRecentConsultantInquiryId(CONSULTANT_A, INQUIRY_IDS[1], storage);
    expect(JSON.parse(storage.values.get(storageKey) ?? "null")).toEqual([
      INQUIRY_IDS[1],
      INQUIRY_IDS[0],
      INQUIRY_IDS[2],
    ]);
  });

  it("손상된 JSON이나 유효하지 않은 입력을 빈 최근 기록으로 처리한다", () => {
    const storage = createStorage();
    const storageKey = getRecentConsultantInquiryIdsStorageKey(CONSULTANT_A);
    if (!storageKey) throw new Error("테스트 저장 키를 만들 수 없습니다.");
    storage.setItem(storageKey, "{broken-json");

    expect(readRecentConsultantInquiryIds(CONSULTANT_A, storage)).toEqual([]);
    expect(
      rememberRecentConsultantInquiryId(CONSULTANT_A, "not-a-uuid", storage),
    ).toEqual([]);
    expect(readRecentConsultantInquiryIds("  ", storage)).toEqual([]);
  });

  it("저장소 접근이 차단되어도 읽기·기록·삭제가 예외를 던지지 않는다", () => {
    const blockedStorage: RecentConsultantInquiryIdStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };

    expect(readRecentConsultantInquiryIds(CONSULTANT_A, blockedStorage)).toEqual(
      [],
    );
    expect(
      rememberRecentConsultantInquiryId(
        CONSULTANT_A,
        INQUIRY_IDS[0],
        blockedStorage,
      ),
    ).toEqual([INQUIRY_IDS[0]]);
    expect(() =>
      clearRecentConsultantInquiryIds(CONSULTANT_A, blockedStorage),
    ).not.toThrow();
  });

  it("현재 상담원의 최근 기록만 삭제한다", () => {
    const storage = createStorage();
    rememberRecentConsultantInquiryId(CONSULTANT_A, INQUIRY_IDS[0], storage);
    rememberRecentConsultantInquiryId(CONSULTANT_B, INQUIRY_IDS[1], storage);

    clearRecentConsultantInquiryIds(CONSULTANT_A, storage);

    expect(readRecentConsultantInquiryIds(CONSULTANT_A, storage)).toEqual([]);
    expect(readRecentConsultantInquiryIds(CONSULTANT_B, storage)).toEqual([
      INQUIRY_IDS[1],
    ]);
  });
});
