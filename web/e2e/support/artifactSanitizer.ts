import {
  readFileSync,
  readdirSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { extname, join } from "node:path";

import { strFromU8, strToU8, unzipSync, zipSync } from "fflate";

const TEXT_EXTENSIONS = new Set([".json", ".log", ".md", ".txt"]);
const REDACTED = "[REDACTED]";

function replaceJsonField(text: string, fieldNames: string): string {
  const plain = new RegExp(
    `("(?:${fieldNames})"\\s*:\\s*)"(?:\\\\.|[^"\\\\])*"`,
    "gi",
  );
  const escaped = new RegExp(
    `(\\\\"(?:${fieldNames})\\\\"\\s*:\\s*)\\\\"(?:\\\\\\\\.|[^"\\\\])*\\\\"`,
    "gi",
  );
  return text
    .replace(plain, `$1"${REDACTED}"`)
    .replace(escaped, `$1\\"${REDACTED}\\"`);
}

export function redactSensitiveText(source: string): string {
  let text = source;
  text = replaceJsonField(
    text,
    "access_token|refresh_token|authorization|cookie|set-cookie|password",
  );
  text = replaceJsonField(
    text,
    "display_name|customer_name|customer_display_name_masked|phone|email|raw_text|answer|consultation_note|additional_check|customer_guidance|summary|inputValue|value",
  );
  text = text.replace(
    /Bearer\s+[A-Za-z0-9._~+/=-]+/gi,
    `Bearer ${REDACTED}`,
  );
  text = text.replace(
    /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g,
    REDACTED,
  );
  text = text.replace(
    /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,
    REDACTED,
  );
  text = text.replace(/01[016789][ -]?\d{3,4}[ -]?\d{4}/g, REDACTED);
  text = text.replace(/0\d{1,2}[ -]?\d{3,4}[ -]?\d{4}/g, REDACTED);
  text = text.replace(/C:\\Users\\[^\\"\s]+/gi, "C:\\Users\\[REDACTED]");
  text = text.replace(/\/home\/[^/"\s]+/g, "/home/[REDACTED]");
  return text;
}

export function containsSensitiveText(text: string): boolean {
  return [
    /Bearer\s+(?!\[REDACTED\])/i,
    /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/,
    /"(?:access_token|refresh_token|password)"\s*:\s*"(?!\[REDACTED\])/i,
    /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
    /01[016789][ -]?\d{3,4}[ -]?\d{4}/,
  ].some((pattern) => pattern.test(text));
}

function decodeText(bytes: Uint8Array): string | null {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}

export function sanitizeTraceArchive(archivePath: string): void {
  const entries = unzipSync(new Uint8Array(readFileSync(archivePath)));

  for (const name of Object.keys(entries)) {
    if (name.endsWith(".network") || name.startsWith("resources/")) {
      delete entries[name];
      continue;
    }
    const decoded = decodeText(entries[name]);
    if (decoded === null) continue;
    const sanitized = redactSensitiveText(decoded);
    if (containsSensitiveText(sanitized)) {
      unlinkSync(archivePath);
      throw new Error(
        `Trace 정제에 실패하여 원본을 삭제했습니다: ${name}`,
      );
    }
    entries[name] = strToU8(sanitized);
  }

  writeFileSync(archivePath, zipSync(entries, { level: 6 }));
}

function sanitizeTextFile(filePath: string): void {
  const sanitized = redactSensitiveText(readFileSync(filePath, "utf8"));
  if (containsSensitiveText(sanitized)) {
    unlinkSync(filePath);
    throw new Error("텍스트 결과물 정제에 실패하여 원본을 삭제했습니다.");
  }
  writeFileSync(filePath, sanitized, "utf8");
}

export function sanitizeArtifactTree(rootPath: string): void {
  const entries = readdirSync(rootPath, { withFileTypes: true });
  for (const entry of entries) {
    const target = join(rootPath, entry.name);
    if (entry.isDirectory()) {
      sanitizeArtifactTree(target);
      continue;
    }
    if (!entry.isFile() || statSync(target).size === 0) continue;
    if (entry.name.endsWith("trace.zip")) {
      sanitizeTraceArchive(target);
      continue;
    }
    if (TEXT_EXTENSIONS.has(extname(entry.name).toLowerCase())) {
      sanitizeTextFile(target);
    }
  }
}

export function readSanitizedTraceEntry(
  archivePath: string,
  entryName: string,
): string | null {
  const entries = unzipSync(new Uint8Array(readFileSync(archivePath)));
  const entry = entries[entryName];
  return entry ? strFromU8(entry) : null;
}
