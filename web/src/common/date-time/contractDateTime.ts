const ISO_DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

interface ContractDateTimeParts {
  day: number;
  hour: number;
  minute: string;
  month: number;
  year: number;
}

function parseContractDateTime(value: string): ContractDateTimeParts | null {
  const match = ISO_DATE_TIME_PATTERN.exec(value);

  if (!match || Number.isNaN(Date.parse(value))) return null;

  const [, year, month, day, hour, minute] = match;
  return {
    year: Number(year),
    month: Number(month),
    day: Number(day),
    hour: Number(hour),
    minute,
  };
}

function formatClock(hour: number, minute: string): string {
  const period = hour < 12 ? "오전" : "오후";
  const displayHour = hour % 12 || 12;
  return `${period} ${String(displayHour).padStart(2, "0")}:${minute}`;
}

// API 계약의 +09:00 wall-clock 값을 그대로 표시한다.
// Date 객체의 로컬/UTC 변환을 거치지 않아 실행 환경에 따라 날짜가 바뀌지 않는다.
export function formatContractDateTimeLong(value: string): string | null {
  const parts = parseContractDateTime(value);
  if (!parts) return null;

  return `${parts.year}년 ${parts.month}월 ${parts.day}일 ${formatClock(
    parts.hour,
    parts.minute,
  )}`;
}

export function formatContractDateTimeShort(value: string): string | null {
  const parts = parseContractDateTime(value);
  if (!parts) return null;

  return `${String(parts.month).padStart(2, "0")}. ${String(parts.day).padStart(
    2,
    "0",
  )}. ${formatClock(parts.hour, parts.minute)}`;
}
