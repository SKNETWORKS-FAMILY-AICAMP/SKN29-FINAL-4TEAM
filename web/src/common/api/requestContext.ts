export interface RequestContext {
  correlationId: string;
  idempotencyKey: string;
  headers: Readonly<Record<"Idempotency-Key" | "X-Correlation-ID", string>>;
}

function createUuid() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createRequestContext(): RequestContext {
  const correlationId = createUuid();
  const idempotencyKey = createUuid();

  return {
    correlationId,
    idempotencyKey,
    headers: {
      "Idempotency-Key": idempotencyKey,
      "X-Correlation-ID": correlationId,
    },
  };
}
