export interface EvidenceCardViewModel {
  dataClassification: string;
  documentTitle: string;
  documentVersion: string;
  page: number;
  prohibitedActions: readonly string[];
  riskLevel: string;
  safeActions: readonly string[];
  sectionTitle: string;
  sourceDirectDownloadUrl?: string;
  sourceLandingUrl?: string;
  sourceOrganization: string;
  summary: string;
  verificationLabel: string;
}
