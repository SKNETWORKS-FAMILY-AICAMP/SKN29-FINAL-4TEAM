export const ROUTE_PATHS = {
  home: "/",
  consultantInquiryList: "/consultant/inquiries",
  consultantInquiryDetail: "/consultant/inquiries/:inquiryId",
  consultantVisitTransition:
    "/consultant/inquiries/:inquiryId/visit-transition",
} as const;

export function createInquiryDetailPath(inquiryId: string): string {
  return `/consultant/inquiries/${encodeURIComponent(inquiryId)}`;
}

export function createVisitTransitionPath(inquiryId: string): string {
  return `/consultant/inquiries/${encodeURIComponent(
    inquiryId,
  )}/visit-transition`;
}

export function getSafeInquiryListReturnPath(value: unknown): string {
  if (
    typeof value === "string" &&
    (value === ROUTE_PATHS.consultantInquiryList ||
      value.startsWith(`${ROUTE_PATHS.consultantInquiryList}?`))
  ) {
    return value;
  }

  return ROUTE_PATHS.consultantInquiryList;
}
