import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { strToU8, zipSync } from "fflate";
import { afterEach, describe, expect, it } from "vitest";

import {
  containsSensitiveText,
  readSanitizedTraceEntry,
  redactSensitiveText,
  sanitizeTraceArchive,
} from "../../e2e/support/artifactSanitizer";

const temporaryDirectories: string[] = [];

afterEach(() => {
  temporaryDirectories.splice(0).forEach((directory) => {
    rmSync(directory, { recursive: true, force: true });
  });
});

describe("Playwright Artifact sanitizer", () => {
  it("Token·이메일·전화번호를 텍스트에서 제거한다", () => {
    const unsafe =
      'Authorization: Bearer abc.def.ghi, email=user@example.com, phone=010-1234-5678';
    const sanitized = redactSensitiveText(unsafe);

    expect(containsSensitiveText(sanitized)).toBe(false);
    expect(sanitized).not.toContain("user@example.com");
    expect(sanitized).not.toContain("010-1234-5678");
  });

  it("Trace의 network와 resource를 제거하고 텍스트를 정제한다", () => {
    const directory = mkdtempSync(join(tmpdir(), "waterbridge-e2e-"));
    temporaryDirectories.push(directory);
    const tracePath = join(directory, "trace.zip");
    const jwt =
      "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJkZW1vLXVzZXIifQ.signature012345";
    writeFileSync(
      tracePath,
      zipSync({
        "0-trace.network": strToU8(`Bearer ${jwt}`),
        "resources/body.json": strToU8('{"phone":"010-1234-5678"}'),
        "0-trace.trace": strToU8(
          `{"value":"private","authorization":"Bearer ${jwt}"}`,
        ),
      }),
    );

    sanitizeTraceArchive(tracePath);

    expect(readSanitizedTraceEntry(tracePath, "0-trace.network")).toBeNull();
    expect(readSanitizedTraceEntry(tracePath, "resources/body.json")).toBeNull();
    const trace = readSanitizedTraceEntry(tracePath, "0-trace.trace");
    expect(trace).not.toContain(jwt);
    expect(trace).not.toContain("private");
    expect(trace).toContain("[REDACTED]");
  });
});
