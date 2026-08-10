import type { EvidenceCardViewModel } from "../../../entities/evidence/evidenceTypes";

export interface PublicEvidenceSource {
  dataClassification: "official" | "team_designed" | "synthetic";
  documentTitle: string;
  documentVersion: string;
  page: number;
  sourceLandingUrl?: string;
  summary: string;
  verificationLabel: string;
}

export const PUBLIC_EVIDENCE_FIELDS = [
  "dataClassification",
  "documentTitle",
  "documentVersion",
  "page",
  "sourceLandingUrl",
  "summary",
  "verificationLabel",
] as const;

function getPublicUrl(value?: string): string | undefined {
  if (!value) return undefined;

  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

export function mapEvidenceToCard(
  source: PublicEvidenceSource,
): EvidenceCardViewModel {
  return {
    dataClassification: source.dataClassification,
    documentTitle: source.documentTitle,
    documentVersion: source.documentVersion,
    page: source.page,
    sourceLandingUrl: getPublicUrl(source.sourceLandingUrl),
    summary: source.summary,
    verificationLabel: source.verificationLabel,
  };
}
