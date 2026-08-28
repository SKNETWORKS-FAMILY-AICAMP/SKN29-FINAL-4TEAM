const PRODUCT_NAMES_BY_MODEL_PREFIX: Readonly<Record<string, string>> = {
  WPUJAC104: "초소형 직수 냉온 정수기",
  WPUIAC425: "원코크 플러스 얼음물 정수기",
  WPUIAC606: "MEGA ICE mini 얼음 냉온정수기",
};

function normalizeModelCode(modelCode: string): string {
  return modelCode.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
}

function isModelCodeAlias(modelCode: string, providedName: string): boolean {
  const normalizedModelCode = normalizeModelCode(modelCode);
  const normalizedProvidedName = normalizeModelCode(providedName);
  if (!normalizedProvidedName) return false;

  const knownModelPrefix = Object.keys(PRODUCT_NAMES_BY_MODEL_PREFIX).find(
    (modelPrefix) => normalizedModelCode.startsWith(modelPrefix),
  );

  if (
    knownModelPrefix &&
    normalizedProvidedName.startsWith(knownModelPrefix)
  ) {
    return true;
  }

  return (
    normalizedProvidedName.length >= 6 &&
    (normalizedModelCode.startsWith(normalizedProvidedName) ||
      normalizedProvidedName.startsWith(normalizedModelCode))
  );
}

export function getProductDisplayName(
  modelCode: string,
  providedName?: string | null,
): string | null {
  const normalizedProvidedName = providedName?.trim();
  if (
    normalizedProvidedName &&
    !isModelCodeAlias(modelCode, normalizedProvidedName)
  ) {
    return normalizedProvidedName;
  }

  const normalizedModelCode = normalizeModelCode(modelCode);
  return (
    Object.entries(PRODUCT_NAMES_BY_MODEL_PREFIX).find(([modelPrefix]) =>
      normalizedModelCode.startsWith(modelPrefix),
    )?.[1] ?? null
  );
}

export function formatProductModelAndName(
  modelCode: string,
  providedName?: string | null,
): string {
  const normalizedModelCode = modelCode.trim();
  const displayName = getProductDisplayName(normalizedModelCode, providedName);

  if (!displayName) return normalizedModelCode;
  return normalizedModelCode
    ? `${normalizedModelCode} · ${displayName}`
    : displayName;
}
