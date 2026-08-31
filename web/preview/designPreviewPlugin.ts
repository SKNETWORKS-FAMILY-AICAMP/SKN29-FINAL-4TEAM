import { Buffer } from "node:buffer";
import type { IncomingMessage } from "node:http";
import type { Plugin } from "vite";

import { createDesignPreviewApi } from "./designPreviewApi.ts";

const MAX_SEARCH_BODY_BYTES = 16_384;

async function readSearchBody(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let length = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    length += buffer.length;
    if (length > MAX_SEARCH_BODY_BYTES) {
      throw new Error("미리보기 검색 요청이 너무 큽니다.");
    }
    chunks.push(buffer);
  }
  const content = Buffer.concat(chunks).toString("utf8");
  return content ? JSON.parse(content) : undefined;
}

/** Local-only API responses: never forward a request to an actual backend. */
export function designPreviewPlugin(): Plugin {
  return {
    name: "waterbridge-isolated-design-preview",
    apply: "serve",
    transformIndexHtml(html) {
      return html.replace(/<title>[^<]*<\/title>/, "<title>Water Bridge · 로컬 미리보기 (저장 안 됨)</title>");
    },
    configureServer(server) {
      const respond = createDesignPreviewApi();
      server.middlewares.use(async (request, response, next) => {
        const url = new URL(request.url ?? "/", "http://localhost");
        if (!/^\/api(?:\/|$)/.test(url.pathname) && url.pathname !== "/health") {
          next();
          return;
        }

        response.setHeader("Content-Type", "application/json; charset=utf-8");
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("X-WaterBridge-Preview", "local-sample-read-only");
        response.setHeader("X-Correlation-ID", "local-design-preview");

        if (url.pathname === "/health" && request.method === "GET") {
          response.statusCode = 200;
          response.end(JSON.stringify({ mode: "local-design-preview", production_connected: false }));
          return;
        }

        try {
          // Only this POST is a read-only lookup. All writes are rejected by
          // the preview API without reading or persisting their request body.
          const body = request.method === "POST" &&
            url.pathname === "/api/v1/consultant/customer-subscriptions/search"
            ? await readSearchBody(request)
            : undefined;
          const result = respond({
            url: request.url ?? "/",
            method: request.method ?? "GET",
            body,
          });
          response.statusCode = result.status;
          response.end(JSON.stringify(result.body));
        } catch {
          response.statusCode = 400;
          response.end(JSON.stringify({
            success: false,
            data: null,
            error: {
              code: "PREVIEW_INVALID_REQUEST",
              message: "로컬 미리보기 요청 형식을 확인해 주세요.",
              details: {},
            },
            metadata: { correlation_id: "local-design-preview" },
          }));
        }
      });
    },
  };
}
