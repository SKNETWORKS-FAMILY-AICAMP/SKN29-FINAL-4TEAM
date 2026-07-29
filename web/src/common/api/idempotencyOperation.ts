import { createIdempotencyKey } from "./requestContext";

interface PendingOperation {
  key: string;
  signature: string;
}

export class IdempotencyOperationTracker {
  private pending: PendingOperation | null = null;
  private readonly createKey: () => string;

  constructor(createKey: () => string = createIdempotencyKey) {
    this.createKey = createKey;
  }

  begin(signature: string): string {
    if (this.pending?.signature === signature) {
      return this.pending.key;
    }

    const key = this.createKey();
    this.pending = { key, signature };
    return key;
  }

  finish(): void {
    this.pending = null;
  }

  fail(retryable: boolean): void {
    if (!retryable) {
      this.pending = null;
    }
  }
}
