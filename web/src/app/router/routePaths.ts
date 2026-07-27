export const ROUTE_PATHS = {
  home: "/",
  consultantInquiryList: "/consultant/inquiries",
  consultantInquiryDetail: "/consultant/inquiries/:inquiryId",
} as const;

export function createInquiryDetailPath(inquiryId: string): string {
  return `/consultant/inquiries/${encodeURIComponent(inquiryId)}`;
}
