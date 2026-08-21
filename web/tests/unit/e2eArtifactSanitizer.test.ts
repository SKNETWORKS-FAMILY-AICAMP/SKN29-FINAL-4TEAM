import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { strToU8, zipSync } from "fflate";
import { afterEach, describe, expect, it } from "vitest";

import {
  containsSensitiveText,
  readSanitizedTraceEntry,
  redactSensitiveText,
  sanitizeArtifactTree,
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

  it("오류 문맥의 Bearer 템플릿 표현을 실제 Token처럼 남기지 않는다", () => {
    const sanitized = redactSensitiveText(
      "Authorization: `Bearer ${session.accessToken}`",
    );

    expect(containsSensitiveText(sanitized)).toBe(false);
    expect(sanitized).toBe("Authorization: `Bearer [REDACTED]`");
  });

  it("환경변수 이름이 붙은 비밀번호·Secret·API Key·DSN도 제거한다", () => {
    const unsafe = JSON.stringify({
      POSTGRES_PASSWORD: "database-password-value",
      DJANGO_SECRET_KEY: "django-secret-value",
      OPENAI_API_KEY: "provider-api-key-value",
      AI_VECTOR_DSN: "sensitive-vector-dsn",
    });

    const sanitized = redactSensitiveText(unsafe);

    expect(containsSensitiveText(sanitized)).toBe(false);
    expect(sanitized).not.toContain("database-password-value");
    expect(sanitized).not.toContain("django-secret-value");
    expect(sanitized).not.toContain("provider-api-key-value");
    expect(sanitized).not.toContain("sensitive-vector-dsn");
    expect(sanitized.match(/\[REDACTED\]/g)).toHaveLength(4);
  });

  it("전화번호처럼 보이는 숫자가 포함된 correlation UUID는 유지한다", () => {
    const correlationId = "80fe6e96-3918-47b2-ba04-a01012345678";
    const sanitized = redactSensitiveText(
      `correlation=${correlationId}, phone=010-1234-5678`,
    );

    expect(sanitized).toContain(correlationId);
    expect(sanitized).not.toContain("010-1234-5678");
    expect(containsSensitiveText(sanitized)).toBe(false);
  });

  it("JSONL과 CSV 결과물도 정제한다", () => {
    const directory = mkdtempSync(join(tmpdir(), "waterbridge-e2e-"));
    temporaryDirectories.push(directory);
    const jsonlPath = join(directory, "backend-requests.jsonl");
    const csvPath = join(directory, "request-map.csv");
    writeFileSync(
      jsonlPath,
      `${JSON.stringify({ POSTGRES_PASSWORD: "database-password-value" })}\n`,
    );
    writeFileSync(csvPath, "phone\n010-1234-5678\n");

    sanitizeArtifactTree(directory);

    expect(readFileSync(jsonlPath, "utf8")).not.toContain(
      "database-password-value",
    );
    expect(readFileSync(csvPath, "utf8")).toBe("phone\n[REDACTED]\n");
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

  it("손상된 Trace를 삭제해도 다른 결과물 정제를 끝까지 수행한다", () => {
    const directory = mkdtempSync(join(tmpdir(), "waterbridge-e2e-"));
    temporaryDirectories.push(directory);
    const tracePath = join(directory, "trace.zip");
    const logPath = join(directory, "result.log");
    writeFileSync(tracePath, "not-a-zip");
    writeFileSync(logPath, "email=user@example.com");

    expect(() => sanitizeArtifactTree(directory)).toThrow(
      "Playwright 결과물 1개를 안전하게 정제하지 못해 삭제했습니다.",
    );
    expect(existsSync(tracePath)).toBe(false);
    expect(readFileSync(logPath, "utf8")).toBe("email=[REDACTED]");
  });
});
