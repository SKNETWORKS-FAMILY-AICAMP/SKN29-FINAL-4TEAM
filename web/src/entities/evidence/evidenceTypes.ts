export interface EvidenceCardViewModel {
  dataClassification: "official" | "team_designed" | "synthetic";
  documentTitle: string;
  documentVersion: string;
  page: number;
  sourceLandingUrl?: string;
  summary: string;
  verificationLabel: string;
}
