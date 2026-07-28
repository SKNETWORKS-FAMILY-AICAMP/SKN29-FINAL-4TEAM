import type { EvidenceCardViewModel } from "../../../entities/evidence/evidenceTypes";

export interface PublicEvidenceSource {
  documentTitle: string;
  documentVersion: string;
  page: number;
  prohibitedActions?: readonly string[];
  riskLevel?: string;
  safeActions?: readonly string[];
  sectionTitle?: string;
  sourceDirectDownloadUrl?: string;
  sourceLandingUrl?: string;
  summary: string;
}

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
    dataClassification: "official",
    documentTitle: source.documentTitle,
    documentVersion: source.documentVersion,
    page: source.page,
    prohibitedActions: source.prohibitedActions ?? [],
    riskLevel: source.riskLevel ?? "미확인",
    safeActions: source.safeActions ?? [],
    sectionTitle: source.sectionTitle ?? "공식 근거",
    sourceDirectDownloadUrl: getPublicUrl(source.sourceDirectDownloadUrl),
    sourceLandingUrl: getPublicUrl(source.sourceLandingUrl),
    sourceOrganization: "SK매직",
    summary: source.summary,
    verificationLabel: "텍스트·시각 검증 완료",
  };
}
