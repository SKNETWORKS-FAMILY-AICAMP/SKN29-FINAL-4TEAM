import { appEnv } from "../../../app/config/env";

export type ApiRuntimeProbe = {
  checkedAt: string;
  correlationId: string;
  latencyMs: number;
};

export function getHealthUrl(apiBaseUrl = appEnv.apiBaseUrl): string {
  if (apiBaseUrl.startsWith("/")) return "/health";

  const url = new URL(apiBaseUrl);
  return `${url.origin}/health`;
}

export async function probeApiRuntime(
  signal?: AbortSignal,
): Promise<ApiRuntimeProbe> {
  const startedAt = performance.now();
  const response = await fetch(getHealthUrl(), {
    method: "GET",
    headers: { Accept: "text/plain" },
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    throw new Error(`API health check failed: ${response.status}`);
  }

  const correlationId = response.headers.get("X-Correlation-ID");
  if (!correlationId) {
    throw new Error("API health response is missing X-Correlation-ID");
  }

  return {
    checkedAt: new Date().toISOString(),
    correlationId,
    latencyMs: Math.max(0, Math.round(performance.now() - startedAt)),
  };
}
