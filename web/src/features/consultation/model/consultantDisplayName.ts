export function getConsultantDisplayName(displayName?: string) {
  const normalizedDisplayName = displayName?.trim();

  return normalizedDisplayName === "합성 상담사 001"
    ? "한예나"
    : (normalizedDisplayName || "상담사");
}
