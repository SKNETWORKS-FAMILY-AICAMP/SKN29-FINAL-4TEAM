declare const inquiryIdBrand: unique symbol;
declare const inquiryCodeBrand: unique symbol;

export type InquiryId = string & {
  readonly [inquiryIdBrand]: "InquiryId";
};

export type InquiryCode = string & {
  readonly [inquiryCodeBrand]: "InquiryCode";
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function parseInquiryId(value: string): InquiryId {
  if (!UUID_PATTERN.test(value)) {
    throw new Error(`문의 공개 ID가 UUID 형식이 아닙니다: ${value}`);
  }

  return value as InquiryId;
}

export function toInquiryId(value: unknown): InquiryId | null {
  return typeof value === "string" && UUID_PATTERN.test(value)
    ? (value as InquiryId)
    : null;
}

export function parseInquiryCode(value: string): InquiryCode {
  if (!value.trim()) {
    throw new Error("문의 표시 코드는 비어 있을 수 없습니다.");
  }

  return value as InquiryCode;
}
