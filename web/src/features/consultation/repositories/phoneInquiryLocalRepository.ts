export type PhoneInquiryUrgency = "GENERAL" | "CAUTION" | "URGENT";

export interface PhoneInquiryRecord {
  id: string;
  customerName: string;
  phoneNumber: string;
  category: string;
  productModel: string;
  inquiryContent: string;
  consultationNote: string;
  urgency: PhoneInquiryUrgency;
  callbackRequired: boolean;
  counselorName: string;
  createdAt: string;
}

export type CreatePhoneInquiryRecord = Omit<
  PhoneInquiryRecord,
  "id" | "createdAt"
>;

const STORAGE_KEY = "waterbridge.phone-inquiry-records.v1";
let memoryRecords: PhoneInquiryRecord[] = [];

function getStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isPhoneInquiryRecord(value: unknown): value is PhoneInquiryRecord {
  if (!value || typeof value !== "object") return false;
  const record = value as Partial<PhoneInquiryRecord>;
  return (
    typeof record.id === "string" &&
    typeof record.customerName === "string" &&
    typeof record.phoneNumber === "string" &&
    typeof record.category === "string" &&
    typeof record.inquiryContent === "string" &&
    typeof record.createdAt === "string"
  );
}

function readRecords(): PhoneInquiryRecord[] {
  const storage = getStorage();
  if (!storage) return memoryRecords;

  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) ?? "[]") as unknown;
    return Array.isArray(parsed) ? parsed.filter(isPhoneInquiryRecord) : [];
  } catch {
    return [];
  }
}

function writeRecords(records: PhoneInquiryRecord[]): void {
  memoryRecords = records;
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(records));
  } catch {
    // Browser storage can be unavailable in private or restricted sessions.
  }
}

export const phoneInquiryLocalRepository = {
  list(): readonly PhoneInquiryRecord[] {
    return readRecords();
  },

  create(input: CreatePhoneInquiryRecord): PhoneInquiryRecord {
    const now = new Date();
    const record: PhoneInquiryRecord = {
      ...input,
      id: `PHONE-${now.getTime().toString(36).toUpperCase()}`,
      createdAt: now.toISOString(),
    };
    writeRecords([record, ...readRecords()].slice(0, 20));
    return record;
  },
};
