export function getConsultantDisplayName(displayName?: string) {
  const normalizedDisplayName = displayName?.trim();

  return normalizedDisplayName || "상담사";
}
