import {
  toInquiryId,
  type InquiryId,
} from "../../../entities/inquiry/inquiryIdentifiers";

export interface RecentConsultantInquiryIdStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const MAX_RECENT_CONSULTANT_INQUIRY_IDS = 5;

const STORAGE_KEY_PREFIX = "waterbridge.consultant.recent-inquiry-ids.v1";

function normalizeConsultantId(consultantId: string): string | null {
  const normalized = consultantId.trim();
  return normalized ? normalized : null;
}

export function getRecentConsultantInquiryIdsStorageKey(
  consultantId: string,
): string | null {
  const normalizedConsultantId = normalizeConsultantId(consultantId);
  return normalizedConsultantId
    ? `${STORAGE_KEY_PREFIX}:${encodeURIComponent(normalizedConsultantId)}`
    : null;
}

function getSessionStorage(): RecentConsultantInquiryIdStorage | null {
  if (typeof window === "undefined") return null;

  try {
    return window.sessionStorage ?? null;
  } catch {
    return null;
  }
}

function resolveStorage(
  storage: RecentConsultantInquiryIdStorage | null | undefined,
): RecentConsultantInquiryIdStorage | null {
  return storage === undefined ? getSessionStorage() : storage;
}

function normalizeInquiryIds(value: unknown): InquiryId[] {
  if (!Array.isArray(value)) return [];

  const normalized: InquiryId[] = [];
  for (const candidate of value) {
    const inquiryId = toInquiryId(candidate);
    if (!inquiryId || normalized.includes(inquiryId)) continue;

    normalized.push(inquiryId);
    if (normalized.length === MAX_RECENT_CONSULTANT_INQUIRY_IDS) break;
  }

  return normalized;
}

export function readRecentConsultantInquiryIds(
  consultantId: string,
  storage?: RecentConsultantInquiryIdStorage | null,
): InquiryId[] {
  const storageKey = getRecentConsultantInquiryIdsStorageKey(consultantId);
  const resolvedStorage = resolveStorage(storage);
  if (!storageKey || !resolvedStorage) return [];

  try {
    const serialized = resolvedStorage.getItem(storageKey);
    if (!serialized) return [];
    return normalizeInquiryIds(JSON.parse(serialized) as unknown);
  } catch {
    return [];
  }
}

export function rememberRecentConsultantInquiryId(
  consultantId: string,
  inquiryIdValue: string,
  storage?: RecentConsultantInquiryIdStorage | null,
): InquiryId[] {
  const storageKey = getRecentConsultantInquiryIdsStorageKey(consultantId);
  const inquiryId = toInquiryId(inquiryIdValue);
  const resolvedStorage = resolveStorage(storage);
  if (!storageKey || !inquiryId || !resolvedStorage) return [];

  const recentInquiryIds = [
    inquiryId,
    ...readRecentConsultantInquiryIds(consultantId, resolvedStorage).filter(
      (candidate) => candidate !== inquiryId,
    ),
  ].slice(0, MAX_RECENT_CONSULTANT_INQUIRY_IDS);

  try {
    resolvedStorage.setItem(storageKey, JSON.stringify(recentInquiryIds));
  } catch {
    // Storage can be unavailable in privacy mode or restricted browser contexts.
  }

  return recentInquiryIds;
}

export function clearRecentConsultantInquiryIds(
  consultantId: string,
  storage?: RecentConsultantInquiryIdStorage | null,
): void {
  const storageKey = getRecentConsultantInquiryIdsStorageKey(consultantId);
  const resolvedStorage = resolveStorage(storage);
  if (!storageKey || !resolvedStorage) return;

  try {
    resolvedStorage.removeItem(storageKey);
  } catch {
    // Clearing recent history must not block authentication or navigation.
  }
}
