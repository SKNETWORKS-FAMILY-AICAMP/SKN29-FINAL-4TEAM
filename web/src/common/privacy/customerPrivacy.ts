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
