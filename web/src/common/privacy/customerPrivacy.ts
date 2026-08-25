const SYNTHETIC_SUFFIX_PATTERN = /\s*(\([^)]*합성[^)]*\))\s*$/;

export function maskCustomerName(value: string): string {
  const normalized = value.trim();
  if (!normalized) return "";

  const suffixMatch = normalized.match(SYNTHETIC_SUFFIX_PATTERN);
  const suffix = suffixMatch?.[1] ? ` ${suffixMatch[1]}` : "";
  const name = suffixMatch
    ? normalized.slice(0, suffixMatch.index).trim()
    : normalized;

  if (!name) return suffix.trim();
  if (name.length === 1) return `*${suffix}`;
  if (name.length === 2) return `${name[0]}*${suffix}`;
  return `${name[0]}${"*".repeat(name.length - 2)}${name.at(-1)}${suffix}`;
}

export function maskCustomerPhone(value: string): string {
  const suffixMatch = value.match(/\s*(\([^)]*\))\s*$/);
  const suffix = suffixMatch?.[1] ? ` ${suffixMatch[1]}` : "";
  const phone = suffixMatch ? value.slice(0, suffixMatch.index).trim() : value.trim();
  const digits = phone.replace(/\D/g, "");

  if (digits.length === 11) {
    return `${digits.slice(0, 3)}-****-${digits.slice(-4)}${suffix}`;
  }

  if (digits.length === 10) {
    return `${digits.slice(0, 3)}-***-${digits.slice(-4)}${suffix}`;
  }

  const parts = phone.split("-");
  if (parts.length === 3 && parts[1]) {
    return `${parts[0]}-${"*".repeat(parts[1].length)}-${parts[2]}${suffix}`;
  }

  return value;
}
