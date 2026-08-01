import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getHealthUrl,
  probeApiRuntime,
} from "../../src/features/runtime-status/api/runtimeStatusApi";

describe("API Runtime 상태 확인", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("상대·절대 API URL에서 health URL을 계산한다", () => {
    expect(getHealthUrl("/api/v1")).toBe("/health");
    expect(getHealthUrl("https://api.example.com/api/v1")).toBe(
      "https://api.example.com/health",
    );
  });

  it("Django health 응답과 Correlation ID를 확인한다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(null, {
          status: 200,
          headers: { "X-Correlation-ID": "corr-live-001" },
        }),
      ),
    );

    const result = await probeApiRuntime();

    expect(result.correlationId).toBe("corr-live-001");
    expect(result.latencyMs).toBeGreaterThanOrEqual(0);
  });

  it("Vite SPA fallback를 API 정상 응답으로 오인하지 않는다", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html></html>", { status: 200 })),
    );

    await expect(probeApiRuntime()).rejects.toThrow("X-Correlation-ID");
  });
});
