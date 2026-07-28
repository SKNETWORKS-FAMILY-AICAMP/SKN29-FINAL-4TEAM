import type {
  AllowedAction,
  EvidenceVerificationStatus,
  InquiryDetail,
  InquiryDetailViewModel,
} from "./inquiryDetailTypes";

function getEvidenceVerificationLabel(
  status: EvidenceVerificationStatus,
): string {
  return status === "VERIFIED" ? "검증 완료" : "검토 필요";
}

export function mapInquiryDetailToViewModel(
  inquiry: InquiryDetail,
): InquiryDetailViewModel {
  return {
    ...inquiry,
    evidence: inquiry.evidence.map((item) => ({
      ...item,
      verificationLabel: getEvidenceVerificationLabel(
        item.verificationStatus,
      ),
    })),
    isDanger: inquiry.riskLevel === "danger",
  };
}

export function canPerformInquiryAction(
  inquiry: InquiryDetailViewModel,
  action: AllowedAction,
): boolean {
  return inquiry.allowedActions.includes(action);
}
