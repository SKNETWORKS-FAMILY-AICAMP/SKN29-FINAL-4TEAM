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
